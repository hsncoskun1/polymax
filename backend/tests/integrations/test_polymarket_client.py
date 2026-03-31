"""Tests for PolymarketClient — all HTTP interaction is mocked via unittest.mock."""
from unittest.mock import MagicMock, patch

import httpx
import pytest

from backend.app.integrations.polymarket.client import PolymarketClient
from backend.app.integrations.polymarket.exceptions import (
    PolymarketHTTPError,
    PolymarketParseError,
    PolymarketTimeoutError,
)


def _mock_response(status_code: int = 200, json_data=None) -> MagicMock:
    """Build a fake httpx.Response-like object."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.is_success = 200 <= status_code < 300
    resp.json.return_value = json_data if json_data is not None else []
    return resp


# ---------------------------------------------------------------------------
# ping()
# ---------------------------------------------------------------------------


class TestPing:
    def test_returns_true_on_success(self):
        resp = _mock_response(200, [{"id": "1"}])
        mock_http = MagicMock()
        mock_http.__enter__ = MagicMock(return_value=mock_http)
        mock_http.__exit__ = MagicMock(return_value=False)
        mock_http.get.return_value = resp

        with patch("backend.app.integrations.polymarket.client.httpx.Client", return_value=mock_http):
            client = PolymarketClient()
            assert client.ping() is True

    def test_returns_false_on_timeout(self):
        mock_http = MagicMock()
        mock_http.__enter__ = MagicMock(return_value=mock_http)
        mock_http.__exit__ = MagicMock(return_value=False)
        mock_http.get.side_effect = httpx.TimeoutException("timed out")

        with patch("backend.app.integrations.polymarket.client.httpx.Client", return_value=mock_http):
            client = PolymarketClient()
            assert client.ping() is False

    def test_returns_false_on_http_error(self):
        resp = _mock_response(503)
        mock_http = MagicMock()
        mock_http.__enter__ = MagicMock(return_value=mock_http)
        mock_http.__exit__ = MagicMock(return_value=False)
        mock_http.get.return_value = resp

        with patch("backend.app.integrations.polymarket.client.httpx.Client", return_value=mock_http):
            client = PolymarketClient()
            assert client.ping() is False


# ---------------------------------------------------------------------------
# get_markets()
# ---------------------------------------------------------------------------


class TestGetMarkets:
    def test_returns_list_of_dicts_on_success(self):
        payload = [{"id": "abc", "question": "Will X happen?"}]
        resp = _mock_response(200, payload)
        mock_http = MagicMock()
        mock_http.__enter__ = MagicMock(return_value=mock_http)
        mock_http.__exit__ = MagicMock(return_value=False)
        mock_http.get.return_value = resp

        with patch("backend.app.integrations.polymarket.client.httpx.Client", return_value=mock_http):
            client = PolymarketClient()
            result = client.get_markets()

        assert result == payload

    def test_passes_limit_param(self):
        resp = _mock_response(200, [])
        mock_http = MagicMock()
        mock_http.__enter__ = MagicMock(return_value=mock_http)
        mock_http.__exit__ = MagicMock(return_value=False)
        mock_http.get.return_value = resp

        with patch("backend.app.integrations.polymarket.client.httpx.Client", return_value=mock_http):
            client = PolymarketClient()
            client.get_markets(limit=5)

        _, kwargs = mock_http.get.call_args
        assert kwargs["params"]["limit"] == 5

    def test_raises_timeout_error(self):
        mock_http = MagicMock()
        mock_http.__enter__ = MagicMock(return_value=mock_http)
        mock_http.__exit__ = MagicMock(return_value=False)
        mock_http.get.side_effect = httpx.TimeoutException("timed out")

        with patch("backend.app.integrations.polymarket.client.httpx.Client", return_value=mock_http):
            client = PolymarketClient()
            with pytest.raises(PolymarketTimeoutError):
                client.get_markets()

    def test_raises_http_error_on_non_2xx(self):
        resp = _mock_response(404)
        mock_http = MagicMock()
        mock_http.__enter__ = MagicMock(return_value=mock_http)
        mock_http.__exit__ = MagicMock(return_value=False)
        mock_http.get.return_value = resp

        with patch("backend.app.integrations.polymarket.client.httpx.Client", return_value=mock_http):
            client = PolymarketClient()
            with pytest.raises(PolymarketHTTPError) as exc_info:
                client.get_markets()

        assert exc_info.value.status_code == 404

    def test_raises_parse_error_when_response_not_list(self):
        resp = _mock_response(200, {"unexpected": "dict"})
        mock_http = MagicMock()
        mock_http.__enter__ = MagicMock(return_value=mock_http)
        mock_http.__exit__ = MagicMock(return_value=False)
        mock_http.get.return_value = resp

        with patch("backend.app.integrations.polymarket.client.httpx.Client", return_value=mock_http):
            client = PolymarketClient()
            with pytest.raises(PolymarketParseError):
                client.get_markets()

    def test_raises_parse_error_on_invalid_json(self):
        resp = _mock_response(200)
        resp.json.side_effect = ValueError("invalid JSON")
        mock_http = MagicMock()
        mock_http.__enter__ = MagicMock(return_value=mock_http)
        mock_http.__exit__ = MagicMock(return_value=False)
        mock_http.get.return_value = resp

        with patch("backend.app.integrations.polymarket.client.httpx.Client", return_value=mock_http):
            client = PolymarketClient()
            with pytest.raises(PolymarketParseError):
                client.get_markets()
