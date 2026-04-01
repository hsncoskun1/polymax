"""Integration tests — Sync Summary Semantics Lock (v0.5.8).

These tests lock the documented semantics of SyncResult and SyncResponse:
the summary describes the **processing window** of a single sync call, not
the full state of the registry.

Locked semantics
----------------
  `fetched`          — discovery CANDIDATES processed (not raw API fetch count).
                       Discovery-rejected markets are invisible here.
  `written`          — new registry entries added in this call only.
  `skipped_duplicate`— candidates that already existed (DuplicateMarketError).
  `registry_total`   — TOTAL registry entries after sync, including stale ones.

What the summary does NOT tell you (locked as documented gap):
  - Raw count of markets fetched from Polymarket API.
  - Count of markets rejected by DiscoveryService.
  - Count of stale/retained entries accumulated across prior syncs.

Tests:
  A  test_sync_summary_describes_processing_window_not_full_registry_state
  B  test_sync_summary_remains_honest_when_registry_contains_stale_entries
  C  test_sync_summary_counts_new_existing_rejected_candidates_deterministically
  D  test_sync_api_response_matches_service_summary_semantics
  E  test_sync_summary_exposes_registry_totals_without_hiding_retained_state

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


# ---------------------------------------------------------------------------
# A — Summary describes processing window, not full registry state
# ---------------------------------------------------------------------------


class TestSyncSummaryProcessingWindow:
    """A: SyncResult fields reflect only what happened in this sync call.

    Specifically:
    - fetched = discovery candidates (not raw API fetch count)
    - written = entries added THIS call (not cumulative total)
    - registry_total = absolute registry size (includes prior entries)
    """

    def test_sync_summary_describes_processing_window_not_full_registry_state(self):
        """fetched/written are call-scoped; registry_total shows full registry.

        Setup:
          Pre-populated registry: 2 entries (m-existing × up + down)
          Sync payload: m-existing (duplicate) + m-new (new candidate)
                        + m-invalid (rejected by discovery)

        Expected summary:
          fetched          = 2   (m-existing + m-new passed discovery; m-invalid did not)
          written          = 2   (only m-new is new)
          skipped_duplicate = 2  (m-existing already in registry)
          registry_total   = 4   (2 old + 2 new = full registry size)

        Proves: fetched ≠ "markets fetched from API" (m-invalid not counted)
                written ≠ "total registry size" (registry_total tells that)
        """
        registry = InMemoryMarketRegistry()
        _run([_gamma(id="m-existing")], registry)   # pre-populate

        result = _run(
            [
                _gamma(id="m-existing"),             # still valid — already in registry
                _gamma(id="m-new"),                  # new valid candidate
                _gamma(id="m-invalid", active=False),  # rejected by discovery
            ],
            registry,
        )

        assert result.fetched == 2           # m-existing + m-new (not m-invalid)
        assert result.written == 2           # m-new-up + m-new-down
        assert result.skipped_duplicate == 2  # m-existing already present
        assert result.registry_total == 4    # full registry: m-existing + m-new

    def test_fetched_count_excludes_discovery_rejected_markets(self):
        """fetched is NOT the raw API fetch count — rejected markets invisible.

        4 markets sent to fetch layer; 3 rejected by discovery; 1 candidate.
        fetched must equal 1 (candidates only), not 4 (raw fetch count).
        """
        registry = InMemoryMarketRegistry()
        result = _run(
            [
                _gamma(id="ok"),
                _gamma(id="no-ob", enableOrderBook=False),
                _gamma(id="inactive", active=False),
                _gamma(id="no-tok", tokens=[]),
            ],
            registry,
        )

        assert result.fetched == 1        # only "ok" passed discovery
        assert result.written == 2        # ok-up + ok-down
        assert result.registry_total == 2

    def test_written_count_is_call_scoped_not_cumulative(self):
        """written reflects only this call; registry_total reflects total accumulation.

        First sync: writes 2. Second sync: writes 2 more.
        Each SyncResult.written == 2, but registry_total grows: 2 → 4.
        """
        registry = InMemoryMarketRegistry()

        r1 = _run([_gamma(id="m-1")], registry)
        assert r1.written == 2
        assert r1.registry_total == 2

        r2 = _run([_gamma(id="m-2")], registry)
        assert r2.written == 2
        assert r2.registry_total == 4    # cumulative


# ---------------------------------------------------------------------------
# B — Summary remains honest when registry contains stale entries
# ---------------------------------------------------------------------------


class TestSyncSummaryHonestWithStaleEntries:
    """B: When stale entries exist, summary fields must not misrepresent the situation.

    The documented gap: summary does NOT tell you about stale entries.
    But what it DOES say must be accurate and not accidentally misleading.
    """

    def test_sync_summary_remains_honest_when_registry_contains_stale_entries(self):
        """Stale entries in registry must not inflate fetched/written counts.

        Setup:
          First sync: m-stale written when valid
          Second sync: m-stale now invalid; m-new is the only valid candidate

        Expected second sync summary:
          fetched          = 1   (only m-new; m-stale rejected by discovery)
          written          = 2   (m-new only)
          skipped_duplicate = 0  (m-stale never reached registry.add())
          registry_total   = 4   (2 stale + 2 new — HONEST about full size)
        """
        registry = InMemoryMarketRegistry()
        _run([_gamma(id="m-stale")], registry)

        result = _run(
            [_gamma(id="m-stale", active=False), _gamma(id="m-new")],
            registry,
        )

        assert result.fetched == 1           # only m-new passed discovery
        assert result.written == 2
        assert result.skipped_duplicate == 0  # m-stale was rejected, not just skipped
        assert result.registry_total == 4    # 2 stale + 2 new (honest total)

    def test_registry_total_grows_with_stale_entries_across_multiple_syncs(self):
        """registry_total accurately tracks accumulation of retained stale entries.

        Three syncs where previous markets become invalid but stay in registry.
        registry_total must reflect the true accumulated size.
        """
        registry = InMemoryMarketRegistry()

        r1 = _run([_gamma(id="m-a")], registry)
        assert r1.registry_total == 2

        # m-a becomes invalid; m-b is new
        r2 = _run([_gamma(id="m-a", active=False), _gamma(id="m-b")], registry)
        assert r2.written == 2
        assert r2.registry_total == 4    # m-a retained + m-b added

        # m-b becomes invalid; m-c is new
        r3 = _run([_gamma(id="m-b", active=False), _gamma(id="m-c")], registry)
        assert r3.written == 2
        assert r3.registry_total == 6    # m-a + m-b retained + m-c added


# ---------------------------------------------------------------------------
# C — Summary counts are deterministic under mixed payload
# ---------------------------------------------------------------------------


class TestSyncSummaryDeterministicCounts:
    """C: All summary fields produce deterministic counts for any payload mix."""

    def test_sync_summary_counts_new_existing_rejected_candidates_deterministically(self):
        """Mixed payload: new + existing-valid + existing-stale + rejected.

        Pre-populate: m-valid (still valid), m-stale (will become invalid)
        Sync payload: m-valid (still valid), m-stale (now invalid), m-brand-new, m-rejected

        Expected:
          fetched          = 2   (m-valid + m-brand-new passed discovery)
          written          = 2   (m-brand-new only)
          skipped_duplicate = 2  (m-valid already in registry)
          registry_total   = 6   (m-valid×2 + m-stale×2 retained + m-brand-new×2)
        """
        registry = InMemoryMarketRegistry()
        _run([_gamma(id="m-valid"), _gamma(id="m-stale")], registry)

        result = _run(
            [
                _gamma(id="m-valid"),                    # still valid, already in registry
                _gamma(id="m-stale", active=False),      # now invalid (retained stale)
                _gamma(id="m-brand-new"),                # new valid candidate
                _gamma(id="m-rejected", tokens=[]),      # rejected by discovery
            ],
            registry,
        )

        assert result.fetched == 2
        assert result.written == 2
        assert result.skipped_duplicate == 2
        assert result.skipped_mapping == 0
        assert result.registry_total == 6

    def test_all_invalid_payload_summary_zeroes_except_registry_total(self):
        """All-invalid payload: fetched=0, written=0, registry_total shows prior entries."""
        registry = InMemoryMarketRegistry()
        _run([_gamma(id="m-prior")], registry)   # pre-populate 2 entries

        result = _run(
            [_gamma(id="a", active=False), _gamma(id="b", tokens=[])],
            registry,
        )

        assert result.fetched == 0
        assert result.written == 0
        assert result.skipped_duplicate == 0
        assert result.registry_total == 2    # prior entries still there

    def test_fresh_registry_first_sync_summary(self):
        """First sync on empty registry: written == registry_total."""
        registry = InMemoryMarketRegistry()
        result = _run([_gamma(id="m-1"), _gamma(id="m-2")], registry)

        assert result.fetched == 2
        assert result.written == 4
        assert result.skipped_duplicate == 0
        assert result.registry_total == 4    # written == registry_total for fresh registry


# ---------------------------------------------------------------------------
# D — API response matches service summary semantics
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_api_response_matches_service_summary_semantics():
    """D: SyncResponse field values match SyncResult values exactly.

    Verifies that the HTTP layer doesn't lose or transform any summary field,
    including the new registry_total_count.
    """
    registry = InMemoryMarketRegistry()
    # Pre-populate to make registry_total interesting
    MarketSyncService(
        PolymarketFetchService(_mock_client([_gamma(id="m-prior")])), registry
    ).run()

    raw_markets = [
        _gamma(id="m-prior"),           # duplicate
        _gamma(id="m-new"),             # new valid
        _gamma(id="m-bad", active=False),  # rejected
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

        # fetched = candidates (m-prior + m-new), not raw API count (3)
        assert data["fetched_count"] == 2
        assert data["written_count"] == 2           # m-new only
        assert data["skipped_duplicate_count"] == 2  # m-prior already present
        assert data["registry_total_count"] == 4    # m-prior (2) + m-new (2)
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# E — registry_total exposes full registry without hiding retained state
# ---------------------------------------------------------------------------


class TestSyncSummaryRegistryTotal:
    """E: registry_total gives honest registry size, including retained stale entries.

    This test class locks the contract that registry_total is the authoritative
    count of ALL entries in the registry after sync — not just the ones written
    in this call.
    """

    def test_sync_summary_exposes_registry_totals_without_hiding_retained_state(self):
        """registry_total includes stale entries — operator sees full registry size.

        Pattern: each sync adds 2 new entries while previous become stale.
        After 3 syncs: 6 entries in registry (all retained, none removed).
        registry_total must equal 6, not just 2 (this sync's written).
        """
        registry = InMemoryMarketRegistry()

        r1 = _run([_gamma(id="gen-1")], registry)
        assert r1.written == 2 and r1.registry_total == 2

        r2 = _run([_gamma(id="gen-1", active=False), _gamma(id="gen-2")], registry)
        assert r2.written == 2 and r2.registry_total == 4

        r3 = _run([_gamma(id="gen-2", active=False), _gamma(id="gen-3")], registry)
        assert r3.written == 2 and r3.registry_total == 6

    def test_registry_total_equals_written_on_perfectly_fresh_registry(self):
        """First-ever sync: registry_total == written (no prior state to retain)."""
        registry = InMemoryMarketRegistry()
        result = _run([_gamma(id="fresh")], registry)
        assert result.written == result.registry_total

    def test_registry_total_stable_when_all_rejected(self):
        """All-rejected sync: registry_total unchanged from prior state."""
        registry = InMemoryMarketRegistry()
        _run([_gamma(id="m-1"), _gamma(id="m-2")], registry)  # write 4 entries

        result = _run([_gamma(id="bad", active=False)], registry)
        assert result.written == 0
        assert result.registry_total == 4    # unchanged
