"""Integration tests — Canonical Text Field Normalization Lock (v0.5.17).

These tests lock the canonical normalization contract for the text fields
slug and question in PolymarketFetchService._normalize().

Status B finding (v0.5.17): whitespace-only slug values were truthy and passed
downstream to the mapper, where they could silently cause mapping failures
(domain non_empty_string validator strips to "" → ValueError).
Production fix: both slug and question now strip leading/trailing whitespace;
whitespace-only slug → None; whitespace-only question → "".

Locked contracts
----------------
  SLUG-CANONICAL    — slug is always None or a stripped non-blank string.
                      Whitespace-only slug is canonicalised to None (not
                      passed downstream as a truthy blank value).
  QUESTION-CANONICAL — question is always a stripped string; never None.
                       Whitespace-only question normalises to "".
  SLUG-PREVENTS-FAILURE — canonical slug=None prevents the mapping failure
                           that whitespace-only slug previously caused when
                           used as symbol fallback in MarketMapper.
  DISCOVERY-SAFE    — canonical normalization does not change whether a
                      market becomes a discovery candidate (slug/question are
                      not discovery criteria; only active/orderBook/tokens/
                      dates/duration matter).
  DOWNSTREAM-SAFE   — mapper uses slug as symbol fallback; None is handled
                      gracefully (falls back to market_id).
  DOCS-RUNTIME-ALIGN — FetchedMarket and _normalize() docstrings match
                        runtime behavior for all documented slug/question
                        variants.

Tests:
  A  TestSlugCanonicalNormalization
  B  TestQuestionCanonicalNormalization
  C  TestSlugPreventsDownstreamMappingFailure
  D  TestDiscoverySafeNormalization
  E  TestDownstreamSafeNormalization
  F  test_docs_runtime_align_for_canonical_text_fields
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from backend.app.services.market_discovery import DiscoveryService
from backend.app.services.market_fetcher import FetchedMarket, PolymarketFetchService
from backend.app.services.market_sync import MarketMapper


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BASE_START = datetime(2024, 1, 1, tzinfo=timezone.utc)
_VALID_END = _BASE_START + timedelta(seconds=300)
_START_STR = "2024-01-01T00:00:00Z"
_VALID_END_STR = "2024-01-01T00:05:00Z"


def _minimal_raw(**overrides) -> dict:
    raw: dict = {
        "id": "m-1",
        "question": "Will BTC hit 100k?",
        "slug": "btc-100k",
        "active": True,
        "closed": False,
        "enableOrderBook": True,
        "tokens": [{"outcome": "YES"}, {"outcome": "NO"}],
        "startDate": _START_STR,
        "endDate": _VALID_END_STR,
        "events": [{"id": "evt-1"}],
    }
    raw.update(overrides)
    return raw


def _normalize_one(raw: dict) -> FetchedMarket | None:
    client = MagicMock()
    client.get_markets.return_value = [raw]
    svc = PolymarketFetchService(client)
    results = svc.fetch_markets()
    return results[0] if results else None


# ---------------------------------------------------------------------------
# A — slug canonical normalization
# ---------------------------------------------------------------------------


class TestSlugCanonicalNormalization:
    """A: slug is always None or a stripped non-blank string."""

    def test_slug_whitespace_only_normalizes_to_none(self):
        """Whitespace-only slug → None (canonical fix: prevents downstream mapping failure)."""
        for ws in ["   ", "  ", " ", "\t", "\n", "  \t  "]:
            m = _normalize_one(_minimal_raw(slug=ws))
            assert m is not None
            assert m.slug is None, (
                f"Expected None for whitespace-only slug {ws!r}, got {m.slug!r}"
            )

    def test_slug_none_normalizes_to_none(self):
        """slug: None in raw → None."""
        m = _normalize_one(_minimal_raw(slug=None))
        assert m is not None
        assert m.slug is None

    def test_slug_empty_string_normalizes_to_none(self):
        """slug: '' → None."""
        m = _normalize_one(_minimal_raw(slug=""))
        assert m is not None
        assert m.slug is None

    def test_slug_absent_normalizes_to_none(self):
        """slug: missing key → None."""
        raw = _minimal_raw()
        del raw["slug"]
        m = _normalize_one(raw)
        assert m is not None
        assert m.slug is None

    def test_slug_non_blank_preserved_and_stripped(self):
        """Non-blank slug → stripped value preserved."""
        m = _normalize_one(_minimal_raw(slug="  btc-100k  "))
        assert m is not None
        assert m.slug == "btc-100k"

    def test_slug_clean_value_unchanged(self):
        """Clean non-padded slug → unchanged."""
        m = _normalize_one(_minimal_raw(slug="eth-monthly"))
        assert m is not None
        assert m.slug == "eth-monthly"

    def test_slug_result_is_always_none_or_non_blank_string(self):
        """Contract: FetchedMarket.slug ∈ {None} ∪ {non-blank strings}."""
        cases = [None, "", "   ", "btc", "  eth  ", "sol-daily"]
        for slug_val in cases:
            m = _normalize_one(_minimal_raw(slug=slug_val))
            if m is not None:
                assert m.slug is None or (
                    isinstance(m.slug, str) and m.slug.strip() == m.slug and m.slug
                ), f"slug {slug_val!r} → {m.slug!r} violates canonical contract"


# ---------------------------------------------------------------------------
# B — question canonical normalization
# ---------------------------------------------------------------------------


class TestQuestionCanonicalNormalization:
    """B: question is always a stripped string; whitespace-only → ''."""

    def test_question_whitespace_only_normalizes_to_empty_string(self):
        """Whitespace-only question → '' (canonical strip policy)."""
        for ws in ["   ", "  ", " ", "\t", "  \t  "]:
            m = _normalize_one(_minimal_raw(question=ws))
            assert m is not None
            assert m.question == "", (
                f"Expected '' for whitespace-only question {ws!r}, got {m.question!r}"
            )

    def test_question_leading_trailing_whitespace_stripped(self):
        """Non-empty question: leading/trailing whitespace stripped."""
        m = _normalize_one(_minimal_raw(question="  Will BTC hit 100k?  "))
        assert m is not None
        assert m.question == "Will BTC hit 100k?"

    def test_question_none_normalizes_to_empty_string(self):
        """question: None → ''."""
        m = _normalize_one(_minimal_raw(question=None))
        assert m is not None
        assert m.question == ""

    def test_question_empty_string_normalizes_to_empty_string(self):
        """question: '' → ''."""
        m = _normalize_one(_minimal_raw(question=""))
        assert m is not None
        assert m.question == ""

    def test_question_is_always_a_string_never_none(self):
        """question field is always str; never None."""
        for val in [None, "", "   ", "BTC?", 0, False]:
            m = _normalize_one(_minimal_raw(question=val))
            if m is not None:
                assert isinstance(m.question, str), (
                    f"question={val!r} → {m.question!r} is not a string"
                )
                assert m.question is not None


# ---------------------------------------------------------------------------
# C — canonical slug prevents downstream mapping failure
# ---------------------------------------------------------------------------


class TestSlugPreventsDownstreamMappingFailure:
    """C: Canonical slug=None prevents the mapping failure whitespace-only slug caused."""

    def test_whitespace_slug_now_normalizes_to_none_not_passed_to_mapper(self):
        """After fix: whitespace-only slug → slug=None in FetchedMarket."""
        m = _normalize_one(_minimal_raw(id="good-id", slug="   ", question="unrelated"))
        assert m is not None
        assert m.slug is None, "Whitespace-only slug must be None, not '   '"

    def test_mapper_handles_slug_none_without_failure(self):
        """MarketMapper.map() succeeds when slug=None — falls back to market_id."""
        fetched = FetchedMarket(
            market_id="test-market",
            question="unrelated question",
            event_id="evt-1",
            slug=None,          # canonical: None is safe
            active=True,
            closed=False,
            source_timestamp=_BASE_START,
            end_date=_VALID_END,
            enable_order_book=True,
            tokens=[{"outcome": "YES"}, {"outcome": "NO"}],
        )
        mapper = MarketMapper()
        result = mapper.map(fetched)
        assert len(result) == 2, "Mapper should produce 2 markets with slug=None"

    def test_canonical_fix_prevents_the_previously_documented_risk(self):
        """End-to-end: whitespace-only slug in raw no longer causes mapping failure."""
        # Pre-fix: "   " would pass through as slug, then be used as symbol fallback
        # → non_empty_string("   ") → ValueError → mapping failure
        # Post-fix: slug normalized to None → market_id used as fallback → success
        raw = _minimal_raw(id="risk-market", slug="   ", question="no crypto here")
        m = _normalize_one(raw)
        assert m is not None
        assert m.slug is None

        # Confirm mapper now succeeds (slug=None is safe)
        mapper = MarketMapper()
        result = mapper.map(m)
        # market_id is "risk-market" → valid non-blank string → symbol fallback succeeds
        assert len(result) == 2


# ---------------------------------------------------------------------------
# D — discovery behavior unaffected by canonical normalization
# ---------------------------------------------------------------------------


class TestDiscoverySafeNormalization:
    """D: Canonical normalization does not change discovery outcomes."""

    def test_candidate_with_whitespace_slug_still_passes_discovery(self):
        """Whitespace-only slug normalizes to None; market still passes all 5 discovery rules."""
        raw = _minimal_raw(slug="   ")
        client = MagicMock()
        client.get_markets.return_value = [raw]
        svc = PolymarketFetchService(client)
        markets = svc.fetch_markets()

        assert len(markets) == 1
        m = markets[0]
        assert m.slug is None  # canonicalized

        # Pass through DiscoveryService — slug/question are not discovery criteria
        result = DiscoveryService().evaluate([m])
        assert len(result.candidates) == 1
        assert result.rejected_count == 0

    def test_question_whitespace_normalization_does_not_affect_discovery(self):
        """Whitespace-only question normalized to ''; discovery outcome unchanged."""
        raw = _minimal_raw(question="   ")
        client = MagicMock()
        client.get_markets.return_value = [raw]
        svc = PolymarketFetchService(client)
        markets = svc.fetch_markets()

        assert len(markets) == 1
        assert markets[0].question == ""

        result = DiscoveryService().evaluate(markets)
        assert len(result.candidates) == 1


# ---------------------------------------------------------------------------
# E — downstream safe: mapper handles canonical slug/question
# ---------------------------------------------------------------------------


class TestDownstreamSafeNormalization:
    """E: Mapper handles canonical None slug and empty question safely."""

    def test_mapper_with_none_slug_and_empty_question_uses_market_id_as_symbol(self):
        """slug=None, question='' → mapper falls back to market_id for symbol."""
        fetched = FetchedMarket(
            market_id="btc-market",
            question="",
            event_id="evt-1",
            slug=None,
            active=True,
            closed=False,
            source_timestamp=_BASE_START,
            end_date=_VALID_END,
            enable_order_book=True,
            tokens=[{"outcome": "YES"}, {"outcome": "NO"}],
        )
        mapper = MarketMapper()
        result = mapper.map(fetched)

        assert len(result) == 2
        # Symbol comes from market_id fallback
        for market in result:
            assert market.symbol == "btc-market"

    def test_mapper_with_valid_slug_uses_slug_derived_symbol(self):
        """When slug is non-None, mapper may use it for symbol extraction."""
        fetched = FetchedMarket(
            market_id="m-xyz",
            question="Will ETH rise?",
            event_id="evt-1",
            slug="eth-rise",
            active=True,
            closed=False,
            source_timestamp=_BASE_START,
            end_date=_VALID_END,
            enable_order_book=True,
            tokens=[{"outcome": "YES"}, {"outcome": "NO"}],
        )
        mapper = MarketMapper()
        result = mapper.map(fetched)

        assert len(result) == 2
        # Symbol extraction from question "Will ETH rise?" → "ETH" or slug fallback
        for market in result:
            assert market.symbol  # non-empty; exact value depends on extract_symbol


# ---------------------------------------------------------------------------
# F — docs/runtime alignment for canonical text fields
# ---------------------------------------------------------------------------


def test_docs_runtime_align_for_canonical_text_fields():
    """F: FetchedMarket and _normalize() docstrings match runtime for slug/question.

    The documented canonical contracts are:
    - slug: None or stripped non-blank string; whitespace-only → None
    - question: stripped string; whitespace-only → ''
    """
    # --- slug canonical variants ---
    slug_cases = [
        (None, None),
        ("", None),
        ("   ", None),
        ("\t", None),
        ("btc-100k", "btc-100k"),
        ("  eth-daily  ", "eth-daily"),
    ]
    for raw_slug, expected in slug_cases:
        m = _normalize_one(_minimal_raw(slug=raw_slug))
        assert m is not None
        assert m.slug == expected, (
            f"slug {raw_slug!r} → expected {expected!r}, got {m.slug!r}"
        )

    # --- question canonical variants ---
    question_cases = [
        (None, ""),
        ("", ""),
        ("   ", ""),
        ("  BTC?  ", "BTC?"),
        ("Will ETH rise?", "Will ETH rise?"),
    ]
    for raw_q, expected_q in question_cases:
        m = _normalize_one(_minimal_raw(question=raw_q))
        assert m is not None
        assert m.question == expected_q, (
            f"question {raw_q!r} → expected {expected_q!r}, got {m.question!r}"
        )

    # --- contract invariants ---
    # slug is always None or non-blank non-padded string
    for raw_slug, expected in slug_cases:
        m = _normalize_one(_minimal_raw(slug=raw_slug))
        if m and m.slug is not None:
            assert m.slug == m.slug.strip() and m.slug, "slug violates stripped non-blank invariant"

    # question is always a string and is stripped
    for raw_q, expected_q in question_cases:
        m = _normalize_one(_minimal_raw(question=raw_q))
        if m:
            assert isinstance(m.question, str)
            assert m.question == m.question.strip(), "question violates stripped invariant"
