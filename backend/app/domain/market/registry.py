from typing import Protocol
from .models import Market, MarketStatus
from .exceptions import DuplicateMarketError, MarketNotFoundError


class MarketRegistry(Protocol):
    """Interface for market registry implementations."""

    def add(self, market: Market) -> None: ...
    def get(self, market_id: str) -> Market: ...
    def list_all(self) -> list[Market]: ...
    def list_active(self) -> list[Market]: ...
    def update_status(self, market_id: str, status: MarketStatus) -> Market: ...
    def deactivate(self, market_id: str) -> Market: ...
    def archive(self, market_id: str) -> Market: ...


class InMemoryMarketRegistry:
    """In-memory implementation. Sufficient until a persistence layer is needed."""

    def __init__(self) -> None:
        self._store: dict[str, Market] = {}

    def add(self, market: Market) -> None:
        if market.id in self._store:
            raise DuplicateMarketError(market.id)
        self._store[market.id] = market

    def get(self, market_id: str) -> Market:
        if market_id not in self._store:
            raise MarketNotFoundError(market_id)
        return self._store[market_id]

    def list_all(self) -> list[Market]:
        return list(self._store.values())

    def list_active(self) -> list[Market]:
        return [m for m in self._store.values() if m.status == MarketStatus.ACTIVE]

    def update_status(self, market_id: str, status: MarketStatus) -> Market:
        market = self.get(market_id)
        updated = market.with_status(status)
        self._store[market_id] = updated
        return updated

    def deactivate(self, market_id: str) -> Market:
        return self.update_status(market_id, MarketStatus.INACTIVE)

    def archive(self, market_id: str) -> Market:
        return self.update_status(market_id, MarketStatus.ARCHIVED)

    def __len__(self) -> int:
        return len(self._store)
