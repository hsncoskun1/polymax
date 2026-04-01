from fastapi import Depends

from backend.app.domain.market.registry import InMemoryMarketRegistry
from backend.app.integrations.polymarket.client import PolymarketClient
from backend.app.services.market_discovery import DiscoveryService
from backend.app.services.market_fetcher import PolymarketFetchService
from backend.app.services.market_sync import MarketSyncService

# Module-level singleton — in-memory, sufficient until persistence layer is added.
_registry = InMemoryMarketRegistry()


def get_registry() -> InMemoryMarketRegistry:
    return _registry


def get_sync_service(
    registry: InMemoryMarketRegistry = Depends(get_registry),
) -> MarketSyncService:
    """Build a MarketSyncService for the current request.

    A fresh PolymarketClient and PolymarketFetchService are created per
    request — no connection pooling is needed for an on-demand endpoint.
    The registry singleton is shared across requests.
    """
    client = PolymarketClient()
    fetcher = PolymarketFetchService(client)
    return MarketSyncService(fetcher, registry)


def get_discovery_service() -> tuple[PolymarketFetchService, DiscoveryService]:
    """Return a (fetcher, discovery) pair for the discover endpoint.

    DiscoveryService is stateless — a new instance per request is fine.
    No registry interaction; read-only.
    """
    client = PolymarketClient()
    fetcher = PolymarketFetchService(client)
    discovery = DiscoveryService()
    return fetcher, discovery
