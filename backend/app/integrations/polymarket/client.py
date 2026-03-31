import httpx
from .config import GAMMA_BASE_URL, DEFAULT_TIMEOUT, DEFAULT_MARKET_LIMIT
from .exceptions import (
    PolymarketError,
    PolymarketTimeoutError,
    PolymarketHTTPError,
    PolymarketParseError,
)


class PolymarketClient:
    """Read-only HTTP client for the Polymarket Gamma API.

    Responsibilities:
    - Issue HTTP GET requests to Polymarket public endpoints
    - Translate HTTP/network errors into domain-specific exceptions
    - Return raw dicts — callers decide how to map to domain models

    Not responsible for:
    - Writing to market registry
    - Discovery logic or filtering
    - Authentication (Gamma API is public for reads)
    """

    def __init__(
        self,
        base_url: str = GAMMA_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def _get(self, path: str, params: dict | None = None) -> object:
        """Shared GET helper. Returns parsed JSON or raises a PolymarketError."""
        url = f"{self._base_url}{path}"
        try:
            with httpx.Client(timeout=self._timeout) as http:
                resp = http.get(url, params=params)
        except httpx.TimeoutException:
            raise PolymarketTimeoutError()
        except httpx.RequestError as exc:
            raise PolymarketError(f"Request failed: {exc}") from exc

        if not resp.is_success:
            raise PolymarketHTTPError(resp.status_code, url)

        try:
            return resp.json()
        except Exception as exc:
            raise PolymarketParseError(f"JSON decode failed: {exc}") from exc

    def ping(self) -> bool:
        """Return True if the Gamma API responds successfully."""
        try:
            self._get("/markets", params={"limit": 1})
            return True
        except PolymarketError:
            return False

    def get_markets(self, limit: int = DEFAULT_MARKET_LIMIT) -> list[dict]:
        """Fetch raw market records from Gamma API.

        Returns a list of dicts. Shape validation is the caller's concern.
        Raises PolymarketError subclasses on network or HTTP failures.
        """
        data = self._get("/markets", params={"limit": limit})
        if not isinstance(data, list):
            raise PolymarketParseError(
                f"Expected list, got {type(data).__name__}"
            )
        return data
