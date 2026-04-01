# Gamma Snapshot Refresh Trigger Policy

**Introduced:** v0.5.21 · **Last updated:** v0.5.21 (2026-04-01)

This document defines when the committed Gamma API snapshot fixture
(`backend/tests/fixtures/gamma_snapshot.json`) must be refreshed, when it
must NOT be refreshed, and the optional proactive cadence available to the
operator.

For HOW to refresh (step-by-step procedure), see:
`docs/testing/gamma_contract_workflow.md`

For WHO is responsible for each refresh decision, see:
`docs/testing/gamma_drift_response_roles.md`

---

## 1. Required triggers — refresh MUST happen

| Trigger event | Signal | Refresh action |
|---------------|--------|---------------|
| `pytest -m live` fails with "missing key" | A required or optional Gamma field is absent | Run `tools/refresh_gamma_snapshot.py`; classify drift; follow workflow doc §5 |
| `tools/refresh_gamma_snapshot.py` prints `[BREAKING DRIFT]` | Required field absent from all live records | Contract review required before fixture update (see ownership doc §2.2) |
| Gamma API version upgrade announced | Planned schema change | Run helper script before any code changes; classify drift type |
| Fixture-based contract tests fail after Gamma API change | Pipeline normalization mismatch | Identify changed field; classify drift; update fixture |

> **Rule:** When a required trigger fires, refresh is not optional.
> Follow the procedure in `docs/testing/gamma_contract_workflow.md` §3.

---

## 2. Live test outcome → refresh decision

| Live test outcome | Refresh required? | Reason |
|------------------|------------------|--------|
| `SKIPPED` (default) | **No** | Test not run; no shape signal generated |
| `PASSED` | **No** | Real API shape matches fixture; no drift detected |
| `FAILED — missing key` | **Yes** | Shape drift confirmed; classify and act |
| `FAILED — connection error` | **No** | Network issue, not a shape drift; retry when connected |
| `FAILED — HTTP 4xx/5xx` | **No (investigate first)** | API endpoint issue; verify URL before treating as drift |

---

## 3. Negative triggers — refresh must NOT happen

Refresh should be explicitly skipped in these situations:

| Situation | Reason to skip |
|-----------|---------------|
| Live test is `SKIPPED` | No signal; test was not run |
| Live test `PASSED` | Shape is current; refresh would be speculative |
| Field **value** changed (price, volume, date) | Not a shape change; fixture is about structure, not values |
| Live test failed due to network/connection error | Not a drift signal |
| No live test has been run recently | Absence of signal ≠ drift; run helper before deciding |
| Speculative refresh without a trigger event | Unnecessary churn; increases risk of unreviewed fixture changes |

> **Rule:** When in doubt, run `tools/refresh_gamma_snapshot.py` first.
> If the output shows `[OK]`, the fixture is current — do not refresh.

---

## 4. Optional proactive refresh cadence (non-mandatory)

These are recommended, not required.  The operator may choose to follow
a proactive cadence to reduce the chance of extended undetected drift.

| Cadence event | Recommendation | Action |
|---------------|---------------|--------|
| Before each versioned milestone release | **Recommended** | Run `tools/refresh_gamma_snapshot.py`; refresh if any drift detected |
| When Gamma API changelog / release notes mention changes | **Recommended** | Run helper script immediately; classify drift before coding |
| When the live test has not been run in a long time (e.g., > 30 days) | **Optional** | Run `pytest -m live` to verify shape |
| When adding a new discovery rule or normalization field | **Recommended** | Verify fixture still covers all expected rejection reasons |

> **These cadence items are suggestions, not gates.**
> Missing a proactive refresh does not block a release.
> Only required triggers (§1) are mandatory.

---

## 5. Trigger policy decision table

```
Trigger event received?
│
├── YES → Is it a required trigger (§1)?
│          │
│          ├── YES → Run tools/refresh_gamma_snapshot.py
│          │          Classify drift (expected or breaking)
│          │          Follow gamma_contract_workflow.md §5
│          │
│          └── NO  → Is it a live-test failure?
│                     │
│                     ├── Missing key   → YES, refresh required (→ required trigger)
│                     ├── Connection err → NO, skip
│                     └── HTTP 4xx/5xx  → Investigate; do not refresh until shape confirmed changed
│
└── NO  → Is a proactive cadence event approaching (§4)?
           │
           ├── YES → Run tools/refresh_gamma_snapshot.py (optional)
           │          If [OK] → no action needed
           │          If drift → treat as required trigger
           │
           └── NO  → No refresh needed
```

---

## 6. When schema change suspicion exists but no trigger has fired

If a developer suspects Gamma API may have changed (e.g., noticed unexpected
market data in a manual observation), but no live test failure or helper alert
has fired:

1. **Do not update the fixture speculatively.**
2. Run `python tools/refresh_gamma_snapshot.py` to get a shape report.
3. If the report shows `[OK]` → suspicion was unfounded; no action.
4. If the report shows drift → treat it as a required trigger (§1).

---

## 7. Relationship to other docs

| Question | Answered by |
|----------|-------------|
| What counts as expected vs breaking drift? | `docs/testing/gamma_contract_workflow.md` §5 |
| Who owns the refresh decision? | `docs/testing/gamma_drift_response_roles.md` §2 |
| How to run the refresh step-by-step? | `docs/testing/gamma_contract_workflow.md` §3 |
| What fields are required / optional? | `tools/refresh_gamma_snapshot.py` (REQUIRED_FIELDS / OPTIONAL_FIELDS) |
| What does "fixture refresh checklist" require? | `docs/testing/gamma_drift_response_roles.md` §4 |
