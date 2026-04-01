"""Integration tests — Discover/Sync Contract Alignment Lock (v0.5.11).

These tests lock the contract that /discover and /sync share the same
discovery basis and expose rejection taxonomy consistently, while their
intentional semantic differences are explicit and documented.

Locked contracts
----------------
  SHARED DISCOVERY BASIS    — Both endpoints invoke the same DiscoveryService
                              logic and produce consistent candidate/rejection
                              counts for identical payloads.
  CANDIDATE ALIGNMENT       — discover.candidate_count == sync.fetched_count
                              for the same raw input.
  SHARED TAXONOMY           — Both endpoints use the same canonical rejection
                              taxonomy (RejectionReason enum values, 5 keys,
                              zero-count policy).
  INTENTIONAL DIFFERENCES   — /discover gives discovery view (raw input context);
                              /sync gives processing + registry view (candidates
                              only context).  fetched_count means different things
                              in each — this is by design, not drift.

Tests:
  A  test_discover_and_sync_expose_same_candidate_count_for_same_payload
  B  test_discover_and_sync_use_same_rejection_taxonomy_and_zero_count_policy
  C  test_discover_and_sync_differ_only_where_their_semantics_intentionally_differ
  D  test_discover_and_sync_api_contracts_remain_operator_consistent_under_mixed_payload
  E  test_contract_alignment_does_not_change_registry_or_candidate_behavior

The ONLY thing mocked is PolymarketClient.get_markets().
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.api.deps import get_discovery_service, get_registry, get_sync_service
from backend.app.domain.market.registry import InMemoryMarketRegistry
from backend.app.main import app
from backend.app.services.market_discovery import RejectionReason
from backend.app.services.market_fetcher import PolymarketFetchService
from backend.app.services.market_sync import MarketSyncService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_START = "2024-01-01T00:00:00Z"
_VALID_END = "2024-01-01T00:05:00Z"
_CANONICAL_KEYS = {r.value for r in RejectionReason}


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
    """Call POST /discover with mocked data, return JSON response."""
    from backend.app.services.market_discovery import DiscoveryService

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
    """Call POST /sync with mocked data, return JSON response."""
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
# A — candidate count alignment
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_discover_and_sync_expose_same_candidate_count_for_same_payload():
    """A: discover.candidate_count == sync.fetched_count for identical raw input.

    Both endpoints share the same DiscoveryService evaluation.  The number of
    markets that passed discovery must be identical regardless of which endpoint
    is called.

    Contract: discover.candidate_count == sync.fetched_count
    """
    raw = [
        _gamma(id="ok-1"),
        _gamma(id="ok-2"),
        _gamma(id="bad", active=False),
    ]

    discover_data = await _call_discover(raw)
    sync_data = await _call_sync(raw, InMemoryMarketRegistry())

    assert discover_data["candidate_count"] == sync_data["fetched_count"], (
        f"candidate alignment failed: discover.candidate_count="
        f"{discover_data['candidate_count']} != sync.fetched_count="
        f"{sync_data['fetched_count']}"
    )
    assert discover_data["candidate_count"] == 2


@pytest.mark.asyncio
async def test_discover_fetched_count_equals_sync_fetched_plus_rejected():
    """A2: discover.fetched_count == sync.fetched_count + sync.rejected_count.

    discover.fetched_count = total raw input
    sync.fetched_count     = candidates only
    The difference is exactly the rejected markets.
    """
    raw = [
        _gamma(id="ok"),
        _gamma(id="bad-inactive", active=False),
        _gamma(id="bad-no-ob", enableOrderBook=False),
    ]

    discover_data = await _call_discover(raw)
    sync_data = await _call_sync(raw, InMemoryMarketRegistry())

    assert (
        discover_data["fetched_count"]
        == sync_data["fetched_count"] + sync_data["rejected_count"]
    ), (
        f"payload split contract failed: discover.fetched_count="
        f"{discover_data['fetched_count']} != sync.fetched_count="
        f"{sync_data['fetched_count']} + sync.rejected_count="
        f"{sync_data['rejected_count']}"
    )
    assert discover_data["fetched_count"] == 3


@pytest.mark.asyncio
async def test_discover_rejected_count_equals_sync_rejected_count():
    """A3: discover.rejected_count == sync.rejected_count for same payload."""
    raw = [
        _gamma(id="ok"),
        _gamma(id="bad", active=False),
    ]

    discover_data = await _call_discover(raw)
    sync_data = await _call_sync(raw, InMemoryMarketRegistry())

    assert discover_data["rejected_count"] == sync_data["rejected_count"]
    assert discover_data["rejected_count"] == 1


# ---------------------------------------------------------------------------
# B — shared rejection taxonomy and zero-count policy
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_discover_and_sync_use_same_rejection_taxonomy_and_zero_count_policy():
    """B: Both endpoints expose identical taxonomy keys and zero-count policy.

    For any payload, rejection_breakdown keys must be the same canonical set
    in both /discover and /sync responses.
    """
    raw = [
        _gamma(id="ok"),
        _gamma(id="bad", active=False),
    ]

    discover_data = await _call_discover(raw)
    sync_data = await _call_sync(raw, InMemoryMarketRegistry())

    discover_keys = set(discover_data["rejection_breakdown"].keys())
    sync_keys = set(sync_data["rejection_breakdown"].keys())

    assert discover_keys == sync_keys == _CANONICAL_KEYS


@pytest.mark.asyncio
async def test_breakdown_values_match_between_endpoints_for_same_payload():
    """B2: rejection_breakdown values are equal in both endpoints for same payload.

    Same raw input → same rejection counts per reason.
    """
    raw = [
        _gamma(id="ok"),
        _gamma(id="inactive", active=False),
        _gamma(id="no-ob", enableOrderBook=False),
        _gamma(id="no-tok", tokens=[]),
    ]

    discover_data = await _call_discover(raw)
    sync_data = await _call_sync(raw, InMemoryMarketRegistry())

    assert discover_data["rejection_breakdown"] == sync_data["rejection_breakdown"]


@pytest.mark.asyncio
async def test_both_endpoints_present_zero_count_keys_when_no_rejections():
    """B3: Zero-count policy holds in both endpoints when payload is all-valid."""
    raw = [_gamma(id="ok")]

    discover_data = await _call_discover(raw)
    sync_data = await _call_sync(raw, InMemoryMarketRegistry())

    for key in _CANONICAL_KEYS:
        assert discover_data["rejection_breakdown"][key] == 0
        assert sync_data["rejection_breakdown"][key] == 0


# ---------------------------------------------------------------------------
# C — intentional differences are documented and stable
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_discover_and_sync_differ_only_where_their_semantics_intentionally_differ():
    """C: The only field where endpoints intentionally diverge is fetched_count.

    /discover: fetched_count = raw input (candidates + rejected)
    /sync:     fetched_count = candidates only

    All other rejection-related fields must agree.
    """
    raw = [
        _gamma(id="ok-a"),
        _gamma(id="ok-b"),
        _gamma(id="bad", active=False),
    ]

    discover_data = await _call_discover(raw)
    sync_data = await _call_sync(raw, InMemoryMarketRegistry())

    # Intentional difference: fetched_count semantics
    assert discover_data["fetched_count"] == 3  # raw input
    assert sync_data["fetched_count"] == 2       # candidates only

    # Consistent: rejected_count
    assert discover_data["rejected_count"] == sync_data["rejected_count"]

    # Consistent: rejection_breakdown
    assert discover_data["rejection_breakdown"] == sync_data["rejection_breakdown"]

    # Consistent: candidate_count == sync.fetched_count
    assert discover_data["candidate_count"] == sync_data["fetched_count"]


@pytest.mark.asyncio
async def test_fetched_count_semantic_difference_is_stable_across_payloads():
    """C2: fetched_count intentional difference holds for all-valid and all-invalid.

    All valid: discover.fetched_count == sync.fetched_count (no rejected)
    All invalid: discover.fetched_count > 0, sync.fetched_count == 0
    """
    # All valid
    raw_valid = [_gamma(id="a"), _gamma(id="b")]
    d_valid = await _call_discover(raw_valid)
    s_valid = await _call_sync(raw_valid, InMemoryMarketRegistry())
    assert d_valid["fetched_count"] == s_valid["fetched_count"] == 2

    # All invalid
    raw_invalid = [_gamma(id="x", active=False), _gamma(id="y", active=False)]
    d_invalid = await _call_discover(raw_invalid)
    s_invalid = await _call_sync(raw_invalid, InMemoryMarketRegistry())
    assert d_invalid["fetched_count"] == 2
    assert s_invalid["fetched_count"] == 0


# ---------------------------------------------------------------------------
# D — operator consistency under mixed payload
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_discover_and_sync_api_contracts_remain_operator_consistent_under_mixed_payload():
    """D: Mixed payload — operator sees consistent picture from both endpoints.

    An operator calling /discover then /sync on the same data should not see
    contradictory counts.  The relationships documented in DiscoveryResponse
    must hold.
    """
    raw = [
        _gamma(id="ok-1"),
        _gamma(id="ok-2"),
        _gamma(id="bad-inactive", active=False),
        _gamma(id="bad-no-ob", enableOrderBook=False),
        _gamma(id="bad-tokens", tokens=[]),
    ]

    discover_data = await _call_discover(raw)
    sync_data = await _call_sync(raw, InMemoryMarketRegistry())

    # Operator can derive: total = candidates + rejected
    assert (
        discover_data["candidate_count"] + discover_data["rejected_count"]
        == discover_data["fetched_count"]
    )

    # Operator can derive: sync partition
    assert (
        sync_data["fetched_count"] + sync_data["rejected_count"]
        == discover_data["fetched_count"]  # same as discover total
    )

    # No contradiction: candidate alignment
    assert discover_data["candidate_count"] == sync_data["fetched_count"] == 2
    assert discover_data["rejected_count"] == sync_data["rejected_count"] == 3


# ---------------------------------------------------------------------------
# E — alignment does not affect registry or candidate behavior
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_contract_alignment_does_not_change_registry_or_candidate_behavior():
    """E: Calling /discover has no side effects; /sync still writes only candidates.

    Contract alignment must not alter the functional behavior of either endpoint.
    """
    raw = [
        _gamma(id="ok"),
        _gamma(id="bad", active=False),
    ]
    registry = InMemoryMarketRegistry()

    # /discover must not write to registry
    await _call_discover(raw)
    assert len(registry) == 0, "/discover must not write to registry"

    # /sync writes only candidates
    await _call_sync(raw, registry)
    ids = {m.id for m in registry.list_all()}
    assert ids == {"ok-up", "ok-down"}
    assert "bad-up" not in ids
    assert "bad-down" not in ids
