from enum import Enum


class Timeframe(str, Enum):
    M5 = "5m"


class Side(str, Enum):
    UP = "up"
    DOWN = "down"


class MarketStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    CLOSED = "closed"
    ARCHIVED = "archived"


SUPPORTED_TIMEFRAMES = {Timeframe.M5}
