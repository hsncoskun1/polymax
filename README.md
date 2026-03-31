# POLYMAX

Local-first application with launcher + localhost panel architecture.

## Status
- v0.1.1 Backend shell — complete

## Quick Start

### Backend
```bash
cd polymax
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

### Run Tests
```bash
python -m pytest backend/tests/ -v
```

## Project Structure
```
polymax/
├── backend/
│   ├── app/
│   │   ├── api/        # API endpoints
│   │   ├── core/       # Config, logging
│   │   └── main.py     # FastAPI entrypoint
│   ├── tests/          # Backend tests
│   └── requirements.txt
├── config/
│   └── default.toml    # Central configuration
├── test-results/       # Test reports
└── .claude/skills/     # Claude Code skills
```

## Tech Stack
- Backend: Python + FastAPI
- Frontend: React + Vite + TypeScript (planned)
- Launcher: TBD
