"""Tests for MarketMapper and MarketSyncService."""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from backend.app.domain.market.registry import InMemoryMarketRegistry
from backend.app.domain.market.types import Side, Timeframe
from backend.app.integrations.polymarket.exceptions import PolymarketTimeoutError
from backend.app.services.market_fetcher import FetchedMarket
from backend.app.services.market_sync import MarketMapper, MarketSyncService, SyncResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Timestamps that satisfy all DiscoveryService rules:
#   active=True, closed=False, both dates present, duration = 300 s [240–360]
_BASE_START = datetime(2024, 1, 1, tzinfo=timezone.utc)
_VALID_END   = _BASE_START + timedelta(seconds=300)


def _fetched(
    market_id: str = "m-1",
    slug: str | None = "btc-100k",
    event_id: str | None = "evt-1",
    active: bool = True,
    closed: bool = False,
    source_timestamp: datetime | None = _BASE_START,
    end_date: datetime | None = _VALID_END,
) -> FetchedMarket:
    return FetchedMarket(
        market_id=market_id,
        question="Will BTC hit 100k?",
        event_id=event_id,
        slug=slug,
        active=active,
        closed=closed,
        source_timestamp=source_timestamp,
        end_date=end_date,
    )


def _mock_fetcher(markets: list[FetchedMarket]) -> MagicMock:
    """Mock fetcher whose fetch_markets() returns *markets*.

    fetch_markets is the method called by MarketSyncService.run() after
    the v0.5.2 discovery-sync integration.
    """
    fetcher = MagicMock()
    fetcher.fetch_markets.return_value = markets
    return fetcher


# ---------------------------------------------------------------------------
# MarketMapper
# ---------------------------------------------------------------------------


class TestMarketMapper:
    def test_produces_up_and_down(self):
        mapper = MarketMapper()
        markets = mapper.map(_fetched())
        sides = {m.side for m in markets}
        assert sides == {Side.UP, Side.DOWN}

    def test_ids_are_suffixed(self):
        mapper = MarketMapper()
        markets = mapper.map(_fetched(market_id="abc"))
        ids = {m.id for m in markets}
        assert ids == {"abc-up", "abc-down"}

    def test_extracts_known_symbol_from_question(self):
        # question contains "BTC" → extract_symbol returns "BTC"
        mapper = MarketMapper()
        markets = mapper.map(_fetched(slug="some-slug"))
        assert all(m.symbol == "BTC" for m in markets)  # _fetched() question = "Will BTC hit 100k?"

    def test_uses_slug_when_symbol_not_extracted(self):
        # question has no coin keyword; slug used as fallback
        mapper = MarketMapper()
        markets = mapper.map(
            FetchedMarket(
                market_id="m-1",
                question="Will the market go up?",
                event_id="evt-1",
                slug="some-unknown-slug",
                active=True,
                closed=False,
                source_timestamp=None,
                end_date=None,
            )
        )
        assert all(m.symbol == "some-unknown-slug" for m in markets)

    def test_falls_back_to_market_id_when_slug_none_and_no_extraction(self):
        # no extractable symbol, no slug → market_id used
        mapper = MarketMapper()
        markets = mapper.map(
            FetchedMarket(
                market_id="x-99",
                question="Will the price go higher?",
                event_id=None,
                slug=None,
                active=True,
                closed=False,
                source_timestamp=None,
                end_date=None,
            )
        )
        assert all(m.symbol == "x-99" for m in markets)

    def test_uses_event_id_when_present(self):
        mapper = MarketMapper()
        markets = mapper.map(_fetched(event_id="evt-42"))
        assert all(m.event_id == "evt-42" for m in markets)

    def test_falls_back_to_market_id_when_event_id_none(self):
        mapper = MarketMapper()
        markets = mapper.map(_fetched(market_id="m-7", event_id=None))
        assert all(m.event_id == "m-7" for m in markets)

    def test_timeframe_is_always_m5(self):
        mapper = MarketMapper()
        markets = mapper.map(_fetched())
        assert all(m.timeframe == Timeframe.M5 for m in markets)

    def test_source_timestamp_is_forwarded(self):
        ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
        mapper = MarketMapper()
        markets = mapper.map(_fetched(source_timestamp=ts))
        assert all(m.source_timestamp == ts for m in markets)

    def test_end_date_is_forwarded(self):
        end = datetime(2024, 1, 1, 0, 5, 0, tzinfo=timezone.utc)
        mapper = MarketMapper()
        markets = mapper.map(_fetched(end_date=end))
        assert all(m.end_date == end for m in markets)

    def test_end_date_none_is_forwarded(self):
        mapper = MarketMapper()
        markets = mapper.map(_fetched(end_date=None))
        assert all(m.end_date is None for m in markets)

    def test_returns_empty_on_mapping_failure(self):
        # Inject a FetchedMarket-like object with an invalid market_id to
        # trigger a domain validation error inside the mapper.
        bad = FetchedMarket(
            market_id="   ",  # stripped → empty → domain validation error
            question="",
            event_id=None,
            slug=None,
            active=True,
            closed=False,
            source_timestamp=None,
            end_date=None,
        )
        # market_id "   ".strip() == "" — create_market will raise ValueError
        mapper = MarketMapper()
        result = mapper.map(bad)
        assert result == []


# ---------------------------------------------------------------------------
# MarketSyncService — run()
# ---------------------------------------------------------------------------


class TestMarketSyncService:
    def test_full_happy_path(self):
        registry = InMemoryMarketRegistry()
        fetcher = _mock_fetcher([_fetched("m-1"), _fetched("m-2")])
        service = MarketSyncService(fetcher, registry)
        result = service.run()

        assert result.fetched == 2
        assert result.mapped == 4        # 2 markets × 2 sides
        assert result.written == 4
        assert result.skipped_mapping == 0
        assert result.skipped_duplicate == 0

    def test_registry_contains_written_markets(self):
        registry = InMemoryMarketRegistry()
        fetcher = _mock_fetcher([_fetched("m-1")])
        MarketSyncService(fetcher, registry).run()

        ids = {m.id for m in registry.list_all()}
        assert ids == {"m-1-up", "m-1-down"}

    def test_empty_fetch_returns_zero_result(self):
        registry = InMemoryMarketRegistry()
        fetcher = _mock_fetcher([])
        result = MarketSyncService(fetcher, registry).run()

        assert result == SyncResult(
            fetched=0, mapped=0, written=0,
            skipped_mapping=0, skipped_duplicate=0,
        )

    def test_duplicate_run_counts_skipped_duplicate(self):
        registry = InMemoryMarketRegistry()
        fetcher = _mock_fetcher([_fetched("m-1")])
        service = MarketSyncService(fetcher, registry)
        service.run()           # first run writes 2
        result = service.run()  # second run: both exist → skipped

        assert result.written == 0
        assert result.skipped_duplicate == 2

    def test_client_error_propagates(self):
        registry = InMemoryMarketRegistry()
        fetcher = MagicMock()
        fetcher.fetch_markets.side_effect = PolymarketTimeoutError()
        service = MarketSyncService(fetcher, registry)

        with pytest.raises(PolymarketTimeoutError):
            service.run()

        assert len(registry) == 0   # registry untouched

    def test_mapping_failure_is_counted_and_skipped(self):
        # bad has valid timestamps (passes DiscoveryService) but empty
        # market_id (fails MarketMapper) — tests that skipped_mapping counts correctly.
        bad = FetchedMarket(
            market_id="   ",   # stripped → empty → mapper raises ValueError
            question="",
            event_id=None,
            slug=None,
            active=True,
            closed=False,
            source_timestamp=_BASE_START,  # valid → passes discovery
            end_date=_VALID_END,           # valid → passes discovery
        )
        registry = InMemoryMarketRegistry()
        fetcher = _mock_fetcher([bad, _fetched("good-1")])
        result = MarketSyncService(fetcher, registry).run()

        assert result.fetched == 2
        assert result.skipped_mapping == 1
        assert result.written == 2       # only good-1's UP+DOWN
        assert len(registry) == 2

    def test_passes_limit_to_fetcher(self):
        registry = InMemoryMarketRegistry()
        fetcher = _mock_fetcher([])
        MarketSyncService(fetcher, registry).run(limit=7)
        fetcher.fetch_markets.assert_called_once_with(limit=7)


# ---------------------------------------------------------------------------
# Discovery integration — DiscoveryService is the single candidate selector
# ---------------------------------------------------------------------------


class TestSyncDiscoveryIntegration:
    def test_inactive_market_not_written(self):
        """active=False → rejected by DiscoveryService → not in registry."""
        registry = InMemoryMarketRegistry()
        fetcher = _mock_fetcher([_fetched("m-inactive", active=False)])
        result = MarketSyncService(fetcher, registry).run()

        assert result.fetched == 0
        assert result.written == 0
        assert len(registry) == 0

    def test_closed_market_not_written(self):
        """closed=True → rejected by DiscoveryService → not in registry."""
        registry = InMemoryMarketRegistry()
        fetcher = _mock_fetcher([_fetched("m-closed", closed=True)])
        result = MarketSyncService(fetcher, registry).run()

        assert result.fetched == 0
        assert len(registry) == 0

    def test_missing_dates_market_not_written(self):
        """source_timestamp=None → rejected by DiscoveryService → not written."""
        registry = InMemoryMarketRegistry()
        fetcher = _mock_fetcher([_fetched("m-no-ts", source_timestamp=None)])
        result = MarketSyncService(fetcher, registry).run()

        assert result.fetched == 0
        assert len(registry) == 0

    def test_duration_out_of_range_not_written(self):
        """duration > 360 s → rejected by DiscoveryService → not written."""
        registry = InMemoryMarketRegistry()
        long_end = _BASE_START + timedelta(hours=1)
        fetcher = _mock_fetcher([_fetched("m-long", end_date=long_end)])
        result = MarketSyncService(fetcher, registry).run()

        assert result.fetched == 0
        assert len(registry) == 0

    def test_only_valid_candidates_written_in_mixed_batch(self):
        """Mixed batch: valid markets written, rejected ones silently dropped."""
        registry = InMemoryMarketRegistry()
        fetcher = _mock_fetcher([
            _fetched("ok-1"),
            _fetched("ok-2"),
            _fetched("bad-inactive", active=False),
            _fetched("bad-no-ts", source_timestamp=None),
        ])
        result = MarketSyncService(fetcher, registry).run()

        assert result.fetched == 2      # only ok-1 and ok-2 passed discovery
        assert result.written == 4      # 2 candidates × 2 sides
        assert len(registry) == 4
        written_ids = {m.id for m in registry.list_all()}
        assert "ok-1-up" in written_ids
        assert "ok-2-down" in written_ids
        assert "bad-inactive-up" not in written_ids
        assert "bad-no-ts-up" not in written_ids

    def test_discovery_service_is_injected_and_used(self):
        """Custom DiscoveryService can be injected — its evaluate() is called."""
        from unittest.mock import MagicMock
        from backend.app.services.market_discovery import DiscoveryResult, RejectionReason

        mock_discovery = MagicMock()
        # Return a DiscoveryResult with no candidates (all rejected)
        mock_discovery.evaluate.return_value = DiscoveryResult(
            fetched_count=2,
            candidate_count=0,
            rejected_count=2,
            candidates=[],
            rejection_breakdown={r: 0 for r in RejectionReason},
        )

        registry = InMemoryMarketRegistry()
        fetcher = _mock_fetcher([_fetched("m-1"), _fetched("m-2")])
        service = MarketSyncService(fetcher, registry, discovery=mock_discovery)
        result = service.run()

        mock_discovery.evaluate.assert_called_once()
        assert result.fetched == 0
        assert len(registry) == 0
