"""Integration tests — Registry Lifecycle Semantics Lock (v0.5.7).

These tests lock the current *add-only / retained* lifecycle model of the
registry and make the deferred-lifecycle decision explicit and test-verified.

Registry lifecycle decision (documented in market_sync.py):
  - Once written, a market entry is NEVER automatically removed, deactivated,
    or archived by MarketSyncService.
  - If a previously-valid market becomes invalid on a later sync, its registry
    entry remains ACTIVE and unchanged.
  - MarketSyncService has no "previous state vs. new candidate set" comparison.
  - Lifecycle infrastructure EXISTS (MarketStatus.INACTIVE/ARCHIVED,
    registry.deactivate(), registry.archive()) but is not driven by sync.
  - This is a deliberate deferred decision, not an oversight.

Tests locked here:
  A  test_registry_entry_lifecycle_when_market_becomes_invalid_after_initial_add
     — entry status stays ACTIVE after market becomes invalid for any reason

  B  test_closed_market_registry_behavior_after_initial_registration
     — closed=True on re-sync: entry retained, status unchanged

  C  test_inactive_market_registry_behavior_after_initial_registration
     — active=False on re-sync: entry retained, status unchanged, ACTIVE

  D  test_sync_summary_matches_registry_lifecycle_behavior
     — SyncResult counts only new candidates; retained/stale entries are
       invisible to the summary (documents the known gap)

  E  test_mixed_payload_with_existing_and_now_invalid_markets_produces_deterministic_registry_state
     — mixed payload with lifecycle transitions: final state is deterministic
       and includes both retained stale entries and new candidates

The ONLY thing mocked is PolymarketClient.get_markets().  All other
components run their real code.
"""
from __future__ import annotations

from unittest.mock import MagicMock

from backend.app.domain.market.models import MarketStatus
from backend.app.domain.market.registry import InMemoryMarketRegistry
from backend.app.services.market_fetcher import PolymarketFetchService
from backend.app.services.market_sync import MarketSyncService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_START = "2024-01-01T00:00:00Z"
_VALID_END = "2024-01-01T00:05:00Z"


def _gamma(**overrides) -> dict:
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


def _mock_client(raw_markets: list[dict]) -> MagicMock:
    client = MagicMock()
    client.get_markets.return_value = raw_markets
    return client


def _run(raw_markets: list[dict], registry: InMemoryMarketRegistry):
    """Run one full sync cycle against raw_markets using the given registry."""
    svc = MarketSyncService(
        PolymarketFetchService(_mock_client(raw_markets)), registry
    )
    return svc.run()


def _initial_sync(market_id: str, registry: InMemoryMarketRegistry):
    """Pre-populate registry with one valid market (UP + DOWN)."""
    _run([_gamma(id=market_id)], registry)
    assert len(registry) == 2, "pre-condition: 2 entries expected after initial sync"


# ---------------------------------------------------------------------------
# A — Registry entry lifecycle when market becomes invalid after initial add
# ---------------------------------------------------------------------------


class TestRegistryLifecycleBehaviorA:
    """A: Entry status stays ACTIVE regardless of why the market becomes invalid.

    Tests each rejection reason independently.  The registry entry that was
    created when the market was valid must remain ACTIVE on all subsequent
    syncs that reject the same market_id.

    This is the explicit contract for the current add-only / retained model.
    """

    def _assert_entry_retained_and_active(
        self, market_id: str, registry: InMemoryMarketRegistry
    ):
        entries = registry.list_all()
        ids = {m.id for m in entries}
        assert f"{market_id}-up" in ids, f"expected {market_id}-up to be retained"
        assert f"{market_id}-down" in ids, f"expected {market_id}-down to be retained"
        for entry in entries:
            if entry.id.startswith(market_id):
                assert entry.status == MarketStatus.ACTIVE, (
                    f"expected ACTIVE status but got {entry.status} for {entry.id}"
                )

    def test_registry_entry_lifecycle_when_market_becomes_inactive(self):
        """active=False: previously-written entry stays ACTIVE in registry."""
        registry = InMemoryMarketRegistry()
        _initial_sync("m-A", registry)

        _run([_gamma(id="m-A", active=False)], registry)

        self._assert_entry_retained_and_active("m-A", registry)

    def test_registry_entry_lifecycle_when_market_loses_order_book(self):
        """enableOrderBook=False: previously-written entry stays ACTIVE."""
        registry = InMemoryMarketRegistry()
        _initial_sync("m-A", registry)

        _run([_gamma(id="m-A", enableOrderBook=False)], registry)

        self._assert_entry_retained_and_active("m-A", registry)

    def test_registry_entry_lifecycle_when_market_loses_tokens(self):
        """tokens=[]: previously-written entry stays ACTIVE."""
        registry = InMemoryMarketRegistry()
        _initial_sync("m-A", registry)

        _run([_gamma(id="m-A", tokens=[])], registry)

        self._assert_entry_retained_and_active("m-A", registry)

    def test_registry_entry_lifecycle_when_market_duration_becomes_invalid(self):
        """Duration out of range (3600s): previously-written entry stays ACTIVE."""
        registry = InMemoryMarketRegistry()
        _initial_sync("m-A", registry)

        _run([_gamma(id="m-A", endDate="2024-01-01T01:00:00Z")], registry)

        self._assert_entry_retained_and_active("m-A", registry)

    def test_registry_entry_lifecycle_when_market_no_longer_present_in_payload(self):
        """Market absent from next payload: previously-written entry stays ACTIVE.

        When a market simply disappears from the Polymarket API response,
        it is not discovered at all — it does not reach discovery, and it
        certainly does not trigger any registry transition.
        """
        registry = InMemoryMarketRegistry()
        _initial_sync("m-A", registry)

        # Second sync: completely different market — m-A absent
        _run([_gamma(id="m-other")], registry)

        # m-A entries must still be present and ACTIVE
        self._assert_entry_retained_and_active("m-A", registry)


# ---------------------------------------------------------------------------
# B — Closed market registry behavior after initial registration
# ---------------------------------------------------------------------------


class TestRegistryLifecycleBehaviorB:
    """B: closed=True on re-sync leaves the registry entry unchanged.

    'closed' is a terminal market state on Polymarket.  The INACTIVE rejection
    rule catches it (active=False OR closed=True).  The registry entry written
    when the market was open stays ACTIVE with all original field values.
    """

    def test_closed_market_registry_behavior_after_initial_registration(self):
        """Market transitions to closed=True: registry entry retained, status ACTIVE."""
        registry = InMemoryMarketRegistry()
        _initial_sync("m-B", registry)

        # Market closes on next sync
        _run([_gamma(id="m-B", closed=True)], registry)

        assert len(registry) == 2
        up = registry.get("m-B-up")
        assert up.status == MarketStatus.ACTIVE

    def test_closed_and_inactive_combined_registry_entry_retained(self):
        """active=False AND closed=True: most conservative rejection, entry still retained."""
        registry = InMemoryMarketRegistry()
        _initial_sync("m-B2", registry)

        _run([_gamma(id="m-B2", active=False, closed=True)], registry)

        assert len(registry) == 2
        assert registry.get("m-B2-up").status == MarketStatus.ACTIVE


# ---------------------------------------------------------------------------
# C — Inactive market registry behavior after initial registration
# ---------------------------------------------------------------------------


class TestRegistryLifecycleBehaviorC:
    """C: active=False on re-sync leaves the registry entry unchanged.

    Complements B.  Explicitly verifies:
    - Registry count unchanged
    - Entry status is still MarketStatus.ACTIVE (not INACTIVE)
    - Entry field values are original (first-write-wins, no update)
    """

    def test_inactive_market_registry_behavior_after_initial_registration(self):
        """active=False: registry entry status stays ACTIVE — no automatic deactivation."""
        registry = InMemoryMarketRegistry()
        _initial_sync("m-C", registry)

        result = _run([_gamma(id="m-C", active=False)], registry)

        assert len(registry) == 2
        up = registry.get("m-C-up")
        assert up.status == MarketStatus.ACTIVE    # not INACTIVE
        # Sync found 0 candidates — m-C was rejected
        assert result.fetched == 0
        assert result.written == 0


# ---------------------------------------------------------------------------
# D — Sync summary matches registry lifecycle behavior
# ---------------------------------------------------------------------------


class TestRegistryLifecycleSummaryD:
    """D: SyncResult counts only new candidates — retained/stale entries are invisible.

    This is a documented gap in the current sync summary.  The SyncResult
    does not track:
      - how many registry entries are stale / no longer candidates
      - how many entries were retained from a previous sync

    Only new candidates that pass discovery are counted.  Previously-written
    markets that are now invalid are rejected by DiscoveryService before
    reaching the map→write stage — they are neither counted as 'fetched' nor
    as 'skipped_duplicate'.
    """

    def test_sync_summary_matches_registry_lifecycle_behavior(self):
        """SyncResult accurately reflects new candidates only; stale entries invisible.

        Setup:
          - First sync: m-stale added (2 entries written)
          - Second sync: m-stale invalid, m-new valid

        Expected SyncResult (second sync):
          fetched          = 1   (only m-new as discovery candidate)
          written          = 2   (m-new-up + m-new-down)
          skipped_duplicate = 0  (m-stale was rejected, never reached add())

        Expected registry after second sync:
          4 entries total — m-stale (retained) + m-new (new)
        """
        registry = InMemoryMarketRegistry()

        # First sync: m-stale is valid
        _run([_gamma(id="m-stale")], registry)
        assert len(registry) == 2

        # Second sync: m-stale becomes invalid, m-new is fresh
        result = _run(
            [
                _gamma(id="m-stale", active=False),   # now invalid
                _gamma(id="m-new"),                    # new valid candidate
            ],
            registry,
        )

        # Summary only reflects new activity, not retained entries
        assert result.fetched == 1              # only m-new passed discovery
        assert result.written == 2              # m-new-up + m-new-down
        assert result.skipped_duplicate == 0    # m-stale never reached registry.add()
        assert result.skipped_mapping == 0

        # Registry has both stale and new entries
        assert len(registry) == 4
        all_ids = {m.id for m in registry.list_all()}
        assert "m-stale-up" in all_ids       # retained from first sync
        assert "m-stale-down" in all_ids     # retained from first sync
        assert "m-new-up" in all_ids         # added in second sync
        assert "m-new-down" in all_ids       # added in second sync

    def test_stale_entry_not_counted_in_skipped_duplicate_when_rejected_by_discovery(self):
        """A stale entry (invalid on re-sync) is rejected before reaching registry.add().

        Key distinction:
          - 'skipped_duplicate' counts markets that PASSED discovery but already
            existed in the registry.
          - A market that is REJECTED by discovery never reaches registry.add()
            at all — it is not counted in skipped_duplicate.

        This means skipped_duplicate does NOT tell you how many stale entries
        the registry holds.  It only counts valid-but-already-present markets.
        """
        registry = InMemoryMarketRegistry()
        _run([_gamma(id="m-stale")], registry)

        # Re-sync: m-stale now invalid (different from "still valid but already present")
        result = _run([_gamma(id="m-stale", active=False)], registry)

        assert result.skipped_duplicate == 0   # NOT counted here — rejected by discovery
        assert result.fetched == 0             # 0 candidates passed discovery


# ---------------------------------------------------------------------------
# E — Mixed payload with lifecycle transitions: deterministic registry state
# ---------------------------------------------------------------------------


class TestRegistryLifecycleMixedPayloadE:
    """E: Mixed payload containing lifecycle transitions yields deterministic registry state.

    Scenario:
      Pre-populate: m-a (valid), m-b (valid) → 4 registry entries
      Sync payload: m-a (now invalid), m-b (still valid), m-c (new valid)

    Expected registry after sync:
      m-a-up, m-a-down  — retained (stale, status=ACTIVE)
      m-b-up, m-b-down  — retained (still valid but already present, skipped_duplicate)
      m-c-up, m-c-down  — newly written
      Total: 6 entries

    Expected SyncResult:
      fetched          = 2  (m-b + m-c passed discovery)
      written          = 2  (m-c-up + m-c-down)
      skipped_duplicate = 2  (m-b-up + m-b-down already present)
      (m-a's stale status NOT in summary)
    """

    def test_mixed_payload_with_existing_and_now_invalid_markets_produces_deterministic_registry_state(self):
        """Final registry state is deterministic with lifecycle transitions in payload."""
        registry = InMemoryMarketRegistry()

        # Pre-populate m-a and m-b
        _run([_gamma(id="m-a"), _gamma(id="m-b")], registry)
        assert len(registry) == 4

        # Mixed sync: m-a invalid, m-b still valid, m-c new
        result = _run(
            [
                _gamma(id="m-a", active=False),   # now invalid — retained but stale
                _gamma(id="m-b"),                  # still valid — skipped as duplicate
                _gamma(id="m-c"),                  # new valid — written
            ],
            registry,
        )

        # Registry: 6 entries (m-a retained + m-b retained + m-c new)
        assert len(registry) == 6
        final_ids = {m.id for m in registry.list_all()}
        assert final_ids == {
            "m-a-up", "m-a-down",    # stale but retained
            "m-b-up", "m-b-down",    # still valid, already present
            "m-c-up", "m-c-down",    # newly written
        }

        # SyncResult: only m-b and m-c were candidates
        assert result.fetched == 2
        assert result.written == 2            # m-c only
        assert result.skipped_duplicate == 2  # m-b already in registry

        # Stale entries (m-a) remain ACTIVE — no automatic status transition
        assert registry.get("m-a-up").status == MarketStatus.ACTIVE
        assert registry.get("m-a-down").status == MarketStatus.ACTIVE
