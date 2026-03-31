class MarketDomainError(Exception):
    """Base class for market domain errors."""


class DuplicateMarketError(MarketDomainError):
    def __init__(self, market_id: str) -> None:
        super().__init__(f"Market already exists: {market_id}")
        self.market_id = market_id


class MarketNotFoundError(MarketDomainError):
    def __init__(self, market_id: str) -> None:
        super().__init__(f"Market not found: {market_id}")
        self.market_id = market_id


class InvalidTimeframeError(MarketDomainError):
    def __init__(self, timeframe: str) -> None:
        super().__init__(f"Unsupported timeframe: {timeframe!r}. Only '5m' is supported.")
        self.timeframe = timeframe
