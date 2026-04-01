"""Tests for DiscoveryService candidate selection."""
from datetime import datetime, timedelta, timezone

import pytest

from backend.app.services.market_discovery import (
    DiscoveryResult,
    DiscoveryService,
    RejectionReason,
)
from backend.app.services.market_fetcher import (
    CANDIDATE_DURATION_MAX_SECONDS,
    CANDIDATE_DURATION_MIN_SECONDS,
    FetchedMarket,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BASE_START = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
_VALID_END = _BASE_START + timedelta(seconds=300)          # 5 m exactly — valid
_VALID_TOKENS = [{"outcome": "YES"}, {"outcome": "NO"}]


def _market(
    market_id: str = "m-1",
    question: str = "Will BTC hit 100k?",
    slug: str | None = "btc-100k",
    event_id: str | None = "evt-1",
    active: bool = True,
    closed: bool = False,
    source_timestamp: datetime | None = _BASE_START,
    end_date: datetime | None = _VALID_END,
    enable_order_book: bool | None = True,
    tokens: list | None = _VALID_TOKENS,
) -> FetchedMarket:
    return FetchedMarket(
        market_id=market_id,
        question=question,
        event_id=event_id,
        slug=slug,
        active=active,
        closed=closed,
        source_timestamp=source_timestamp,
        end_date=end_date,
        enable_order_book=enable_order_book,
        tokens=tokens,
    )


def _market_with_duration(seconds: int) -> FetchedMarket:
    """Return a fully valid market whose duration is exactly *seconds*."""
    return _market(
        source_timestamp=_BASE_START,
        end_date=_BASE_START + timedelta(seconds=seconds),
    )


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------


class TestCandidateSelection:
    def test_valid_market_is_a_candidate(self):
        result = DiscoveryService().evaluate([_market()])
        assert result.candidate_count == 1
        assert result.rejected_count == 0
        assert result.candidates[0].market_id == "m-1"

    def test_empty_input_returns_zero_result(self):
        result = DiscoveryService().evaluate([])
        assert result.fetched_count == 0
        assert result.candidate_count == 0
        assert result.rejected_count == 0
        assert result.candidates == []

    def test_multiple_valid_markets_all_become_candidates(self):
        markets = [_market(market_id=f"m-{i}") for i in range(4)]
        result = DiscoveryService().evaluate(markets)
        assert result.candidate_count == 4
        assert result.rejected_count == 0

    def test_fetched_count_equals_input_length(self):
        markets = [_market(market_id=f"m-{i}") for i in range(3)]
        result = DiscoveryService().evaluate(markets)
        assert result.fetched_count == 3

    def test_candidate_ids_preserved_in_order(self):
        markets = [_market(market_id=f"m-{i}") for i in range(3)]
        result = DiscoveryService().evaluate(markets)
        assert [m.market_id for m in result.candidates] == ["m-0", "m-1", "m-2"]


# ---------------------------------------------------------------------------
# Rule 1 — INACTIVE
# ---------------------------------------------------------------------------


class TestInactiveRejection:
    def test_inactive_market_is_rejected(self):
        result = DiscoveryService().evaluate([_market(active=False)])
        assert result.candidate_count == 0
        assert result.rejection_breakdown[RejectionReason.INACTIVE] == 1

    def test_closed_market_is_rejected(self):
        result = DiscoveryService().evaluate([_market(closed=True)])
        assert result.candidate_count == 0
        assert result.rejection_breakdown[RejectionReason.INACTIVE] == 1

    def test_inactive_and_closed_counts_as_one_rejection(self):
        result = DiscoveryService().evaluate([_market(active=False, closed=True)])
        assert result.rejection_breakdown[RejectionReason.INACTIVE] == 1
        assert result.rejected_count == 1

    def test_inactive_takes_priority_over_missing_dates(self):
        """First rule wins — missing dates should NOT be the reason."""
        market = _market(active=False, source_timestamp=None, end_date=None)
        result = DiscoveryService().evaluate([market])
        assert result.rejection_breakdown[RejectionReason.INACTIVE] == 1
        assert result.rejection_breakdown[RejectionReason.MISSING_DATES] == 0

    def test_inactive_takes_priority_over_no_order_book(self):
        market = _market(active=False, enable_order_book=False)
        result = DiscoveryService().evaluate([market])
        assert result.rejection_breakdown[RejectionReason.INACTIVE] == 1
        assert result.rejection_breakdown[RejectionReason.NO_ORDER_BOOK] == 0


# ---------------------------------------------------------------------------
# Rule 2 — NO_ORDER_BOOK
# ---------------------------------------------------------------------------


class TestNoOrderBookRejection:
    def test_enable_order_book_false_is_rejected(self):
        result = DiscoveryService().evaluate([_market(enable_order_book=False)])
        assert result.candidate_count == 0
        assert result.rejection_breakdown[RejectionReason.NO_ORDER_BOOK] == 1

    def test_enable_order_book_none_is_rejected(self):
        """Absent field → conservative reject (None is not True)."""
        result = DiscoveryService().evaluate([_market(enable_order_book=None)])
        assert result.candidate_count == 0
        assert result.rejection_breakdown[RejectionReason.NO_ORDER_BOOK] == 1

    def test_enable_order_book_true_passes(self):
        result = DiscoveryService().evaluate([_market(enable_order_book=True)])
        assert result.candidate_count == 1

    def test_no_order_book_takes_priority_over_empty_tokens(self):
        """Rule 2 before Rule 3 — NO_ORDER_BOOK is the recorded reason."""
        market = _market(enable_order_book=False, tokens=[])
        result = DiscoveryService().evaluate([market])
        assert result.rejection_breakdown[RejectionReason.NO_ORDER_BOOK] == 1
        assert result.rejection_breakdown[RejectionReason.EMPTY_TOKENS] == 0

    def test_no_order_book_takes_priority_over_missing_dates(self):
        market = _market(enable_order_book=False, source_timestamp=None)
        result = DiscoveryService().evaluate([market])
        assert result.rejection_breakdown[RejectionReason.NO_ORDER_BOOK] == 1
        assert result.rejection_breakdown[RejectionReason.MISSING_DATES] == 0


# ---------------------------------------------------------------------------
# Rule 3 — EMPTY_TOKENS
# ---------------------------------------------------------------------------


class TestEmptyTokensRejection:
    def test_empty_tokens_list_is_rejected(self):
        result = DiscoveryService().evaluate([_market(tokens=[])])
        assert result.candidate_count == 0
        assert result.rejection_breakdown[RejectionReason.EMPTY_TOKENS] == 1

    def test_tokens_none_is_rejected(self):
        """Absent field → conservative reject."""
        result = DiscoveryService().evaluate([_market(tokens=None)])
        assert result.candidate_count == 0
        assert result.rejection_breakdown[RejectionReason.EMPTY_TOKENS] == 1

    def test_single_token_passes(self):
        result = DiscoveryService().evaluate([_market(tokens=[{"outcome": "YES"}])])
        assert result.candidate_count == 1

    def test_two_tokens_passes(self):
        result = DiscoveryService().evaluate([_market(tokens=_VALID_TOKENS)])
        assert result.candidate_count == 1

    def test_empty_tokens_takes_priority_over_missing_dates(self):
        market = _market(tokens=[], source_timestamp=None)
        result = DiscoveryService().evaluate([market])
        assert result.rejection_breakdown[RejectionReason.EMPTY_TOKENS] == 1
        assert result.rejection_breakdown[RejectionReason.MISSING_DATES] == 0


# ---------------------------------------------------------------------------
# Rule 4 — MISSING_DATES
# ---------------------------------------------------------------------------


class TestMissingDatesRejection:
    def test_missing_source_timestamp_is_rejected(self):
        result = DiscoveryService().evaluate([_market(source_timestamp=None)])
        assert result.candidate_count == 0
        assert result.rejection_breakdown[RejectionReason.MISSING_DATES] == 1

    def test_missing_end_date_is_rejected(self):
        result = DiscoveryService().evaluate([_market(end_date=None)])
        assert result.candidate_count == 0
        assert result.rejection_breakdown[RejectionReason.MISSING_DATES] == 1

    def test_both_dates_missing_counts_as_one_rejection(self):
        result = DiscoveryService().evaluate([_market(source_timestamp=None, end_date=None)])
        assert result.rejection_breakdown[RejectionReason.MISSING_DATES] == 1
        assert result.rejected_count == 1

    def test_missing_dates_takes_priority_over_duration(self):
        """source_timestamp=None → MISSING_DATES, not DURATION_OUT_OF_RANGE."""
        market = _market(source_timestamp=None, end_date=_BASE_START + timedelta(hours=1))
        result = DiscoveryService().evaluate([market])
        assert result.rejection_breakdown[RejectionReason.MISSING_DATES] == 1
        assert result.rejection_breakdown[RejectionReason.DURATION_OUT_OF_RANGE] == 0


# ---------------------------------------------------------------------------
# Rule 5 — DURATION_OUT_OF_RANGE
# ---------------------------------------------------------------------------


class TestDurationRejection:
    def test_passes_exact_5_minutes(self):
        result = DiscoveryService().evaluate([_market_with_duration(300)])
        assert result.candidate_count == 1

    def test_passes_lower_boundary(self):
        result = DiscoveryService().evaluate([_market_with_duration(CANDIDATE_DURATION_MIN_SECONDS)])
        assert result.candidate_count == 1

    def test_passes_upper_boundary(self):
        result = DiscoveryService().evaluate([_market_with_duration(CANDIDATE_DURATION_MAX_SECONDS)])
        assert result.candidate_count == 1

    def test_rejects_one_second_below_lower_boundary(self):
        result = DiscoveryService().evaluate(
            [_market_with_duration(CANDIDATE_DURATION_MIN_SECONDS - 1)]
        )
        assert result.candidate_count == 0
        assert result.rejection_breakdown[RejectionReason.DURATION_OUT_OF_RANGE] == 1

    def test_rejects_one_second_above_upper_boundary(self):
        result = DiscoveryService().evaluate(
            [_market_with_duration(CANDIDATE_DURATION_MAX_SECONDS + 1)]
        )
        assert result.candidate_count == 0
        assert result.rejection_breakdown[RejectionReason.DURATION_OUT_OF_RANGE] == 1

    def test_rejects_very_short_duration(self):
        result = DiscoveryService().evaluate([_market_with_duration(60)])
        assert result.rejection_breakdown[RejectionReason.DURATION_OUT_OF_RANGE] == 1

    def test_rejects_hourly_duration(self):
        result = DiscoveryService().evaluate([_market_with_duration(3600)])
        assert result.rejection_breakdown[RejectionReason.DURATION_OUT_OF_RANGE] == 1

    def test_rejects_daily_duration(self):
        result = DiscoveryService().evaluate([_market_with_duration(86400)])
        assert result.rejection_breakdown[RejectionReason.DURATION_OUT_OF_RANGE] == 1


# ---------------------------------------------------------------------------
# Rejection breakdown counts
# ---------------------------------------------------------------------------


class TestRejectionBreakdown:
    def test_all_reason_keys_present_in_empty_result(self):
        result = DiscoveryService().evaluate([])
        for reason in RejectionReason:
            assert reason in result.rejection_breakdown
            assert result.rejection_breakdown[reason] == 0

    def test_all_reason_keys_present_in_valid_result(self):
        result = DiscoveryService().evaluate([_market()])
        for reason in RejectionReason:
            assert reason in result.rejection_breakdown

    def test_multiple_same_reason_accumulates(self):
        markets = [_market(active=False, market_id=f"m-{i}") for i in range(3)]
        result = DiscoveryService().evaluate(markets)
        assert result.rejection_breakdown[RejectionReason.INACTIVE] == 3

    def test_mixed_reasons_counted_separately(self):
        markets = [
            _market(market_id="ok"),
            _market(market_id="inactive", active=False),
            _market(market_id="no-ob", enable_order_book=False),
            _market(market_id="no-tok", tokens=[]),
            _market(market_id="no-dates", source_timestamp=None),
            _market(market_id="long", end_date=_BASE_START + timedelta(hours=1)),
        ]
        result = DiscoveryService().evaluate(markets)
        assert result.fetched_count == 6
        assert result.candidate_count == 1
        assert result.rejected_count == 5
        assert result.rejection_breakdown[RejectionReason.INACTIVE] == 1
        assert result.rejection_breakdown[RejectionReason.NO_ORDER_BOOK] == 1
        assert result.rejection_breakdown[RejectionReason.EMPTY_TOKENS] == 1
        assert result.rejection_breakdown[RejectionReason.MISSING_DATES] == 1
        assert result.rejection_breakdown[RejectionReason.DURATION_OUT_OF_RANGE] == 1

    def test_rejected_count_equals_sum_of_breakdown(self):
        markets = [
            _market(active=False),
            _market(enable_order_book=False),
            _market(tokens=None),
            _market(source_timestamp=None),
            _market_with_duration(9999),
        ]
        result = DiscoveryService().evaluate(markets)
        total_breakdown = sum(result.rejection_breakdown.values())
        assert result.rejected_count == total_breakdown

    def test_fetched_equals_candidate_plus_rejected(self):
        markets = [_market(market_id=f"m-{i}") for i in range(5)]
        markets[1] = _market(market_id="bad", active=False)
        result = DiscoveryService().evaluate(markets)
        assert result.fetched_count == result.candidate_count + result.rejected_count


# ---------------------------------------------------------------------------
# Symbol extraction — controlled fallback (not a rejection criterion)
# ---------------------------------------------------------------------------


class TestSymbolFallbackNotRejection:
    def test_market_with_no_extractable_symbol_and_slug_is_still_a_candidate(self):
        """No coin ticker in question or slug → fallback to market_id → still a candidate."""
        market = _market(
            question="Will the price go higher?",
            slug=None,
        )
        result = DiscoveryService().evaluate([market])
        assert result.candidate_count == 1
        assert result.rejected_count == 0

    def test_market_with_unknown_slug_but_no_coin_in_question_is_still_a_candidate(self):
        market = _market(
            question="General market question",
            slug="some-random-market-slug",
        )
        result = DiscoveryService().evaluate([market])
        assert result.candidate_count == 1

    def test_market_with_known_coin_in_question_is_a_candidate(self):
        market = _market(question="Will BTC reach $100k?", slug="btc-100k")
        result = DiscoveryService().evaluate([market])
        assert result.candidate_count == 1
