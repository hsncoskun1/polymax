"""Market sync service — single-shot fetch → map → registry write.

Orchestrates the path from raw Polymarket data to persisted domain Markets.
Does NOT run on a schedule.  The caller decides when to invoke run().
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from ..domain.market.exceptions import DuplicateMarketError
from ..domain.market.models import Market, create_market
from ..domain.market.registry import MarketRegistry
from ..domain.market.types import Side, Timeframe
from .market_fetcher import FetchedMarket, PolymarketFetchService
from .symbol_extractor import extract_symbol
from ..integrations.polymarket.config import DEFAULT_MARKET_LIMIT

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result summary
# ---------------------------------------------------------------------------


@dataclass
class SyncResult:
    """Summary of a single sync run."""

    fetched: int            # candidates returned by the fetcher
    mapped: int             # domain Markets successfully produced
    written: int            # Markets newly written to the registry
    skipped_mapping: int    # records that could not be mapped to a Market
    skipped_duplicate: int  # records that already existed in the registry


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
    """Single-shot sync: fetch candidates → map → write to registry.

    Duplicate entries are silently skipped (idempotent).  Records that fail
    mapping are counted and logged but do not abort the run.
    """

    def __init__(
        self,
        fetcher: PolymarketFetchService,
        registry: MarketRegistry,
        mapper: MarketMapper | None = None,
    ) -> None:
        self._fetcher = fetcher
        self._registry = registry
        self._mapper = mapper or MarketMapper()

    def run(self, limit: int = DEFAULT_MARKET_LIMIT) -> SyncResult:
        """Execute one full fetch → map → write cycle.

        Client-level errors (PolymarketError subclasses) propagate to the
        caller — the registry is left unchanged in that case.
        """
        candidates = self._fetcher.fetch_candidates(limit=limit)
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
        )
        logger.info(
            "Sync complete — fetched=%d mapped=%d written=%d "
            "skipped_mapping=%d skipped_duplicate=%d",
            result.fetched,
            result.mapped,
            result.written,
            result.skipped_mapping,
            result.skipped_duplicate,
        )
        return result
