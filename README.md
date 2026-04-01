# POLYMAX

Local-first trading platform. Fetches, classifies, and monitors short-term crypto prediction markets on Polymarket. Backend is the single source of truth; frontend is display and trigger only.

## Status

### Foundation (v0.1.x)
- v0.1.1 Backend shell (FastAPI + health endpoint) — complete
- v0.1.2 Frontend shell (React + Vite + Tailwind + routing) — complete
- v0.1.3 Launcher shell (subprocess + readiness polling) — complete

### Market Registry (v0.2.x)
- v0.2.1 Market registry domain shell (frozen Pydantic model, InMemoryRegistry, exceptions) — complete
- v0.2.2 Market registry API (5 CRUD endpoints) — complete
- v0.2.3 Frontend market list (MarketList component) — complete
- v0.2.4 Frontend API config cleanup (VITE_BACKEND_URL, api.ts helper) — complete

### Polymarket Integration (v0.3.x)
- v0.3.1 Polymarket HTTP client shell (httpx, read-only, Gamma API) — complete
- v0.3.2 Market fetch service shell (FetchedMarket DTO, PolymarketFetchService) — complete
- v0.3.3 FetchedMarket → domain mapper + single-shot registry sync — complete
- v0.3.4 POST /api/v1/markets/sync manual sync endpoint — complete
- v0.3.5 Admin sync action UI (Sync now button + result summary) — complete
- v0.3.6 Sync → market list refresh flow (refreshKey callback chain) — complete
- v0.3.7 5m candidate cleanup (enableOrderBook + tokens gates) — complete
- v0.3.8 5m duration filter (endDate-based candidate gate, [240-360] s window) — complete
- v0.3.9 Symbol extraction shell (question/slug → BTC/ETH/SOL via regex + keyword catalogue) — complete

### Discovery (v0.4.x)
- v0.4.1 Discovery shell (DiscoveryService, RejectionReason, candidate selection with reason breakdown) — complete
- v0.4.2 Manual discovery API (POST /api/v1/markets/discover — fetch → evaluate, no registry write) — complete
- v0.4.3 Admin discovery action UI (Discover now button + candidate/rejection summary card) — complete

### Market Model (v0.5.x)
- v0.5.1 Market domain end_date (end_date field on Market model, mapper propagation) — complete
- v0.5.2 Discovery-sync integration (DiscoveryService single candidate source in MarketSyncService) — complete
- v0.5.3 Discovery input quality tightening (enable_order_book + tokens fields on FetchedMarket; NO_ORDER_BOOK + EMPTY_TOKENS rejection reasons in DiscoveryService) — complete
- v0.5.4 Discovery single-entry cleanup (removed fetch_candidates + _is_5m_candidate dead code; PolymarketFetchService is now a pure normalisation layer) — complete
- v0.5.5 Discovery flow integration lock (integration test suite; four architecture contracts locked: C1 fetcher=normaliser, C2 discovery=sole selector, C3 sync=respects discovery, C4 endpoint=surfaces discovery output) — complete
- v0.5.5a Duration semantics lock (duration rule verified as total_duration not remaining_time; 10 new tests — 6 unit + 4 integration — lock the near-expiry contract) — complete
- v0.5.5b Duration source semantics lock (source_timestamp confirmed as event start from Polymarket startDate; misleading domain comment fixed; 3 new tests) — complete
- v0.5.6 Sync / registry behavior lock (5 registry contracts C1–C5 + Scenario G; 18 integration tests; POST /sync response integrity; regression matrix updated to 83 scenarios / 234 tests) — complete
- v0.5.7 Registry lifecycle semantics lock (add-only/retained model documented as deliberate deferred decision; lifecycle docstring in market_sync.py; 11 new lifecycle integration tests A–E; 245 total tests; 94 regression scenarios) — complete
- v0.5.8 Sync summary semantics lock (SyncResult.registry_total + SyncResponse.registry_total_count added; SyncResult docstring clarified; 12 new tests A–E; 257 total tests; 106 regression scenarios) — complete
- v0.5.9 Rejection observability lock (SyncResult.rejected_count + rejection_breakdown added; SyncResponse exposes both fields; 14 new integration tests A–E; 271 total tests; 120 regression scenarios) — complete
- v0.5.10 Rejection taxonomy contract lock (DiscoveryResult.string_breakdown canonical serialization point; single source for enum→string conversion; 15 new taxonomy contract tests A–E; 286 total tests; 135 regression scenarios) — complete
- v0.5.11 Discover/sync contract alignment lock (DiscoveryResponse docstring expanded; intentional fetched_count semantic difference documented; 10 new alignment tests A–E; 296 total tests; 145 regression scenarios) — complete
- v0.5.12 Cross-layer field semantics lock (SyncResult docstring API field name mapping table added; 9 new cross-layer field semantics tests A–E; 305 total tests; 154 regression scenarios) — complete
- v0.5.13 Mapper multiplicity contract lock (MarketMapper.MARKETS_PER_CANDIDATE=2 constant; exact-two canonical contract documented; 14 new multiplicity tests A–E; 319 total tests; 168 regression scenarios) — complete
- v0.5.14 Mapping failure semantics lock (SyncResult three-pipeline-gate section: Gate 1 discovery rejection / Gate 2 mapping failure / Gate 3 registry duplicate; pipeline invariant documented; 12 new mapping failure semantics tests A–E; 331 total tests; 180 regression scenarios) — complete

## Quick Start

### Launch Everything
```bash
python launcher/main.py
```
Starts backend + frontend, waits for readiness, opens browser. Ctrl+C to stop.

### Individual Services
```bash
# Backend only
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000

# Frontend only
cd frontend && npm run dev
```

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
│   │   ├── api/                # HTTP endpoints (health, markets + sync)
│   │   ├── core/               # Config, logging
│   │   ├── domain/
│   │   │   └── market/         # Market entity, registry, exceptions, types
│   │   ├── integrations/
│   │   │   └── polymarket/     # HTTP client, config, exceptions
│   │   └── services/           # market_fetcher, market_sync
│   └── tests/
│       ├── api/
│       ├── domain/
│       ├── integrations/
│       └── services/
├── frontend/
│   ├── src/
│   │   ├── components/         # AppShell, HealthBadge, MarketList, SyncAction
│   │   ├── pages/              # UserPanel, AdminPanel
│   │   ├── lib/                # config.ts, api.ts
│   │   └── tests/
│   └── package.json
├── config/default.toml         # Central configuration
└── test-results/               # Test reports per milestone
```

## Tech Stack
- Backend: Python 3.13 + FastAPI + Pydantic v2 + httpx
- Frontend: React 19 + Vite + TypeScript + Tailwind v4
- Launcher: Python (subprocess + readiness polling)
