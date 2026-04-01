"""Integration tests — discovery flow architectural contracts.

These tests verify the full production path from a raw Gamma API payload
through normalisation, candidate selection, and orchestration.

The ONLY thing mocked is PolymarketClient.get_markets() — the actual
network boundary.  Every other component (PolymarketFetchService,
DiscoveryService, MarketSyncService, FastAPI app) runs its real code.

Four architecture contracts are locked here:

  C1  PolymarketFetchService is a normaliser, not a candidate selector.
      It must return every record the API sends, preserving field values
      faithfully so that DiscoveryService can evaluate them.

  C2  DiscoveryService is the sole candidate-selection authority.
      All five rejection rules (INACTIVE, NO_ORDER_BOOK, EMPTY_TOKENS,
      MISSING_DATES, DURATION_OUT_OF_RANGE) are applied only here.

  C3  MarketSyncService respects DiscoveryService output.
      It writes exactly the candidates discovery returns — no extra
      filtering, no silent drops.

  C4  The /discover endpoint surfaces only DiscoveryService candidates.
      The HTTP response counts must match what DiscoveryService returns
      when run against the same payload.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.api.deps import get_discovery_service
from backend.app.domain.market.registry import InMemoryMarketRegistry
from backend.app.main import app
from backend.app.services.market_discovery import DiscoveryService, RejectionReason
from backend.app.services.market_fetcher import FetchedMarket, PolymarketFetchService
from backend.app.services.market_sync import MarketSyncService


# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

_START = "2024-01-01T00:00:00Z"
_VALID_END = "2024-01-01T00:05:00Z"   # 300 s after _START — valid 5m window
_LONG_END = "2024-01-01T01:00:00Z"    # 3600 s — duration_out_of_range


# ---------------------------------------------------------------------------
# Gamma API payload factory
#
# _gamma(**overrides) builds a fully valid raw Gamma market dict.
# Pass field overrides to create specific rejection scenarios.
# To simulate an absent API field, build the dict and del the key:
#   raw = _gamma(id="m-x"); del raw["enableOrderBook"]
# ---------------------------------------------------------------------------

def _gamma(**overrides) -> dict:
    """Return a minimal Gamma API market dict that satisfies all discovery rules.

    All overrides are applied after the defaults, so any field can be
    replaced.  Pass id= to distinguish markets in multi-market tests.
    """
    raw: dict = {
        "id":              "m-1",
        "question":        "Will BTC hit 100k?",
        "slug":            "btc-100k",
        "active":          True,
        "closed":          False,
        "enableOrderBook": True,
        "tokens":          [{"outcome": "YES"}, {"outcome": "NO"}],
        "startDate":       _START,
        "endDate":         _VALID_END,
        "events":          [{"id": "evt-1"}],
    }
    raw.update(overrides)
    return raw


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def _mock_client(raw_markets: list[dict]) -> MagicMock:
    """Return a MagicMock PolymarketClient whose get_markets() returns raw_markets."""
    client = MagicMock()
    client.get_markets.return_value = raw_markets
    return client


def _pipeline(raw_markets: list[dict]) -> tuple[list[FetchedMarket], object]:
    """Run real fetch_markets() + real DiscoveryService.evaluate().

    Returns (fetched_list, discovery_result) so tests can assert on both
    layers independently — the key tool for verifying C1 and C2 together.
    """
    fetcher = PolymarketFetchService(_mock_client(raw_markets))
    fetched = fetcher.fetch_markets()
    result = DiscoveryService().evaluate(fetched)
    return fetched, result


# ---------------------------------------------------------------------------
# C1 — PolymarketFetchService is a normaliser, not a candidate selector
# ---------------------------------------------------------------------------


class TestFetcherIsNormaliserNotSelector:
    """Contract C1: fetch_markets() must return every record from the API.

    Invalid markets (inactive, no order book, empty tokens, missing dates,
    bad duration) must all pass through the fetch layer unchanged so that
    DiscoveryService receives them and can apply its rules.
    """

    def test_fetch_returns_all_markets_including_invalid_ones(self):
        """All five rejection-scenario markets pass through fetch_markets()."""
        raw_end_out_of_range = _gamma(id="long", endDate=_LONG_END)

        raw_missing_date = _gamma(id="no-date")
        del raw_missing_date["startDate"]

        raw_markets = [
            _gamma(id="inactive", active=False),
            _gamma(id="no-ob", enableOrderBook=False),
            _gamma(id="empty-tok", tokens=[]),
            raw_missing_date,
            raw_end_out_of_range,
        ]
        fetcher = PolymarketFetchService(_mock_client(raw_markets))
        fetched = fetcher.fetch_markets()

        # ALL five must come back — the fetch layer must not filter
        assert len(fetched) == 5
        ids = {m.market_id for m in fetched}
        assert ids == {"inactive", "no-ob", "empty-tok", "no-date", "long"}

    def test_fetch_preserves_field_values_discovery_needs_to_evaluate(self):
        """Field values that DiscoveryService checks must survive normalisation.

        active=False, enable_order_book=False, tokens=[] must not be
        silently coerced or hidden during normalisation.
        """
        raw_markets = [
            _gamma(id="inactive", active=False),
            _gamma(id="no-ob", enableOrderBook=False),
            _gamma(id="empty-tok", tokens=[]),
        ]
        fetcher = PolymarketFetchService(_mock_client(raw_markets))
        fetched = {m.market_id: m for m in fetcher.fetch_markets()}

        assert fetched["inactive"].active is False
        assert fetched["no-ob"].enable_order_book is False
        assert fetched["empty-tok"].tokens == []


# ---------------------------------------------------------------------------
# C2 — DiscoveryService is the sole candidate-selection authority
# ---------------------------------------------------------------------------


class TestDiscoveryIsTheSoleSelector:
    """Contract C2: all acceptance/rejection decisions happen in DiscoveryService.

    Each test verifies: fetch returns the market (C1 still holds), then
    discovery applies the correct rejection rule, so the market does not
    appear as a candidate.
    """

    def test_valid_5m_market_becomes_candidate(self):
        """A market satisfying all five rules is accepted as a candidate."""
        fetched, result = _pipeline([_gamma()])

        assert len(fetched) == 1          # fetch returned it
        assert result.candidate_count == 1
        assert result.rejected_count == 0
        assert result.candidates[0].market_id == "m-1"

    def test_inactive_active_false_fetch_passes_discovery_rejects(self):
        """active=False: fetch layer returns it; discovery assigns INACTIVE."""
        fetched, result = _pipeline([_gamma(id="bad", active=False)])

        assert len(fetched) == 1                                          # C1
        assert result.candidate_count == 0                                # C2
        assert result.rejection_breakdown[RejectionReason.INACTIVE] == 1

    def test_inactive_closed_true_fetch_passes_discovery_rejects(self):
        """closed=True: fetch layer returns it; discovery assigns INACTIVE."""
        fetched, result = _pipeline([_gamma(id="bad", closed=True)])

        assert len(fetched) == 1
        assert result.rejection_breakdown[RejectionReason.INACTIVE] == 1

    def test_no_order_book_false_fetch_passes_discovery_rejects(self):
        """enableOrderBook=False: fetch returns it; discovery assigns NO_ORDER_BOOK."""
        fetched, result = _pipeline([_gamma(id="bad", enableOrderBook=False)])

        assert len(fetched) == 1
        assert result.candidate_count == 0
        assert result.rejection_breakdown[RejectionReason.NO_ORDER_BOOK] == 1

    def test_no_order_book_absent_field_fetch_passes_discovery_rejects(self):
        """enableOrderBook absent in API response: conservative NO_ORDER_BOOK reject."""
        raw = _gamma(id="bad")
        del raw["enableOrderBook"]

        fetched, result = _pipeline([raw])

        assert len(fetched) == 1                                              # C1: fetch returned it
        assert result.rejection_breakdown[RejectionReason.NO_ORDER_BOOK] == 1

    def test_empty_tokens_list_fetch_passes_discovery_rejects(self):
        """tokens=[]: fetch returns it; discovery assigns EMPTY_TOKENS."""
        fetched, result = _pipeline([_gamma(id="bad", tokens=[])])

        assert len(fetched) == 1
        assert result.candidate_count == 0
        assert result.rejection_breakdown[RejectionReason.EMPTY_TOKENS] == 1

    def test_missing_start_date_fetch_passes_discovery_rejects(self):
        """startDate absent: fetch returns it (source_timestamp=None); discovery assigns MISSING_DATES."""
        raw = _gamma(id="bad")
        del raw["startDate"]

        fetched, result = _pipeline([raw])

        assert len(fetched) == 1
        fetched_market = fetched[0]
        assert fetched_market.source_timestamp is None                        # normaliser preserved None
        assert result.rejection_breakdown[RejectionReason.MISSING_DATES] == 1

    def test_missing_end_date_fetch_passes_discovery_rejects(self):
        """endDate absent: fetch returns it (end_date=None); discovery assigns MISSING_DATES."""
        raw = _gamma(id="bad")
        del raw["endDate"]

        fetched, result = _pipeline([raw])

        assert len(fetched) == 1
        assert fetched[0].end_date is None
        assert result.rejection_breakdown[RejectionReason.MISSING_DATES] == 1

    def test_duration_out_of_range_fetch_passes_discovery_rejects(self):
        """endDate 3600 s after startDate: fetch returns it; discovery assigns DURATION_OUT_OF_RANGE."""
        fetched, result = _pipeline([_gamma(id="bad", endDate=_LONG_END)])

        assert len(fetched) == 1
        assert result.rejection_breakdown[RejectionReason.DURATION_OUT_OF_RANGE] == 1

    def test_mixed_payload_only_valid_candidates_survive(self):
        """One valid market + one per rejection reason — only the valid one becomes a candidate.

        This is the key end-to-end assertion: all six records reach the fetch
        layer, but only one passes discovery.
        """
        raw_markets = [
            _gamma(id="ok"),
            _gamma(id="inactive", active=False),
            _gamma(id="no-ob", enableOrderBook=False),
            _gamma(id="empty-tok", tokens=[]),
            _gamma(id="no-dates", endDate=None),          # will be ignored (None via override → keep key)
            _gamma(id="long", endDate=_LONG_END),
        ]
        # Override endDate=None properly: remove the key
        raw_markets[4] = _gamma(id="no-dates")
        del raw_markets[4]["endDate"]

        fetched, result = _pipeline(raw_markets)

        assert len(fetched) == 6                          # C1: all reached fetch
        assert result.candidate_count == 1                # C2: only "ok" passed
        assert result.candidates[0].market_id == "ok"
        assert result.rejected_count == 5
        assert result.rejection_breakdown[RejectionReason.INACTIVE] == 1
        assert result.rejection_breakdown[RejectionReason.NO_ORDER_BOOK] == 1
        assert result.rejection_breakdown[RejectionReason.EMPTY_TOKENS] == 1
        assert result.rejection_breakdown[RejectionReason.MISSING_DATES] == 1
        assert result.rejection_breakdown[RejectionReason.DURATION_OUT_OF_RANGE] == 1


# ---------------------------------------------------------------------------
# C3 — MarketSyncService respects DiscoveryService output
# ---------------------------------------------------------------------------


class TestSyncRespectsDiscovery:
    """Contract C3: MarketSyncService.run() writes exactly what DiscoveryService returns.

    No extra filtering.  No extra candidates.  The registry state after a
    run must mirror the DiscoveryService candidate list exactly.
    """

    def test_sync_writes_only_discovery_candidates(self):
        """Invalid markets in the payload must not appear in the registry."""
        raw_markets = [
            _gamma(id="ok"),
            _gamma(id="inactive", active=False),
            _gamma(id="no-ob", enableOrderBook=False),
        ]
        registry = InMemoryMarketRegistry()
        MarketSyncService(
            PolymarketFetchService(_mock_client(raw_markets)), registry
        ).run()

        written_ids = {m.id for m in registry.list_all()}
        assert "ok-up" in written_ids
        assert "ok-down" in written_ids
        assert "inactive-up" not in written_ids
        assert "inactive-down" not in written_ids
        assert "no-ob-up" not in written_ids

    def test_sync_all_invalid_payload_writes_nothing(self):
        """When every market fails discovery, the registry stays empty."""
        raw_markets = [
            _gamma(id="a", active=False),
            _gamma(id="b", enableOrderBook=False),
            _gamma(id="c", tokens=[]),
        ]
        registry = InMemoryMarketRegistry()
        result = MarketSyncService(
            PolymarketFetchService(_mock_client(raw_markets)), registry
        ).run()

        assert result.fetched == 0
        assert result.written == 0
        assert len(registry) == 0

    def test_sync_valid_payload_produces_up_down_pairs_per_candidate(self):
        """Each discovery candidate produces exactly one UP and one DOWN entry."""
        raw_markets = [_gamma(id="m-1"), _gamma(id="m-2")]
        registry = InMemoryMarketRegistry()
        MarketSyncService(
            PolymarketFetchService(_mock_client(raw_markets)), registry
        ).run()

        assert {m.id for m in registry.list_all()} == {
            "m-1-up", "m-1-down",
            "m-2-up", "m-2-down",
        }


# ---------------------------------------------------------------------------
# C4 — /discover endpoint surfaces only DiscoveryService candidates
# ---------------------------------------------------------------------------
#
# These tests override get_discovery_service with real services backed by
# a mock client — more of the production stack runs than in test_discover_api.py.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_discover_endpoint_mixed_payload_returns_only_candidates():
    """Real fetcher + real discovery with mock client — mixed payload.

    The endpoint must report exactly what DiscoveryService returns.
    """
    raw_markets = [
        _gamma(id="ok"),
        _gamma(id="bad-inactive", active=False),
        _gamma(id="bad-no-ob", enableOrderBook=False),
    ]
    real_fetcher = PolymarketFetchService(_mock_client(raw_markets))
    real_discovery = DiscoveryService()
    app.dependency_overrides[get_discovery_service] = lambda: (real_fetcher, real_discovery)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/api/v1/markets/discover")
        assert resp.status_code == 200
        data = resp.json()
        assert data["fetched_count"] == 3
        assert data["candidate_count"] == 1
        assert data["rejected_count"] == 2
        assert data["rejection_breakdown"]["inactive"] == 1
        assert data["rejection_breakdown"]["no_order_book"] == 1
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_discover_endpoint_all_valid_payload():
    """All three markets pass discovery — endpoint reports candidate_count=3."""
    raw_markets = [_gamma(id="m-1"), _gamma(id="m-2"), _gamma(id="m-3")]
    real_fetcher = PolymarketFetchService(_mock_client(raw_markets))
    real_discovery = DiscoveryService()
    app.dependency_overrides[get_discovery_service] = lambda: (real_fetcher, real_discovery)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/api/v1/markets/discover")
        data = resp.json()
        assert data["fetched_count"] == 3
        assert data["candidate_count"] == 3
        assert data["rejected_count"] == 0
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_discover_endpoint_all_invalid_payload():
    """All three markets fail discovery — endpoint reports candidate_count=0."""
    raw_markets = [
        _gamma(id="a", active=False),
        _gamma(id="b", enableOrderBook=False),
        _gamma(id="c", tokens=[]),
    ]
    real_fetcher = PolymarketFetchService(_mock_client(raw_markets))
    real_discovery = DiscoveryService()
    app.dependency_overrides[get_discovery_service] = lambda: (real_fetcher, real_discovery)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/api/v1/markets/discover")
        data = resp.json()
        assert data["fetched_count"] == 3
        assert data["candidate_count"] == 0
        assert data["rejected_count"] == 3
        assert data["rejection_breakdown"]["inactive"] == 1
        assert data["rejection_breakdown"]["no_order_book"] == 1
        assert data["rejection_breakdown"]["empty_tokens"] == 1
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Duration semantics — total duration, not remaining time
#
# These tests lock the contract that DiscoveryService evaluates the
# *structural* 5m format of a market (end_date − source_timestamp),
# not how much time is left until the market closes (end_date − now).
#
# The "is it too late to enter?" question belongs to a runtime/strategy
# layer, not to discovery.
# ---------------------------------------------------------------------------


class TestDurationSemantics:
    """Integration-level duration contract: total duration, not remaining time.

    All tests run through the full real pipeline:
      raw Gamma dict → PolymarketFetchService.fetch_markets()
                     → DiscoveryService.evaluate()
    Only PolymarketClient.get_markets() is mocked.
    """

    def _now_iso(self, delta_seconds: int) -> str:
        """Return an ISO-8601 UTC string offset from now by delta_seconds."""
        dt = datetime.now(timezone.utc) + timedelta(seconds=delta_seconds)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    def test_near_expiry_valid_5m_market_passes_full_pipeline(self):
        """A market near expiry with valid total duration must survive the full pipeline.

        Payload: startDate = 4 minutes ago, endDate = 1 minute from now.
          total duration  = 300 s  → valid [240, 360]
          remaining time  = ~60 s  → would be invalid if remaining-time based

        Expected: DiscoveryService accepts it as a candidate.
        Proves: the raw → normalise → evaluate chain uses total duration.
        """
        raw = _gamma(
            id="near-expiry",
            startDate=self._now_iso(-240),   # started 4 min ago
            endDate=self._now_iso(60),       # ends in 1 min
        )
        fetched, result = _pipeline([raw])

        assert len(fetched) == 1                    # fetch layer returned it
        assert result.candidate_count == 1          # discovery accepted it
        assert result.candidates[0].market_id == "near-expiry"

    def test_final_30s_market_with_300s_total_duration_is_candidate(self):
        """Market in its final 30 seconds (total=300s) remains a valid candidate.

        Even with only 30 seconds remaining, the market is structurally a
        5m event and must pass discovery.
        """
        raw = _gamma(
            id="last-30s",
            startDate=self._now_iso(-270),   # started 4m30s ago
            endDate=self._now_iso(30),       # ends in 30s; total=300s
        )
        fetched, result = _pipeline([raw])

        assert len(fetched) == 1
        assert result.candidate_count == 1

    def test_mixed_payload_near_expiry_valid_market_survives_with_invalid_durations(self):
        """Near-expiry valid market survives in a mixed batch.

        Batch:
          - near-expiry valid (total=300s, remaining=~60s) → must be candidate
          - structurally-short (total=120s)                → DURATION_OUT_OF_RANGE
          - structurally-long  (total=3600s)               → DURATION_OUT_OF_RANGE
          - inactive                                       → INACTIVE

        Only the near-expiry valid market should be a candidate.
        """
        raw_markets = [
            _gamma(id="near-expiry-ok",
                   startDate=self._now_iso(-240),
                   endDate=self._now_iso(60)),
            _gamma(id="short",
                   startDate=_START, endDate="2024-01-01T00:02:00Z"),    # 120 s
            _gamma(id="long",
                   startDate=_START, endDate="2024-01-01T01:00:00Z"),    # 3600 s
            _gamma(id="inactive", active=False),
        ]
        fetched, result = _pipeline(raw_markets)

        assert len(fetched) == 4               # all four reach the fetch layer
        assert result.candidate_count == 1
        assert result.candidates[0].market_id == "near-expiry-ok"
        assert result.rejected_count == 3

    def test_sync_writes_near_expiry_valid_market(self):
        """MarketSyncService must write a near-expiry valid market to the registry.

        Proves C3 (sync respects discovery) holds for the near-expiry scenario
        specifically — the market is not lost between discovery and registry write.
        """
        raw = _gamma(
            id="near-expiry-sync",
            startDate=self._now_iso(-250),
            endDate=self._now_iso(50),       # total=300s, remaining=~50s
        )
        registry = InMemoryMarketRegistry()
        MarketSyncService(
            PolymarketFetchService(_mock_client([raw])), registry
        ).run()

        ids = {m.id for m in registry.list_all()}
        assert "near-expiry-sync-up" in ids
        assert "near-expiry-sync-down" in ids
