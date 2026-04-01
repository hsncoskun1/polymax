"""Integration tests — Rejection Taxonomy Contract Lock (v0.5.10).

These tests lock the contract that the rejection taxonomy (RejectionReason enum)
is the single canonical source of truth for all rejection breakdown keys across
every layer: DiscoveryService → SyncResult → SyncResponse (API).

Locked contracts
----------------
  CANONICAL SOURCE    — RejectionReason enum is the single source of rejection
                        identifiers.  Its .value strings are the canonical keys
                        used everywhere (service layer, API layer, docs).
  SERIALIZATION POINT — DiscoveryResult.string_breakdown is the only place that
                        converts enum keys to string keys.  No caller may repeat
                        the r.value conversion.
  ZERO-COUNT POLICY   — All five reason keys are always present in every
                        breakdown dict (value may be 0).  Missing key is a
                        contract violation.
  DRIFT DETECTION     — If RejectionReason enum changes, these tests break
                        explicitly rather than allowing silent drift.

Tests:
  A  test_rejection_breakdown_keys_exactly_match_canonical_rejection_reason_set
  B  test_sync_result_and_api_response_use_same_rejection_taxonomy
  C  test_zero_count_rejection_reasons_follow_documented_contract
  D  test_rejection_taxonomy_contract_does_not_drift_when_reason_set_changes
  E  test_docs_and_runtime_contract_are_aligned_for_rejection_breakdown

The ONLY thing mocked is PolymarketClient.get_markets().
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.api.deps import get_registry, get_sync_service
from backend.app.domain.market.registry import InMemoryMarketRegistry
from backend.app.main import app
from backend.app.services.market_discovery import DiscoveryResult, DiscoveryService, RejectionReason
from backend.app.services.market_fetcher import PolymarketFetchService
from backend.app.services.market_sync import MarketSyncService


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


def _run_sync(raw_markets: list[dict], registry: InMemoryMarketRegistry):
    svc = MarketSyncService(PolymarketFetchService(_mock_client(raw_markets)), registry)
    return svc.run()


# The canonical key set — derived from RejectionReason enum at test time.
# If the enum changes, this derivation changes too, and tests that compare
# against hardcoded sets will break, surfacing the drift.
_CANONICAL_KEYS = {r.value for r in RejectionReason}
_CANONICAL_KEY_LIST = sorted(_CANONICAL_KEYS)


# ---------------------------------------------------------------------------
# A — breakdown keys exactly match canonical reason set
# ---------------------------------------------------------------------------


class TestBreakdownKeysMatchCanonicalSet:
    """A: Every breakdown dict returned at every layer must have exactly the
    canonical key set — no more, no less."""

    def test_rejection_breakdown_keys_exactly_match_canonical_rejection_reason_set(self):
        """SyncResult.rejection_breakdown keys == {r.value for r in RejectionReason}.

        This test is the primary drift guard: if a reason is added to the enum
        but not propagated, or a string is hardcoded incorrectly, it fails here.
        """
        registry = InMemoryMarketRegistry()
        result = _run_sync(
            [_gamma(id="ok"), _gamma(id="bad", active=False)],
            registry,
        )

        assert set(result.rejection_breakdown.keys()) == _CANONICAL_KEYS

    def test_discovery_result_string_breakdown_keys_match_canonical_set(self):
        """DiscoveryResult.string_breakdown keys == canonical enum values."""
        svc = DiscoveryService()
        from backend.app.services.market_fetcher import PolymarketFetchService
        fetcher = PolymarketFetchService(_mock_client([_gamma(id="m")]))
        markets = fetcher.fetch_markets()
        result = svc.evaluate(markets)

        assert set(result.string_breakdown.keys()) == _CANONICAL_KEYS

    def test_breakdown_contains_no_extra_keys_beyond_canonical(self):
        """breakdown must not contain keys outside the canonical set."""
        registry = InMemoryMarketRegistry()
        result = _run_sync([_gamma(id="ok")], registry)

        extra_keys = set(result.rejection_breakdown.keys()) - _CANONICAL_KEYS
        assert extra_keys == set(), f"Unexpected keys in breakdown: {extra_keys}"

    def test_breakdown_contains_no_missing_keys_from_canonical(self):
        """breakdown must not omit any canonical key."""
        registry = InMemoryMarketRegistry()
        result = _run_sync([_gamma(id="ok")], registry)

        missing_keys = _CANONICAL_KEYS - set(result.rejection_breakdown.keys())
        assert missing_keys == set(), f"Missing canonical keys in breakdown: {missing_keys}"


# ---------------------------------------------------------------------------
# B — SyncResult and API response use same taxonomy
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_result_and_api_response_use_same_rejection_taxonomy():
    """B: SyncResponse.rejection_breakdown keys == SyncResult.rejection_breakdown keys.

    Verifies that the HTTP layer does not transform, filter, or add keys
    relative to the service layer output.
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

    # Capture service-level result
    service_result = sync_svc.run()
    service_keys = set(service_result.rejection_breakdown.keys())

    # Re-create service with same input for API call
    registry2 = InMemoryMarketRegistry()
    sync_svc2 = MarketSyncService(
        PolymarketFetchService(_mock_client(raw_markets)), registry2
    )
    app.dependency_overrides[get_sync_service] = lambda: sync_svc2
    app.dependency_overrides[get_registry] = lambda: registry2
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/api/v1/markets/sync")
        assert resp.status_code == 200
        api_keys = set(resp.json()["rejection_breakdown"].keys())

        assert api_keys == service_keys == _CANONICAL_KEYS
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# C — zero-count policy is a locked contract
# ---------------------------------------------------------------------------


class TestZeroCountPolicy:
    """C: All canonical reason keys are always present, even when count is 0.

    This is a documented contract: callers may rely on key presence without
    KeyError guards.
    """

    def test_zero_count_rejection_reasons_follow_documented_contract(self):
        """All 5 reason keys present with value 0 when no rejections occur."""
        registry = InMemoryMarketRegistry()
        result = _run_sync([_gamma(id="ok")], registry)

        for key in _CANONICAL_KEYS:
            assert key in result.rejection_breakdown, f"Missing zero-count key: {key}"
            assert result.rejection_breakdown[key] == 0, (
                f"Expected 0 for {key!r}, got {result.rejection_breakdown[key]}"
            )

    def test_zero_count_policy_holds_for_empty_input(self):
        """Empty input: all keys present with value 0."""
        registry = InMemoryMarketRegistry()
        result = _run_sync([], registry)

        assert set(result.rejection_breakdown.keys()) == _CANONICAL_KEYS
        assert all(v == 0 for v in result.rejection_breakdown.values())

    def test_non_triggered_reasons_are_zero_not_absent(self):
        """Only 'inactive' triggered → other 4 keys present with value 0."""
        registry = InMemoryMarketRegistry()
        result = _run_sync([_gamma(id="bad", active=False)], registry)

        assert result.rejection_breakdown["inactive"] == 1
        other_keys = _CANONICAL_KEYS - {"inactive"}
        for key in other_keys:
            assert key in result.rejection_breakdown, f"Missing key: {key}"
            assert result.rejection_breakdown[key] == 0

    def test_string_breakdown_property_preserves_zero_count_policy(self):
        """DiscoveryResult.string_breakdown preserves zero-count for all keys."""
        svc = DiscoveryService()
        fetcher = PolymarketFetchService(_mock_client([_gamma(id="m")]))
        markets = fetcher.fetch_markets()
        result = svc.evaluate(markets)

        assert set(result.string_breakdown.keys()) == _CANONICAL_KEYS
        assert all(v == 0 for v in result.string_breakdown.values())


# ---------------------------------------------------------------------------
# D — taxonomy contract breaks explicitly when reason set changes
# ---------------------------------------------------------------------------


class TestTaxonomyDriftDetection:
    """D: If RejectionReason enum changes, these tests must fail loudly.

    This class does NOT assert that the enum has specific members — it asserts
    structural properties that would break if the enum drifted silently.
    """

    def test_rejection_taxonomy_contract_does_not_drift_when_reason_set_changes(self):
        """breakdown key count == len(RejectionReason).

        If a new reason is added to the enum, the breakdown must expose it.
        If a reason is removed, the breakdown must shrink accordingly.
        This test will fail if enum and breakdown fall out of sync.
        """
        registry = InMemoryMarketRegistry()
        result = _run_sync([], registry)

        expected_count = len(RejectionReason)
        actual_count = len(result.rejection_breakdown)
        assert actual_count == expected_count, (
            f"breakdown has {actual_count} keys but RejectionReason has "
            f"{expected_count} members — taxonomy has drifted"
        )

    def test_string_breakdown_count_matches_enum_member_count(self):
        """DiscoveryResult.string_breakdown count == len(RejectionReason).

        Direct check that the serialization property stays in sync.
        """
        svc = DiscoveryService()
        fetcher = PolymarketFetchService(_mock_client([]))
        markets = fetcher.fetch_markets()
        result = svc.evaluate(markets)

        assert len(result.string_breakdown) == len(RejectionReason)

    def test_all_enum_values_appear_as_breakdown_keys(self):
        """Every RejectionReason.value must appear as a breakdown key.

        Locks the contract: r.value → breakdown key is exhaustive and correct.
        If an enum member's value is changed, this test catches it.
        """
        registry = InMemoryMarketRegistry()
        result = _run_sync([], registry)

        for reason in RejectionReason:
            assert reason.value in result.rejection_breakdown, (
                f"RejectionReason.{reason.name}.value={reason.value!r} "
                f"not found in breakdown keys"
            )


# ---------------------------------------------------------------------------
# E — docs and runtime contract are aligned
# ---------------------------------------------------------------------------


class TestDocsRuntimeAlignment:
    """E: The runtime taxonomy matches the documented 5-key contract.

    These tests verify the specific key names documented in:
    - SyncResult docstring (market_sync.py)
    - SyncResponse docstring (api/markets.py)
    - discovery_regression_matrix.md (section 3.3)
    - README.md (v0.5.9 milestone)

    If a key name changes in the code, these tests will fail, prompting
    a documentation update.
    """

    def test_docs_and_runtime_contract_are_aligned_for_rejection_breakdown(self):
        """The five documented key names match the runtime keys exactly.

        Documented keys (from SyncResult docstring and regression matrix):
          inactive, no_order_book, empty_tokens, missing_dates,
          duration_out_of_range
        """
        documented_keys = {
            "inactive",
            "no_order_book",
            "empty_tokens",
            "missing_dates",
            "duration_out_of_range",
        }

        registry = InMemoryMarketRegistry()
        result = _run_sync([], registry)

        assert set(result.rejection_breakdown.keys()) == documented_keys, (
            "Runtime breakdown keys differ from documented contract. "
            "Update docs to match, or fix the runtime taxonomy."
        )

    def test_each_documented_key_maps_to_a_rejection_reason_enum_member(self):
        """Every documented key string is the .value of a RejectionReason member.

        This ensures docs describe the canonical enum, not a derived artifact.
        """
        documented_keys = {
            "inactive",
            "no_order_book",
            "empty_tokens",
            "missing_dates",
            "duration_out_of_range",
        }

        enum_values = {r.value for r in RejectionReason}
        assert documented_keys == enum_values, (
            "Mismatch between documented keys and RejectionReason enum values. "
            "Either the docs or the enum needs updating."
        )

    def test_rejection_reason_enum_values_are_snake_case_strings(self):
        """RejectionReason enum values are lowercase snake_case strings.

        Locks the value format — API consumers rely on these exact strings.
        """
        for reason in RejectionReason:
            value = reason.value
            assert isinstance(value, str), f"{reason.name}.value is not a string"
            assert value == value.lower(), f"{reason.name}.value is not lowercase: {value!r}"
            assert " " not in value, f"{reason.name}.value contains spaces: {value!r}"
