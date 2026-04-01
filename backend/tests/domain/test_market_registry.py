import pytest
from datetime import datetime, timezone
from pydantic import ValidationError

from backend.app.domain.market.models import Market, create_market
from backend.app.domain.market.types import Side, MarketStatus, Timeframe
from backend.app.domain.market.exceptions import (
    DuplicateMarketError,
    MarketNotFoundError,
    InvalidTimeframeError,
)
from backend.app.domain.market.registry import InMemoryMarketRegistry


# ── helpers ──────────────────────────────────────────────────────────────────

def make_market(id: str = "mkt-1", side: Side = Side.UP) -> Market:
    return create_market(
        id=id,
        event_id="evt-001",
        symbol="BTC",
        side=side,
    )


# ── model validation ─────────────────────────────────────────────────────────

def test_market_defaults_to_active():
    m = make_market()
    assert m.status == MarketStatus.ACTIVE


def test_market_timeframe_is_5m():
    m = make_market()
    assert m.timeframe == Timeframe.M5


def test_invalid_timeframe_raises():
    with pytest.raises((ValidationError, InvalidTimeframeError)):
        create_market(id="x", event_id="e", symbol="BTC", side=Side.UP, timeframe="1h")  # type: ignore


def test_empty_id_raises():
    with pytest.raises(ValidationError):
        Market(
            id="",
            event_id="e",
            symbol="BTC",
            timeframe=Timeframe.M5,
            side=Side.UP,
            created_at=__import__("datetime").datetime.now(),
            updated_at=__import__("datetime").datetime.now(),
        )


def test_with_status_returns_new_instance():
    m = make_market()
    updated = m.with_status(MarketStatus.CLOSED)
    assert updated.status == MarketStatus.CLOSED
    assert m.status == MarketStatus.ACTIVE  # original unchanged (frozen)


# ── registry: add / get ───────────────────────────────────────────────────────

def test_add_and_get():
    reg = InMemoryMarketRegistry()
    m = make_market("mkt-1")
    reg.add(m)
    assert reg.get("mkt-1") == m


def test_duplicate_add_raises():
    reg = InMemoryMarketRegistry()
    reg.add(make_market("mkt-1"))
    with pytest.raises(DuplicateMarketError):
        reg.add(make_market("mkt-1"))


def test_get_missing_raises():
    reg = InMemoryMarketRegistry()
    with pytest.raises(MarketNotFoundError):
        reg.get("nonexistent")


# ── registry: list ────────────────────────────────────────────────────────────

def test_list_all():
    reg = InMemoryMarketRegistry()
    reg.add(make_market("a"))
    reg.add(make_market("b"))
    assert len(reg.list_all()) == 2


def test_list_active_filters_inactive():
    reg = InMemoryMarketRegistry()
    reg.add(make_market("a"))
    reg.add(make_market("b"))
    reg.deactivate("b")
    active = reg.list_active()
    assert len(active) == 1
    assert active[0].id == "a"


# ── registry: status updates ──────────────────────────────────────────────────

def test_deactivate():
    reg = InMemoryMarketRegistry()
    reg.add(make_market("mkt-1"))
    m = reg.deactivate("mkt-1")
    assert m.status == MarketStatus.INACTIVE
    assert reg.get("mkt-1").status == MarketStatus.INACTIVE


def test_archive():
    reg = InMemoryMarketRegistry()
    reg.add(make_market("mkt-1"))
    m = reg.archive("mkt-1")
    assert m.status == MarketStatus.ARCHIVED


def test_update_status_missing_raises():
    reg = InMemoryMarketRegistry()
    with pytest.raises(MarketNotFoundError):
        reg.deactivate("ghost")


# ── side ──────────────────────────────────────────────────────────────────────

def test_up_and_down_sides():
    up = create_market(id="u", event_id="e", symbol="ETH", side=Side.UP)
    down = create_market(id="d", event_id="e", symbol="ETH", side=Side.DOWN)
    assert up.side == Side.UP
    assert down.side == Side.DOWN


# ── len ───────────────────────────────────────────────────────────────────────

def test_registry_len():
    reg = InMemoryMarketRegistry()
    assert len(reg) == 0
    reg.add(make_market("x"))
    assert len(reg) == 1


# ── end_date ──────────────────────────────────────────────────────────────────

def test_end_date_defaults_to_none():
    m = make_market()
    assert m.end_date is None


def test_end_date_can_be_set():
    ts = datetime(2024, 1, 1, 0, 5, 0, tzinfo=timezone.utc)
    m = create_market(id="m1", event_id="e1", symbol="BTC", side=Side.UP, end_date=ts)
    assert m.end_date == ts


def test_end_date_preserved_in_registry():
    ts = datetime(2024, 6, 15, 12, 35, 0, tzinfo=timezone.utc)
    m = create_market(id="m1", event_id="e1", symbol="ETH", side=Side.DOWN, end_date=ts)
    reg = InMemoryMarketRegistry()
    reg.add(m)
    assert reg.get("m1").end_date == ts


def test_end_date_none_preserved_in_registry():
    m = create_market(id="m1", event_id="e1", symbol="SOL", side=Side.UP)
    reg = InMemoryMarketRegistry()
    reg.add(m)
    assert reg.get("m1").end_date is None
