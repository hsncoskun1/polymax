"""Tests for PolymarketFetchService — all HTTP interaction mocked."""
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from backend.app.integrations.polymarket.exceptions import PolymarketTimeoutError
from backend.app.services.market_fetcher import FetchedMarket, PolymarketFetchService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_client(return_value: list[dict]) -> MagicMock:
    client = MagicMock()
    client.get_markets.return_value = return_value
    return client


def _raw_market(**overrides) -> dict:
    """Minimal valid Gamma API market record."""
    base = {
        "id": "market-1",
        "question": "Will BTC hit 100k?",
        "slug": "btc-100k",
        "active": True,
        "closed": False,
        "startDate": "2024-01-01T00:00:00Z",
        "events": [{"id": "event-1", "title": "BTC milestone"}],
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# fetch_markets
# ---------------------------------------------------------------------------


class TestFetchMarkets:
    def test_returns_fetched_market_list(self):
        client = _make_client([_raw_market()])
        service = PolymarketFetchService(client)
        result = service.fetch_markets()

        assert len(result) == 1
        m = result[0]
        assert isinstance(m, FetchedMarket)
        assert m.market_id == "market-1"
        assert m.question == "Will BTC hit 100k?"
        assert m.slug == "btc-100k"
        assert m.active is True
        assert m.closed is False

    def test_returns_empty_list_when_no_markets(self):
        client = _make_client([])
        service = PolymarketFetchService(client)
        assert service.fetch_markets() == []

    def test_passes_limit_to_client(self):
        client = _make_client([])
        service = PolymarketFetchService(client)
        service.fetch_markets(limit=5)
        client.get_markets.assert_called_once_with(limit=5)

    def test_propagates_client_error(self):
        client = MagicMock()
        client.get_markets.side_effect = PolymarketTimeoutError()
        service = PolymarketFetchService(client)
        with pytest.raises(PolymarketTimeoutError):
            service.fetch_markets()

    def test_skips_record_with_missing_id(self):
        records = [
            _raw_market(id=""),           # empty string
            {"question": "No id here"},   # missing key entirely
            _raw_market(id="valid-2"),
        ]
        client = _make_client(records)
        service = PolymarketFetchService(client)
        result = service.fetch_markets()

        assert len(result) == 1
        assert result[0].market_id == "valid-2"

    def test_handles_multiple_valid_records(self):
        records = [_raw_market(id=f"m-{i}") for i in range(3)]
        client = _make_client(records)
        service = PolymarketFetchService(client)
        result = service.fetch_markets()
        assert [m.market_id for m in result] == ["m-0", "m-1", "m-2"]


# ---------------------------------------------------------------------------
# Normalisation — optional fields
# ---------------------------------------------------------------------------


class TestNormalization:
    def test_extracts_event_id_from_events_list(self):
        raw = _raw_market(events=[{"id": "evt-42"}, {"id": "evt-99"}])
        service = PolymarketFetchService(_make_client([raw]))
        result = service.fetch_markets()
        assert result[0].event_id == "evt-42"

    def test_event_id_is_none_when_events_absent(self):
        raw = _raw_market()
        del raw["events"]
        service = PolymarketFetchService(_make_client([raw]))
        result = service.fetch_markets()
        assert result[0].event_id is None

    def test_event_id_is_none_when_events_empty(self):
        raw = _raw_market(events=[])
        service = PolymarketFetchService(_make_client([raw]))
        result = service.fetch_markets()
        assert result[0].event_id is None

    def test_parses_source_timestamp(self):
        raw = _raw_market(startDate="2024-06-15T12:30:00Z")
        service = PolymarketFetchService(_make_client([raw]))
        result = service.fetch_markets()
        ts = result[0].source_timestamp
        assert ts == datetime(2024, 6, 15, 12, 30, 0, tzinfo=timezone.utc)

    def test_source_timestamp_none_when_start_date_absent(self):
        raw = _raw_market()
        del raw["startDate"]
        service = PolymarketFetchService(_make_client([raw]))
        result = service.fetch_markets()
        assert result[0].source_timestamp is None

    def test_source_timestamp_none_on_unparseable_date(self):
        raw = _raw_market(startDate="not-a-date")
        service = PolymarketFetchService(_make_client([raw]))
        result = service.fetch_markets()
        assert result[0].source_timestamp is None

    def test_slug_none_when_absent(self):
        raw = _raw_market()
        del raw["slug"]
        service = PolymarketFetchService(_make_client([raw]))
        result = service.fetch_markets()
        assert result[0].slug is None

    def test_question_defaults_to_empty_string_when_absent(self):
        raw = _raw_market()
        del raw["question"]
        service = PolymarketFetchService(_make_client([raw]))
        result = service.fetch_markets()
        assert result[0].question == ""


# ---------------------------------------------------------------------------
# fetch_candidates (5m filter placeholder)
# ---------------------------------------------------------------------------


class TestFetchCandidates:
    def test_passes_active_non_closed(self):
        raw = _raw_market(active=True, closed=False)
        client = _make_client([raw])
        result = PolymarketFetchService(client).fetch_candidates()
        assert len(result) == 1

    def test_filters_out_inactive(self):
        records = [
            _raw_market(id="a", active=False, closed=False),
            _raw_market(id="b", active=True, closed=True),
            _raw_market(id="c", active=True, closed=False),
        ]
        result = PolymarketFetchService(_make_client(records)).fetch_candidates()
        assert len(result) == 1
        assert result[0].market_id == "c"

    def test_returns_empty_when_all_filtered(self):
        records = [_raw_market(active=False, closed=True)]
        result = PolymarketFetchService(_make_client(records)).fetch_candidates()
        assert result == []
