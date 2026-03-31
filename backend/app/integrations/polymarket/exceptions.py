class PolymarketError(Exception):
    """Base class for Polymarket client errors."""


class PolymarketTimeoutError(PolymarketError):
    def __init__(self) -> None:
        super().__init__("Request to Polymarket timed out")


class PolymarketHTTPError(PolymarketError):
    def __init__(self, status_code: int, url: str) -> None:
        super().__init__(f"HTTP {status_code} from {url}")
        self.status_code = status_code


class PolymarketParseError(PolymarketError):
    def __init__(self, detail: str) -> None:
        super().__init__(f"Unexpected response shape: {detail}")
