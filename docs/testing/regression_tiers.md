# POLYMAX — Regression Tier Contract

**Introduced:** v0.5.23 · **Last updated:** v0.5.23 (2026-04-01)

This document defines the three canonical regression tiers for POLYMAX:
Smoke, Standard, and Full.  It answers when to run each tier and provides
the exact executable commands.

For the full scenario matrix, see:
`docs/testing/discovery_regression_matrix.md`

For the canonical contract index, see:
`docs/testing/discovery_sync_contract_atlas.md`

---

## 1. The three tiers

| Tier | Scope | Tests | Approx time | Required? |
|------|-------|-------|-------------|-----------|
| **Smoke** | Health · Domain model · Service units · API endpoints | ~185 | < 1 s | REQUIRED — any code change |
| **Standard** | All automated tests (live excluded) | ~553 | < 5 s | REQUIRED — milestone / merge |
| **Full** | Standard + live Polymarket API shape test | ~554 | varies | RECOMMENDED — planned releases |

---

## 2. Tier definitions

### Smoke — minimum required suite

**What it covers:**
- `backend/tests/test_health.py` — HTTP readiness
- `backend/tests/domain/` — domain model invariants (Market, registry, exceptions)
- `backend/tests/services/` — service unit contracts (fetcher, discovery, sync, symbol)
- `backend/tests/api/` — API endpoint shape and response codes

**What it does NOT cover:**
- Integration contract tests (`backend/tests/integration/`)
- Polymarket HTTP client tests (`backend/tests/integrations/`)
- Live API shape tests (`@pytest.mark.live`)

**Executable command:**
```bash
python -m pytest backend/tests/test_health.py backend/tests/domain/ backend/tests/services/ backend/tests/api/ -q
```

**When Smoke is the minimum:**
- Any code change to a service, domain model, or API endpoint
- After dependency updates
- Before committing a fix or refactor

---

### Standard — full automated regression

**What it covers:**
- Everything in Smoke
- All integration contract tests (`backend/tests/integration/`)
- Polymarket HTTP client tests (`backend/tests/integrations/`)
- All P0 + P1 + P2 scenarios from the regression matrix

**What it does NOT cover:**
- Live Polymarket API tests (`@pytest.mark.live`) — skipped by default

**Executable command:**
```bash
python -m pytest backend/tests/ -q
```

**When Standard is required:**
- Before every versioned milestone commit
- Before merging any non-trivial change
- After any contract document update
- When a `LOCKED` contract surface is touched

---

### Full — complete verification including live API

**What it covers:**
- Everything in Standard
- Live Polymarket Gamma API shape test (`@pytest.mark.live`)
- Verifies real API response shape matches `backend/tests/fixtures/gamma_snapshot.json`

**Prerequisite:** network access to `https://gamma-api.polymarket.com`

**Executable command:**
```bash
python -m pytest backend/tests/ -q && python -m pytest backend/tests/ -m live -v
```

**When Full is recommended:**
- Before each versioned milestone release
- When Gamma API changelog / release notes mention changes
- After refreshing `backend/tests/fixtures/gamma_snapshot.json`
- When adding a new discovery rule or normalization field

---

## 3. Tier decision table by change type

| Change type | Minimum tier | Notes |
|-------------|-------------|-------|
| Doc-only change (`docs/`, `README`) | **Smoke** | No runtime behaviour changed |
| Contract doc only (`docs/testing/`) | **Smoke** | Run Standard to verify doc tests still pass |
| Fetcher-only change (`market_fetcher.py`) | **Standard** | Fetcher normalization contract locked |
| Discovery-only change (`market_discovery.py`) | **Standard** | Discovery selection contract locked |
| Sync-only change (`market_sync.py`) | **Standard** | Multiple contracts locked |
| API endpoint change (`routers/`) | **Standard** | Response shape contracts locked |
| Domain model change (`domain/market/`) | **Standard** | Registry and domain contracts locked |
| New normalization field or discovery rule | **Full** | Verify Gamma fixture coverage |
| Dependency upgrade | **Standard** | No live needed unless HTTP client affected |
| Pre-release verification | **Full** | Full shape + live verification |

---

## 4. Live and optional tests — placement outside Smoke

`@pytest.mark.live` tests are **explicitly excluded** from Smoke and Standard tiers.
They are network-dependent and skipped by default.

Rules:
- Live tests are **never** part of the Smoke requirement
- Live tests are **never** part of the Standard requirement
- Live tests are **always** opt-in: requires `pytest -m live` or the Full tier command
- A `SKIPPED` live test result is **not** a drift signal (see trigger policy)

Current live tests: 1
- `backend/tests/integration/test_live_gamma_contract_snapshot.py::TestLiveGammaAPIShape::test_live_gamma_api_shape_matches_required_fields`

---

## 5. Priority system alignment

The regression matrix uses P0 / P1 / P2 priority markers.  These map to tiers
as follows:

| Priority | Meaning | Tier coverage |
|----------|---------|--------------|
| P0 | Release-blocking — failure = system fundamentally broken | Smoke (core P0) + Standard (all P0) |
| P1 | Important — significant regression if fails | Standard |
| P2 | Helpful — edge-case or defensive coverage | Standard |

> **Note:** Smoke does not guarantee all P0 scenarios are covered — only those
> in the health / domain / services / api layers.  Full P0 coverage requires
> Standard.

---

## 6. Relationship to other docs

| Question | Answered by |
|----------|-------------|
| Which contracts are LOCKED? | `docs/testing/discovery_sync_contract_atlas.md` |
| Full scenario matrix (all 403 scenarios) | `docs/testing/discovery_regression_matrix.md` |
| When to refresh the Gamma fixture | `docs/testing/gamma_snapshot_refresh_policy.md` |
| Who decides on drift response | `docs/testing/gamma_drift_response_roles.md` |
| How to run the Gamma fixture refresh | `docs/testing/gamma_contract_workflow.md` |
