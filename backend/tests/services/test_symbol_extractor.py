"""Tests for extract_symbol() — question/slug → canonical ticker."""
import pytest

from backend.app.services.symbol_extractor import extract_symbol


# ---------------------------------------------------------------------------
# Question extraction
# ---------------------------------------------------------------------------


class TestQuestionExtraction:
    def test_btc_full_name(self):
        assert extract_symbol("Will Bitcoin hit 100k?", None) == "BTC"

    def test_btc_ticker(self):
        assert extract_symbol("Will BTC close above $50,000?", None) == "BTC"

    def test_eth_full_name(self):
        assert extract_symbol("Will Ethereum surpass $5,000?", None) == "ETH"

    def test_eth_ticker(self):
        assert extract_symbol("ETH price above 3k by end of day?", None) == "ETH"

    def test_sol_full_name(self):
        assert extract_symbol("Will Solana reach $300?", None) == "SOL"

    def test_sol_ticker(self):
        assert extract_symbol("SOL above $200 tonight?", None) == "SOL"

    def test_case_insensitive_lower(self):
        assert extract_symbol("will btc pump today?", None) == "BTC"

    def test_case_insensitive_mixed(self):
        assert extract_symbol("Will Btc go up?", None) == "BTC"

    def test_question_takes_priority_over_slug(self):
        # question clearly says SOL; slug says btc — question wins
        assert extract_symbol("Will Solana reach $300?", "btc-price-target") == "SOL"


# ---------------------------------------------------------------------------
# Slug fallback
# ---------------------------------------------------------------------------


class TestSlugFallback:
    def test_btc_in_slug(self):
        assert extract_symbol(None, "btc-above-100k") == "BTC"

    def test_eth_in_slug(self):
        assert extract_symbol(None, "eth-price-3k") == "ETH"

    def test_sol_in_slug(self):
        assert extract_symbol(None, "sol-100-eoy") == "SOL"

    def test_slug_hyphen_normalised(self):
        # hyphens are replaced with spaces before scanning
        assert extract_symbol(None, "bitcoin-above-50000") == "BTC"

    def test_slug_used_when_question_has_no_match(self):
        assert extract_symbol("Will the price go up?", "eth-2000") == "ETH"


# ---------------------------------------------------------------------------
# None / empty inputs
# ---------------------------------------------------------------------------


class TestEmptyInputs:
    def test_both_none(self):
        assert extract_symbol(None, None) is None

    def test_empty_question_empty_slug(self):
        assert extract_symbol("", "") is None

    def test_empty_question_none_slug(self):
        assert extract_symbol("", None) is None

    def test_none_question_empty_slug(self):
        assert extract_symbol(None, "") is None

    def test_unknown_question_none_slug(self):
        assert extract_symbol("Will the market close higher?", None) is None

    def test_unknown_question_unknown_slug(self):
        assert extract_symbol("Random question about weather", "weather-forecast") is None


# ---------------------------------------------------------------------------
# Partial-match guard (word boundaries)
# ---------------------------------------------------------------------------


class TestPartialMatchGuard:
    def test_fetch_token_does_not_match_eth(self):
        # "FETCH" contains "ETH" as a substring — must NOT match
        assert extract_symbol("Will FETCH token rise?", "fetch-token") is None

    def test_solvent_does_not_match_sol(self):
        assert extract_symbol("Is the protocol solvent?", None) is None

    def test_battle_does_not_match_btc(self):
        # no substring of "battle" matches btc/bitcoin
        assert extract_symbol("Will the battle end?", None) is None

    def test_dotcom_does_not_match_dot(self):
        assert extract_symbol("Is this a dotcom bubble?", None) is None


# ---------------------------------------------------------------------------
# Additional known coins
# ---------------------------------------------------------------------------


class TestOtherCoins:
    def test_doge(self):
        assert extract_symbol("Will Dogecoin moon?", None) == "DOGE"

    def test_doge_ticker(self):
        assert extract_symbol("DOGE above 1 cent?", None) == "DOGE"

    def test_bnb(self):
        assert extract_symbol("Will BNB reach $700?", None) == "BNB"

    def test_xrp(self):
        assert extract_symbol("XRP wins the SEC case?", None) == "XRP"

    def test_ada(self):
        assert extract_symbol("ADA above $1?", None) == "ADA"

    def test_avax(self):
        assert extract_symbol("Will AVAX hit $50?", None) == "AVAX"

    def test_link(self):
        assert extract_symbol("Chainlink above $20?", None) == "LINK"

    def test_ltc(self):
        assert extract_symbol("Litecoin halving pump?", None) == "LTC"
