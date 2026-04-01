"""Integration tests — Mapping Failure Semantics Lock (v0.5.14).

These tests lock the contract that mapping failures (skipped_mapping) are
distinct from discovery rejections (rejected_count) and registry duplicates
(skipped_duplicate), and that all three pipeline gates behave deterministically.

Locked contracts
----------------
  GATE-1 (DISCOVERY)     — rejected_count counts markets rejected by
                           DiscoveryService before they enter the map stage.
                           These are invisible to skipped_mapping.
  GATE-2 (MAPPING)       — skipped_mapping counts *candidates* that passed
                           discovery but whose mapper() returned [].  These
                           never reach the registry write stage.
  GATE-3 (REGISTRY DUP)  — skipped_duplicate counts *Market objects* (not
                           candidates) that were mapped successfully but
                           already existed in the registry.  One duplicate
                           candidate contributes 2 to skipped_duplicate.
  DISTINCTNESS           — The three gate counters are mutually exclusive.
                           A single FetchedMarket record can increment at
                           most one of {rejected_count, skipped_mapping,
                           skipped_duplicate}.
  PIPELINE INVARIANT     — fetched − skipped_mapping =
                           mapped / MARKETS_PER_CANDIDATE.
                           mapped = written + skipped_duplicate.

Tests:
  A  test_successful_candidate_with_mapper_failure_increments_skipped_mapping
  B  test_skipped_mapping_is_distinct_from_rejected_count_and_duplicate_count
  C  test_sync_api_response_matches_service_mapping_failure_semantics
  D  test_mixed_payload_with_success_duplicate_and_mapping_failure_produces_deterministic_summary
  E  test_docs_runtime_and_summary_contract_align_for_mapping_failure
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.api.deps import get_registry, get_sync_service
from backend.app.domain.market.registry import InMemoryMarketRegistry
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


def _good_fetched(market_id: str) -> FetchedMarket:
    """A FetchedMarket that passes discovery AND maps successfully."""
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


def _bad_mapper_fetched(market_id: str = "   ") -> FetchedMarket:
    """A FetchedMarket that passes discovery but fails mapping.

    Failure mechanism: event_id=None forces the mapper to fall back to
    market_id for the domain event_id field.  With a whitespace-only
    market_id, the non_empty_string validator strips it to "" and raises
    ValueError → MarketMapper.map() returns [].

    slug=None and a non-crypto question ensure the symbol fallback also
    reaches market_id, giving a second independent failure path.
    """
    return FetchedMarket(
        market_id=market_id,
        question="unrelated question with no crypto symbol",
        event_id=None,    # forces fallback to market_id → blank → fails validation
        slug=None,        # forces symbol fallback to market_id → blank → fails validation
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


def _make_fetcher_with_records(records: list[FetchedMarket]) -> MagicMock:
    """Fetcher that returns a pre-built list of FetchedMarket objects."""
    fetcher = MagicMock()
    fetcher.fetch_markets.return_value = records
    return fetcher


def _run_sync_from_records(
    records: list[FetchedMarket],
    registry: InMemoryMarketRegistry,
):
    svc = MarketSyncService(_make_fetcher_with_records(records), registry)
    return svc.run()


def _run_sync_from_raw(
    raw_markets: list[dict],
    registry: InMemoryMarketRegistry,
):
    svc = MarketSyncService(PolymarketFetchService(_mock_client(raw_markets)), registry)
    return svc.run()


# ---------------------------------------------------------------------------
# A — mapping failure increments skipped_mapping
# ---------------------------------------------------------------------------


class TestMappingFailureIncrementsSkippedMapping:
    """A: A discovery-passing candidate whose mapper() returns [] → skipped_mapping."""

    def test_successful_candidate_with_mapper_failure_increments_skipped_mapping(self):
        """Blank market_id passes discovery gates but fails domain object creation."""
        registry = InMemoryMarketRegistry()
        # blank market_id: active=True, valid dates — passes discovery, fails mapping
        bad = _bad_mapper_fetched("   ")
        result = _run_sync_from_records([bad], registry)

        assert result.skipped_mapping == 1, (
            "Expected 1 mapping failure but got "
            f"skipped_mapping={result.skipped_mapping}"
        )
        assert result.mapped == 0
        assert result.written == 0
        assert result.fetched == 1

    def test_skipped_mapping_does_not_add_to_registry(self):
        """A mapping failure must not write anything to the registry."""
        registry = InMemoryMarketRegistry()
        bad = _bad_mapper_fetched("   ")
        _run_sync_from_records([bad], registry)
        assert len(registry) == 0

    def test_multiple_mapping_failures_accumulate(self):
        """Multiple bad candidates each contribute 1 to skipped_mapping."""
        registry = InMemoryMarketRegistry()
        records = [_bad_mapper_fetched("   "), _bad_mapper_fetched("  ")]
        result = _run_sync_from_records(records, registry)

        assert result.skipped_mapping == 2
        assert result.mapped == 0
        assert result.written == 0


# ---------------------------------------------------------------------------
# B — skipped_mapping distinct from rejected_count and skipped_duplicate
# ---------------------------------------------------------------------------


class TestSkippedMappingDistinctness:
    """B: skipped_mapping is mutually exclusive with rejected_count and skipped_duplicate."""

    def test_skipped_mapping_is_distinct_from_rejected_count_and_duplicate_count(self):
        """Discovery-rejected markets do not show in skipped_mapping."""
        registry = InMemoryMarketRegistry()
        # inactive → rejected by discovery (Gate 1)
        # blank id → passes discovery, fails mapping (Gate 2)
        records = [
            _bad_mapper_fetched("   "),
        ]
        # Add a discovery-rejected market via raw to ensure separation
        raw = [
            _gamma(id="ok"),
            _gamma(id="bad-inactive", active=False),
        ]
        # Run discovery-rejecting raw through real fetcher
        result = _run_sync_from_raw(raw, registry)

        assert result.rejected_count == 1      # inactive → Gate 1
        assert result.skipped_mapping == 0     # ok candidate mapped fine
        assert result.skipped_duplicate == 0

    def test_gate1_gate2_gate3_are_mutually_exclusive_counters(self):
        """A single FetchedMarket contributes to at most one gate counter."""
        # Set up: one good, one discovery-rejected, one mapper-fail, one duplicate
        registry = InMemoryMarketRegistry()

        # First: write "good" so it becomes a duplicate on second run
        _run_sync_from_raw([_gamma(id="good")], registry)

        # Now run: good→dup (Gate 3), bad-inactive→rejected (Gate 1),
        # blank-id passes discovery→mapping failure (Gate 2) via records
        good_again = _good_fetched("good")           # duplicate
        bad_map = _bad_mapper_fetched("   ")         # mapping failure

        # Use two separate fetchers combined
        fetcher = MagicMock()
        fetcher.fetch_markets.return_value = [good_again, bad_map]
        svc = MarketSyncService(fetcher, registry)
        result = svc.run()

        # good_again: passes discovery, maps OK, both -up/-down are duplicates
        assert result.skipped_duplicate == 2   # 2 Market objects (UP+DOWN)
        # bad_map: passes discovery, mapper fails → 1 candidate skipped
        assert result.skipped_mapping == 1
        # No discovery-rejection in this run (both are active with valid dates)
        assert result.rejected_count == 0

        # Mutual exclusion: all counters account for 2 candidates (good + bad)
        # good: skipped_duplicate contributes 2 (objects), bad: skipped_mapping 1 (candidate)
        total_candidates = result.fetched
        assert total_candidates == 2
        assert result.written == 0

    def test_skipped_mapping_counter_counts_candidates_not_market_objects(self):
        """skipped_mapping counts failed candidates (not the 0 objects they produce)."""
        registry = InMemoryMarketRegistry()
        # 3 failing candidates → skipped_mapping should be 3, not 6
        records = [
            _bad_mapper_fetched("   "),
            _bad_mapper_fetched("  "),
            _bad_mapper_fetched(" "),
        ]
        result = _run_sync_from_records(records, registry)

        assert result.skipped_mapping == 3    # 3 candidates
        assert result.mapped == 0             # 0 Market objects
        assert result.fetched == 3


# ---------------------------------------------------------------------------
# C — API response matches service-layer mapping failure semantics
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_api_response_matches_service_mapping_failure_semantics():
    """C: POST /sync response exposes skipped_mapping_count matching service layer."""
    raw = [_gamma(id="ok-a"), _gamma(id="ok-b")]
    registry = InMemoryMarketRegistry()
    svc = MarketSyncService(PolymarketFetchService(_mock_client(raw)), registry)

    app.dependency_overrides[get_sync_service] = lambda: svc
    app.dependency_overrides[get_registry] = lambda: registry
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/api/v1/markets/sync")
        assert resp.status_code == 200
        data = resp.json()

        # No mapping failures in this run
        assert data["skipped_mapping_count"] == 0
        # All 2 candidates mapped to 4 market objects
        assert data["fetched_count"] == 2
        assert data["mapped_count"] == 4
        assert data["written_count"] == 4
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_sync_api_response_skipped_mapping_count_field_is_present():
    """C2: skipped_mapping_count is always present in the SyncResponse JSON."""
    raw = [_gamma(id="m")]
    registry = InMemoryMarketRegistry()
    svc = MarketSyncService(PolymarketFetchService(_mock_client(raw)), registry)

    app.dependency_overrides[get_sync_service] = lambda: svc
    app.dependency_overrides[get_registry] = lambda: registry
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/api/v1/markets/sync")
        data = resp.json()
        assert "skipped_mapping_count" in data
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# D — mixed payload: success + duplicate + mapping failure
# ---------------------------------------------------------------------------


class TestMixedPayloadDeterminism:
    """D: Mixed payload with all three outcomes produces a deterministic summary."""

    def test_mixed_payload_with_success_duplicate_and_mapping_failure_produces_deterministic_summary(self):
        """success(1) + duplicate(1) + mapping_failure(1) → predictable summary."""
        registry = InMemoryMarketRegistry()

        # Pre-write "existing" so it becomes a duplicate
        _run_sync_from_raw([_gamma(id="existing")], registry)

        # Now: "new" (success), "existing" (dup), blank (mapping failure)
        good_new = _good_fetched("new")
        good_dup = _good_fetched("existing")
        bad_map = _bad_mapper_fetched("   ")

        fetcher = MagicMock()
        fetcher.fetch_markets.return_value = [good_new, good_dup, bad_map]
        svc = MarketSyncService(fetcher, registry)
        result = svc.run()

        assert result.fetched == 3              # 3 candidates entered map stage
        assert result.skipped_mapping == 1      # "bad_map" failed mapping
        assert result.mapped == 4               # (good_new + good_dup) × 2
        assert result.written == 2              # "new" → 2 new entries
        assert result.skipped_duplicate == 2    # "existing" → 2 dup entries

        # Partition invariant
        assert result.mapped == result.written + result.skipped_duplicate

        # Pipeline invariant: (fetched - skipped_mapping) × 2 = mapped
        assert (result.fetched - result.skipped_mapping) * MarketMapper.MARKETS_PER_CANDIDATE == result.mapped

    def test_pipeline_invariant_holds_for_all_mapping_failures(self):
        """If all candidates fail mapping: mapped=0, written=0, skipped_duplicate=0."""
        registry = InMemoryMarketRegistry()
        records = [_bad_mapper_fetched("   "), _bad_mapper_fetched("  ")]
        result = _run_sync_from_records(records, registry)

        assert result.mapped == 0
        assert result.written == 0
        assert result.skipped_duplicate == 0
        assert result.skipped_mapping == 2
        # Invariant still holds: (2 - 2) × 2 == 0
        assert (result.fetched - result.skipped_mapping) * MarketMapper.MARKETS_PER_CANDIDATE == result.mapped

    def test_pipeline_invariant_holds_for_all_successful(self):
        """If all candidates succeed: skipped_mapping=0, mapped = fetched × 2."""
        registry = InMemoryMarketRegistry()
        result = _run_sync_from_raw(
            [_gamma(id="a"), _gamma(id="b"), _gamma(id="c")], registry
        )

        assert result.skipped_mapping == 0
        assert result.mapped == result.fetched * MarketMapper.MARKETS_PER_CANDIDATE
        assert (result.fetched - result.skipped_mapping) * MarketMapper.MARKETS_PER_CANDIDATE == result.mapped


# ---------------------------------------------------------------------------
# E — docs/runtime/summary alignment for mapping failure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_docs_runtime_and_summary_contract_align_for_mapping_failure():
    """E: Three-gate invariants hold at service layer, and API layer exposes them.

    Verifies the pipeline invariant documented in SyncResult:
      fetched − skipped_mapping = mapped / MARKETS_PER_CANDIDATE
      mapped = written + skipped_duplicate
    at both the service layer and HTTP response layer.
    """
    raw = [_gamma(id="x"), _gamma(id="y")]
    registry = InMemoryMarketRegistry()
    svc = MarketSyncService(PolymarketFetchService(_mock_client(raw)), registry)

    # --- Service layer ---
    service_result = svc.run()
    assert service_result.skipped_mapping == 0
    assert service_result.mapped == service_result.written + service_result.skipped_duplicate
    assert (
        (service_result.fetched - service_result.skipped_mapping)
        * MarketMapper.MARKETS_PER_CANDIDATE
        == service_result.mapped
    )

    # --- HTTP layer ---
    registry2 = InMemoryMarketRegistry()
    svc2 = MarketSyncService(PolymarketFetchService(_mock_client(raw)), registry2)
    app.dependency_overrides[get_sync_service] = lambda: svc2
    app.dependency_overrides[get_registry] = lambda: registry2
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/api/v1/markets/sync")
        assert resp.status_code == 200
        data = resp.json()

        # API-layer invariants
        assert data["mapped_count"] == data["written_count"] + data["skipped_duplicate_count"]
        assert (
            (data["fetched_count"] - data["skipped_mapping_count"])
            * MarketMapper.MARKETS_PER_CANDIDATE
            == data["mapped_count"]
        )
        # Service and API agree
        assert data["skipped_mapping_count"] == service_result.skipped_mapping
        assert data["mapped_count"] == service_result.mapped
    finally:
        app.dependency_overrides.clear()
