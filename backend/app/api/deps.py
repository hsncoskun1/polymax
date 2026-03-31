from backend.app.domain.market.registry import InMemoryMarketRegistry

# Module-level singleton — in-memory, sufficient until persistence layer is added.
_registry = InMemoryMarketRegistry()


def get_registry() -> InMemoryMarketRegistry:
    return _registry
