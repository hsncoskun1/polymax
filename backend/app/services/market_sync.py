"""Market sync service — single-shot fetch → discovery → map → registry write.

Orchestrates the path from raw Polymarket data to persisted domain Markets.
Does NOT run on a schedule.  The caller decides when to invoke run().

Candidate selection is delegated entirely to DiscoveryService — the single
authoritative source of selection rules.  MarketSyncService itself applies
no additional filtering.

Registry lifecycle model (v0.5.7 decision)
------------------------------------------
MarketSyncService currently uses **add-only / retained** semantics:

  - Once a market is written to the registry it is never removed, deactivated,
    or archived by sync.  It persists regardless of what happens to the market
    on subsequent syncs.
  - If a market was valid at T0 and invalid at T1, the registry entry written
    at T0 stays ACTIVE.  MarketSyncService has no knowledge of it.
  - Duplicate writes (same market_id on a later sync) are silently skipped
    (DuplicateMarketError → skipped_duplicate counter).

This is a **deliberate deferred decision**, not an oversight:
  The infrastructure for lifecycle transitions exists (MarketStatus.INACTIVE /
  ARCHIVED, registry.deactivate(), registry.archive()) but driving those
  transitions from the sync layer requires a "previous state vs. new candidate
  set" comparison that is not yet implemented.  The risk is that the registry
  may accumulate stale entries over time, which is acceptable until a
  scheduler / persistence layer is introduced.

  Future milestone: Registry Lifecycle Handling (cleanup / stale detection).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from ..domain.market.exceptions import DuplicateMarketError
from ..domain.market.models import Market, create_market
from ..domain.market.registry import MarketRegistry
from ..domain.market.types import Side, Timeframe
from .market_discovery import DiscoveryService
from .market_fetcher import FetchedMarket, PolymarketFetchService
from .symbol_extractor import extract_symbol
from ..integrations.polymarket.config import DEFAULT_MARKET_LIMIT

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result summary
# ---------------------------------------------------------------------------


@dataclass
class SyncResult:
    """Summary of a single sync run.

    Summary semantics — processing window, not registry state
    ---------------------------------------------------------
    This summary describes only what happened inside THIS sync call.
    It does NOT describe the full state of the registry.

    fetched            — number of DiscoveryService CANDIDATES that entered
                         the map→write stage.  This is NOT the raw count of
                         markets fetched from the Polymarket API; markets
                         rejected by discovery are invisible here.
    mapped             — domain Market objects successfully produced
                         (= written + skipped_duplicate, when mapping succeeds).
    written            — new Markets written to the registry in this call.
    skipped_mapping    — candidates whose mapper() call returned [].
    skipped_duplicate  — candidates whose registry key already existed
                         (DuplicateMarketError → silently skipped).
    registry_total     — total number of entries in the registry AFTER this
                         sync call completes.  Includes all retained/stale
                         entries from prior syncs plus any newly written ones.
                         Provides context for interpreting `written`.

    rejected_count     — number of FetchedMarket records rejected by
                         DiscoveryService in this call (did not become
                         candidates).  Together with `fetched`, this lets
                         the operator see the full payload split:
                         fetched + rejected_count = total fetch layer output
                         (minus any records skipped by the fetch layer itself).
    rejection_breakdown — per-reason rejection counts as a string-keyed dict
                         (keys: "inactive", "no_order_book", "empty_tokens",
                         "missing_dates", "duration_out_of_range").
                         All five keys are always present (value may be 0).
                         Matches the format returned by POST /discover.

    What the summary does NOT tell you
    -----------------------------------
    - Raw count of markets fetched from the Polymarket API (only candidates
      and rejected-by-discovery are in this summary).
    - How many registry entries are stale (valid when written, now invalid).
    - Whether the registry is growing, stable, or shrinking over time.

    Cross-layer field name mapping (SyncResult → SyncResponse API)
    --------------------------------------------------------------
    SyncResult field    → SyncResponse JSON field
    ------------------    -------------------------
    fetched             → fetched_count
    mapped              → mapped_count
    written             → written_count
    skipped_mapping     → skipped_mapping_count
    skipped_duplicate   → skipped_duplicate_count
    registry_total      → registry_total_count
    rejected_count      → rejected_count          (same name)
    rejection_breakdown → rejection_breakdown      (same name)

    Note: The `_count` suffix in SyncResponse field names is a convention
    for numeric API response fields.  SyncResult uses shorter names for
    internal ergonomics.  The semantics are identical in both layers.
    """

    fetched: int
    mapped: int
    written: int
    skipped_mapping: int
    skipped_duplicate: int
    registry_total: int = 0
    rejected_count: int = 0
    rejection_breakdown: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Mapper
# ---------------------------------------------------------------------------


class MarketMapper:
    """Maps a FetchedMarket to a pair of domain Market objects (UP + DOWN).

    Binary prediction markets have two sides by definition — YES (UP) and
    NO (DOWN).  Each side becomes an independent Market entry so downstream
    logic can track them separately.

    Symbol resolution order:
    1. extract_symbol(question, slug) — regex/keyword extraction for known coins.
    2. slug — raw slug as fallback when no coin is recognised.
    3. market_id — last resort when slug is also absent.

    Timeframe is always M5 — the only timeframe POLYMAX currently supports.
    """

    def map(self, fetched: FetchedMarket) -> list[Market]:
        """Return [UP market, DOWN market] or [] on failure."""
        try:
            symbol = (
                extract_symbol(fetched.question, fetched.slug)
                or fetched.slug
                or fetched.market_id
            )
            event_id = fetched.event_id or fetched.market_id

            return [
                create_market(
                    id=f"{fetched.market_id}-up",
                    event_id=event_id,
                    symbol=symbol,
                    side=Side.UP,
                    timeframe=Timeframe.M5,
                    source_timestamp=fetched.source_timestamp,
                    end_date=fetched.end_date,
                ),
                create_market(
                    id=f"{fetched.market_id}-down",
                    event_id=event_id,
                    symbol=symbol,
                    side=Side.DOWN,
                    timeframe=Timeframe.M5,
                    source_timestamp=fetched.source_timestamp,
                    end_date=fetched.end_date,
                ),
            ]
        except Exception:
            logger.warning(
                "Could not map FetchedMarket %r to domain Market",
                fetched.market_id,
                exc_info=True,
            )
            return []


# ---------------------------------------------------------------------------
# Sync service
# ---------------------------------------------------------------------------


class MarketSyncService:
    """Single-shot sync: fetch → discovery evaluate → map → write to registry.

    DiscoveryService is the single authoritative candidate selector.
    MarketSyncService fetches all normalised markets, delegates candidate
    selection to DiscoveryService, then maps and writes the survivors.

    Duplicate entries are silently skipped (idempotent).  Records that fail
    mapping are counted and logged but do not abort the run.
    """

    def __init__(
        self,
        fetcher: PolymarketFetchService,
        registry: MarketRegistry,
        mapper: MarketMapper | None = None,
        discovery: DiscoveryService | None = None,
    ) -> None:
        self._fetcher = fetcher
        self._registry = registry
        self._mapper = mapper or MarketMapper()
        self._discovery = discovery or DiscoveryService()

    def run(self, limit: int = DEFAULT_MARKET_LIMIT) -> SyncResult:
        """Execute one full fetch → discovery → map → write cycle.

        1. Fetches all normalised markets from Polymarket.
        2. Passes them to DiscoveryService.evaluate() — single source of
           candidate selection rules.
        3. Maps each candidate to UP + DOWN domain Markets.
        4. Writes new Markets to the registry; duplicates are counted and
           skipped.

        Client-level errors (PolymarketError subclasses) propagate to the
        caller — the registry is left unchanged in that case.
        """
        all_markets = self._fetcher.fetch_markets(limit=limit)
        discovery_result = self._discovery.evaluate(all_markets)
        candidates = discovery_result.candidates

        fetched = len(candidates)
        mapped = 0
        written = 0
        skipped_mapping = 0
        skipped_duplicate = 0

        for fetched_market in candidates:
            domain_markets = self._mapper.map(fetched_market)

            if not domain_markets:
                skipped_mapping += 1
                continue

            mapped += len(domain_markets)

            for market in domain_markets:
                try:
                    self._registry.add(market)
                    written += 1
                except DuplicateMarketError:
                    skipped_duplicate += 1

        result = SyncResult(
            fetched=fetched,
            mapped=mapped,
            written=written,
            skipped_mapping=skipped_mapping,
            skipped_duplicate=skipped_duplicate,
            registry_total=len(self._registry),
            rejected_count=discovery_result.rejected_count,
            rejection_breakdown=discovery_result.string_breakdown,
        )
        logger.info(
            "Sync complete — fetched=%d rejected=%d mapped=%d written=%d "
            "skipped_mapping=%d skipped_duplicate=%d",
            result.fetched,
            result.rejected_count,
            result.mapped,
            result.written,
            result.skipped_mapping,
            result.skipped_duplicate,
        )
        return result
