"""Polymarket market fetch service.

Fetches raw market records from the Gamma API and normalises them into
FetchedMarket DTOs.  This layer has no knowledge of the registry and does
not write anything — callers decide what to do with the results.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from ..integrations.polymarket.client import PolymarketClient
from ..integrations.polymarket.config import DEFAULT_MARKET_LIMIT

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 5m duration window (seconds) — tolerant ±1 minute around the 5m target.
# Markets whose endDate − startDate falls outside this range are not
# considered 5m candidates.  These are NOT final discovery thresholds;
# they will be tightened once real 5m market data is observed in production.
# ---------------------------------------------------------------------------
CANDIDATE_DURATION_MIN_SECONDS: int = 240   # 4 minutes
CANDIDATE_DURATION_MAX_SECONDS: int = 360   # 6 minutes


@dataclass(frozen=True)
class FetchedMarket:
    """Normalised Polymarket market record.

    Intermediate DTO between the raw Gamma API response and the POLYMAX
    domain Market model.  Fields like *side* and *timeframe* are not
    resolved here — that is a classification step that comes later.
    """

    market_id: str
    question: str
    event_id: str | None        # first event id from the events list, if any
    slug: str | None
    active: bool
    closed: bool
    source_timestamp: datetime | None   # parsed from startDate when present
    end_date: datetime | None           # parsed from endDate when present


class PolymarketFetchService:
    """Fetches and normalises Polymarket markets.

    Does NOT write to the registry.
    Does NOT perform discovery or side/timeframe classification.
    Propagates client-level errors (PolymarketError subclasses) to the caller.
    """

    def __init__(self, client: PolymarketClient) -> None:
        self._client = client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch_markets(self, limit: int = DEFAULT_MARKET_LIMIT) -> list[FetchedMarket]:
        """Return all normalised markets from Polymarket.

        Records with a missing or empty *id* are skipped with a warning.
        No candidate filtering is applied.
        """
        return self._fetch_and_normalize(self._client.get_markets(limit=limit))

    def fetch_candidates(self, limit: int = DEFAULT_MARKET_LIMIT) -> list[FetchedMarket]:
        """Return normalised markets filtered to 5m candidates.

        A record must pass _is_5m_candidate() before normalisation.
        Records that fail the gate are discarded silently (no warning —
        most Polymarket markets are not short-duration).
        """
        raw_list = self._client.get_markets(limit=limit)
        return self._fetch_and_normalize(
            [r for r in raw_list if self._is_5m_candidate(r)]
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fetch_and_normalize(self, raw_list: list[dict]) -> list[FetchedMarket]:
        results: list[FetchedMarket] = []
        for raw in raw_list:
            market = self._normalize(raw)
            if market is not None:
                results.append(market)
        return results

    def _normalize(self, raw: dict) -> FetchedMarket | None:
        """Map one raw Gamma API dict to a FetchedMarket.

        Returns None and emits a warning when the required *id* field is absent.
        """
        market_id = raw.get("id")
        if not isinstance(market_id, str) or not market_id.strip():
            logger.warning("Skipping market with missing/invalid id: %r", raw)
            return None

        question: str = raw.get("question") or ""
        slug: str | None = raw.get("slug") or None
        active: bool = bool(raw.get("active", False))
        closed: bool = bool(raw.get("closed", False))

        # event_id — take the first event's id when the events list is present
        event_id: str | None = None
        events = raw.get("events")
        if isinstance(events, list) and events:
            first = events[0]
            if isinstance(first, dict):
                event_id = first.get("id") or None

        source_timestamp = _parse_iso_dt(raw.get("startDate"), label="startDate",
                                          market_id=market_id)
        end_date = _parse_iso_dt(raw.get("endDate"), label="endDate",
                                  market_id=market_id)

        return FetchedMarket(
            market_id=market_id.strip(),
            question=question,
            event_id=event_id,
            slug=slug,
            active=active,
            closed=closed,
            source_timestamp=source_timestamp,
            end_date=end_date,
        )

    @staticmethod
    def _is_5m_candidate(raw: dict) -> bool:
        """Gate for markets considered suitable for 5-minute timeframe tracking.

        A record must pass ALL of the following checks:

        1. active=True, closed=False  — market is live and tradeable.
        2. enableOrderBook=True       — CLOB order book present; AMM-only markets
                                        lack intra-minute price resolution.
        3. tokens list non-empty      — confirms binary YES/NO market structure.
        4. Duration in [240, 360] s   — endDate − startDate within the 5m window
                                        (±1 min tolerance).  Records with absent
                                        or unparseable dates are rejected.

        Deliberately NOT checked here (future steps):
        - Coin/symbol identification (question pattern matching).
        - volume24hr threshold — absent on some records.
        - YES/NO → UP/DOWN semantic mapping.

        Known limitations:
        - Non-crypto CLOB markets whose duration happens to be ~5m will pass.
        - Liquidity is not checked; a volume gate will reduce noise later.
        """
        if not bool(raw.get("active", False)):
            return False
        if bool(raw.get("closed", False)):
            return False
        if not bool(raw.get("enableOrderBook", False)):
            return False
        tokens = raw.get("tokens")
        if not isinstance(tokens, list) or len(tokens) == 0:
            return False

        # Duration check — both dates must be present and parseable
        start_dt = _parse_iso_dt(raw.get("startDate"))
        end_dt = _parse_iso_dt(raw.get("endDate"))
        if start_dt is None or end_dt is None:
            return False
        duration = (end_dt - start_dt).total_seconds()
        if not (CANDIDATE_DURATION_MIN_SECONDS <= duration <= CANDIDATE_DURATION_MAX_SECONDS):
            return False

        return True


# ---------------------------------------------------------------------------
# Module-level helper
# ---------------------------------------------------------------------------

def _parse_iso_dt(
    value: object,
    *,
    label: str = "date",
    market_id: str = "<unknown>",
) -> datetime | None:
    """Parse an ISO-8601 date string to a timezone-aware datetime.

    Returns None (and logs a warning when label/market_id are provided) if
    the value is absent, not a string, or cannot be parsed.

    The 'Z' suffix is normalised to '+00:00' for Python < 3.11 compatibility.
    """
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        logger.warning(
            "Could not parse %s %r for market %s", label, value, market_id
        )
        return None
