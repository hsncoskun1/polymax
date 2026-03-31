import pytest
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.api.deps import get_registry
from backend.app.domain.market.registry import InMemoryMarketRegistry


# ── fixture: fresh registry per test ─────────────────────────────────────────

@pytest.fixture
def client():
    """Each test gets a clean in-memory registry."""
    fresh = InMemoryMarketRegistry()
    app.dependency_overrides[get_registry] = lambda: fresh
    transport = ASGITransport(app=app)
    yield AsyncClient(transport=transport, base_url="http://test")
    app.dependency_overrides.clear()


VALID_MARKET = {
    "id": "mkt-btc-up",
    "event_id": "evt-001",
    "symbol": "BTC",
    "side": "up",
    "timeframe": "5m",
}


# ── list all ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_empty_registry(client):
    resp = await client.get("/api/v1/markets")
    assert resp.status_code == 200
    assert resp.json() == []


# ── create ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_market(client):
    resp = await client.post("/api/v1/markets", json=VALID_MARKET)
    assert resp.status_code == 201
    data = resp.json()
    assert data["id"] == "mkt-btc-up"
    assert data["symbol"] == "BTC"
    assert data["status"] == "active"
    assert data["timeframe"] == "5m"


@pytest.mark.asyncio
async def test_create_duplicate_returns_409(client):
    await client.post("/api/v1/markets", json=VALID_MARKET)
    resp = await client.post("/api/v1/markets", json=VALID_MARKET)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_create_invalid_timeframe_returns_422(client):
    bad = {**VALID_MARKET, "id": "mkt-x", "timeframe": "1h"}
    resp = await client.post("/api/v1/markets", json=bad)
    assert resp.status_code == 422


# ── get by id ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_market(client):
    await client.post("/api/v1/markets", json=VALID_MARKET)
    resp = await client.get("/api/v1/markets/mkt-btc-up")
    assert resp.status_code == 200
    assert resp.json()["id"] == "mkt-btc-up"


@pytest.mark.asyncio
async def test_get_missing_market_returns_404(client):
    resp = await client.get("/api/v1/markets/nonexistent")
    assert resp.status_code == 404


# ── list active ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_active_filters_inactive(client):
    await client.post("/api/v1/markets", json=VALID_MARKET)
    await client.post("/api/v1/markets", json={**VALID_MARKET, "id": "mkt-eth-down", "symbol": "ETH", "side": "down"})
    await client.patch("/api/v1/markets/mkt-eth-down/status", json={"status": "inactive"})

    resp = await client.get("/api/v1/markets/active")
    assert resp.status_code == 200
    ids = [m["id"] for m in resp.json()]
    assert "mkt-btc-up" in ids
    assert "mkt-eth-down" not in ids


# ── status update ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_status(client):
    await client.post("/api/v1/markets", json=VALID_MARKET)
    resp = await client.patch("/api/v1/markets/mkt-btc-up/status", json={"status": "closed"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "closed"


@pytest.mark.asyncio
async def test_update_status_missing_market_returns_404(client):
    resp = await client.patch("/api/v1/markets/ghost/status", json={"status": "inactive"})
    assert resp.status_code == 404
