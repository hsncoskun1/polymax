"""Integration tests — Cross-Layer Field Semantics Lock (v0.5.12).

These tests lock the contract that field names and semantics are consistent
across service layer, API response layer, and documentation.

Locked contracts
----------------
  DISCOVER FIELD MAP    — DiscoveryResult fields map to DiscoveryResponse
                          fields with consistent semantics.
  SYNC FIELD MAP        — SyncResult fields map to SyncResponse fields with
                          consistent semantics (short names → _count suffix).
  RAW/CANDIDATE/REJECTED — The three-way partition relationship is named and
                           exposed consistently at both endpoints.
  REGISTRY vs WINDOW    — registry_total_count is semantically distinct from
                          processing-window fields (fetched_count, written_count).
  DOCS/RUNTIME ALIGNMENT — SyncResponse and DiscoveryResponse field sets match
                           documented expectations.

Tests:
  A  test_cross_layer_field_semantics_map_is_consistent_for_discover
  B  test_cross_layer_field_semantics_map_is_consistent_for_sync
  C  test_raw_candidate_rejected_relationships_are_named_and_exposed_consistently
  D  test_registry_related_fields_are_semantically_distinct_from_processing_window_fields
  E  test_documented_field_semantics_match_runtime_contract

The ONLY thing mocked is PolymarketClient.get_markets().
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.api.deps import get_discovery_service, get_registry, get_sync_service
from backend.app.domain.market.registry import InMemoryMarketRegistry
from backend.app.main import app
from backend.app.services.market_discovery import DiscoveryService, RejectionReason
from backend.app.services.market_fetcher import PolymarketFetchService
from backend.app.services.market_sync import MarketSyncService, SyncResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_START = "2024-01-01T00:00:00Z"
_VALID_END = "2024-01-01T00:05:00Z"


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


async def _call_discover(raw_markets: list[dict]) -> dict:
    fetcher = PolymarketFetchService(_mock_client(raw_markets))
    discovery = DiscoveryService()
    app.dependency_overrides[get_discovery_service] = lambda: (fetcher, discovery)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/api/v1/markets/discover")
        assert resp.status_code == 200
        return resp.json()
    finally:
        app.dependency_overrides.pop(get_discovery_service, None)


async def _call_sync(raw_markets: list[dict], registry: InMemoryMarketRegistry) -> dict:
    svc = MarketSyncService(PolymarketFetchService(_mock_client(raw_markets)), registry)
    app.dependency_overrides[get_sync_service] = lambda: svc
    app.dependency_overrides[get_registry] = lambda: registry
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/api/v1/markets/sync")
        assert resp.status_code == 200
        return resp.json()
    finally:
        app.dependency_overrides.pop(get_sync_service, None)
        app.dependency_overrides.pop(get_registry, None)


# ---------------------------------------------------------------------------
# A — discover cross-layer field semantics
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cross_layer_field_semantics_map_is_consistent_for_discover():
    """A: /discover API fields carry the correct semantics documented in DiscoveryResult.

    DiscoveryResult → DiscoveryResponse mapping:
      fetched_count   = total raw input evaluated
      candidate_count = markets that passed all rules
      rejected_count  = markets that failed at least one rule
      rejection_breakdown = per-reason string-keyed dict, all 5 keys present
    """
    raw = [
        _gamma(id="ok-1"),
        _gamma(id="ok-2"),
        _gamma(id="bad-inactive", active=False),
    ]

    data = await _call_discover(raw)

    # fetched_count = total raw input
    assert data["fetched_count"] == 3

    # candidate_count = passed rules
    assert data["candidate_count"] == 2

    # rejected_count = failed rules
    assert data["rejected_count"] == 1

    # invariant: fetched = candidate + rejected
    assert data["fetched_count"] == data["candidate_count"] + data["rejected_count"]

    # rejection_breakdown has canonical 5 keys
    expected_keys = {r.value for r in RejectionReason}
    assert set(data["rejection_breakdown"].keys()) == expected_keys
    assert data["rejection_breakdown"]["inactive"] == 1


@pytest.mark.asyncio
async def test_discover_response_has_exactly_the_documented_field_set():
    """A2: DiscoveryResponse JSON keys match the documented field set exactly."""
    data = await _call_discover([_gamma(id="ok")])

    expected_fields = {"fetched_count", "candidate_count", "rejected_count", "rejection_breakdown"}
    assert set(data.keys()) == expected_fields


# ---------------------------------------------------------------------------
# B — sync cross-layer field semantics
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cross_layer_field_semantics_map_is_consistent_for_sync():
    """B: /sync API fields carry the correct semantics documented in SyncResult.

    SyncResult → SyncResponse name mapping (short → _count suffix):
      fetched          → fetched_count     (candidates, not raw input)
      mapped           → mapped_count      (domain Markets created)
      written          → written_count     (new registry entries)
      skipped_mapping  → skipped_mapping_count
      skipped_duplicate→ skipped_duplicate_count
      registry_total   → registry_total_count   (ALL entries after sync)
      rejected_count   → rejected_count    (same name)
      rejection_breakdown → rejection_breakdown  (same name)
    """
    raw = [
        _gamma(id="ok-1"),
        _gamma(id="ok-2"),
        _gamma(id="bad", active=False),
    ]
    registry = InMemoryMarketRegistry()
    data = await _call_sync(raw, registry)

    # fetched_count = candidates only (not raw input)
    assert data["fetched_count"] == 2

    # mapped_count = domain markets created = written + skipped_duplicate
    assert data["mapped_count"] == data["written_count"] + data["skipped_duplicate_count"]

    # written_count = new entries added
    assert data["written_count"] == 4  # 2 candidates × 2 sides

    # registry_total_count = full registry size
    assert data["registry_total_count"] == 4

    # rejected_count = rejected by discovery
    assert data["rejected_count"] == 1

    # rejection_breakdown has canonical 5 keys
    expected_keys = {r.value for r in RejectionReason}
    assert set(data["rejection_breakdown"].keys()) == expected_keys


@pytest.mark.asyncio
async def test_sync_response_has_exactly_the_documented_field_set():
    """B2: SyncResponse JSON keys match the documented field set exactly."""
    data = await _call_sync([_gamma(id="ok")], InMemoryMarketRegistry())

    expected_fields = {
        "fetched_count", "mapped_count", "written_count",
        "skipped_mapping_count", "skipped_duplicate_count",
        "registry_total_count", "rejected_count", "rejection_breakdown",
    }
    assert set(data.keys()) == expected_fields


@pytest.mark.asyncio
async def test_sync_result_to_response_field_name_mapping_is_complete():
    """B3: SyncResult service fields all appear in SyncResponse with _count suffix convention.

    SyncResult short names → SyncResponse _count names.
    Verifies no field is silently dropped in the HTTP layer.
    """
    registry = InMemoryMarketRegistry()
    svc = MarketSyncService(PolymarketFetchService(_mock_client([_gamma(id="m")])), registry)

    service_result: SyncResult = svc.run()
    app.dependency_overrides[get_sync_service] = lambda: svc
    app.dependency_overrides[get_registry] = lambda: registry

    # Re-run via API with fresh registry to get HTTP response
    registry2 = InMemoryMarketRegistry()
    svc2 = MarketSyncService(PolymarketFetchService(_mock_client([_gamma(id="m")])), registry2)
    app.dependency_overrides[get_sync_service] = lambda: svc2
    app.dependency_overrides[get_registry] = lambda: registry2
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/api/v1/markets/sync")
        data = resp.json()

        # Verify the name mapping contract documented in SyncResult docstring
        assert data["fetched_count"] == service_result.fetched
        assert data["mapped_count"] == service_result.mapped
        assert data["written_count"] == service_result.written
        assert data["skipped_mapping_count"] == service_result.skipped_mapping
        assert data["skipped_duplicate_count"] == service_result.skipped_duplicate
        assert data["registry_total_count"] == service_result.registry_total
        assert data["rejected_count"] == service_result.rejected_count
        assert data["rejection_breakdown"] == service_result.rejection_breakdown
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# C — raw/candidate/rejected partition naming
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_raw_candidate_rejected_relationships_are_named_and_exposed_consistently():
    """C: raw/candidate/rejected partition is consistently named at both endpoints.

    The three-way relationship:
      /discover: fetched_count = candidate_count + rejected_count (total input)
      /sync:     (fetched_count + rejected_count) = discover.fetched_count

    Both endpoints expose rejected_count with the same name and same meaning.
    """
    raw = [
        _gamma(id="ok"),
        _gamma(id="bad-a", active=False),
        _gamma(id="bad-b", tokens=[]),
    ]

    discover_data = await _call_discover(raw)
    sync_data = await _call_sync(raw, InMemoryMarketRegistry())

    # Discover: total = candidates + rejected
    assert (
        discover_data["candidate_count"] + discover_data["rejected_count"]
        == discover_data["fetched_count"]
    )

    # Sync: candidates + rejected = discover total (same concept, different field names)
    assert (
        sync_data["fetched_count"] + sync_data["rejected_count"]
        == discover_data["fetched_count"]
    )

    # rejected_count is the same field name in both endpoints and carries same value
    assert discover_data["rejected_count"] == sync_data["rejected_count"] == 2


# ---------------------------------------------------------------------------
# D — registry_total_count vs processing-window fields
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_registry_related_fields_are_semantically_distinct_from_processing_window_fields():
    """D: registry_total_count is semantically distinct from processing-window fields.

    Processing-window fields (fetched_count, written_count, etc.) describe
    what happened IN THIS sync call.  registry_total_count describes the
    ABSOLUTE state of the registry AFTER this call, including all prior entries.

    This test verifies: registry_total_count >= written_count (always)
    and that registry_total_count accumulates across syncs while
    written_count reflects only the current call.
    """
    raw_a = [_gamma(id="a")]
    raw_b = [_gamma(id="b")]

    registry = InMemoryMarketRegistry()
    data_a = await _call_sync(raw_a, registry)

    assert data_a["written_count"] == 2
    assert data_a["registry_total_count"] == 2

    data_b = await _call_sync(raw_b, registry)

    # written_count reflects only this call
    assert data_b["written_count"] == 2

    # registry_total_count is cumulative (not reset)
    assert data_b["registry_total_count"] == 4
    assert data_b["registry_total_count"] > data_b["written_count"]


@pytest.mark.asyncio
async def test_registry_total_count_is_not_confused_with_fetched_count():
    """D2: registry_total_count and fetched_count are distinct concepts.

    After a sync where some candidates are rejected:
    - fetched_count = candidates processed in this call
    - registry_total_count = all entries ever written

    They must not be equal when stale entries exist.
    """
    # First sync: write 2 entries
    registry = InMemoryMarketRegistry()
    raw_first = [_gamma(id="prior")]
    await _call_sync(raw_first, registry)

    # Second sync: 1 candidate, but registry still has 2 from before + 2 new = 4
    raw_second = [_gamma(id="new"), _gamma(id="bad", active=False)]
    data = await _call_sync(raw_second, registry)

    assert data["fetched_count"] == 1        # only "new" passed discovery
    assert data["registry_total_count"] == 4  # prior 2 + new 2


# ---------------------------------------------------------------------------
# E — documented field semantics match runtime
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_documented_field_semantics_match_runtime_contract():
    """E: The complete field semantic contract is verified at runtime.

    This is the canonical contract verification test.  It checks that every
    documented relationship between fields holds at runtime, ensuring docs
    and code stay in sync.
    """
    raw = [
        _gamma(id="ok-a"),
        _gamma(id="ok-b"),
        _gamma(id="bad", active=False),
    ]
    registry = InMemoryMarketRegistry()
    sync_data = await _call_sync(raw, registry)
    discover_data = await _call_discover(raw)

    # --- Discover field semantics ---
    # fetched = candidate + rejected (total input partition)
    assert (
        discover_data["candidate_count"] + discover_data["rejected_count"]
        == discover_data["fetched_count"]
    )

    # --- Sync field semantics ---
    # mapped = written + skipped_duplicate (successful mapping outcomes)
    # Note: mapped counts domain Market objects (2 per candidate: UP+DOWN),
    # not candidates.  So mapped != fetched.
    assert (
        sync_data["written_count"] + sync_data["skipped_duplicate_count"]
        == sync_data["mapped_count"]
    )
    # registry_total >= written (always; includes prior entries)
    assert sync_data["registry_total_count"] >= sync_data["written_count"]

    # --- Cross-layer semantics ---
    # discover.candidate_count == sync.fetched_count (same payload)
    assert discover_data["candidate_count"] == sync_data["fetched_count"]
    # rejected_count same in both
    assert discover_data["rejected_count"] == sync_data["rejected_count"]
