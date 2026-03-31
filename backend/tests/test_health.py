import pytest
from httpx import AsyncClient, ASGITransport
from backend.app.main import app


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_health_returns_200(client):
    resp = await client.get("/health")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_health_body(client):
    resp = await client.get("/health")
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "polymax-backend"
    assert data["version"] == "0.1.0"
