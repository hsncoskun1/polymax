from datetime import datetime, timezone
from pydantic import BaseModel, field_validator, model_validator
from .types import Side, MarketStatus, Timeframe, SUPPORTED_TIMEFRAMES
from .exceptions import InvalidTimeframeError


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Market(BaseModel):
    """Core market entity. Backend is the single source of truth."""

    id: str
    event_id: str
    symbol: str                          # e.g. "BTC", "ETH"
    timeframe: Timeframe
    side: Side
    status: MarketStatus = MarketStatus.ACTIVE
    source_timestamp: datetime | None = None   # event start time (from Polymarket startDate)
    end_date: datetime | None = None           # when the market resolves (from Polymarket endDate)
    created_at: datetime
    updated_at: datetime

    model_config = {"frozen": True}

    @field_validator("timeframe", mode="before")
    @classmethod
    def validate_timeframe(cls, v: object) -> Timeframe:
        try:
            tf = Timeframe(v)
        except ValueError:
            raise InvalidTimeframeError(str(v))
        if tf not in SUPPORTED_TIMEFRAMES:
            raise InvalidTimeframeError(str(v))
        return tf

    @field_validator("id", "event_id", "symbol", mode="before")
    @classmethod
    def non_empty_string(cls, v: object) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("Field must be a non-empty string")
        return v.strip()

    def with_status(self, status: MarketStatus) -> "Market":
        return self.model_copy(update={"status": status, "updated_at": _utcnow()})

    def with_source_timestamp(self, ts: datetime) -> "Market":
        return self.model_copy(update={"source_timestamp": ts, "updated_at": _utcnow()})


def create_market(
    id: str,
    event_id: str,
    symbol: str,
    side: Side,
    timeframe: Timeframe = Timeframe.M5,
    source_timestamp: datetime | None = None,
    end_date: datetime | None = None,
) -> Market:
    """Factory that sets created_at / updated_at automatically."""
    now = _utcnow()
    return Market(
        id=id,
        event_id=event_id,
        symbol=symbol,
        timeframe=timeframe,
        side=side,
        source_timestamp=source_timestamp,
        end_date=end_date,
        created_at=now,
        updated_at=now,
    )
