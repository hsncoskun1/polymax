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
        """
        return self._fetch_and_normalize(self._client.get_markets(limit=limit))

    def fetch_candidates(self, limit: int = DEFAULT_MARKET_LIMIT) -> list[FetchedMarket]:
        """Return normalised markets pre-filtered to 5m candidates.

        Uses _is_5m_candidate as the gate — currently active and non-closed.
        The filter criterion will be refined in future classification steps.
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

        # source_timestamp — parse ISO-8601 startDate if present
        source_timestamp: datetime | None = None
        start_date = raw.get("startDate")
        if isinstance(start_date, str) and start_date:
            try:
                source_timestamp = datetime.fromisoformat(
                    start_date.replace("Z", "+00:00")
                )
            except ValueError:
                logger.warning(
                    "Could not parse startDate %r for market %s",
                    start_date,
                    market_id,
                )

        return FetchedMarket(
            market_id=market_id.strip(),
            question=question,
            event_id=event_id,
            slug=slug,
            active=active,
            closed=closed,
            source_timestamp=source_timestamp,
        )

    @staticmethod
    def _is_5m_candidate(raw: dict) -> bool:
        """Placeholder: gate for markets suitable for 5-minute timeframe tracking.

        Currently passes active, non-closed markets.
        Future: narrow by tags, question patterns, or token characteristics.
        """
        return bool(raw.get("active", False)) and not bool(raw.get("closed", False))
