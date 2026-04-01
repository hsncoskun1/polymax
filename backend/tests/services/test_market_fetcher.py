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
    """Minimal valid Gamma API market record (passes _is_5m_candidate by default)."""
    base = {
        "id": "market-1",
        "question": "Will BTC hit 100k?",
        "slug": "btc-100k",
        "active": True,
        "closed": False,
        "enableOrderBook": True,
        "tokens": [{"outcome": "YES", "price": "0.6"}, {"outcome": "NO", "price": "0.4"}],
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
    # ── passes ────────────────────────────────────────────────────────────────

    def test_passes_fully_valid_candidate(self):
        raw = _raw_market(active=True, closed=False, enableOrderBook=True,
                          tokens=[{"outcome": "YES"}, {"outcome": "NO"}])
        result = PolymarketFetchService(_make_client([raw])).fetch_candidates()
        assert len(result) == 1

    # ── active / closed ───────────────────────────────────────────────────────

    def test_filters_out_inactive_market(self):
        raw = _raw_market(active=False)
        result = PolymarketFetchService(_make_client([raw])).fetch_candidates()
        assert result == []

    def test_filters_out_closed_market(self):
        raw = _raw_market(closed=True)
        result = PolymarketFetchService(_make_client([raw])).fetch_candidates()
        assert result == []

    # ── enableOrderBook ───────────────────────────────────────────────────────

    def test_filters_out_amm_only_market(self):
        """Markets without an order book lack intra-minute price resolution."""
        raw = _raw_market(enableOrderBook=False)
        result = PolymarketFetchService(_make_client([raw])).fetch_candidates()
        assert result == []

    def test_filters_out_missing_enable_order_book_field(self):
        raw = _raw_market()
        del raw["enableOrderBook"]
        result = PolymarketFetchService(_make_client([raw])).fetch_candidates()
        assert result == []

    # ── tokens ────────────────────────────────────────────────────────────────

    def test_filters_out_empty_tokens_list(self):
        raw = _raw_market(tokens=[])
        result = PolymarketFetchService(_make_client([raw])).fetch_candidates()
        assert result == []

    def test_filters_out_missing_tokens_field(self):
        raw = _raw_market()
        del raw["tokens"]
        result = PolymarketFetchService(_make_client([raw])).fetch_candidates()
        assert result == []

    def test_filters_out_non_list_tokens(self):
        raw = _raw_market(tokens=None)
        result = PolymarketFetchService(_make_client([raw])).fetch_candidates()
        assert result == []

    # ── mixed batch ───────────────────────────────────────────────────────────

    def test_passes_only_fully_qualifying_records(self):
        records = [
            _raw_market(id="ok",     active=True,  closed=False, enableOrderBook=True,  tokens=[{"outcome": "YES"}]),
            _raw_market(id="no-ob",  active=True,  closed=False, enableOrderBook=False, tokens=[{"outcome": "YES"}]),
            _raw_market(id="no-tok", active=True,  closed=False, enableOrderBook=True,  tokens=[]),
            _raw_market(id="closed", active=True,  closed=True,  enableOrderBook=True,  tokens=[{"outcome": "YES"}]),
            _raw_market(id="inact",  active=False, closed=False, enableOrderBook=True,  tokens=[{"outcome": "YES"}]),
        ]
        result = PolymarketFetchService(_make_client(records)).fetch_candidates()
        assert len(result) == 1
        assert result[0].market_id == "ok"

    def test_returns_empty_when_all_filtered(self):
        records = [_raw_market(active=False, closed=True)]
        result = PolymarketFetchService(_make_client(records)).fetch_candidates()
        assert result == []
