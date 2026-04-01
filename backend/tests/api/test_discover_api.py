"""API tests for POST /api/v1/markets/discover."""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.api.deps import get_discovery_service, get_registry
from backend.app.domain.market.registry import InMemoryMarketRegistry
from backend.app.integrations.polymarket.exceptions import (
    PolymarketHTTPError,
    PolymarketTimeoutError,
)
from backend.app.main import app
from backend.app.services.market_discovery import DiscoveryService, RejectionReason
from backend.app.services.market_fetcher import FetchedMarket, PolymarketFetchService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BASE_START = datetime(2024, 1, 1, tzinfo=timezone.utc)
_VALID_END = _BASE_START + timedelta(seconds=300)


def _fetched(
    market_id: str = "m-1",
    active: bool = True,
    closed: bool = False,
    source_timestamp: datetime | None = _BASE_START,
    end_date: datetime | None = _VALID_END,
    enable_order_book: bool | None = True,
    tokens: list | None = None,
) -> FetchedMarket:
    if tokens is None:
        tokens = [{"outcome": "YES"}, {"outcome": "NO"}]
    return FetchedMarket(
        market_id=market_id,
        question="Will BTC hit 100k?",
        event_id="evt-1",
        slug="btc-100k",
        active=active,
        closed=closed,
        source_timestamp=source_timestamp,
        end_date=end_date,
        enable_order_book=enable_order_book,
        tokens=tokens,
    )


def _mock_fetcher(markets: list[FetchedMarket]) -> MagicMock:
    fetcher = MagicMock(spec=PolymarketFetchService)
    fetcher.fetch_markets.return_value = markets
    return fetcher


def _override(fetcher: MagicMock, registry: InMemoryMarketRegistry | None = None):
    """Install dependency overrides and return teardown callable."""
    discovery = DiscoveryService()
    app.dependency_overrides[get_discovery_service] = lambda: (fetcher, discovery)
    if registry is not None:
        app.dependency_overrides[get_registry] = lambda: registry


def _clear():
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Success scenarios
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_discover_returns_200():
    _override(_mock_fetcher([_fetched()]))
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/api/v1/markets/discover")
        assert resp.status_code == 200
    finally:
        _clear()


@pytest.mark.asyncio
async def test_discover_response_shape():
    _override(_mock_fetcher([_fetched("m-1"), _fetched("m-2")]))
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/api/v1/markets/discover")
        data = resp.json()
        assert "fetched_count" in data
        assert "candidate_count" in data
        assert "rejected_count" in data
        assert "rejection_breakdown" in data
    finally:
        _clear()


@pytest.mark.asyncio
async def test_discover_all_valid_become_candidates():
    _override(_mock_fetcher([_fetched("m-1"), _fetched("m-2"), _fetched("m-3")]))
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/api/v1/markets/discover")
        data = resp.json()
        assert data["fetched_count"] == 3
        assert data["candidate_count"] == 3
        assert data["rejected_count"] == 0
    finally:
        _clear()


@pytest.mark.asyncio
async def test_discover_empty_fetch():
    _override(_mock_fetcher([]))
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/api/v1/markets/discover")
        data = resp.json()
        assert data["fetched_count"] == 0
        assert data["candidate_count"] == 0
        assert data["rejected_count"] == 0
        assert data["rejection_breakdown"]["inactive"] == 0
        assert data["rejection_breakdown"]["no_order_book"] == 0
        assert data["rejection_breakdown"]["empty_tokens"] == 0
        assert data["rejection_breakdown"]["missing_dates"] == 0
        assert data["rejection_breakdown"]["duration_out_of_range"] == 0
    finally:
        _clear()


@pytest.mark.asyncio
async def test_discover_no_candidates_all_rejected():
    markets = [
        _fetched("inactive", active=False),
        _fetched("no-start", source_timestamp=None),
        _fetched("long", end_date=_BASE_START + timedelta(hours=1)),
    ]
    _override(_mock_fetcher(markets))
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/api/v1/markets/discover")
        data = resp.json()
        assert data["fetched_count"] == 3
        assert data["candidate_count"] == 0
        assert data["rejected_count"] == 3
    finally:
        _clear()


# ---------------------------------------------------------------------------
# Rejection breakdown
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_discover_breakdown_all_keys_present():
    _override(_mock_fetcher([]))
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/api/v1/markets/discover")
        breakdown = resp.json()["rejection_breakdown"]
        assert "inactive" in breakdown
        assert "no_order_book" in breakdown
        assert "empty_tokens" in breakdown
        assert "missing_dates" in breakdown
        assert "duration_out_of_range" in breakdown
    finally:
        _clear()


@pytest.mark.asyncio
async def test_discover_breakdown_inactive_counted():
    markets = [_fetched("a", active=False), _fetched("b", closed=True), _fetched("ok")]
    _override(_mock_fetcher(markets))
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/api/v1/markets/discover")
        data = resp.json()
        assert data["rejection_breakdown"]["inactive"] == 2
        assert data["candidate_count"] == 1
    finally:
        _clear()


@pytest.mark.asyncio
async def test_discover_breakdown_missing_dates_counted():
    markets = [
        _fetched("no-start", source_timestamp=None),
        _fetched("no-end", end_date=None),
        _fetched("ok"),
    ]
    _override(_mock_fetcher(markets))
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/api/v1/markets/discover")
        data = resp.json()
        assert data["rejection_breakdown"]["missing_dates"] == 2
        assert data["candidate_count"] == 1
    finally:
        _clear()


@pytest.mark.asyncio
async def test_discover_breakdown_duration_counted():
    markets = [
        _fetched("short", end_date=_BASE_START + timedelta(seconds=60)),
        _fetched("long", end_date=_BASE_START + timedelta(hours=1)),
        _fetched("ok"),
    ]
    _override(_mock_fetcher(markets))
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/api/v1/markets/discover")
        data = resp.json()
        assert data["rejection_breakdown"]["duration_out_of_range"] == 2
        assert data["candidate_count"] == 1
    finally:
        _clear()


@pytest.mark.asyncio
async def test_discover_fetched_equals_candidate_plus_rejected():
    markets = [_fetched("ok"), _fetched("bad", active=False)]
    _override(_mock_fetcher(markets))
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/api/v1/markets/discover")
        data = resp.json()
        assert data["fetched_count"] == data["candidate_count"] + data["rejected_count"]
    finally:
        _clear()


# ---------------------------------------------------------------------------
# Error scenarios
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_discover_timeout_returns_504():
    fetcher = MagicMock(spec=PolymarketFetchService)
    fetcher.fetch_markets.side_effect = PolymarketTimeoutError()
    _override(fetcher)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/api/v1/markets/discover")
        assert resp.status_code == 504
        assert "timed out" in resp.json()["detail"].lower()
    finally:
        _clear()


@pytest.mark.asyncio
async def test_discover_upstream_http_error_returns_502():
    fetcher = MagicMock(spec=PolymarketFetchService)
    fetcher.fetch_markets.side_effect = PolymarketHTTPError(
        status_code=503, url="https://gamma-api.polymarket.com/markets"
    )
    _override(fetcher)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/api/v1/markets/discover")
        assert resp.status_code == 502
    finally:
        _clear()


# ---------------------------------------------------------------------------
# Registry not touched
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_discover_does_not_write_to_registry():
    """Discovery endpoint must leave the registry empty."""
    registry = InMemoryMarketRegistry()
    fetcher = _mock_fetcher([_fetched("m-1"), _fetched("m-2")])
    _override(fetcher, registry)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/api/v1/markets/discover")
        assert resp.status_code == 200
        assert len(registry) == 0   # no write happened
    finally:
        _clear()


@pytest.mark.asyncio
async def test_discover_on_error_does_not_write_to_registry():
    registry = InMemoryMarketRegistry()
    fetcher = MagicMock(spec=PolymarketFetchService)
    fetcher.fetch_markets.side_effect = PolymarketTimeoutError()
    _override(fetcher, registry)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            await c.post("/api/v1/markets/discover")
        assert len(registry) == 0
    finally:
        _clear()
