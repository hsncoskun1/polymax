# Gamma Drift Response — Ownership & Decision Matrix

**Introduced:** v0.5.20 · **Last updated:** v0.5.20 (2026-04-01)

This document answers the six ownership questions for upstream Gamma API drift
events.  It defines who acts, in what order, and at what decision threshold —
so that role ambiguity never blocks a response when drift is detected.

For the technical drift classification guide (expected vs breaking, field
contracts, fixture coverage), see:
`docs/testing/gamma_contract_workflow.md`

---

## 1. Project role definitions

POLYMAX is currently a single-operator project.  The three logical roles map
to the same person in solo development, but remain distinct for clarity and
future team expansion.

| Role | Responsibility in drift context | Who fills it today |
|------|---------------------------------|--------------------|
| **Operator** | Detects drift signals; initiates triage; makes all go/no-go decisions | Project owner (human) |
| **Implementer** | Executes approved technical changes (fixture updates, code fixes, tests) | Claude (under operator direction) |
| **Reviewer** | Validates that changes match the approved scope before committing | Operator (self-review) |

> In solo development, the Operator both initiates and reviews.
> Claude never makes unilateral production or fixture decisions.

---

## 2. Drift response ownership matrix

### 2.1 Expected drift (fixture refresh only)

Expected drift = optional field absent/changed; no pipeline logic affected.
See `docs/testing/gamma_contract_workflow.md` §5.1 for classification criteria.

| Step | Action | Owner | Gate |
|------|--------|-------|------|
| 1 | Run `python tools/refresh_gamma_snapshot.py` | Operator | — |
| 2 | Confirm drift is expected (optional field only) | Operator | Decision point — stop if breaking |
| 3 | Manually update `backend/tests/fixtures/gamma_snapshot.json` | Operator or Implementer (on request) | — |
| 4 | Run `pytest backend/tests/` and verify all pass | Operator or Implementer | Must pass before commit |
| 5 | Commit updated fixture with a descriptive message | Operator | Self-review complete |

**Decision threshold:** Operator can approve and commit expected drift solo,
without opening a milestone or requesting Claude's involvement.

---

### 2.2 Breaking drift (contract review required)

Breaking drift = required field renamed/removed/type-changed; pipeline behaviour
affected.  See `docs/testing/gamma_contract_workflow.md` §5.2 for classification.

| Step | Action | Owner | Gate |
|------|--------|-------|------|
| 1 | Run `python tools/refresh_gamma_snapshot.py` | Operator | — |
| 2 | Confirm drift is breaking (required field affected) | Operator | Decision point — escalate if breaking |
| 3 | Open a new versioned milestone (e.g. v0.5.x) describing the breaking change | Operator | Milestone opened before any code changes |
| 4 | Identify affected layers: `_normalize()`, discovery rules, tests, fixture | Operator (with Claude analysis) | — |
| 5 | Implement fix: update `_normalize()` + docstring + tests + fixture | Implementer (Claude), under operator approval | Operator approves each step |
| 6 | Run `pytest backend/tests/` — all must pass | Implementer + Operator | Must pass before commit |
| 7 | Operator reviews changes: do they match the approved scope? | Operator (self-review) | Review complete before commit |
| 8 | Commit + push | Operator or Implementer | Post-review only |

**Decision threshold:** Operator must open a milestone before Claude implements
any breaking drift fix.  No code changes are made until the operator explicitly
approves the scope.

---

## 3. Live test outcome → role-based action

| Live test outcome | Signal | First responder | Action |
|------------------|--------|-----------------|--------|
| `SKIPPED` (default) | No drift signal; test not run | — | No action needed |
| `PASSED` | Real API shape matches fixture | — | No action needed; fixture is current |
| `FAILED — missing key` | Field drift detected | **Operator** | Run `refresh_gamma_snapshot.py`; classify drift (§5 of workflow doc); follow §2.1 or §2.2 above |
| `FAILED — connection error` | Network unavailable, not a drift signal | **Operator** | Retry when connected; no fixture action |
| `FAILED — HTTP 4xx/5xx` | API endpoint issue, not necessarily shape drift | **Operator** | Verify endpoint URL; retry; do not update fixture until shape confirmed changed |

**Rule:** Claude never interprets live test failures independently.  The operator
always makes the first classification call.

---

## 4. Fixture refresh responsibility checklist

Before committing any fixture update, the responsible person (Operator or
Implementer on request) must confirm all items:

```
[ ] helper script output reviewed (no [BREAKING DRIFT] alert)
[ ] drift classified as expected (optional field only)
[ ] new fixture records include all required coverage
    (≥2 valid candidates, all 5 rejection reasons, edge cases)
[ ] pytest backend/tests/ — all pass (454 or more)
[ ] commit message describes the specific change
    format: "fix(fixture): refresh gamma_snapshot.json — <reason>"
[ ] no real token IDs or credentials committed
    (synthetic values used for token_id, dates)
```

**Gate:** Review tamamlanmadan fixture commit edilemez.
An incomplete checklist = do not commit.

---

## 5. Decision matrix — who escalates, who acts

| Scenario | Decision owner | Action owner | Escalation path |
|----------|---------------|--------------|-----------------|
| Expected drift, solo confirmation | Operator | Operator (or Claude on request) | — |
| Expected drift, unsure of impact | Operator | Claude (analysis only) | Operator reviews Claude's analysis before acting |
| Breaking drift detected | Operator | Claude (after milestone approved) | Operator opens milestone → Claude implements → Operator reviews |
| Ambiguous drift (can't classify) | Operator | Claude (analysis only) | Operator makes final call after analysis |
| Test failure (cause unclear) | Operator | Claude (diagnosis) | Operator approves any fix before commit |
| Fixture refresh (scheduled) | Operator | Operator | No escalation needed for expected drift |

---

## 6. What the operator decides; what Claude does not decide

**Operator always decides:**
- Is this drift expected or breaking?
- Should a milestone be opened?
- Is the fixture update acceptable?
- Can the commit go in?

**Claude never decides unilaterally:**
- Whether a breaking drift fix is safe to commit
- Whether a required field change is "minor enough" to skip review
- Whether to open or skip a milestone
- Whether a fixture change is within scope

---

## 7. Cross-references

| Artifact | What it provides |
|----------|-----------------|
| `docs/testing/gamma_contract_workflow.md` | Technical drift classification; field contracts; refresh procedure |
| `tools/refresh_gamma_snapshot.py` | CLI shape inspector; `REQUIRED_FIELDS` / `OPTIONAL_FIELDS` validation |
| `backend/tests/fixtures/gamma_snapshot.json` | Committed upstream contract fixture |
| `backend/tests/integration/test_live_gamma_contract_snapshot.py` | Automated fixture contract tests |
| `backend/tests/integration/test_upstream_drift_triage_workflow.py` | Workflow + helper contract tests |
| `backend/tests/integration/test_drift_response_ownership.py` | Ownership contract tests (this document) |
