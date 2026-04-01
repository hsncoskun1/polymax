# Gamma API Contract Workflow

**Introduced:** v0.5.19 · **Last updated:** v0.5.19 (2026-04-01)

This document answers the canonical questions about how POLYMAX detects,
classifies, and responds to changes in the Gamma API upstream shape.

---

## 1. What is locked and where

| Artifact | Location | What it locks |
|----------|----------|---------------|
| Committed fixture | `backend/tests/fixtures/gamma_snapshot.json` | Expected Gamma API response shape (10 records) |
| Contract tests | `backend/tests/integration/test_live_gamma_contract_snapshot.py` | Schema, pipeline, discovery, sync, cross-layer invariants |
| Live marker | `backend/tests/conftest.py` | `@pytest.mark.live` — optional real-API check |
| Refresh helper | `tools/refresh_gamma_snapshot.py` | CLI tool for manual shape inspection |
| This document | `docs/testing/gamma_contract_workflow.md` | Drift triage process |

---

## 2. When to refresh the snapshot

Refresh `backend/tests/fixtures/gamma_snapshot.json` when:

- The `test_live_gamma_api_response_shape_matches_expected_schema` live test
  (run manually with `pytest -m live`) fails on a field that the real Gamma API
  now provides differently.
- A developer notices a new Gamma API field that POLYMAX should be normalising
  but currently ignores.
- A planned upgrade to the Gamma API client requires updated fixture records.

**Do not** refresh the fixture:
- Because a field value changed (price, volume, timestamp) — those are not
  shape changes.
- Speculatively, before confirming the live API actually changed.
- Without running the full test suite afterward.

---

## 3. Who refreshes the snapshot and how

**Anyone on the team can refresh the fixture** by following these steps:

### Step-by-step refresh procedure

```bash
# Step 1 — Inspect the live API shape (no writes yet)
python tools/refresh_gamma_snapshot.py

# Step 2 — Review the output
#   [OK]              → shape matches expectations; no fixture update needed
#   [EXPECTED DRIFT?] → optional field changed; update fixture comment if desired
#   [BREAKING DRIFT]  → required field changed; see Section 5 before proceeding

# Step 3 — Manually update the fixture (only after reviewing Step 2)
#   Edit: backend/tests/fixtures/gamma_snapshot.json
#   Keep: at least 2 valid candidates + all 5 rejection reasons + edge cases

# Step 4 — Run the full test suite
pytest backend/tests/

# Step 5 — Commit the updated fixture
git add backend/tests/fixtures/gamma_snapshot.json
git commit -m "fix(fixture): refresh gamma_snapshot.json — <reason>"
```

The helper script (`tools/refresh_gamma_snapshot.py`) **never writes to the
fixture automatically**.  Every fixture update is a deliberate human commit.

---

## 4. Which fields are sanitized before committing

The Gamma API is a **public API** — no authentication tokens, wallet
addresses, or user-specific data appear in market records.  The following
sanitization principles apply:

| Field type | Action |
|------------|--------|
| Market `id`, `slug`, `question` | Keep as-is; these are public identifiers |
| `events[*].id`, `events[*].title` | Keep as-is; public event metadata |
| `startDate`, `endDate` | Anonymise to synthetic but structurally valid ISO-8601 values in the committed fixture |
| `tokens[*].token_id` | Use synthetic values (e.g. `tok-yes-001`) in the committed fixture |
| Any credential / API key | Should never appear; if found, do not commit and report immediately |

> **Note:** The committed `gamma_snapshot.json` already uses synthetic dates
> and token IDs.  When refreshing from live data, replace real values with
> synthetic equivalents using the same format before committing.

---

## 5. Drift classification

A **drift** is any difference between the current committed fixture and the
live Gamma API response shape.  Drifts fall into two categories:

### 5.1 Expected drift — fixture update only

These changes do not affect existing pipeline logic.  Update the fixture and
re-run tests; no code changes required.

| Drift type | Examples | Action |
|------------|----------|--------|
| New optional field added | Gamma adds `volume`, `liquidity` | Update fixture to include the new field; update `OPTIONAL_FIELDS` in helper if desired |
| Optional field removed | `events` disappears from some records | Update fixture comment; verify `event_id=None` path still tested |
| Field value format cosmetic change | `startDate` uses a different but still valid ISO-8601 format | Update fixture values; verify datetime parsing still passes |
| New enum value in existing string field | `outcome` gains a new value | Update fixture; verify normalization handles the new value |

### 5.2 Breaking drift — contract review required

These changes affect the fetch → discovery → sync pipeline behaviour.  **Do
not update the fixture without reviewing the affected layers.**

| Drift type | Examples | Layers to review |
|------------|----------|-----------------|
| Required field renamed | `enableOrderBook` → `orderBookEnabled` | `_normalize()` in `market_fetcher.py`; discovery rule `NO_ORDER_BOOK`; fixture |
| Required field removed | `tokens` field disappears | `_normalize()` in `market_fetcher.py`; discovery rule `EMPTY_TOKENS`; fixture |
| Required field type change | `active` changes from `bool` to `"true"/"false"` string | `_normalize()` normalization policy; discovery rule `INACTIVE`; fixture |
| Structural shape change | `tokens` changes from list of dicts to list of strings | `_normalize()` tokens branch; discovery `EMPTY_TOKENS` gate; fixture |
| Date field semantics change | `startDate` no longer means event start time | `_normalize()` + `source_timestamp` semantics; duration rule; fixture |

**Contract review checklist for breaking drift:**

1. Read the `_normalize()` docstring in `backend/app/services/market_fetcher.py`.
2. Identify which field(s) are affected by the drift.
3. Determine the correct new normalization policy.
4. Update `_normalize()` and its docstring.
5. Update the relevant tests (normalization + discovery + sync).
6. Update the fixture to reflect the new shape.
7. Update this document if the field contract table changes.

---

## 6. How to interpret live test skip/fail output

The live test is:

```
backend/tests/integration/test_live_gamma_contract_snapshot.py::test_live_gamma_api_response_shape_matches_expected_schema
```

It is marked `@pytest.mark.live` and **skipped by default** in CI and local
runs.  To run it:

```bash
pytest -m live backend/tests/
```

### Interpretation

| Live test outcome | Meaning | Action |
|------------------|---------|--------|
| **SKIPPED** (default) | Test not run; no network access attempted | Normal; no action needed |
| **PASSED** | Real Gamma API shape matches fixture schema | No drift; fixture is current |
| **FAILED — missing key** | Gamma removed or renamed a field that the live test checks | Check if it is a required or optional field; follow drift classification in Section 5 |
| **FAILED — connection error** | Network unavailable | Not a drift signal; retry when connected |
| **FAILED — HTTP 4xx/5xx** | Gamma API endpoint changed or is down | Verify the endpoint URL in `polymarket/client.py`; not necessarily a shape drift |

---

## 7. Required fields reference

The following table documents every Gamma API field that `_normalize()` reads,
its normalization behaviour, and whether its absence constitutes a breaking
drift.

| Field | Drift class | Absent behaviour | Discovery impact |
|-------|-------------|-----------------|-----------------|
| `id` | **Breaking** | Record skipped (return None) | No candidate produced |
| `active` | **Breaking** | Defaults to `False` → INACTIVE rejection | Candidate lost |
| `closed` | **Breaking** | Defaults to `False` → INACTIVE rejection | Candidate lost |
| `startDate` | **Breaking** | `source_timestamp = None` → MISSING_DATES rejection | Candidate lost |
| `endDate` | **Breaking** | `end_date = None` → MISSING_DATES / DURATION_OUT_OF_RANGE | Candidate lost |
| `enableOrderBook` | **Breaking** | `None` (conservative) → NO_ORDER_BOOK rejection | Candidate lost |
| `tokens` | **Breaking** | `None` (conservative) → EMPTY_TOKENS rejection | Candidate lost |
| `question` | Expected | `""` (empty string); symbol extraction falls back to slug/id | No discovery impact |
| `slug` | Expected | `None`; mapper uses market_id for symbol | No discovery impact |
| `events` | Expected | `event_id = None`; not a rejection criterion | No discovery impact |

---

## 8. Fixture structure requirements

When updating the fixture, ensure it still covers:

| Coverage requirement | Minimum records |
|----------------------|-----------------|
| Valid candidates (active, order book, tokens, dates, 5m duration) | ≥ 2 |
| `INACTIVE` rejection (`active=False` or `closed=True`) | ≥ 1 |
| `NO_ORDER_BOOK` rejection (`enableOrderBook=False` or absent) | ≥ 1 |
| `EMPTY_TOKENS` rejection (`tokens=[]` or absent) | ≥ 1 |
| `MISSING_DATES` rejection (`startDate` or `endDate` absent) | ≥ 1 |
| `DURATION_OUT_OF_RANGE` rejection (duration < 240s or > 360s) | ≥ 1 |

The current `gamma_snapshot.json` has 10 records covering all requirements.

---

## 9. Quick reference commands

```bash
# Check live shape without touching fixture
python tools/refresh_gamma_snapshot.py

# Run live contract test (requires network)
pytest -m live backend/tests/

# Run all fixture-based (no-network) contract tests
pytest backend/tests/integration/test_live_gamma_contract_snapshot.py

# Run full test suite
pytest backend/tests/

# Run drift triage workflow tests
pytest backend/tests/integration/test_upstream_drift_triage_workflow.py
```
