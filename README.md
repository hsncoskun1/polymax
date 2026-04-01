# POLYMAX

Local-first trading platform. Fetches, classifies, and monitors short-term crypto prediction markets on Polymarket. Backend is the single source of truth; frontend is display and trigger only.

## Quick Start

### Recommended — Launch Everything
```bash
python launcher/main.py
```
Starts backend + frontend, waits for readiness, opens browser. Ctrl+C to stop.
Reads host/port from `config/default.toml` — the single authoritative startup path.

### Individual Services (isolated development / debugging only)
```bash
# Backend only — hardcoded values; match config/default.toml defaults
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000

# Frontend only — port comes from frontend/vite.config.ts (hardcoded 5173)
cd frontend && npm run dev
```
> **Note:** Individual service commands use hardcoded values. If you change host/port in
> `config/default.toml`, you must also update these commands and `frontend/vite.config.ts`
> manually — they are not config-driven.

### Run Tests
```bash
# Backend
python -m pytest backend/tests/ -v

# Frontend
cd frontend && npm test
```

## Project Structure
```
POLYMAX/
├── launcher/main.py            # Starts backend + frontend, opens browser
├── backend/
│   ├── app/
│   │   ├── api/                # HTTP endpoints (health, markets + sync + discover)
│   │   ├── core/               # Config, logging
│   │   ├── domain/
│   │   │   └── market/         # Market entity, registry, exceptions, types
│   │   ├── integrations/
│   │   │   └── polymarket/     # HTTP client, config, exceptions
│   │   └── services/           # market_fetcher, market_discovery, market_sync
│   └── tests/
│       ├── api/                # API endpoint tests
│       ├── domain/             # Domain model tests
│       ├── integration/        # Contract lock integration tests (largest suite)
│       ├── integrations/       # Polymarket HTTP client tests
│       ├── services/           # Service unit tests
│       └── fixtures/           # gamma_snapshot.json (committed Gamma API fixture)
├── docs/
│   ├── governance/             # Decisions, branch rules, source-of-truth map, doc rules
│   ├── releases/               # Versioned delivery reports
│   └── testing/                # Test contracts, regression matrix, tier definitions
├── frontend/
│   ├── src/
│   │   ├── components/         # AppShell, HealthBadge, MarketList, SyncAction, DiscoverAction
│   │   ├── pages/              # UserPanel, AdminPanel
│   │   ├── lib/                # config.ts, api.ts
│   │   └── tests/
│   └── package.json
├── config/default.toml         # Central configuration (host, port, logging)
├── tools/
│   └── refresh_gamma_snapshot.py  # Manual CLI helper for Gamma API shape inspection
└── test-results/               # Test execution output (per-milestone pytest reports)
```

## Testing

### Regression tiers

```bash
# Smoke — fast sanity check (~185 tests, <1s)
python -m pytest backend/tests/test_health.py backend/tests/domain/ backend/tests/services/ backend/tests/api/ -q

# Standard — full automated regression (~594 tests)
python -m pytest backend/tests/ -q

# Full — standard + live Polymarket API shape check
python -m pytest backend/tests/ -q && python -m pytest backend/tests/ -m live -v
```

### Testing docs

| Document | Purpose |
|----------|---------|
| [`regression_tiers.md`](docs/testing/regression_tiers.md) | **Start here** — Smoke / Standard / Full tier definitions with executable pytest commands |
| [`discovery_sync_contract_atlas.md`](docs/testing/discovery_sync_contract_atlas.md) | Single-page index of all 13 locked/deferred contracts |
| [`discovery_regression_matrix.md`](docs/testing/discovery_regression_matrix.md) | Full scenario matrix (400+ test scenarios mapped to test files) |
| [`gamma_contract_workflow.md`](docs/testing/gamma_contract_workflow.md) | How to triage and refresh the Gamma API fixture |
| [`gamma_drift_response_roles.md`](docs/testing/gamma_drift_response_roles.md) | Who owns drift response decisions |
| [`gamma_snapshot_refresh_policy.md`](docs/testing/gamma_snapshot_refresh_policy.md) | When to refresh the fixture (required vs optional triggers) |

## Governance and releases

| Document | Purpose |
|----------|---------|
| [`docs/governance/decision-log.md`](docs/governance/decision-log.md) | Dated architectural and process decisions |
| [`docs/governance/branch-and-pr-rules.md`](docs/governance/branch-and-pr-rules.md) | Branch naming, scope isolation, commit discipline |
| [`docs/governance/source-of-truth-map.md`](docs/governance/source-of-truth-map.md) | Authoritative source for every class of information |
| [`docs/governance/documentation-rules.md`](docs/governance/documentation-rules.md) | Where each document type lives; README scope |
| [`docs/releases/`](docs/releases/) | Per-milestone delivery reports |

## Tech Stack
- Backend: Python 3.13 + FastAPI + Pydantic v2 + httpx
- Frontend: React 19 + Vite + TypeScript + Tailwind v4
- Launcher: Python (subprocess + readiness polling)
