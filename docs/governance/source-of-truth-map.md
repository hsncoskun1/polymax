# POLYMAX — Source of Truth Map

**Area:** docs/governance · **Authority:** Operator
**Purpose:** For any piece of information, this map says which file is authoritative.
When two sources conflict, the file listed here wins.

---

## Application configuration

| Information | Authoritative source |
|-------------|---------------------|
| Backend host / port | `config/default.toml` → `[backend]` |
| Frontend host / port | `config/default.toml` → `[frontend]` |
| Logging level / format | `config/default.toml` → `[logging]` |

**Rule:** Launcher, backend startup, and any tooling that needs host/port must read
`config/default.toml`. Hardcoded defaults in source files are fallbacks only.

---

## Domain model

| Information | Authoritative source |
|-------------|---------------------|
| `Market` field definitions | `backend/app/domain/market/models.py` |
| `MarketStatus` / `Side` enums | `backend/app/domain/market/types.py` |
| Registry contract (add-only) | `backend/app/domain/market/registry.py` |
| Registry exceptions | `backend/app/domain/market/exceptions.py` |

**Rule:** Frontend `Market` and `SyncResult` TypeScript interfaces in
`frontend/src/lib/api.ts` are derived from the backend domain model and must be
kept in sync manually. Backend is authoritative; frontend is a mirror.

---

## Fetcher / normalization

| Information | Authoritative source |
|-------------|---------------------|
| `FetchedMarket` field definitions | `backend/app/services/market_fetcher.py` — `FetchedMarket` docstring |
| `_normalize()` field policy table | `backend/app/services/market_fetcher.py` — `_normalize()` docstring |
| `source_timestamp` semantics | `backend/app/services/market_fetcher.py` — `FetchedMarket.source_timestamp` docstring |

---

## Discovery rules

| Information | Authoritative source |
|-------------|---------------------|
| Rejection rule set (5 rules, order) | `backend/app/services/market_discovery.py` — `DiscoveryService.evaluate()` docstring |
| Rejection taxonomy (enum → string) | `backend/app/services/market_discovery.py` — `DiscoveryResult.string_breakdown` docstring |
| Duration semantics (total span, [240 s, 360 s]) | `backend/app/services/market_discovery.py` — `DURATION_OUT_OF_RANGE` rule |

---

## Sync pipeline

| Information | Authoritative source |
|-------------|---------------------|
| `SyncResult` field semantics | `backend/app/services/market_sync.py` — `SyncResult` docstring |
| Three-gate pipeline model | `backend/app/services/market_sync.py` — `SyncResult` "Three pipeline failure gates" section |
| Pipeline edge-state reference table | `backend/app/services/market_sync.py` — `SyncResult` "Pipeline edge-state reference table" section |
| Mapper multiplicity (×2 per candidate) | `backend/app/services/market_sync.py` — `MarketMapper` docstring + `MARKETS_PER_CANDIDATE` constant |
| Registry lifecycle / add-only decision | `backend/app/services/market_sync.py` — `MarketSyncService._LIFECYCLE_NOTE` |

---

## API contracts

| Information | Authoritative source |
|-------------|---------------------|
| Discover endpoint response shape | `backend/app/api/routers/markets.py` — `DiscoveryResponse` docstring |
| Sync endpoint response shape | `backend/app/api/routers/markets.py` — `SyncResponse` |
| intentional `fetched_count` semantic difference (discover vs sync) | `backend/app/api/routers/markets.py` — `DiscoveryResponse` docstring |

---

## Health and version

| Information | Authoritative source | Notes |
|-------------|---------------------|-------|
| Backend version string | `config/default.toml` → `[app] version` | Read by `health.py` via `load_config()` |
| Backend health response | `GET /health` → `{"status","service","version"}` | `version` derived from config |
| Backend version in UI | `AdminPanel` fetches `/health` on mount | Displayed in "Backend" StatusChip |
| Frontend version | **Not available** | `package.json version = "0.0.0"` (Vite default); no build-time injection configured; Frontend chip shows "—" |

**Rule:** Backend version has one authoritative source (`config/default.toml`) and one authoritative endpoint (`GET /health`). Frontend version has no authoritative source in this repo at this stage; do not fabricate a value.

## Network and connectivity

| Information | Authoritative source | Drift risk |
|-------------|---------------------|------------|
| Backend host / port (runtime) | `config/default.toml` → `[backend]` — read by launcher and `backend/app/core/config.py` | LOW |
| Frontend host / port (Vite dev server) | `frontend/vite.config.ts` — hardcoded `host: "127.0.0.1", port: 5173` | LOW NON-BLOCKER — Vite cannot read TOML at runtime; values intentionally match config defaults; documented known drift |
| Frontend → backend URL (runtime) | `frontend/src/lib/config.ts` — `VITE_BACKEND_URL` env var, fallback `http://127.0.0.1:8000` | LOW — fallback matches config; env var override available for non-default deployments; by design |
| CORS allowed origins | `config/default.toml` → `[frontend] host + port` — derived in `backend/app/main.py` `_build_cors_origins()` | LOW — config-driven since v0.5.29; `localhost` alias kept explicitly (browser security context difference) |

**localhost alias rationale:** CORS always includes both `http://{frontend_host}:{port}` (from config) and `http://localhost:{port}`. Browsers treat `127.0.0.1` and `localhost` as distinct origins in some security contexts (e.g. cookies, service workers). Keeping the alias prevents silent auth failures if a user opens `http://localhost:5173` instead of `http://127.0.0.1:5173`.

**Vite config known drift:** `frontend/vite.config.ts` hardcodes `port: 5173` and `host: "127.0.0.1"`. Vite is a Node.js tool that cannot read `config/default.toml` without a new build dependency. The hardcoded values match config defaults. If the frontend port is changed in config, `vite.config.ts` must be updated manually — this is a documented LOW NON-BLOCKER.

## Gamma API integration

| Information | Authoritative source |
|-------------|---------------------|
| Gamma API base URL | `backend/app/integrations/polymarket/config.py` — `GAMMA_BASE_URL` |
| HTTP timeout | `backend/app/integrations/polymarket/config.py` — `DEFAULT_TIMEOUT` |
| Market fetch limit | `backend/app/integrations/polymarket/config.py` — `DEFAULT_MARKET_LIMIT` |

These constants are integration-layer config, not exposed in `config/default.toml`. This is intentional: they are not intended to be user-configurable at this stage.

## Testing

| Information | Authoritative source |
|-------------|---------------------|
| All locked contract surfaces (index) | `docs/testing/discovery_sync_contract_atlas.md` |
| Full test scenario matrix | `docs/testing/discovery_regression_matrix.md` |
| Regression tier definitions + commands | `docs/testing/regression_tiers.md` |
| Gamma fixture refresh workflow | `docs/testing/gamma_contract_workflow.md` |
| Drift response ownership | `docs/testing/gamma_drift_response_roles.md` |
| Snapshot refresh trigger policy | `docs/testing/gamma_snapshot_refresh_policy.md` |
| Gamma API fixture (committed snapshot) | `backend/tests/fixtures/gamma_snapshot.json` |

---

## Governance and process

| Information | Authoritative source |
|-------------|---------------------|
| Architectural decisions (log) | `docs/governance/decision-log.md` |
| Branch naming and PR discipline | `docs/governance/branch-and-pr-rules.md` |
| Document placement rules | `docs/governance/documentation-rules.md` |
| Source of truth map (this file) | `docs/governance/source-of-truth-map.md` |
| Project rules and skill policy | `CLAUDE.md` |
| Release delivery records | `docs/releases/` |

---

## Conflict resolution rule

If two files contain conflicting information about the same topic:

1. Identify which file is listed as authoritative in this map.
2. The listed file wins — update the other to match.
3. If neither is listed, stop and report to the operator before editing.
