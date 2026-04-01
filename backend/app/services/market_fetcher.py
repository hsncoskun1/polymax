"""Polymarket market fetch service.

Fetches raw market records from the Gamma API and normalises them into
FetchedMarket DTOs.  This layer is a pure normalisation pass — it applies
no candidate filtering.  Candidate selection is the sole responsibility of
DiscoveryService.  Callers decide what to do with the results.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from ..integrations.polymarket.client import PolymarketClient
from ..integrations.polymarket.config import DEFAULT_MARKET_LIMIT

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 5m duration window (seconds) — used by DiscoveryService for candidate gating.
# Tolerant ±1 minute around the 5m target.
# ---------------------------------------------------------------------------
CANDIDATE_DURATION_MIN_SECONDS: int = 240   # 4 minutes
CANDIDATE_DURATION_MAX_SECONDS: int = 360   # 6 minutes


@dataclass(frozen=True)
class FetchedMarket:
    """Normalised Polymarket market record.

    Intermediate DTO between the raw Gamma API response and the POLYMAX
    domain Market model.  Fields like *side* and *timeframe* are not
    resolved here — that is a classification step that comes later.

    question:
        Always a str; never None.  Leading/trailing whitespace stripped.
        Whitespace-only upstream value normalises to "".

    slug:
        Canonical stripped value, or None.
        None when: absent, falsy, or whitespace-only after strip.
        Non-blank non-empty string after strip otherwise.
        Safe for use as symbol fallback (no whitespace-only slug leaks downstream).

    enable_order_book:
        True  — CLOB order book present; intra-minute price data available.
        False — AMM-only; no order book.
        None  — field absent in upstream response.

    tokens:
        List of outcome token dicts (e.g. [{"outcome": "YES"}, ...]).
        None  — field absent or not a list in upstream response.
        []    — field present but empty list.
        Discovery uses this as a binary "non-empty" gate only.
    """

    market_id: str
    question: str
    event_id: str | None        # first event id from the events list, if any
    slug: str | None
    active: bool
    closed: bool
    source_timestamp: datetime | None   # parsed from startDate when present
    end_date: datetime | None           # parsed from endDate when present
    enable_order_book: bool | None = None   # from enableOrderBook field
    tokens: list | None = None              # from tokens field


class PolymarketFetchService:
    """Fetches and normalises Polymarket markets.

    Does NOT write to the registry.
    Does NOT perform discovery or side/timeframe classification.
    Does NOT filter candidates — that is DiscoveryService's responsibility.
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
        No candidate filtering is applied — pass the result to
        DiscoveryService.evaluate() to obtain candidates.
        """
        return self._fetch_and_normalize(self._client.get_markets(limit=limit))

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

        Field normalization policy table
        ---------------------------------
        Raw field       Raw variants handled         Normalized value
        ─────────────  ──────────────────────────   ─────────────────────────
        id             absent/None/non-str/blank     → skip record (return None)
                       any string after strip        → market_id (stripped)
        question       absent/None/falsy             → "" (empty string; never None)
                       any string                    → stripped; whitespace-only → ""
        slug           absent/None/falsy/""          → None
                       whitespace-only string        → None (stripped to empty → None)
                       non-empty non-blank string    → stripped value
        active         absent                        → False (default)
                       any value                     → bool() coercion
        closed         absent                        → False (default)
                       any value                     → bool() coercion
        events         absent/None/non-list/empty    → event_id = None
                       non-empty list of dicts       → event_id = first["id"] or None
        startDate      absent/None/non-str/blank     → source_timestamp = None
                       unparseable                   → None + warning
                       valid ISO-8601                → tz-aware datetime
        endDate        (same policy as startDate)    → end_date
        enableOrderBook absent/None                  → None (conservative; discovery
                                                       rejects None as NO_ORDER_BOOK)
                       any non-None value            → bool() coercion
        tokens         absent/None/non-list          → None (conservative; discovery
                                                       rejects None as EMPTY_TOKENS)
                       list (incl. empty [])         → list as-is

        Downstream effects:
          - question="" is safe: symbol extraction falls back to slug then market_id.
          - slug=None: mapper falls back to market_id for symbol; safe.
          - enable_order_book=None / tokens=None: discovery rejects via NO_ORDER_BOOK /
            EMPTY_TOKENS; these records never become candidates.
          - source_timestamp=None / end_date=None: discovery rejects via MISSING_DATES.
        """
        market_id = raw.get("id")
        if not isinstance(market_id, str) or not market_id.strip():
            logger.warning("Skipping market with missing/invalid id: %r", raw)
            return None

        question: str = (raw.get("question") or "").strip()
        _slug = raw.get("slug")
        slug: str | None = (_slug.strip() or None) if isinstance(_slug, str) else None
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

        # enable_order_book — None when field absent, bool otherwise
        _eob = raw.get("enableOrderBook")
        enable_order_book: bool | None = None if _eob is None else bool(_eob)

        # tokens — None when field absent or not a list; [] when present but empty
        _tok = raw.get("tokens")
        tokens: list | None = _tok if isinstance(_tok, list) else None

        return FetchedMarket(
            market_id=market_id.strip(),
            question=question,
            event_id=event_id,
            slug=slug,
            active=active,
            closed=closed,
            source_timestamp=source_timestamp,
            end_date=end_date,
            enable_order_book=enable_order_book,
            tokens=tokens,
        )


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
