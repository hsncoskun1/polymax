"""Market discovery service — candidate selection with rejection tracking.

Evaluates normalised FetchedMarket records and partitions them into
*candidates* (suitable for tracking) and *rejected* (with stated reason).

This module does not schedule, loop, or persist.  It is a pure function
layer: given a list of FetchedMarket records it returns a DiscoveryResult.

Candidate selection rules (evaluated in order)
------------------------------------------------
1. INACTIVE             — active=False or closed=True.
2. NO_ORDER_BOOK        — enable_order_book is not True (covers False and None).
                          Markets without a CLOB order book lack intra-minute
                          price resolution.
3. EMPTY_TOKENS         — tokens is None or empty list.
                          Confirms binary YES/NO market structure.
4. MISSING_DATES        — source_timestamp or end_date is None.
5. DURATION_OUT_OF_RANGE — (end_date − source_timestamp) outside [240, 360] s.

Symbol extraction is NOT a rejection criterion.  extract_symbol() provides a
best-effort ticker; when it returns None the mapper falls back to slug then
market_id — a candidate is always writable downstream.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .market_fetcher import (
    CANDIDATE_DURATION_MAX_SECONDS,
    CANDIDATE_DURATION_MIN_SECONDS,
    FetchedMarket,
)


# ---------------------------------------------------------------------------
# Rejection reason
# ---------------------------------------------------------------------------


class RejectionReason(str, Enum):
    """Why a FetchedMarket was excluded from the candidate set."""

    INACTIVE = "inactive"
    NO_ORDER_BOOK = "no_order_book"
    EMPTY_TOKENS = "empty_tokens"
    MISSING_DATES = "missing_dates"
    DURATION_OUT_OF_RANGE = "duration_out_of_range"


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DiscoveryResult:
    """Summary of one candidate-selection pass.

    Attributes
    ----------
    fetched_count:
        Total number of FetchedMarket records evaluated.
    candidate_count:
        Records that passed all selection rules.
    rejected_count:
        Records that failed at least one rule.
    candidates:
        The FetchedMarket objects that passed — ready for mapping/sync.
    rejection_breakdown:
        How many records were rejected for each RejectionReason.
        Every RejectionReason key is always present (value may be 0).
    """

    fetched_count: int
    candidate_count: int
    rejected_count: int
    candidates: list[FetchedMarket]
    rejection_breakdown: dict[RejectionReason, int]


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class DiscoveryService:
    """Partitions FetchedMarket records into candidates and rejected.

    Stateless and deterministic — each evaluate() call is independent.
    """

    def evaluate(self, markets: list[FetchedMarket]) -> DiscoveryResult:
        """Evaluate *markets* and return a DiscoveryResult.

        Rules are applied in order; the first failing rule records the
        rejection reason and stops further evaluation for that market.
        """
        candidates: list[FetchedMarket] = []
        breakdown: dict[RejectionReason, int] = {r: 0 for r in RejectionReason}

        for market in markets:
            reason = self._reject_reason(market)
            if reason is None:
                candidates.append(market)
            else:
                breakdown[reason] += 1

        return DiscoveryResult(
            fetched_count=len(markets),
            candidate_count=len(candidates),
            rejected_count=len(markets) - len(candidates),
            candidates=candidates,
            rejection_breakdown=breakdown,
        )

    @staticmethod
    def _reject_reason(market: FetchedMarket) -> RejectionReason | None:
        """Return the first failing rule for *market*, or None if it is a candidate."""
        # Rule 1 — market must be live and tradeable
        if not market.active or market.closed:
            return RejectionReason.INACTIVE

        # Rule 2 — CLOB order book must be present
        if market.enable_order_book is not True:
            return RejectionReason.NO_ORDER_BOOK

        # Rule 3 — must have at least one outcome token (binary market structure)
        if not market.tokens:
            return RejectionReason.EMPTY_TOKENS

        # Rule 4 — both date fields must be present
        if market.source_timestamp is None or market.end_date is None:
            return RejectionReason.MISSING_DATES

        # Rule 5 — duration must fall within the 5m window
        duration = (market.end_date - market.source_timestamp).total_seconds()
        if not (CANDIDATE_DURATION_MIN_SECONDS <= duration <= CANDIDATE_DURATION_MAX_SECONDS):
            return RejectionReason.DURATION_OUT_OF_RANGE

        return None
