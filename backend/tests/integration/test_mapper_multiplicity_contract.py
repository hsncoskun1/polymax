"""Integration tests — Mapper Multiplicity Contract Lock (v0.5.13).

These tests lock the contract that MarketMapper produces exactly 2 domain
Market objects (UP + DOWN) per successfully mapped candidate.

Locked contracts
----------------
  EXACT-TWO CONTRACT    — Each successfully mapped FetchedMarket candidate
                          produces exactly 2 domain Market objects: one with
                          Side.UP and one with Side.DOWN.
                          This is a canonical contract (not implementation
                          detail): Polymarket binary markets are fundamentally
                          YES/NO structures and POLYMAX tracks both sides.
  MAPPED SEMANTICS      — SyncResult.mapped counts domain Market objects, not
                          candidates.  mapped = successful_candidates × 2.
  PARTITION CONTRACT    — mapped = written + skipped_duplicate (output
                          partition: each mapped market is either new or dup).
  IDENTITY CONTRACT     — The two produced markets have stable identity:
                          ids {market_id}-up and {market_id}-down with
                          Side.UP and Side.DOWN respectively.
  DOCS/RUNTIME ALIGN    — MarketMapper.MARKETS_PER_CANDIDATE constant and
                          SyncResult.mapped semantics are consistent at runtime.

Tests:
  A  test_candidate_maps_to_exactly_two_domain_markets_when_mapper_contract_is_up_down_pair
  B  test_mapped_count_semantics_are_derived_from_mapper_output_not_raw_candidate_count_alone
  C  test_written_and_skipped_duplicate_partition_total_mapped_output
  D  test_mapper_output_identity_is_stable_for_up_down_pair
  E  test_docs_runtime_and_summary_contract_align_for_mapper_multiplicity
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.api.deps import get_registry, get_sync_service
from backend.app.domain.market.registry import InMemoryMarketRegistry
from backend.app.domain.market.types import Side
from backend.app.main import app
from backend.app.services.market_fetcher import FetchedMarket, PolymarketFetchService
from backend.app.services.market_sync import MarketMapper, MarketSyncService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BASE_START = datetime(2024, 1, 1, tzinfo=timezone.utc)
_VALID_END = _BASE_START + timedelta(seconds=300)
_START_STR = "2024-01-01T00:00:00Z"
_VALID_END_STR = "2024-01-01T00:05:00Z"


def _fetched(market_id: str = "m-1") -> FetchedMarket:
    return FetchedMarket(
        market_id=market_id,
        question="Will BTC hit 100k?",
        event_id="evt-1",
        slug="btc-100k",
        active=True,
        closed=False,
        source_timestamp=_BASE_START,
        end_date=_VALID_END,
        enable_order_book=True,
        tokens=[{"outcome": "YES"}, {"outcome": "NO"}],
    )


def _gamma(**overrides) -> dict:
    raw: dict = {
        "id": "m-1", "question": "Will BTC hit 100k?", "slug": "btc-100k",
        "active": True, "closed": False, "enableOrderBook": True,
        "tokens": [{"outcome": "YES"}, {"outcome": "NO"}],
        "startDate": _START_STR, "endDate": _VALID_END_STR,
        "events": [{"id": "evt-1"}],
    }
    raw.update(overrides)
    return raw


def _mock_client(raw_markets: list[dict]) -> MagicMock:
    client = MagicMock()
    client.get_markets.return_value = raw_markets
    return client


def _run_sync(raw_markets: list[dict], registry: InMemoryMarketRegistry):
    svc = MarketSyncService(PolymarketFetchService(_mock_client(raw_markets)), registry)
    return svc.run()


# ---------------------------------------------------------------------------
# A — exact-two contract
# ---------------------------------------------------------------------------


class TestExactTwoContract:
    """A: MarketMapper produces exactly 2 domain Markets per successful candidate."""

    def test_candidate_maps_to_exactly_two_domain_markets_when_mapper_contract_is_up_down_pair(self):
        """Single candidate → exactly 2 Market objects."""
        mapper = MarketMapper()
        result = mapper.map(_fetched("m-1"))

        assert len(result) == 2, (
            f"Expected exactly 2 domain Markets per candidate, got {len(result)}"
        )

    def test_mapper_markets_per_candidate_constant_equals_two(self):
        """MarketMapper.MARKETS_PER_CANDIDATE == 2 (canonical constant)."""
        assert MarketMapper.MARKETS_PER_CANDIDATE == 2

    def test_n_candidates_produce_n_times_two_market_objects(self):
        """N candidates → N × 2 domain Market objects in sync."""
        registry = InMemoryMarketRegistry()
        n = 3
        raw = [_gamma(id=f"m-{i}") for i in range(n)]
        result = _run_sync(raw, registry)

        assert result.mapped == n * MarketMapper.MARKETS_PER_CANDIDATE
        assert result.mapped == n * 2
        assert len(registry) == n * 2

    def test_mapper_returns_empty_list_on_failure_not_partial_output(self):
        """Failed mapping returns [] (0 markets), never a partial list."""
        mapper = MarketMapper()
        bad = FetchedMarket(
            market_id="   ",  # stripped → empty → domain validation error
            question="", event_id=None, slug=None,
            active=True, closed=False,
            source_timestamp=None, end_date=None,
        )
        result = mapper.map(bad)
        assert result == []


# ---------------------------------------------------------------------------
# B — mapped counts Market objects, not candidates
# ---------------------------------------------------------------------------


class TestMappedCountSemantics:
    """B: SyncResult.mapped counts domain Market objects, not candidate count."""

    def test_mapped_count_semantics_are_derived_from_mapper_output_not_raw_candidate_count_alone(self):
        """mapped != fetched; mapped == fetched × 2 (for 0 skipped_mapping)."""
        registry = InMemoryMarketRegistry()
        result = _run_sync([_gamma(id="a"), _gamma(id="b")], registry)

        assert result.fetched == 2
        assert result.mapped == 4  # 2 candidates × 2 sides
        assert result.mapped != result.fetched  # NOT the same thing

    def test_mapped_reflects_mapper_output_not_candidate_count_with_skipped(self):
        """With one skipped_mapping: mapped = (fetched - skipped) × 2."""
        bad = FetchedMarket(
            market_id="   ",  # triggers mapping failure
            question="", event_id=None, slug=None,
            active=True, closed=False,
            source_timestamp=_BASE_START, end_date=_VALID_END,
            enable_order_book=True, tokens=[{"outcome": "YES"}],
        )
        registry = InMemoryMarketRegistry()
        fetcher = MagicMock()
        fetcher.fetch_markets.return_value = [
            PolymarketFetchService(_mock_client([_gamma(id="ok")])).fetch_markets()[0],
            bad,
        ]
        result = MarketSyncService(fetcher, registry).run()

        # 1 candidate passed discovery (bad passes discovery but fails mapping)
        # wait — bad has active=True, source_timestamp=_BASE_START, end_date=_VALID_END
        # so bad passes discovery but fails mapping
        assert result.skipped_mapping == 1
        # mapped only counts successful mapper output
        assert result.mapped == 2   # only "ok" → 2 markets
        assert result.mapped == (result.fetched - result.skipped_mapping) * 2


# ---------------------------------------------------------------------------
# C — written + skipped_duplicate = mapped partition
# ---------------------------------------------------------------------------


class TestMappedPartitionContract:
    """C: mapped = written + skipped_duplicate (mapper output partition)."""

    def test_written_and_skipped_duplicate_partition_total_mapped_output(self):
        """All new: mapped == written (no duplicates)."""
        registry = InMemoryMarketRegistry()
        result = _run_sync([_gamma(id="m")], registry)

        assert result.mapped == result.written + result.skipped_duplicate
        assert result.skipped_duplicate == 0
        assert result.mapped == result.written == 2

    def test_partition_holds_when_all_are_duplicates(self):
        """All duplicates: mapped == skipped_duplicate (written == 0)."""
        registry = InMemoryMarketRegistry()
        _run_sync([_gamma(id="m")], registry)  # first write
        result = _run_sync([_gamma(id="m")], registry)  # second: all duplicates

        assert result.mapped == result.written + result.skipped_duplicate
        assert result.written == 0
        assert result.skipped_duplicate == 2

    def test_partition_holds_for_mixed_new_and_duplicate(self):
        """Mixed: mapped == written + skipped_duplicate."""
        registry = InMemoryMarketRegistry()
        _run_sync([_gamma(id="existing")], registry)

        result = _run_sync([_gamma(id="existing"), _gamma(id="new")], registry)

        assert result.mapped == result.written + result.skipped_duplicate
        assert result.written == 2        # "new" only
        assert result.skipped_duplicate == 2  # "existing" already present
        assert result.mapped == 4


# ---------------------------------------------------------------------------
# D — mapper output identity (stable UP/DOWN pair)
# ---------------------------------------------------------------------------


class TestMapperOutputIdentity:
    """D: The two produced markets have stable identity: -up and -down suffixes."""

    def test_mapper_output_identity_is_stable_for_up_down_pair(self):
        """map() always produces one Side.UP and one Side.DOWN market."""
        mapper = MarketMapper()
        markets = mapper.map(_fetched("abc"))

        sides = {m.side for m in markets}
        assert sides == {Side.UP, Side.DOWN}

    def test_up_market_id_has_up_suffix(self):
        """The UP market always has id '{market_id}-up'."""
        mapper = MarketMapper()
        markets = mapper.map(_fetched("abc"))
        up_market = next(m for m in markets if m.side == Side.UP)
        assert up_market.id == "abc-up"

    def test_down_market_id_has_down_suffix(self):
        """The DOWN market always has id '{market_id}-down'."""
        mapper = MarketMapper()
        markets = mapper.map(_fetched("abc"))
        down_market = next(m for m in markets if m.side == Side.DOWN)
        assert down_market.id == "abc-down"

    def test_up_down_identity_stable_across_multiple_candidates(self):
        """Multiple candidates: each produces exactly one -up and one -down."""
        mapper = MarketMapper()
        for mid in ["x", "y", "z"]:
            markets = mapper.map(_fetched(mid))
            ids = {m.id for m in markets}
            assert ids == {f"{mid}-up", f"{mid}-down"}
            sides = {m.side for m in markets}
            assert sides == {Side.UP, Side.DOWN}


# ---------------------------------------------------------------------------
# E — docs/runtime/summary alignment
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_docs_runtime_and_summary_contract_align_for_mapper_multiplicity():
    """E: MARKETS_PER_CANDIDATE constant, SyncResult.mapped, and API response agree.

    The documented multiplicity contract is verifiable at every layer:
      MarketMapper.MARKETS_PER_CANDIDATE == 2
      SyncResult.mapped == N × MARKETS_PER_CANDIDATE
      SyncResponse.mapped_count == SyncResult.mapped
    """
    n_candidates = 3
    raw = [_gamma(id=f"m-{i}") for i in range(n_candidates)]
    registry = InMemoryMarketRegistry()
    svc = MarketSyncService(PolymarketFetchService(_mock_client(raw)), registry)

    app.dependency_overrides[get_sync_service] = lambda: svc
    app.dependency_overrides[get_registry] = lambda: registry
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/api/v1/markets/sync")
        assert resp.status_code == 200
        data = resp.json()

        expected_mapped = n_candidates * MarketMapper.MARKETS_PER_CANDIDATE
        assert data["mapped_count"] == expected_mapped
        assert data["fetched_count"] == n_candidates
        assert data["written_count"] == expected_mapped

        # Invariant: mapped = fetched × MARKETS_PER_CANDIDATE (no skipped_mapping)
        assert data["mapped_count"] == data["fetched_count"] * MarketMapper.MARKETS_PER_CANDIDATE
    finally:
        app.dependency_overrides.clear()
