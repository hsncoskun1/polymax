"""Integration tests — Sync / Registry Behavior Lock (v0.5.6).

Locks five contracts about how discovery candidates flow into the registry
after DiscoveryService has evaluated the fetch layer output.

  C1 — Only discovery candidates enter the registry.
       Rejected markets (any rejection reason) must never appear in the store.

  C2 — Same market synced twice does not create a duplicate entry.
       The registry's add-only path raises DuplicateMarketError on the second
       attempt; MarketSyncService catches it and counts it as skipped_duplicate.

  C3 — Registry write semantics are deterministic: first-write-wins, add-only.
       Re-syncing a market with changed field values preserves the original
       registry entry.  No field-update path exists in the current
       implementation.

  C4 — Invalid / rejected markets can never reach the registry regardless of
       the mixture of valid and invalid markets in the payload.

  C5 — Mixed payload registry state after a single sync is deterministic and
       matches expected content exactly (correct IDs, count, and structure).

Scenario G — Previously-valid market becomes invalid on a later sync:
       The original registry entry is preserved unchanged.  MarketSyncService
       has no removal or deactivation logic; the registry is append-only.

The ONLY thing mocked is PolymarketClient.get_markets() — the actual
network boundary.  Every other component runs its real code.
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.api.deps import get_registry, get_sync_service
from backend.app.domain.market.models import MarketStatus
from backend.app.domain.market.registry import InMemoryMarketRegistry
from backend.app.domain.market.types import Side, Timeframe
from backend.app.main import app
from backend.app.services.market_fetcher import PolymarketFetchService
from backend.app.services.market_sync import MarketSyncService


# ---------------------------------------------------------------------------
# Gamma API payload factory — duplicated here for test-file isolation
# ---------------------------------------------------------------------------

_START = "2024-01-01T00:00:00Z"
_VALID_END = "2024-01-01T00:05:00Z"   # 300 s after _START — valid 5m window


def _gamma(**overrides) -> dict:
    """Return a minimal Gamma API market dict that satisfies all discovery rules."""
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


def _sync(raw_markets: list[dict], registry: InMemoryMarketRegistry | None = None):
    """Run a full sync pipeline against raw_markets and return (service, registry, result)."""
    reg = registry or InMemoryMarketRegistry()
    svc = MarketSyncService(PolymarketFetchService(_mock_client(raw_markets)), reg)
    result = svc.run()
    return svc, reg, result


# ---------------------------------------------------------------------------
# C1 — Only discovery candidates enter the registry
# ---------------------------------------------------------------------------


class TestSyncRegistryContractC1:
    """C1: Only markets that pass DiscoveryService evaluation are written to the registry.

    Any market rejected for any reason must leave the registry unchanged.
    """

    def test_sync_adds_new_valid_candidate_to_registry(self):
        """A single valid 5m market produces UP + DOWN entries in the registry.

        Verifies:
        - Registry gains exactly 2 entries (one UP, one DOWN).
        - Both keys follow the {market_id}-{side} format.
        - SyncResult.written == 2.
        """
        _, registry, result = _sync([_gamma(id="m-1")])

        ids = {m.id for m in registry.list_all()}
        assert ids == {"m-1-up", "m-1-down"}
        assert result.written == 2
        assert result.fetched == 1     # 1 discovery candidate

    def test_registry_key_format_is_market_id_hyphen_side(self):
        """Registry keys are always '{market_id}-up' and '{market_id}-down'.

        This locks the key contract that all downstream lookups depend on.
        """
        _, registry, _ = _sync([_gamma(id="btc-market")])

        all_ids = {m.id for m in registry.list_all()}
        assert "btc-market-up" in all_ids
        assert "btc-market-down" in all_ids

    def test_registry_market_fields_are_populated_correctly(self):
        """Core domain fields on written Market objects match the source payload.

        Locked fields:
        - side: UP / DOWN
        - timeframe: M5 (POLYMAX only supports M5)
        - status: ACTIVE (default on creation)
        - source_timestamp: event start time from Gamma startDate
        - end_date: event close time from Gamma endDate
        - event_id: from events[0].id
        """
        raw = _gamma(
            id="m-field-check",
            startDate="2024-06-15T12:00:00Z",
            endDate="2024-06-15T12:05:00Z",
            events=[{"id": "evt-field"}],
        )
        _, registry, _ = _sync([raw])

        by_id = {m.id: m for m in registry.list_all()}
        up = by_id["m-field-check-up"]
        down = by_id["m-field-check-down"]

        assert up.side == Side.UP
        assert down.side == Side.DOWN
        assert up.timeframe == Timeframe.M5
        assert up.status == MarketStatus.ACTIVE
        assert up.source_timestamp == datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        assert up.end_date == datetime(2024, 6, 15, 12, 5, 0, tzinfo=timezone.utc)
        assert up.event_id == "evt-field"
        assert down.event_id == "evt-field"


# ---------------------------------------------------------------------------
# C2 — Same market synced twice does not create a duplicate
# ---------------------------------------------------------------------------


class TestSyncRegistryContractC2:
    """C2: Syncing the same valid market a second time does not create a duplicate.

    InMemoryMarketRegistry.add() raises DuplicateMarketError for existing keys.
    MarketSyncService catches the error and increments skipped_duplicate.
    """

    def test_sync_repeated_same_market_does_not_create_duplicate(self):
        """Two sync runs with the same valid market leave exactly 2 registry entries.

        After the first run:  2 entries (up + down)
        After the second run: still 2 entries — duplicate skipped silently.
        """
        svc = MarketSyncService(
            PolymarketFetchService(_mock_client([_gamma(id="m-dup")])),
            InMemoryMarketRegistry(),
        )
        first = svc.run()
        second = svc.run()

        registry = svc._registry
        assert len(registry) == 2
        assert first.written == 2
        assert second.written == 0
        assert second.skipped_duplicate == 2

    def test_sync_result_counts_skipped_duplicates_correctly(self):
        """SyncResult.skipped_duplicate reflects the exact number of skipped entries.

        Two valid candidates × 2 sides = 4 existing entries on resync.
        """
        raw_markets = [_gamma(id="m-a"), _gamma(id="m-b")]
        registry = InMemoryMarketRegistry()
        svc = MarketSyncService(
            PolymarketFetchService(_mock_client(raw_markets)), registry
        )
        svc.run()           # first run writes 4 entries
        result = svc.run()  # second run: all 4 already exist

        assert result.written == 0
        assert result.skipped_duplicate == 4
        assert len(registry) == 4    # count unchanged


# ---------------------------------------------------------------------------
# C3 — Add-only semantics: first-write-wins, no field update on re-sync
# ---------------------------------------------------------------------------


class TestSyncRegistryContractC3:
    """C3: MarketSyncService.run() is add-only — re-syncing preserves original fields.

    When a market with the same ID returns on a subsequent sync with different
    field values (e.g., different question or slug), the registry entry that
    was created on the first sync is never modified.  The second attempt raises
    DuplicateMarketError and is counted as skipped_duplicate.

    This is the real documented behavior: first-write-wins, no update path.
    """

    def test_sync_second_pass_same_market_preserves_original_fields_no_update(self):
        """Re-syncing a market with changed content keeps the original registry entry.

        First sync:  m-stable with question="Will SOL hit 200?", slug="sol-200"
        Second sync: m-stable with question="Will DOGE hit 1?",  slug="doge-1"

        Expected: registry still contains the SOL market; DOGE is never written.
        Proves:   registry is add-only — no field-update path in sync.
        """
        registry = InMemoryMarketRegistry()

        # First sync — SOL market
        svc_v1 = MarketSyncService(
            PolymarketFetchService(_mock_client([
                _gamma(id="m-stable", question="Will SOL hit 200?", slug="sol-200"),
            ])),
            registry,
        )
        svc_v1.run()

        # Capture original registry entry
        original_up = registry.get("m-stable-up")
        original_symbol = original_up.symbol

        # Second sync — same market_id but different content
        svc_v2 = MarketSyncService(
            PolymarketFetchService(_mock_client([
                _gamma(id="m-stable", question="Will DOGE hit 1?", slug="doge-1"),
            ])),
            registry,
        )
        result_v2 = svc_v2.run()

        # Registry entry must be unchanged from first sync
        unchanged_up = registry.get("m-stable-up")
        assert unchanged_up.symbol == original_symbol   # first-write-wins
        assert result_v2.written == 0
        assert result_v2.skipped_duplicate == 2


# ---------------------------------------------------------------------------
# C4 — Invalid / rejected markets never reach the registry
# ---------------------------------------------------------------------------


class TestSyncRegistryContractC4:
    """C4: Every rejection reason prevents the market from entering the registry.

    Tests one rejection reason at a time to confirm the guard holds for
    each of the five DiscoveryService rules.
    """

    def test_sync_does_not_add_inactive_active_false(self):
        _, registry, result = _sync([_gamma(id="bad", active=False)])
        assert len(registry) == 0
        assert result.written == 0

    def test_sync_does_not_add_inactive_closed_true(self):
        _, registry, result = _sync([_gamma(id="bad", closed=True)])
        assert len(registry) == 0
        assert result.written == 0

    def test_sync_does_not_add_no_order_book(self):
        _, registry, result = _sync([_gamma(id="bad", enableOrderBook=False)])
        assert len(registry) == 0
        assert result.written == 0

    def test_sync_does_not_add_empty_tokens(self):
        _, registry, result = _sync([_gamma(id="bad", tokens=[])])
        assert len(registry) == 0
        assert result.written == 0

    def test_sync_does_not_add_missing_dates(self):
        raw = _gamma(id="bad")
        del raw["startDate"]
        _, registry, result = _sync([raw])
        assert len(registry) == 0
        assert result.written == 0

    def test_sync_does_not_add_duration_out_of_range(self):
        _, registry, result = _sync([
            _gamma(id="bad", endDate="2024-01-01T01:00:00Z")  # 3600 s → out of range
        ])
        assert len(registry) == 0
        assert result.written == 0


# ---------------------------------------------------------------------------
# C5 — Mixed payload registry state is deterministic
# ---------------------------------------------------------------------------


class TestSyncRegistryContractC5:
    """C5: A mixed payload produces a deterministic, predictable registry state.

    Tests the full interaction of valid + existing + invalid markets in a
    single sync run, and verifies the final registry state is exactly correct.
    """

    def test_sync_mixed_payload_results_in_expected_registry_state(self):
        """Mixed payload: new + pre-existing + invalid + duplicate.

        Payload:
          m-new      — valid, not yet in registry       → written (×2)
          m-existing — valid, already in registry        → skipped_duplicate (×2)
          m-inactive — inactive                          → rejected, not written
          m-no-ob    — enableOrderBook=False             → rejected, not written

        Pre-condition: registry contains m-existing (from a previous sync).
        Post-condition: registry contains exactly m-new + m-existing (4 entries total).
        """
        registry = InMemoryMarketRegistry()

        # Pre-populate registry with m-existing
        MarketSyncService(
            PolymarketFetchService(_mock_client([_gamma(id="m-existing")])),
            registry,
        ).run()
        assert len(registry) == 2   # sanity check pre-condition

        # Run mixed-payload sync
        raw_markets = [
            _gamma(id="m-new"),
            _gamma(id="m-existing"),
            _gamma(id="m-inactive", active=False),
            _gamma(id="m-no-ob", enableOrderBook=False),
        ]
        _, _, result = _sync(raw_markets, registry)

        # Final registry state must be exactly {m-new, m-existing} × {up, down}
        final_ids = {m.id for m in registry.list_all()}
        assert final_ids == {"m-new-up", "m-new-down", "m-existing-up", "m-existing-down"}
        assert len(registry) == 4

        # SyncResult must accurately reflect what happened
        assert result.fetched == 2         # 2 discovery candidates (m-new + m-existing)
        assert result.written == 2         # only m-new entries were new
        assert result.skipped_duplicate == 2   # m-existing entries already existed

    def test_sync_multiple_valid_candidates_all_written(self):
        """Three valid candidates produce six registry entries (3 × UP + DOWN).

        Verifies: all candidates are processed, no candidate is silently dropped.
        """
        raw_markets = [_gamma(id=f"m-{i}") for i in range(3)]
        _, registry, result = _sync(raw_markets)

        expected_ids = {f"m-{i}-{side}" for i in range(3) for side in ("up", "down")}
        assert {m.id for m in registry.list_all()} == expected_ids
        assert result.fetched == 3
        assert result.written == 6

    def test_sync_all_invalid_payload_leaves_registry_empty(self):
        """If every market is rejected, the registry must remain empty."""
        raw_markets = [
            _gamma(id="a", active=False),
            _gamma(id="b", enableOrderBook=False),
            _gamma(id="c", tokens=[]),
        ]
        _, registry, result = _sync(raw_markets)

        assert len(registry) == 0
        assert result.written == 0
        assert result.fetched == 0


# ---------------------------------------------------------------------------
# Scenario G — Previously-valid market becomes invalid (current behavior)
# ---------------------------------------------------------------------------


class TestPreviouslyValidMarketBecomingInvalid:
    """G: Documents the current behavior when a market transitions from valid to invalid.

    MarketSyncService has no removal or deactivation logic.  A market that
    was accepted and written on a previous sync stays in the registry
    unchanged even after it is rejected on all subsequent syncs.

    This is the documented real behavior.  A future "stale market cleanup"
    feature would change this contract and require updating these tests.
    """

    def test_market_stays_in_registry_after_becoming_inactive(self):
        """Market synced as valid stays in registry after active=False on resync.

        First sync:   m-flip with active=True  → written (accepted)
        Second sync:  m-flip with active=False  → rejected (INACTIVE), not removed
        """
        registry = InMemoryMarketRegistry()

        # First sync — market is valid
        MarketSyncService(
            PolymarketFetchService(_mock_client([_gamma(id="m-flip")])),
            registry,
        ).run()
        assert len(registry) == 2   # m-flip-up + m-flip-down written

        # Second sync — same market is now inactive
        result = MarketSyncService(
            PolymarketFetchService(_mock_client([_gamma(id="m-flip", active=False)])),
            registry,
        ).run()

        # Registry still holds the original entries — no automatic removal
        assert len(registry) == 2
        assert "m-flip-up" in {m.id for m in registry.list_all()}
        assert result.fetched == 0     # no candidates from second sync
        assert result.written == 0

    def test_market_stays_in_registry_after_losing_order_book(self):
        """Market synced as valid stays in registry after enableOrderBook=False."""
        registry = InMemoryMarketRegistry()

        MarketSyncService(
            PolymarketFetchService(_mock_client([_gamma(id="m-ob")])),
            registry,
        ).run()

        # Market loses order book on next sync
        MarketSyncService(
            PolymarketFetchService(_mock_client([_gamma(id="m-ob", enableOrderBook=False)])),
            registry,
        ).run()

        # Original entries remain
        assert len(registry) == 2
        assert {m.id for m in registry.list_all()} == {"m-ob-up", "m-ob-down"}


# ---------------------------------------------------------------------------
# API contract — POST /sync response summary matches registry final state
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_endpoint_response_summary_matches_registry_final_state():
    """POST /sync response summary must be consistent with the actual registry state.

    Payload: 2 valid candidates + 1 inactive.
    Expected:
      - response.fetched_count == 2  (discovery candidates)
      - response.written_count == 4  (2 candidates × UP + DOWN)
      - registry contains exactly 4 entries matching the 2 valid candidates
    """
    registry = InMemoryMarketRegistry()
    raw_markets = [
        _gamma(id="m-1"),
        _gamma(id="m-2"),
        _gamma(id="bad-inactive", active=False),
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

        # API summary must match SyncResult values
        assert data["fetched_count"] == 2
        assert data["written_count"] == 4
        assert data["skipped_duplicate_count"] == 0

        # Registry state must match what the API reported
        assert len(registry) == 4
        assert {m.id for m in registry.list_all()} == {
            "m-1-up", "m-1-down", "m-2-up", "m-2-down",
        }
    finally:
        app.dependency_overrides.clear()
