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
