# POLYMAX — Branch and PR Rules

**Area:** docs/governance · **Authority:** Operator

---

## Branch naming

All branches follow one of these prefixes:

| Prefix | Use |
|--------|-----|
| `feat/` | New feature or capability |
| `fix/` | Bug fix or production correction |
| `docs/` | Documentation-only changes (`docs/`, `README.md`) |
| `cleanup/` | Non-functional refactor, dead code removal, path fixes |
| `test/` | Test-only additions or corrections |

**Examples:**
- `feat/price-monitor`
- `fix/slug-whitespace-normalization`
- `docs/governance-and-release-registry`
- `cleanup/windows-path-artefacts`
- `test/tier-contract-lock`

---

## Scope isolation

Each branch covers one logical change. Mixed-concern branches are not allowed.

**Allowed:**
- A test-only branch that adds contract tests
- A doc-only branch that adds governance files
- A fix branch that corrects one production bug + its test

**Not allowed:**
- A branch that adds a feature AND rewrites docs AND refactors a service
- A branch that makes "cleanup while I'm here" changes outside its stated scope

If scope needs to expand, stop and report to the operator before continuing.

---

## Commit discipline

1. Tests must pass before committing (Standard tier minimum for any code change)
2. Each commit covers one logical change
3. Commit message format: `type(scope): description`
4. Never use `--no-verify`, `--amend` on published commits, or force push
5. Never stage `.env`, credentials, or sensitive files

**Examples:**
- `feat(discovery): add NO_ORDER_BOOK rejection rule`
- `fix(fetcher): normalize whitespace-only slug to None`
- `docs(governance): add decision log and branch rules`
- `test(integration): lock mapper multiplicity contract`

---

## PR / delivery report

After each versioned milestone:

1. Confirm tests pass (Standard tier)
2. Commit with descriptive message
3. Merge to `main` via `--no-ff` merge commit
4. Push to remote
5. Create delivery report in `docs/releases/v{version}-delivery-report.md`

The delivery report records:
- Scope / what was approved
- Changes made (files, decisions)
- Test results
- Remaining risks

Delivery reports are permanent records. They are not edited after the fact.

---

## What requires operator approval before proceeding

- Any change outside the approved step scope
- Adding a new external dependency
- Creating a new module, service, or abstraction layer
- Opening a new `docs/` subdirectory
- Any deferred decision being re-opened

If unsure whether something is in scope: stop and ask.
