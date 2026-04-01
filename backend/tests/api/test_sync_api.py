"""API tests for POST /api/v1/markets/sync."""
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import MagicMock

from backend.app.main import app
from backend.app.api.deps import get_sync_service, get_registry
from backend.app.domain.market.registry import InMemoryMarketRegistry
from backend.app.integrations.polymarket.exceptions import (
    PolymarketTimeoutError,
    PolymarketHTTPError,
)
from backend.app.services.market_sync import SyncResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_service(result: SyncResult) -> MagicMock:
    svc = MagicMock()
    svc.run.return_value = result
    return svc


def _zero_result(**overrides) -> SyncResult:
    base = SyncResult(
        fetched=0, mapped=0, written=0,
        skipped_mapping=0, skipped_duplicate=0,
    )
    return SyncResult(**{**base.__dict__, **overrides})


@pytest.fixture
def client_with(request):
    """Parametrised fixture: pass a SyncResult or Exception via indirect."""
    payload = request.param
    registry = InMemoryMarketRegistry()

    if isinstance(payload, Exception):
        svc = MagicMock()
        svc.run.side_effect = payload
    else:
        svc = _mock_service(payload)

    app.dependency_overrides[get_sync_service] = lambda: svc
    app.dependency_overrides[get_registry] = lambda: registry
    transport = ASGITransport(app=app)
    client = AsyncClient(transport=transport, base_url="http://test")
    yield client, registry
    app.dependency_overrides.clear()


@pytest.fixture
def plain_client():
    """Simple fixture for tests that build their own mock service."""
    registry = InMemoryMarketRegistry()
    app.dependency_overrides[get_registry] = lambda: registry
    transport = ASGITransport(app=app)
    client = AsyncClient(transport=transport, base_url="http://test")
    yield client, registry
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Success scenarios
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_success_response_shape():
    result = SyncResult(fetched=4, mapped=4, written=4, skipped_mapping=0, skipped_duplicate=0)
    svc = _mock_service(result)
    app.dependency_overrides[get_sync_service] = lambda: svc
    app.dependency_overrides[get_registry] = lambda: InMemoryMarketRegistry()
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            resp = await c.post("/api/v1/markets/sync")
        assert resp.status_code == 200
        data = resp.json()
        assert data["fetched_count"] == 4
        assert data["mapped_count"] == 4
        assert data["written_count"] == 4
        assert data["skipped_mapping_count"] == 0
        assert data["skipped_duplicate_count"] == 0
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_sync_empty_candidates():
    svc = _mock_service(_zero_result())
    app.dependency_overrides[get_sync_service] = lambda: svc
    app.dependency_overrides[get_registry] = lambda: InMemoryMarketRegistry()
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            resp = await c.post("/api/v1/markets/sync")
        assert resp.status_code == 200
        data = resp.json()
        assert data["fetched_count"] == 0
        assert data["written_count"] == 0
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_sync_duplicate_skip_reflected_in_response():
    result = SyncResult(fetched=2, mapped=4, written=0, skipped_mapping=0, skipped_duplicate=4)
    svc = _mock_service(result)
    app.dependency_overrides[get_sync_service] = lambda: svc
    app.dependency_overrides[get_registry] = lambda: InMemoryMarketRegistry()
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            resp = await c.post("/api/v1/markets/sync")
        assert resp.status_code == 200
        data = resp.json()
        assert data["skipped_duplicate_count"] == 4
        assert data["written_count"] == 0
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_sync_mapping_skip_reflected_in_response():
    result = SyncResult(fetched=3, mapped=2, written=2, skipped_mapping=1, skipped_duplicate=0)
    svc = _mock_service(result)
    app.dependency_overrides[get_sync_service] = lambda: svc
    app.dependency_overrides[get_registry] = lambda: InMemoryMarketRegistry()
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            resp = await c.post("/api/v1/markets/sync")
        assert resp.status_code == 200
        data = resp.json()
        assert data["skipped_mapping_count"] == 1
        assert data["written_count"] == 2
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Error scenarios
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_timeout_returns_504():
    svc = MagicMock()
    svc.run.side_effect = PolymarketTimeoutError()
    app.dependency_overrides[get_sync_service] = lambda: svc
    app.dependency_overrides[get_registry] = lambda: InMemoryMarketRegistry()
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            resp = await c.post("/api/v1/markets/sync")
        assert resp.status_code == 504
        assert "timed out" in resp.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_sync_upstream_http_error_returns_502():
    svc = MagicMock()
    svc.run.side_effect = PolymarketHTTPError(status_code=503, url="https://gamma-api.polymarket.com/markets")
    app.dependency_overrides[get_sync_service] = lambda: svc
    app.dependency_overrides[get_registry] = lambda: InMemoryMarketRegistry()
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            resp = await c.post("/api/v1/markets/sync")
        assert resp.status_code == 502
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Registry state integration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_endpoint_does_not_touch_registry_on_timeout():
    """On upstream failure the registry must remain unchanged."""
    registry = InMemoryMarketRegistry()
    svc = MagicMock()
    svc.run.side_effect = PolymarketTimeoutError()
    app.dependency_overrides[get_sync_service] = lambda: svc
    app.dependency_overrides[get_registry] = lambda: registry
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            await c.post("/api/v1/markets/sync")
        assert len(registry) == 0
    finally:
        app.dependency_overrides.clear()
