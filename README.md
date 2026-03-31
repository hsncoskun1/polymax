# POLYMAX

Local-first application with launcher + localhost panel architecture.

## Status
- v0.1.1 Backend shell — complete
- v0.1.2 Frontend shell — complete
- v0.1.3 Launcher shell — complete

## Quick Start

### Launch Everything
```bash
python launcher/main.py
```
This starts backend + frontend, waits for readiness, opens browser. Ctrl+C to stop.

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
polymax/
├── launcher/main.py        # Starts backend + frontend, opens browser
├── backend/
│   ├── app/
│   │   ├── api/            # API endpoints
│   │   ├── core/           # Config, logging
│   │   └── main.py         # FastAPI entrypoint
│   └── tests/
├── frontend/
│   ├── src/
│   │   ├── components/     # AppShell, HealthBadge
│   │   ├── pages/          # UserPanel, AdminPanel
│   │   └── tests/
│   └── package.json
├── config/default.toml     # Central configuration
└── test-results/           # Test reports
```

## Tech Stack
- Backend: Python + FastAPI
- Frontend: React + Vite + TypeScript + Tailwind
- Launcher: Python (subprocess + readiness polling)
