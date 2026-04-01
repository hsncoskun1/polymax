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
from backend.app.integrations.polymarket.exceptions import (
    PolymarketError,
    PolymarketTimeoutError,
)
from backend.app.services.market_sync import MarketSyncService
from .deps import get_registry, get_sync_service

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


class SyncResponse(BaseModel):
    """Summary of a single manual sync run."""

    fetched_count: int
    mapped_count: int
    written_count: int
    skipped_mapping_count: int
    skipped_duplicate_count: int


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/sync", response_model=SyncResponse)
def trigger_sync(service: MarketSyncService = Depends(get_sync_service)):
    """Manually trigger a single fetch → map → registry write cycle.

    Fetches active candidates from Polymarket, maps them to domain Markets,
    and writes new entries to the registry.  Duplicate entries are counted
    and skipped — the call is safe to repeat.

    Note: symbol and side fields are placeholder values at this stage.
    A future classification step will resolve them properly.
    """
    try:
        result = service.run()
    except PolymarketTimeoutError:
        raise HTTPException(status_code=504, detail="Polymarket API timed out")
    except PolymarketError as exc:
        raise HTTPException(status_code=502, detail=f"Polymarket upstream error: {exc}")

    return SyncResponse(
        fetched_count=result.fetched,
        mapped_count=result.mapped,
        written_count=result.written,
        skipped_mapping_count=result.skipped_mapping,
        skipped_duplicate_count=result.skipped_duplicate,
    )


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
