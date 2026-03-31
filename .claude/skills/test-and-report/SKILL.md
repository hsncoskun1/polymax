---
name: test-and-report
description: Run tests after every code change and report results. Use this skill after any implementation, bug fix, or refactor in POLYMAX. Ensures no change is considered complete without verification. Triggers after code changes, on "test this", "verify", "check if it works", or when preparing for commit.
---

# Test and Report

Every change must be tested. Untested work is not complete.

## After Every Change

1. Identify appropriate tests for the change
2. Run them
3. Record results
4. Report pass/fail with details

## Test Strategy

- Unit tests for isolated logic
- Integration tests for API endpoints and data flow
- Manual verification for UI changes (use browser-use skill)
- If no test exists for the changed code, note this in the report

## Report Format

```
## Test Report - [date] - [what was changed]
- Tests run: [list]
- Passed: [count]
- Failed: [count]
- Skipped: [count]
- Details: [failure details if any]
- Verdict: PASS / FAIL / PARTIAL
```

## Rules

- Never mark a task as complete if tests fail
- If a test fails, investigate before retrying
- Report test results honestly, even if they reveal problems
- Save test reports to `test-results/` directory
- A change without test verification cannot be committed
