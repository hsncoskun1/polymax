"""Tests for PolymarketFetchService — all HTTP interaction mocked."""
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from backend.app.integrations.polymarket.exceptions import PolymarketTimeoutError
from backend.app.services.market_fetcher import (
    FetchedMarket,
    PolymarketFetchService,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_client(return_value: list[dict]) -> MagicMock:
    client = MagicMock()
    client.get_markets.return_value = return_value
    return client


def _raw_market(**overrides) -> dict:
    """Minimal valid Gamma API market record.

    startDate and endDate are exactly 300 seconds apart.
    All fields that DiscoveryService checks are present and valid.
    """
    base = {
        "id": "market-1",
        "question": "Will BTC hit 100k?",
        "slug": "btc-100k",
        "active": True,
        "closed": False,
        "enableOrderBook": True,
        "tokens": [{"outcome": "YES", "price": "0.6"}, {"outcome": "NO", "price": "0.4"}],
        "startDate": "2024-01-01T00:00:00Z",
        "endDate":   "2024-01-01T00:05:00Z",   # exactly 300 s after startDate
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

    def test_no_candidate_filtering_applied(self):
        """fetch_markets must return inactive/AMM-only/short-duration markets unchanged.

        Candidate selection is DiscoveryService's responsibility — the fetcher
        must not silently drop any normalised records.
        """
        records = [
            _raw_market(id="inactive", active=False),
            _raw_market(id="amm-only", enableOrderBook=False),
            _raw_market(id="no-tokens", tokens=[]),
            _raw_market(id="long-duration", endDate="2024-01-02T00:00:00Z"),
        ]
        client = _make_client(records)
        result = PolymarketFetchService(client).fetch_markets()
        assert len(result) == 4
        assert {m.market_id for m in result} == {
            "inactive", "amm-only", "no-tokens", "long-duration"
        }


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

    def test_parses_end_date(self):
        raw = _raw_market(endDate="2024-06-15T12:35:00Z")
        service = PolymarketFetchService(_make_client([raw]))
        result = service.fetch_markets()
        assert result[0].end_date == datetime(2024, 6, 15, 12, 35, 0, tzinfo=timezone.utc)

    def test_end_date_none_when_absent(self):
        raw = _raw_market()
        del raw["endDate"]
        service = PolymarketFetchService(_make_client([raw]))
        result = service.fetch_markets()
        assert result[0].end_date is None

    def test_end_date_none_on_unparseable_date(self):
        raw = _raw_market(endDate="not-a-date")
        service = PolymarketFetchService(_make_client([raw]))
        result = service.fetch_markets()
        assert result[0].end_date is None

    # -- Duration source semantics --------------------------------------------

    def test_source_timestamp_is_event_start_time_from_gamma_start_date(self):
        """source_timestamp carries the event's structural start time, not a fetch timestamp.

        Mapping chain: Gamma API "startDate" → FetchedMarket.source_timestamp

        This is the field DiscoveryService uses as the start point for duration
        calculation.  It must equal the parsed startDate value — a fixed event
        property — not any kind of dynamic fetch/snapshot time.
        """
        raw = _raw_market(startDate="2024-06-15T12:00:00Z")
        service = PolymarketFetchService(_make_client([raw]))
        result = service.fetch_markets()

        assert result[0].source_timestamp == datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)

    def test_duration_field_mapping_startDate_to_source_timestamp_and_endDate_to_end_date(self):
        """Both structural time fields normalise correctly and their difference is the event span.

        Verifies the full mapping used by duration calculation:
          Gamma "startDate" → source_timestamp  (event structural start)
          Gamma "endDate"   → end_date          (event structural end)
          end_date − source_timestamp            = 300 s (structural duration)

        This locks the semantic chain that makes duration calculation valid.
        """
        raw = _raw_market(startDate="2024-01-01T00:00:00Z", endDate="2024-01-01T00:05:00Z")
        service = PolymarketFetchService(_make_client([raw]))
        result = service.fetch_markets()

        m = result[0]
        assert m.source_timestamp == datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        assert m.end_date == datetime(2024, 1, 1, 0, 5, 0, tzinfo=timezone.utc)
        structural_duration = (m.end_date - m.source_timestamp).total_seconds()
        assert structural_duration == 300.0

    def test_enable_order_book_true_when_present(self):
        raw = _raw_market(enableOrderBook=True)
        service = PolymarketFetchService(_make_client([raw]))
        result = service.fetch_markets()
        assert result[0].enable_order_book is True

    def test_enable_order_book_false_when_false(self):
        raw = _raw_market(enableOrderBook=False)
        service = PolymarketFetchService(_make_client([raw]))
        result = service.fetch_markets()
        assert result[0].enable_order_book is False

    def test_enable_order_book_none_when_absent(self):
        raw = _raw_market()
        del raw["enableOrderBook"]
        service = PolymarketFetchService(_make_client([raw]))
        result = service.fetch_markets()
        assert result[0].enable_order_book is None

    def test_tokens_list_preserved(self):
        tok = [{"outcome": "YES"}, {"outcome": "NO"}]
        raw = _raw_market(tokens=tok)
        service = PolymarketFetchService(_make_client([raw]))
        result = service.fetch_markets()
        assert result[0].tokens == tok

    def test_tokens_empty_list_preserved(self):
        raw = _raw_market(tokens=[])
        service = PolymarketFetchService(_make_client([raw]))
        result = service.fetch_markets()
        assert result[0].tokens == []

    def test_tokens_none_when_absent(self):
        raw = _raw_market()
        del raw["tokens"]
        service = PolymarketFetchService(_make_client([raw]))
        result = service.fetch_markets()
        assert result[0].tokens is None

    def test_tokens_none_when_not_a_list(self):
        raw = _raw_market(tokens="invalid")
        service = PolymarketFetchService(_make_client([raw]))
        result = service.fetch_markets()
        assert result[0].tokens is None
