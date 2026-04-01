"""Integration tests — Rejection Observability Lock (v0.5.9).

These tests lock the contract that SyncResult and SyncResponse expose
rejection counts and per-reason breakdowns from DiscoveryService.

Locked semantics
----------------
  `rejected_count`        — number of FetchedMarket records rejected by
                            DiscoveryService in this call (did not become
                            candidates).
  `rejection_breakdown`   — per-reason counts; keys: inactive, no_order_book,
                            empty_tokens, missing_dates, duration_out_of_range.
                            All five keys are always present (value may be 0).

Tests:
  A  test_sync_summary_includes_rejected_count_for_non_candidates
  B  test_sync_summary_rejected_count_is_distinct_from_fetched_candidates
  C  test_sync_summary_rejection_breakdown_is_deterministic
  D  test_sync_api_response_matches_service_rejection_observability
  E  test_rejection_observability_does_not_change_candidate_or_registry_behavior

The ONLY thing mocked is PolymarketClient.get_markets().
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.api.deps import get_registry, get_sync_service
from backend.app.domain.market.registry import InMemoryMarketRegistry
from backend.app.main import app
from backend.app.services.market_fetcher import PolymarketFetchService
from backend.app.services.market_sync import MarketSyncService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_START = "2024-01-01T00:00:00Z"
_VALID_END = "2024-01-01T00:05:00Z"
_SHORT_END = "2024-01-01T00:01:00Z"   # 60s — duration_out_of_range


def _gamma(**overrides) -> dict:
    raw: dict = {
        "id": "m-1", "question": "Will BTC hit 100k?", "slug": "btc-100k",
        "active": True, "closed": False, "enableOrderBook": True,
        "tokens": [{"outcome": "YES"}, {"outcome": "NO"}],
        "startDate": _START, "endDate": _VALID_END, "events": [{"id": "evt-1"}],
    }
    raw.update(overrides)
    return raw


def _mock_client(raw_markets: list[dict]) -> MagicMock:
    client = MagicMock()
    client.get_markets.return_value = raw_markets
    return client


def _run(raw_markets: list[dict], registry: InMemoryMarketRegistry):
    svc = MarketSyncService(PolymarketFetchService(_mock_client(raw_markets)), registry)
    return svc.run()


_ALL_REASONS = {"inactive", "no_order_book", "empty_tokens", "missing_dates", "duration_out_of_range"}


# ---------------------------------------------------------------------------
# A — rejected_count surfaces non-candidate markets
# ---------------------------------------------------------------------------


class TestRejectedCountSurfacesNonCandidates:
    """A: rejected_count equals the number of markets that failed discovery."""

    def test_sync_summary_includes_rejected_count_for_non_candidates(self):
        """rejected_count reflects markets that did not pass discovery.

        Setup: 2 valid candidates + 3 rejected (inactive, no_order_book, empty_tokens)
        Expected:
          fetched          = 2   (only valid candidates)
          rejected_count   = 3
          written          = 4
        """
        registry = InMemoryMarketRegistry()
        result = _run(
            [
                _gamma(id="ok-1"),
                _gamma(id="ok-2"),
                _gamma(id="bad-inactive", active=False),
                _gamma(id="bad-no-ob", enableOrderBook=False),
                _gamma(id="bad-tokens", tokens=[]),
            ],
            registry,
        )

        assert result.fetched == 2
        assert result.rejected_count == 3
        assert result.written == 4

    def test_all_valid_means_zero_rejected(self):
        """All markets pass discovery: rejected_count must be 0."""
        registry = InMemoryMarketRegistry()
        result = _run([_gamma(id="a"), _gamma(id="b")], registry)

        assert result.rejected_count == 0
        assert result.fetched == 2

    def test_all_rejected_means_zero_fetched(self):
        """All markets fail discovery: fetched=0, rejected_count=total."""
        registry = InMemoryMarketRegistry()
        result = _run(
            [
                _gamma(id="x", active=False),
                _gamma(id="y", tokens=[]),
                _gamma(id="z", enableOrderBook=False),
            ],
            registry,
        )

        assert result.fetched == 0
        assert result.rejected_count == 3


# ---------------------------------------------------------------------------
# B — rejected_count is distinct from fetched
# ---------------------------------------------------------------------------


class TestRejectedCountDistinctFromFetched:
    """B: fetched + rejected_count = total input to discovery."""

    def test_sync_summary_rejected_count_is_distinct_from_fetched_candidates(self):
        """fetched and rejected_count partition the discovery input set.

        Setup: 1 valid + 2 rejected → fetched=1, rejected_count=2,
               fetched + rejected_count = 3 (total input).
        """
        registry = InMemoryMarketRegistry()
        result = _run(
            [
                _gamma(id="ok"),
                _gamma(id="no-ob", enableOrderBook=False),
                _gamma(id="inactive", active=False),
            ],
            registry,
        )

        assert result.fetched == 1
        assert result.rejected_count == 2
        assert result.fetched + result.rejected_count == 3

    def test_partition_holds_for_empty_input(self):
        """Empty input: fetched=0, rejected_count=0, sum=0."""
        registry = InMemoryMarketRegistry()
        result = _run([], registry)

        assert result.fetched == 0
        assert result.rejected_count == 0
        assert result.fetched + result.rejected_count == 0

    def test_partition_holds_for_single_valid(self):
        """Single valid input: fetched=1, rejected_count=0, sum=1."""
        registry = InMemoryMarketRegistry()
        result = _run([_gamma(id="solo")], registry)

        assert result.fetched == 1
        assert result.rejected_count == 0

    def test_partition_holds_for_single_invalid(self):
        """Single invalid input: fetched=0, rejected_count=1, sum=1."""
        registry = InMemoryMarketRegistry()
        result = _run([_gamma(id="bad", active=False)], registry)

        assert result.fetched == 0
        assert result.rejected_count == 1


# ---------------------------------------------------------------------------
# C — rejection_breakdown is deterministic per reason
# ---------------------------------------------------------------------------


class TestRejectionBreakdownDeterministic:
    """C: rejection_breakdown keys are always present; counts match rejections."""

    def test_sync_summary_rejection_breakdown_is_deterministic(self):
        """One market rejected per reason → breakdown has count 1 per reason.

        Setup: one market for each of the 5 rejection reasons + one valid.
        """
        registry = InMemoryMarketRegistry()
        result = _run(
            [
                _gamma(id="ok"),
                _gamma(id="inactive", active=False),
                _gamma(id="no-ob", enableOrderBook=False),
                _gamma(id="no-tok", tokens=[]),
                _gamma(id="no-dates", startDate=None, endDate=None),
                _gamma(id="bad-dur", endDate=_SHORT_END),
            ],
            registry,
        )

        assert result.rejection_breakdown["inactive"] == 1
        assert result.rejection_breakdown["no_order_book"] == 1
        assert result.rejection_breakdown["empty_tokens"] == 1
        assert result.rejection_breakdown["missing_dates"] == 1
        assert result.rejection_breakdown["duration_out_of_range"] == 1
        assert result.rejected_count == 5

    def test_all_keys_present_even_when_no_rejections(self):
        """All 5 keys must be present even when rejected_count == 0."""
        registry = InMemoryMarketRegistry()
        result = _run([_gamma(id="ok")], registry)

        assert set(result.rejection_breakdown.keys()) == _ALL_REASONS
        assert all(v == 0 for v in result.rejection_breakdown.values())

    def test_all_keys_present_for_empty_input(self):
        """All 5 keys present when input is empty."""
        registry = InMemoryMarketRegistry()
        result = _run([], registry)

        assert set(result.rejection_breakdown.keys()) == _ALL_REASONS
        assert all(v == 0 for v in result.rejection_breakdown.values())

    def test_multiple_rejections_same_reason_accumulate(self):
        """Two markets rejected for same reason: breakdown count == 2."""
        registry = InMemoryMarketRegistry()
        result = _run(
            [
                _gamma(id="i1", active=False),
                _gamma(id="i2", active=False),
            ],
            registry,
        )

        assert result.rejection_breakdown["inactive"] == 2
        assert result.rejected_count == 2
        assert result.fetched == 0


# ---------------------------------------------------------------------------
# D — API response matches service rejection observability
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_api_response_matches_service_rejection_observability():
    """D: SyncResponse exposes rejected_count and rejection_breakdown from SyncResult.

    Verifies that the HTTP layer passes through both new fields without loss.
    """
    registry = InMemoryMarketRegistry()
    raw_markets = [
        _gamma(id="ok"),
        _gamma(id="bad-inactive", active=False),
        _gamma(id="bad-no-ob", enableOrderBook=False),
    ]
    sync_svc = MarketSyncService(
        PolymarketFetchService(_mock_client(raw_markets)), registry
    )
    app.dependency_overrides[get_sync_service] = lambda: sync_svc
    app.dependency_overrides[get_registry] = lambda: registry
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/api/v1/markets/sync")
        assert resp.status_code == 200
        data = resp.json()

        assert data["fetched_count"] == 1
        assert data["rejected_count"] == 2
        assert set(data["rejection_breakdown"].keys()) == _ALL_REASONS
        assert data["rejection_breakdown"]["inactive"] == 1
        assert data["rejection_breakdown"]["no_order_book"] == 1
        assert data["rejection_breakdown"]["empty_tokens"] == 0
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# E — Observability does not affect candidate or registry behavior
# ---------------------------------------------------------------------------


class TestObservabilityDoesNotAffectBehavior:
    """E: Adding rejection observability must not change which markets are written."""

    def test_rejection_observability_does_not_change_candidate_or_registry_behavior(self):
        """Registry state is unchanged by the presence of rejection tracking.

        Candidates that pass discovery are still written; rejected ones are not.
        This test verifies observability is read-only relative to registry behavior.
        """
        registry = InMemoryMarketRegistry()
        result = _run(
            [
                _gamma(id="ok-a"),
                _gamma(id="ok-b"),
                _gamma(id="rej", active=False),
            ],
            registry,
        )

        # Registry contains only candidates
        ids = {m.id for m in registry.list_all()}
        assert "ok-a-up" in ids
        assert "ok-a-down" in ids
        assert "ok-b-up" in ids
        assert "ok-b-down" in ids
        assert "rej-up" not in ids
        assert "rej-down" not in ids

        # Observability fields present but did not alter written count
        assert result.written == 4
        assert result.rejected_count == 1
        assert result.rejection_breakdown["inactive"] == 1

    def test_rejected_markets_not_in_registry_after_sync(self):
        """All 5 rejection reasons: none of the rejected markets enter registry."""
        registry = InMemoryMarketRegistry()
        _run(
            [
                _gamma(id="ok"),
                _gamma(id="r-inactive", active=False),
                _gamma(id="r-no-ob", enableOrderBook=False),
                _gamma(id="r-no-tok", tokens=[]),
                _gamma(id="r-no-dates", startDate=None, endDate=None),
                _gamma(id="r-dur", endDate=_SHORT_END),
            ],
            registry,
        )

        ids = {m.id for m in registry.list_all()}
        assert ids == {"ok-up", "ok-down"}
