"""Manual snapshot refresh helper for the Gamma API contract fixture.

Usage
-----
    python tools/refresh_gamma_snapshot.py

This script fetches a small sample of live Gamma API records, validates
their shape against the POLYMAX required-field contract, and prints a
structured report.  It does NOT automatically overwrite the committed
fixture — that step always requires human review and a deliberate commit.

Fixture location
----------------
    backend/tests/fixtures/gamma_snapshot.json

Workflow
--------
1.  Run this script to fetch fresh live records.
2.  Review the shape summary printed to stdout.
3.  If the shape is acceptable, MANUALLY update the fixture:
        backend/tests/fixtures/gamma_snapshot.json
4.  Run the full test suite to verify nothing regressed:
        pytest backend/tests/
5.  Commit the updated fixture with a clear message, e.g.:
        "fix(fixture): refresh gamma_snapshot.json — added <field>"
6.  See docs/testing/gamma_contract_workflow.md for the full triage guide.

Shape validation
----------------
The script returns exit code 1 and prints a [BREAKING DRIFT] warning when
any REQUIRED_FIELD is absent from ALL fetched records.  This indicates a
potentially breaking upstream change that needs contract review before the
fixture is updated.

Exit codes
----------
    0   Shape validation passed (required fields present).
    1   HTTP error, JSON parse error, or breaking drift detected.
"""
from __future__ import annotations

import sys
from typing import Any

# ---------------------------------------------------------------------------
# Canonical field contracts
# ---------------------------------------------------------------------------

#: Fields that _normalize() in market_fetcher.py explicitly reads and whose
#: absence changes the pipeline behaviour (conservative defaults, rejections,
#: or record skips).  If ALL fetched records are missing any of these fields,
#: it is a BREAKING DRIFT requiring contract review before fixture refresh.
REQUIRED_FIELDS: list[str] = [
    "id",            # absent → record skipped entirely
    "active",        # absent → defaults False; INACTIVE rule may miscategorise
    "closed",        # absent → defaults False; INACTIVE rule may miscategorise
    "startDate",     # absent → source_timestamp=None → MISSING_DATES rejection
    "endDate",       # absent → end_date=None → MISSING_DATES rejection
    "enableOrderBook",  # absent → None → NO_ORDER_BOOK rejection (conservative)
    "tokens",        # absent → None → EMPTY_TOKENS rejection (conservative)
]

#: Fields that _normalize() reads but handles gracefully when absent.
#: Absence from fetched records is an EXPECTED DRIFT: update the fixture
#: comment and re-run tests; no pipeline logic changes needed.
OPTIONAL_FIELDS: list[str] = [
    "question",   # absent → "" (empty string; symbol extraction falls back)
    "slug",       # absent → None (mapper falls back to market_id)
    "events",     # absent → event_id=None (not a rejection criterion)
]

# ---------------------------------------------------------------------------
# Gamma API endpoint
# ---------------------------------------------------------------------------

GAMMA_API_URL = "https://gamma-api.polymarket.com/markets"
_DEFAULT_PARAMS: dict[str, object] = {
    "active": "true",
    "enableOrderBook": "true",
    "limit": 5,
}

# ---------------------------------------------------------------------------
# Validation helpers (importable for tests)
# ---------------------------------------------------------------------------


def check_required_fields(records: list[dict[str, Any]]) -> list[str]:
    """Return REQUIRED_FIELDS absent from ALL records (breaking drift).

    A field is reported only when it is missing from every record in the
    sample — a single record containing it is enough to pass the check.
    An empty return list means shape validation passed.
    """
    if not records:
        return list(REQUIRED_FIELDS)
    return [f for f in REQUIRED_FIELDS if not any(f in r for r in records)]


def check_optional_fields(records: list[dict[str, Any]]) -> list[str]:
    """Return OPTIONAL_FIELDS absent from ALL records (expected drift)."""
    if not records:
        return list(OPTIONAL_FIELDS)
    return [f for f in OPTIONAL_FIELDS if not any(f in r for r in records)]


def summarize_shape(records: list[dict[str, Any]]) -> str:
    """Return a human-readable shape summary string."""
    if not records:
        return "  [WARN] No records returned from API."

    all_keys: set[str] = set()
    for r in records:
        all_keys |= set(r.keys())

    lines: list[str] = [
        f"  Records fetched   : {len(records)}",
        f"  All top-level keys: {sorted(all_keys)}",
        "",
    ]

    missing_required = check_required_fields(records)
    if missing_required:
        lines.append(
            f"  [BREAKING DRIFT] Required fields absent from all records: {missing_required}"
        )
    else:
        lines.append("  [OK] All required fields present in at least one record.")

    missing_optional = check_optional_fields(records)
    if missing_optional:
        lines.append(
            f"  [EXPECTED DRIFT?] Optional fields absent from all records: {missing_optional}"
        )
    else:
        lines.append("  [OK] All optional fields present.")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> int:  # pragma: no cover — network-dependent
    """Fetch live Gamma records and validate shape.  Returns exit code."""
    try:
        import httpx  # local import — only needed for CLI usage
    except ImportError:
        print("[ERROR] httpx not installed. Run: pip install httpx")
        return 1

    print("=== POLYMAX Gamma Snapshot Refresh Helper ===")
    print(f"Fetching from: {GAMMA_API_URL}")
    print()

    try:
        response = httpx.get(GAMMA_API_URL, params=_DEFAULT_PARAMS, timeout=10.0)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        print(f"[ERROR] HTTP request failed: {exc}")
        return 1

    try:
        body = response.json()
        records: list[dict[str, Any]] = body if isinstance(body, list) else body.get("markets", [])
    except Exception as exc:
        print(f"[ERROR] Failed to parse response JSON: {exc}")
        return 1

    print(summarize_shape(records))

    missing_required = check_required_fields(records)
    if missing_required:
        print()
        print("[FAIL] Breaking drift detected.")
        print("       DO NOT update the fixture without contract review.")
        print("       See docs/testing/gamma_contract_workflow.md for triage steps.")
        return 1

    print()
    print("Shape validation PASSED.")
    print()
    print("Next steps (do not skip):")
    print("  1. Review the shape summary above for unexpected changes.")
    print("  2. If acceptable, manually update the fixture:")
    print("       backend/tests/fixtures/gamma_snapshot.json")
    print("  3. Run full test suite:  pytest backend/tests/")
    print("  4. Commit the fixture with a descriptive message.")
    print("  5. See docs/testing/gamma_contract_workflow.md for the full guide.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
