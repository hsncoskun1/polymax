"""Integration tests — Live Gamma Contract Snapshot Lock (v0.5.18).

These tests lock the contract between the committed Gamma API snapshot fixture
and the POLYMAX fetcher/discovery/sync pipeline.  All non-live tests use the
committed fixture (no network required).  Live tests are @pytest.mark.live
and are skipped by default — run with: pytest -m live

Fixture location: backend/tests/fixtures/gamma_snapshot.json

The fixture documents the expected Gamma API response shape.  If Gamma
changes their payload schema, the schema contract tests will surface the
drift.  The fixture contains 10 records covering:
  - 2 valid 5m candidates (BTC, ETH)
  - 5 rejection reasons (inactive, no_order_book, empty_tokens,
    missing_dates, duration_out_of_range)
  - 3 edge cases (enableOrderBook absent, events absent, closed=True)

Locked contracts
----------------
  FIXTURE-SHAPE    — The committed fixture has the expected Gamma API top-level
                     fields present in every record.
  FIXTURE-PIPELINE — Feeding the fixture through PolymarketFetchService produces
                     the expected FetchedMarket records (normalization correct).
  FIXTURE-DISCOVERY — DiscoveryService produces the expected candidate/rejection
                      counts from the fixture.
  FIXTURE-SYNC     — Full sync pipeline on the fixture produces a deterministic
                     summary (2 candidates → 4 written, 8 rejected).
  FIXTURE-CROSSLAYER — Cross-layer invariants hold for the fixture payload.
  LIVE-SHAPE       — (live, skipped by default) Real Gamma API response contains
                     all expected field keys in at least one market record.

Tests:
  A  TestFixtureSchemaContract
  B  TestFixturePipelineNormalization
  C  TestFixtureDiscoveryContract
  D  TestFixtureSyncContract
  E  TestFixtureCrossLayerInvariants
  F  test_live_gamma_api_response_shape_matches_expected_schema (live)
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from backend.app.domain.market.registry import InMemoryMarketRegistry
from backend.app.services.market_discovery import DiscoveryService, RejectionReason
from backend.app.services.market_fetcher import PolymarketFetchService
from backend.app.services.market_sync import MarketSyncService


# ---------------------------------------------------------------------------
# Fixture loading
# ---------------------------------------------------------------------------

_FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
_SNAPSHOT_PATH = _FIXTURES_DIR / "gamma_snapshot.json"

# Fields expected in every Gamma API market record
_EXPECTED_GAMMA_FIELDS = {
    "id", "question", "slug", "active", "closed",
    "enableOrderBook", "tokens", "startDate", "endDate",
}

# Optional fields (present in some records, absent in others by design)
_OPTIONAL_GAMMA_FIELDS = {"events"}

# All taxonomy keys
_ALL_TAXONOMY_KEYS = {r.value for r in RejectionReason}


def _load_snapshot() -> list[dict]:
    with open(_SNAPSHOT_PATH, encoding="utf-8") as f:
        return json.load(f)


def _make_svc(raw_markets: list[dict]) -> tuple[PolymarketFetchService, InMemoryMarketRegistry]:
    client = MagicMock()
    client.get_markets.return_value = raw_markets
    registry = InMemoryMarketRegistry()
    svc = MarketSyncService(PolymarketFetchService(client), registry)
    return svc, registry


# ---------------------------------------------------------------------------
# A — fixture schema contract
# ---------------------------------------------------------------------------


class TestFixtureSchemaContract:
    """A: The committed fixture has the expected Gamma API field shape."""

    def test_fixture_file_exists_and_is_valid_json(self):
        """gamma_snapshot.json exists and is parseable JSON."""
        assert _SNAPSHOT_PATH.exists(), f"Fixture missing at {_SNAPSHOT_PATH}"
        records = _load_snapshot()
        assert isinstance(records, list)
        assert len(records) > 0

    def test_fixture_contains_expected_number_of_records(self):
        """Fixture has exactly 10 records covering all expected scenarios."""
        records = _load_snapshot()
        assert len(records) == 10

    def test_each_fixture_record_has_id_field(self):
        """Every record has an 'id' field (required by fetcher)."""
        records = _load_snapshot()
        for rec in records:
            assert "id" in rec, f"Record missing 'id': {rec}"
            assert isinstance(rec["id"], str), f"id is not str: {rec['id']!r}"
            assert rec["id"].strip(), f"id is blank: {rec['id']!r}"

    def test_valid_candidate_records_have_all_expected_fields(self):
        """Records without _comment exclusions have all expected Gamma fields."""
        records = _load_snapshot()
        # The two valid candidates (index 0 and 1) should have all expected fields
        for i in [0, 1]:
            rec = records[i]
            for field in _EXPECTED_GAMMA_FIELDS:
                assert field in rec, (
                    f"Valid record {rec['id']} missing field: {field}"
                )

    def test_fixture_active_and_closed_are_booleans(self):
        """active and closed fields are proper JSON booleans (not strings)."""
        records = _load_snapshot()
        for rec in records:
            if "active" in rec:
                assert isinstance(rec["active"], bool), (
                    f"active is not bool in {rec['id']}: {rec['active']!r}"
                )
            if "closed" in rec:
                assert isinstance(rec["closed"], bool), (
                    f"closed is not bool in {rec['id']}: {rec['closed']!r}"
                )

    def test_fixture_tokens_are_lists_or_absent(self):
        """tokens field is a list (possibly empty) or absent."""
        records = _load_snapshot()
        for rec in records:
            if "tokens" in rec:
                assert isinstance(rec["tokens"], list), (
                    f"tokens is not list in {rec['id']}: {type(rec['tokens'])}"
                )

    def test_fixture_start_end_date_are_iso8601_strings(self):
        """startDate and endDate are ISO-8601 strings when present."""
        from datetime import datetime
        records = _load_snapshot()
        for rec in records:
            for field in ["startDate", "endDate"]:
                if field in rec:
                    val = rec[field]
                    assert isinstance(val, str), f"{field} not str in {rec['id']}"
                    # Must parse successfully
                    parsed = datetime.fromisoformat(val.replace("Z", "+00:00"))
                    assert parsed is not None


# ---------------------------------------------------------------------------
# B — fixture pipeline normalization
# ---------------------------------------------------------------------------


class TestFixturePipelineNormalization:
    """B: Feeding the fixture through PolymarketFetchService normalizes correctly."""

    def test_fixture_produces_expected_fetched_market_count(self):
        """Fixture → fetcher: 10 records → 10 FetchedMarkets (none skipped)."""
        records = _load_snapshot()
        client = MagicMock()
        client.get_markets.return_value = records
        svc = PolymarketFetchService(client)
        results = svc.fetch_markets()
        # All 10 records have valid (non-blank) ids → none skipped
        assert len(results) == 10

    def test_fixture_valid_records_normalize_with_correct_fields(self):
        """The two valid BTC/ETH records normalize with expected field values."""
        records = _load_snapshot()
        client = MagicMock()
        client.get_markets.return_value = records
        svc = PolymarketFetchService(client)
        results = svc.fetch_markets()

        btc = next(m for m in results if m.market_id == "btc-100k-snap-001")
        assert btc.active is True
        assert btc.closed is False
        assert btc.enable_order_book is True
        assert len(btc.tokens) == 2
        assert btc.source_timestamp is not None
        assert btc.end_date is not None
        assert btc.event_id == "evt-btc-001"
        assert btc.slug == "btc-100k-snap-001"

    def test_fixture_enableOrderBook_absent_normalizes_to_none(self):
        """Record without enableOrderBook → enable_order_book=None (conservative)."""
        records = _load_snapshot()
        client = MagicMock()
        client.get_markets.return_value = records
        svc = PolymarketFetchService(client)
        results = svc.fetch_markets()

        eob_absent = next(m for m in results if m.market_id == "eob-absent-snap-008")
        assert eob_absent.enable_order_book is None

    def test_fixture_events_absent_normalizes_event_id_to_none(self):
        """Record without events → event_id=None."""
        records = _load_snapshot()
        client = MagicMock()
        client.get_markets.return_value = records
        svc = PolymarketFetchService(client)
        results = svc.fetch_markets()

        no_events = next(m for m in results if m.market_id == "no-events-snap-009")
        assert no_events.event_id is None


# ---------------------------------------------------------------------------
# C — fixture discovery contract
# ---------------------------------------------------------------------------


class TestFixtureDiscoveryContract:
    """C: DiscoveryService produces the expected candidate/rejection counts from fixture."""

    def _evaluate_fixture(self):
        records = _load_snapshot()
        client = MagicMock()
        client.get_markets.return_value = records
        fetcher = PolymarketFetchService(client)
        fetched = fetcher.fetch_markets()
        return DiscoveryService().evaluate(fetched)

    def test_fixture_discovery_produces_expected_candidate_count(self):
        """Fixture: 3 valid records → candidate_count=3.

        BTC, ETH, and no-events (events-absent) records all pass discovery.
        events absence only affects event_id normalization (mapper concern),
        not discovery (active/orderBook/tokens/dates/duration criteria).
        """
        result = self._evaluate_fixture()
        assert len(result.candidates) == 3, (
            f"Expected 3 candidates, got {len(result.candidates)}: "
            f"{[c.market_id for c in result.candidates]}"
        )

    def test_fixture_discovery_produces_expected_rejection_count(self):
        """Fixture: 7 non-candidate records → rejected_count=7."""
        result = self._evaluate_fixture()
        assert result.rejected_count == 7

    def test_fixture_discovery_candidates_include_btc_eth_and_no_events(self):
        """The three candidates are BTC, ETH, and no-events valid records."""
        result = self._evaluate_fixture()
        candidate_ids = {c.market_id for c in result.candidates}
        assert "btc-100k-snap-001" in candidate_ids
        assert "eth-3k-snap-002" in candidate_ids
        assert "no-events-snap-009" in candidate_ids   # events absent is not a rejection criterion

    def test_fixture_rejection_breakdown_covers_all_expected_reasons(self):
        """Each of the 5 rejection reasons is represented in the fixture."""
        result = self._evaluate_fixture()
        bd = result.string_breakdown

        assert set(bd.keys()) == _ALL_TAXONOMY_KEYS
        assert bd["inactive"] >= 2        # inactive + closed records
        assert bd["no_order_book"] >= 2   # no_order_book + absent enableOrderBook
        assert bd["empty_tokens"] >= 1    # tokens=[] record
        assert bd["missing_dates"] >= 1   # startDate absent record
        assert bd["duration_out_of_range"] >= 1  # hourly record

    def test_fixture_partition_invariant(self):
        """fetched == candidates + rejected; total == 10 fixture records."""
        result = self._evaluate_fixture()
        # All 10 fixture records are normalized (none skipped by fetcher)
        assert len(result.candidates) + result.rejected_count == 10
        assert result.fetched_count == 10


# ---------------------------------------------------------------------------
# D — fixture sync contract
# ---------------------------------------------------------------------------


class TestFixtureSyncContract:
    """D: Full sync pipeline on fixture produces a deterministic summary."""

    def test_fixture_sync_writes_two_markets_per_valid_candidate(self):
        """Fixture sync: 3 valid candidates → 6 written (3 × UP+DOWN)."""
        records = _load_snapshot()
        svc, registry = _make_svc(records)
        result = svc.run()

        assert result.fetched == 3       # 3 candidates from discovery
        assert result.written == 6       # 3 candidates × 2 sides
        assert result.mapped == 6
        assert result.skipped_mapping == 0
        assert result.skipped_duplicate == 0
        assert result.rejected_count == 7

    def test_fixture_sync_registry_contains_six_entries(self):
        """Registry has exactly 6 entries after fixture sync (3 candidates × 2 sides)."""
        records = _load_snapshot()
        svc, registry = _make_svc(records)
        svc.run()

        assert len(registry) == 6

    def test_fixture_sync_rejection_breakdown_all_keys_present(self):
        """SyncResult.rejection_breakdown has all 5 taxonomy keys after fixture sync."""
        records = _load_snapshot()
        svc, registry = _make_svc(records)
        result = svc.run()

        assert set(result.rejection_breakdown.keys()) == _ALL_TAXONOMY_KEYS

    def test_fixture_sync_pipeline_invariants_hold(self):
        """Pipeline invariants hold for fixture: partition + (fetched−skipped)×2=mapped."""
        from backend.app.services.market_sync import MarketMapper
        records = _load_snapshot()
        svc, registry = _make_svc(records)
        result = svc.run()

        assert result.mapped == result.written + result.skipped_duplicate
        assert (result.fetched - result.skipped_mapping) * MarketMapper.MARKETS_PER_CANDIDATE == result.mapped


# ---------------------------------------------------------------------------
# E — fixture cross-layer invariants
# ---------------------------------------------------------------------------


class TestFixtureCrossLayerInvariants:
    """E: Cross-layer invariants hold for the fixture payload."""

    def test_fixture_discovery_fetched_equals_candidates_plus_rejected(self):
        """discover: fetched == candidate + rejected for fixture."""
        records = _load_snapshot()
        client = MagicMock()
        client.get_markets.return_value = records
        fetcher = PolymarketFetchService(client)
        fetched = fetcher.fetch_markets()
        result = DiscoveryService().evaluate(fetched)

        assert len(result.candidates) + result.rejected_count == len(fetched)

    def test_fixture_sync_fetched_plus_rejected_equals_discover_fetched(self):
        """sync.fetched + sync.rejected == discover.fetched for fixture."""
        records = _load_snapshot()
        client = MagicMock()
        client.get_markets.return_value = records
        fetcher = PolymarketFetchService(client)
        fetched = fetcher.fetch_markets()

        discover_result = DiscoveryService().evaluate(fetched)

        svc_client = MagicMock()
        svc_client.get_markets.return_value = records
        registry = InMemoryMarketRegistry()
        sync_svc = MarketSyncService(PolymarketFetchService(svc_client), registry)
        sync_result = sync_svc.run()

        # discover.fetched = sync.fetched + sync.rejected (cross-layer partition)
        assert (
            len(discover_result.candidates)
            == sync_result.fetched
        ), "discover.candidate_count must equal sync.fetched_count"
        assert (
            len(fetched)
            == sync_result.fetched + sync_result.rejected_count
        ), "discover.fetched must equal sync.fetched + sync.rejected"


# ---------------------------------------------------------------------------
# F — live Gamma API shape test (skipped by default)
# ---------------------------------------------------------------------------


@pytest.mark.live
def test_live_gamma_api_response_shape_matches_expected_schema():
    """F: Real Gamma API response contains expected field keys in at least one record.

    This test makes a live HTTP call to gamma-api.polymarket.com.
    Run with: pytest -m live

    Verifies:
    - API returns a non-empty list
    - At least one record has all expected Gamma fields
    - enableOrderBook, tokens, startDate, endDate are present in most records
    """
    from backend.app.integrations.polymarket.client import PolymarketClient

    client = PolymarketClient()
    records = client.get_markets(limit=5)

    assert isinstance(records, list), "Gamma API must return a list"
    assert len(records) > 0, "Gamma API must return at least one record"

    # Check that at least one record has 'id' (required field)
    ids_present = [r for r in records if isinstance(r.get("id"), str) and r["id"].strip()]
    assert len(ids_present) > 0, "At least one record must have a valid 'id'"

    # Check field presence across records
    field_counts = {field: 0 for field in _EXPECTED_GAMMA_FIELDS}
    for rec in records:
        for field in _EXPECTED_GAMMA_FIELDS:
            if field in rec:
                field_counts[field] += 1

    # 'id', 'active', 'closed' should be present in every record
    for required_field in ["id", "active", "closed"]:
        assert field_counts[required_field] == len(records), (
            f"Field '{required_field}' missing from some records: "
            f"{field_counts[required_field]}/{len(records)}"
        )

    # Optional but expected fields should be in at least one record
    for expected_field in ["enableOrderBook", "tokens", "startDate", "endDate"]:
        assert field_counts[expected_field] > 0, (
            f"Field '{expected_field}' not found in any of {len(records)} records. "
            f"Schema drift detected — review PolymarketFetchService._normalize()"
        )
