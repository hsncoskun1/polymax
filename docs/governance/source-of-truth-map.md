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

## Network and connectivity

| Information | Authoritative source | Drift risk |
|-------------|---------------------|------------|
| Backend host / port (runtime) | `config/default.toml` → read by launcher and `backend/app/core/config.py` | LOW — values match hardcoded fallbacks today |
| Frontend → backend URL (runtime) | `frontend/src/lib/config.ts` fallback: `http://127.0.0.1:8000` | LOW — not linked to `config/default.toml`; frontend cannot read TOML at runtime; by design |
| CORS allowed origins | `backend/app/main.py` — **hardcoded**: `["http://127.0.0.1:5173", "http://localhost:5173"]` | **MEDIUM** — not read from `config/default.toml`; if frontend port changes in config, CORS breaks silently |

**Known gap:** CORS allowed origins are not config-driven. `config/default.toml` has `[frontend] host` and `port`, but `backend/app/main.py` does not read them. The hardcoded values happen to match the config defaults. This is a latent drift risk if the frontend port is changed in config.

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
