"""Integration tests — Fetcher Input Normalization Contract Lock (v0.5.16).

These tests lock the boundary-case normalization behaviour of
PolymarketFetchService._normalize() at the contract level, ensuring that
the field-by-field policy documented in the _normalize() docstring matches
the runtime implementation.

Locked contracts
----------------
  EMPTY/WHITESPACE  — question: None/falsy → ""; slug: falsy → None;
                      question whitespace preserved; market_id blank → skip.
  DATETIME PARSING  — startDate/endDate: absent/non-str/blank/unparseable → None;
                      valid ISO-8601 → tz-aware datetime.
  BOOL COERCION     — active/closed: absent → False; int/str values → bool();
                      bool fields default-False when key missing.
  ENABLE_ORDER_BOOK — absent/None → None (conservative); non-None → bool().
  TOKENS            — absent/None/non-list → None (conservative); list → as-is.
  CANDIDATE RESPECT — Normalization output does not itself filter candidates;
                      all records pass through regardless of field values,
                      except records with missing/blank market_id.
  DOCS/RUNTIME ALIGN — The normalization policy table in _normalize() docstring
                       matches runtime behaviour for each documented variant.

Tests:
  A  test_fetcher_normalizes_empty_and_whitespace_fields_deterministically
  B  test_fetcher_parses_structural_datetime_fields_consistently
  C  test_fetcher_preserves_candidate_selection_responsibility_despite_input_variation
  D  test_fetcher_boolean_and_nullable_fields_follow_documented_contract
  E  test_fetcher_list_like_fields_follow_documented_contract
  F  test_docs_runtime_and_normalized_output_contract_align
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

from backend.app.services.market_fetcher import FetchedMarket, PolymarketFetchService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_START = "2024-01-01T00:00:00Z"
_VALID_END = "2024-01-01T00:05:00Z"


def _minimal_valid_raw(**overrides) -> dict:
    """Minimal raw dict that produces a valid FetchedMarket."""
    raw: dict = {
        "id": "m-1",
        "question": "Will BTC hit 100k?",
        "slug": "btc-100k",
        "active": True,
        "closed": False,
        "enableOrderBook": True,
        "tokens": [{"outcome": "YES"}, {"outcome": "NO"}],
        "startDate": _VALID_START,
        "endDate": _VALID_END,
        "events": [{"id": "evt-1"}],
    }
    raw.update(overrides)
    return raw


def _normalize_one(raw: dict) -> FetchedMarket | None:
    """Run the fetcher normalizer on a single raw record."""
    client = MagicMock()
    client.get_markets.return_value = [raw]
    svc = PolymarketFetchService(client)
    results = svc.fetch_markets()
    return results[0] if results else None


# ---------------------------------------------------------------------------
# A — empty and whitespace field normalization
# ---------------------------------------------------------------------------


class TestEmptyAndWhitespaceNormalization:
    """A: Empty/whitespace/falsy values for string fields follow documented policy."""

    def test_question_none_normalizes_to_empty_string(self):
        """question: None in raw → '' (never None) in FetchedMarket."""
        m = _normalize_one(_minimal_valid_raw(question=None))
        assert m is not None
        assert m.question == ""

    def test_question_missing_key_normalizes_to_empty_string(self):
        """question: absent key → ''."""
        raw = _minimal_valid_raw()
        del raw["question"]
        m = _normalize_one(raw)
        assert m is not None
        assert m.question == ""

    def test_question_empty_string_normalizes_to_empty_string(self):
        """question: "" → ''."""
        m = _normalize_one(_minimal_valid_raw(question=""))
        assert m is not None
        assert m.question == ""

    def test_question_whitespace_only_normalizes_to_empty_string(self):
        """question: whitespace-only string is stripped → '' (v0.5.17 canonical policy)."""
        m = _normalize_one(_minimal_valid_raw(question="   "))
        assert m is not None
        assert m.question == ""

    def test_slug_none_normalizes_to_none(self):
        """slug: None in raw → None in FetchedMarket."""
        m = _normalize_one(_minimal_valid_raw(slug=None))
        assert m is not None
        assert m.slug is None

    def test_slug_missing_key_normalizes_to_none(self):
        """slug: absent key → None."""
        raw = _minimal_valid_raw()
        del raw["slug"]
        m = _normalize_one(raw)
        assert m is not None
        assert m.slug is None

    def test_slug_empty_string_normalizes_to_none(self):
        """slug: '' → None (falsy → None policy)."""
        m = _normalize_one(_minimal_valid_raw(slug=""))
        assert m is not None
        assert m.slug is None

    def test_market_id_whitespace_only_skips_record(self):
        """market_id blank after strip → record skipped (return None)."""
        result = _normalize_one(_minimal_valid_raw(id="   "))
        assert result is None

    def test_market_id_is_stripped(self):
        """market_id with surrounding whitespace → stripped value in FetchedMarket."""
        m = _normalize_one(_minimal_valid_raw(id="  m-1  "))
        assert m is not None
        assert m.market_id == "m-1"


# ---------------------------------------------------------------------------
# B — datetime field normalization
# ---------------------------------------------------------------------------


class TestDatetimeFieldNormalization:
    """B: startDate/endDate boundary cases follow documented policy."""

    def test_start_date_absent_produces_none_source_timestamp(self):
        """startDate: missing key → source_timestamp = None."""
        raw = _minimal_valid_raw()
        del raw["startDate"]
        m = _normalize_one(raw)
        assert m is not None
        assert m.source_timestamp is None

    def test_end_date_absent_produces_none_end_date(self):
        """endDate: missing key → end_date = None."""
        raw = _minimal_valid_raw()
        del raw["endDate"]
        m = _normalize_one(raw)
        assert m is not None
        assert m.end_date is None

    def test_start_date_blank_string_produces_none(self):
        """startDate: '' → None (blank string is not parseable)."""
        m = _normalize_one(_minimal_valid_raw(startDate=""))
        assert m is not None
        assert m.source_timestamp is None

    def test_end_date_unparseable_string_produces_none(self):
        """endDate: non-ISO string → None + warning (no raise)."""
        m = _normalize_one(_minimal_valid_raw(endDate="not-a-date"))
        assert m is not None
        assert m.end_date is None

    def test_valid_iso_date_parsed_to_aware_datetime(self):
        """startDate: valid ISO-8601 → tz-aware datetime."""
        m = _normalize_one(_minimal_valid_raw(startDate="2024-01-01T00:00:00Z"))
        assert m is not None
        assert isinstance(m.source_timestamp, datetime)
        assert m.source_timestamp.tzinfo is not None
        assert m.source_timestamp == datetime(2024, 1, 1, tzinfo=timezone.utc)

    def test_asymmetric_dates_both_normalised_independently(self):
        """startDate present + endDate absent → source_timestamp set, end_date None."""
        raw = _minimal_valid_raw()
        del raw["endDate"]
        m = _normalize_one(raw)
        assert m is not None
        assert m.source_timestamp is not None
        assert m.end_date is None


# ---------------------------------------------------------------------------
# C — active/closed bool coercion and candidate responsibility
# ---------------------------------------------------------------------------


class TestBoolCoercionAndCandidateResponsibility:
    """C: active/closed coercion; normalization never filters candidates itself."""

    def test_active_absent_defaults_to_false(self):
        """active: missing key → False (bool default)."""
        raw = _minimal_valid_raw()
        del raw["active"]
        m = _normalize_one(raw)
        assert m is not None
        assert m.active is False

    def test_active_false_preserved(self):
        """active: False → False."""
        m = _normalize_one(_minimal_valid_raw(active=False))
        assert m is not None
        assert m.active is False

    def test_active_true_preserved(self):
        """active: True → True."""
        m = _normalize_one(_minimal_valid_raw(active=True))
        assert m is not None
        assert m.active is True

    def test_closed_absent_defaults_to_false(self):
        """closed: missing key → False."""
        raw = _minimal_valid_raw()
        del raw["closed"]
        m = _normalize_one(raw)
        assert m is not None
        assert m.closed is False

    def test_normalization_passes_inactive_record_without_filtering(self):
        """Inactive market is normalised and returned; filtering is discovery's job."""
        client = MagicMock()
        client.get_markets.return_value = [
            _minimal_valid_raw(id="active", active=True),
            _minimal_valid_raw(id="inactive", active=False),
        ]
        svc = PolymarketFetchService(client)
        results = svc.fetch_markets()

        assert len(results) == 2
        assert any(m.market_id == "inactive" for m in results)

    def test_normalization_passes_closed_record_without_filtering(self):
        """Closed market is normalised and returned; filtering is discovery's job."""
        client = MagicMock()
        client.get_markets.return_value = [
            _minimal_valid_raw(id="open", closed=False),
            _minimal_valid_raw(id="closed", closed=True),
        ]
        svc = PolymarketFetchService(client)
        results = svc.fetch_markets()

        assert len(results) == 2
        assert any(m.market_id == "closed" for m in results)


# ---------------------------------------------------------------------------
# D — enable_order_book: absent → None (conservative)
# ---------------------------------------------------------------------------


class TestEnableOrderBookNormalization:
    """D: enable_order_book: absent/None → None; non-None → bool()."""

    def test_enable_order_book_absent_produces_none(self):
        """enableOrderBook: missing key → None (conservative)."""
        raw = _minimal_valid_raw()
        del raw["enableOrderBook"]
        m = _normalize_one(raw)
        assert m is not None
        assert m.enable_order_book is None

    def test_enable_order_book_none_in_raw_produces_none(self):
        """enableOrderBook: None in raw → None."""
        m = _normalize_one(_minimal_valid_raw(enableOrderBook=None))
        assert m is not None
        assert m.enable_order_book is None

    def test_enable_order_book_true_preserved(self):
        """enableOrderBook: True → True."""
        m = _normalize_one(_minimal_valid_raw(enableOrderBook=True))
        assert m is not None
        assert m.enable_order_book is True

    def test_enable_order_book_false_preserved(self):
        """enableOrderBook: False → False."""
        m = _normalize_one(_minimal_valid_raw(enableOrderBook=False))
        assert m is not None
        assert m.enable_order_book is False

    def test_enable_order_book_none_passes_through_to_discovery(self):
        """enable_order_book=None is distinct from False; discovery rejects both."""
        m = _normalize_one(_minimal_valid_raw(enableOrderBook=None))
        assert m is not None
        # None means "field absent in upstream" — a different case from False
        assert m.enable_order_book is None  # not False


# ---------------------------------------------------------------------------
# E — tokens: absent/non-list → None; list → as-is
# ---------------------------------------------------------------------------


class TestTokensNormalization:
    """E: tokens field: absent/non-list → None; list (incl. empty) → as-is."""

    def test_tokens_absent_produces_none(self):
        """tokens: missing key → None."""
        raw = _minimal_valid_raw()
        del raw["tokens"]
        m = _normalize_one(raw)
        assert m is not None
        assert m.tokens is None

    def test_tokens_none_produces_none(self):
        """tokens: None in raw → None."""
        m = _normalize_one(_minimal_valid_raw(tokens=None))
        assert m is not None
        assert m.tokens is None

    def test_tokens_empty_list_preserved(self):
        """tokens: [] → [] (distinct from None; discovery rejects as EMPTY_TOKENS)."""
        m = _normalize_one(_minimal_valid_raw(tokens=[]))
        assert m is not None
        assert m.tokens == []

    def test_tokens_non_list_produces_none(self):
        """tokens: dict/string/int in raw → None (conservative)."""
        for bad_value in [{"a": 1}, "YES,NO", 42]:
            m = _normalize_one(_minimal_valid_raw(tokens=bad_value))
            assert m is not None, f"Expected FetchedMarket for tokens={bad_value!r}"
            assert m.tokens is None, f"Expected None for tokens={bad_value!r}, got {m.tokens!r}"

    def test_tokens_list_with_dicts_preserved_as_is(self):
        """tokens: valid list of dicts → preserved exactly."""
        toks = [{"outcome": "YES"}, {"outcome": "NO"}]
        m = _normalize_one(_minimal_valid_raw(tokens=toks))
        assert m is not None
        assert m.tokens == toks


# ---------------------------------------------------------------------------
# F — docs/runtime alignment: normalization policy contract
# ---------------------------------------------------------------------------


class TestNormalizationPolicyContractAlignment:
    """F: The normalization policy documented in _normalize() matches runtime."""

    def test_full_normalization_policy_table_matches_runtime_for_canonical_variants(self):
        """Comprehensive policy table contract: each documented variant verified."""
        # --- id policy: blank → skip ---
        assert _normalize_one(_minimal_valid_raw(id="   ")) is None
        assert _normalize_one(_minimal_valid_raw(id="  m  ")) is not None

        # --- question policy: None/missing/'' → ''; non-empty preserved ---
        for falsy_q in [None, "", 0, False]:
            m = _normalize_one(_minimal_valid_raw(question=falsy_q))
            assert m is not None
            assert m.question == "", f"Expected '' for question={falsy_q!r}"

        # --- slug policy: None/missing/''/whitespace-only → None ---
        for falsy_s in [None, "", "   "]:
            m = _normalize_one(_minimal_valid_raw(slug=falsy_s))
            assert m is not None
            assert m.slug is None, f"Expected None for slug={falsy_s!r}"
        # non-empty slug stripped and preserved
        m = _normalize_one(_minimal_valid_raw(slug="btc-slug"))
        assert m is not None
        assert m.slug == "btc-slug"

        # --- question whitespace-only → '' (v0.5.17 canonical policy) ---
        m = _normalize_one(_minimal_valid_raw(question="   "))
        assert m is not None
        assert m.question == ""

        # --- active/closed: absent → False ---
        raw = _minimal_valid_raw()
        del raw["active"]
        del raw["closed"]
        m = _normalize_one(raw)
        assert m is not None
        assert m.active is False
        assert m.closed is False

        # --- enable_order_book: absent → None; True/False → True/False ---
        raw = _minimal_valid_raw()
        del raw["enableOrderBook"]
        m = _normalize_one(raw)
        assert m.enable_order_book is None
        assert _normalize_one(_minimal_valid_raw(enableOrderBook=True)).enable_order_book is True
        assert _normalize_one(_minimal_valid_raw(enableOrderBook=False)).enable_order_book is False

        # --- tokens: None/non-list → None; [] → []; list → list ---
        assert _normalize_one(_minimal_valid_raw(tokens=None)).tokens is None
        assert _normalize_one(_minimal_valid_raw(tokens="bad")).tokens is None
        assert _normalize_one(_minimal_valid_raw(tokens=[])).tokens == []
        assert _normalize_one(_minimal_valid_raw(tokens=[{"a": 1}])).tokens == [{"a": 1}]

        # --- datetime: absent → None; invalid → None; valid → datetime ---
        raw_no_start = _minimal_valid_raw()
        del raw_no_start["startDate"]
        assert _normalize_one(raw_no_start).source_timestamp is None
        assert _normalize_one(_minimal_valid_raw(startDate="bad")).source_timestamp is None
        m = _normalize_one(_minimal_valid_raw(startDate="2024-06-01T12:00:00Z"))
        assert isinstance(m.source_timestamp, datetime)

    def test_conservative_none_policy_preserved_for_discovery_gating_fields(self):
        """enableOrderBook and tokens use conservative None for absent values.

        This ensures DiscoveryService can distinguish 'absent' from 'explicitly False/empty'
        and reject both conservatively.  The normalization layer must NOT replace
        None with False or [] to preserve this distinction.
        """
        # enableOrderBook absent → None (not False)
        raw_no_eob = _minimal_valid_raw()
        del raw_no_eob["enableOrderBook"]
        m_eob = _normalize_one(raw_no_eob)
        assert m_eob.enable_order_book is None
        assert m_eob.enable_order_book is not False  # None ≠ False

        # tokens absent → None (not [])
        raw_no_tok = _minimal_valid_raw()
        del raw_no_tok["tokens"]
        m_tok = _normalize_one(raw_no_tok)
        assert m_tok.tokens is None
        assert m_tok.tokens != []  # None ≠ []

    def test_event_id_normalization_follows_documented_contract(self):
        """event_id: extracted from first event dict's 'id' key; None when absent."""
        # Normal case: events present
        m = _normalize_one(_minimal_valid_raw(events=[{"id": "evt-42"}]))
        assert m is not None
        assert m.event_id == "evt-42"

        # Empty events list → None
        m = _normalize_one(_minimal_valid_raw(events=[]))
        assert m is not None
        assert m.event_id is None

        # Events key absent → None
        raw = _minimal_valid_raw()
        del raw["events"]
        m = _normalize_one(raw)
        assert m is not None
        assert m.event_id is None

        # Events is not a list → None
        m = _normalize_one(_minimal_valid_raw(events="invalid"))
        assert m is not None
        assert m.event_id is None
