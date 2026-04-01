"""Symbol extraction — question/slug → canonical coin ticker.

Extracts a known cryptocurrency ticker (e.g. "BTC", "ETH", "SOL") from a
Polymarket question string or slug.  Designed to be simple and conservative:
only well-known coins are matched, unknown inputs return None.

Strategy
--------
1. Try the *question* text first (richer context).
2. Fall back to the *slug* if the question yields no match.
3. Return None when neither source produces a match — the caller decides
   what to do with unrecognised markets.

Matching rules
--------------
- Case-insensitive.
- Word-boundary anchors prevent partial matches (e.g. "FETCH" ≠ ETH,
  "bitcoin cash" triggers BTC via "bitcoin" — acceptable for now).
- Longer / more specific aliases are tried before shorter ones within each
  coin to avoid shadowing (e.g. "ethereum" before "eth").
- Slug uses the same patterns after replacing hyphens with spaces so that
  "btc-usd-100k" reads as "btc usd 100k".

Extension
---------
Add entries to SYMBOL_PATTERNS to support more coins.  Each entry is a
(ticker, [alias, ...]) pair; aliases are matched in order.
"""
from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Symbol catalogue
# (ticker → ordered list of aliases, longest/most-specific first)
# ---------------------------------------------------------------------------

_CATALOGUE: list[tuple[str, list[str]]] = [
    ("BTC",  ["bitcoin", "btc", "xbt"]),
    ("ETH",  ["ethereum", "eth"]),
    ("SOL",  ["solana", "sol"]),
    ("BNB",  ["binance coin", "bnb"]),
    ("XRP",  ["ripple", "xrp"]),
    ("DOGE", ["dogecoin", "doge"]),
    ("ADA",  ["cardano", "ada"]),
    ("AVAX", ["avalanche", "avax"]),
    ("MATIC",["polygon", "matic"]),
    ("LINK", ["chainlink", "link"]),
    ("DOT",  ["polkadot", "dot"]),
    ("UNI",  ["uniswap", "uni"]),
    ("LTC",  ["litecoin", "ltc"]),
    ("ATOM", ["cosmos", "atom"]),
    ("XLM",  ["stellar", "xlm"]),
]

# Pre-compile: pattern per alias, with word-boundary anchors
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (ticker, re.compile(rf"\b{re.escape(alias)}\b", re.IGNORECASE))
    for ticker, aliases in _CATALOGUE
    for alias in aliases
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_symbol(question: str | None, slug: str | None) -> str | None:
    """Return the canonical ticker for the coin mentioned in *question* or *slug*.

    Tries *question* first; if no match is found, normalises *slug* (hyphens
    → spaces) and tries again.  Returns None if neither yields a known ticker.

    Parameters
    ----------
    question:
        The market question text (e.g. "Will BTC close above $100,000?").
    slug:
        The Polymarket slug (e.g. "btc-above-100k-dec-2024").

    Returns
    -------
    str | None
        Canonical uppercase ticker ("BTC", "ETH", …) or None.
    """
    if question:
        match = _scan(question)
        if match:
            return match

    if slug:
        match = _scan(slug.replace("-", " "))
        if match:
            return match

    return None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _scan(text: str) -> str | None:
    """Return the first ticker whose alias is found in *text*, else None."""
    for ticker, pattern in _PATTERNS:
        if pattern.search(text):
            return ticker
    return None
