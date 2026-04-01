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
from backend.app.services.market_discovery import DiscoveryService, RejectionReason
from backend.app.services.market_fetcher import PolymarketFetchService
from backend.app.services.market_sync import MarketSyncService
from .deps import get_discovery_service, get_registry, get_sync_service

router = APIRouter(prefix="/api/v1/markets", tags=["markets"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class CreateMarketRequest(BaseModel):
    id: str
    event_id: str
    symbol: str
    side: Side
    timeframe: Timeframe = Timeframe.M5
    source_timestamp: datetime | None = None
    end_date: datetime | None = None


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
    end_date: datetime | None
    created_at: datetime
    updated_at: datetime


class SyncResponse(BaseModel):
    """Summary of a single manual sync run.

    Summary semantics — processing window, not full registry state
    --------------------------------------------------------------
    fetched_count          — discovery CANDIDATES processed (not raw Polymarket
                             fetch count; rejected markets are not included).
    mapped_count           — domain Market objects created (written + skipped_dup).
    written_count          — new registry entries added in this call.
    skipped_mapping_count  — candidates that failed mapping.
    skipped_duplicate_count — candidates already present in registry (skipped).
    registry_total_count   — TOTAL registry entries after this sync, including
                             retained/stale entries from prior syncs.

    rejected_count         — markets rejected by discovery in this call
                             (did not become candidates).
    rejection_breakdown    — per-reason counts for rejected markets
                             (keys: inactive, no_order_book, empty_tokens,
                             missing_dates, duration_out_of_range; all keys
                             always present; 0 if no rejections for that reason).
                             Matches the format of POST /discover response.

    Full payload split: fetched_count + rejected_count = total discovery input
    (markets that passed the fetch layer, before any rejection).
    """

    fetched_count: int
    mapped_count: int
    written_count: int
    skipped_mapping_count: int
    skipped_duplicate_count: int
    registry_total_count: int
    rejected_count: int
    rejection_breakdown: dict[str, int]


class DiscoveryResponse(BaseModel):
    """Summary of a single manual discovery run.

    Fetch → evaluate only — no registry writes, no side effects.

    Field semantics
    ---------------
    fetched_count   — total raw input evaluated by DiscoveryService
                      (candidates + rejected_count = fetched_count).
    candidate_count — markets that passed all discovery rules.
    rejected_count  — markets that failed at least one discovery rule.
    rejection_breakdown — per-reason counts (canonical 5-key taxonomy;
                      all keys always present; 0 if no rejections for that
                      reason).

    Relationship to POST /sync
    --------------------------
    For the same raw payload both endpoints share the same discovery basis:
      discover.candidate_count  == sync.fetched_count
      discover.fetched_count    == sync.fetched_count + sync.rejected_count
      discover.rejected_count   == sync.rejected_count
      discover.rejection_breakdown == sync.rejection_breakdown

    Intentional differences (by design, not drift):
      /discover — discovery view: how many passed/failed evaluation.
      /sync     — processing + registry view: what was mapped and written.
      fetched_count means different things:
        /discover: total raw input (candidates + rejected)
        /sync: candidates only (rejected not counted in fetched_count)
    """

    fetched_count: int
    candidate_count: int
    rejected_count: int
    rejection_breakdown: dict[str, int]


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
        registry_total_count=result.registry_total,
        rejected_count=result.rejected_count,
        rejection_breakdown=result.rejection_breakdown,
    )


@router.post("/discover", response_model=DiscoveryResponse)
def trigger_discover(
    pair: tuple[PolymarketFetchService, DiscoveryService] = Depends(get_discovery_service),
):
    """Manually trigger a fetch → candidate selection pass.

    Fetches all available markets from Polymarket, evaluates each against
    the discovery rules, and returns a breakdown of candidates vs rejected.

    Does NOT write to the registry.  Safe to call at any time.
    """
    fetcher, discovery = pair
    try:
        markets = fetcher.fetch_markets()
    except PolymarketTimeoutError:
        raise HTTPException(status_code=504, detail="Polymarket API timed out")
    except PolymarketError as exc:
        raise HTTPException(status_code=502, detail=f"Polymarket upstream error: {exc}")

    result = discovery.evaluate(markets)

    return DiscoveryResponse(
        fetched_count=result.fetched_count,
        candidate_count=result.candidate_count,
        rejected_count=result.rejected_count,
        rejection_breakdown=result.string_breakdown,
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
            end_date=body.end_date,
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
