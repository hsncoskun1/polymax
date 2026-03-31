"""Tests for MarketMapper and MarketSyncService."""
from datetime import datetime, timezone
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


def _fetched(
    market_id: str = "m-1",
    slug: str | None = "btc-100k",
    event_id: str | None = "evt-1",
    active: bool = True,
    closed: bool = False,
    source_timestamp: datetime | None = None,
) -> FetchedMarket:
    return FetchedMarket(
        market_id=market_id,
        question="Will BTC hit 100k?",
        event_id=event_id,
        slug=slug,
        active=active,
        closed=closed,
        source_timestamp=source_timestamp,
    )


def _mock_fetcher(candidates: list[FetchedMarket]) -> MagicMock:
    fetcher = MagicMock()
    fetcher.fetch_candidates.return_value = candidates
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

    def test_uses_slug_as_symbol(self):
        mapper = MarketMapper()
        markets = mapper.map(_fetched(slug="eth-flip"))
        assert all(m.symbol == "eth-flip" for m in markets)

    def test_falls_back_to_market_id_when_slug_none(self):
        mapper = MarketMapper()
        markets = mapper.map(_fetched(market_id="x-99", slug=None))
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
        fetcher.fetch_candidates.side_effect = PolymarketTimeoutError()
        service = MarketSyncService(fetcher, registry)

        with pytest.raises(PolymarketTimeoutError):
            service.run()

        assert len(registry) == 0   # registry untouched

    def test_mapping_failure_is_counted_and_skipped(self):
        bad = FetchedMarket(
            market_id="   ",
            question="",
            event_id=None,
            slug=None,
            active=True,
            closed=False,
            source_timestamp=None,
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
        fetcher.fetch_candidates.assert_called_once_with(limit=7)
