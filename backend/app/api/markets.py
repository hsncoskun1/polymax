from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.app.domain.market.models import create_market
from backend.app.domain.market.registry import InMemoryMarketRegistry
from backend.app.domain.market.types import Side, MarketStatus, Timeframe
from backend.app.domain.market.exceptions import (
    DuplicateMarketError,
    MarketNotFoundError,
    InvalidTimeframeError,
)
from .deps import get_registry

router = APIRouter(prefix="/api/v1/markets", tags=["markets"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class CreateMarketRequest(BaseModel):
    id: str
    event_id: str
    symbol: str
    side: Side
    timeframe: Timeframe = Timeframe.M5
    source_timestamp: datetime | None = None


class UpdateStatusRequest(BaseModel):
    status: MarketStatus


class MarketResponse(BaseModel):
    id: str
    event_id: str
    symbol: str
    timeframe: Timeframe
    side: Side
    status: MarketStatus
    source_timestamp: datetime | None
    created_at: datetime
    updated_at: datetime


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=list[MarketResponse])
def list_markets(reg: InMemoryMarketRegistry = Depends(get_registry)):
    return reg.list_all()


@router.get("/active", response_model=list[MarketResponse])
def list_active_markets(reg: InMemoryMarketRegistry = Depends(get_registry)):
    return reg.list_active()


@router.get("/{market_id}", response_model=MarketResponse)
def get_market(market_id: str, reg: InMemoryMarketRegistry = Depends(get_registry)):
    try:
        return reg.get(market_id)
    except MarketNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("", response_model=MarketResponse, status_code=201)
def create_market_endpoint(
    body: CreateMarketRequest,
    reg: InMemoryMarketRegistry = Depends(get_registry),
):
    try:
        market = create_market(
            id=body.id,
            event_id=body.event_id,
            symbol=body.symbol,
            side=body.side,
            timeframe=body.timeframe,
            source_timestamp=body.source_timestamp,
        )
        reg.add(market)
        return market
    except InvalidTimeframeError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except DuplicateMarketError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.patch("/{market_id}/status", response_model=MarketResponse)
def update_market_status(
    market_id: str,
    body: UpdateStatusRequest,
    reg: InMemoryMarketRegistry = Depends(get_registry),
):
    try:
        return reg.update_status(market_id, body.status)
    except MarketNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
