from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api.health import router as health_router
from .api.markets import router as markets_router
from .core.config import load_config
from .core.logger import setup_logger

logger = setup_logger("polymax.backend")


def _build_cors_origins() -> list[str]:
    """Derive CORS allowed origins from config/default.toml [frontend] host and port.

    Two origins are always produced:
      - http://{frontend_host}:{frontend_port}  (matches config exactly)
      - http://localhost:{frontend_port}         (browser alias; kept explicitly because
                                                  browsers distinguish localhost from
                                                  127.0.0.1 for some security contexts)

    If config is unavailable the hardcoded defaults match the TOML defaults so
    runtime behaviour is unchanged.
    """
    cfg = load_config()
    host = cfg.get("frontend", {}).get("host", "127.0.0.1")
    port = cfg.get("frontend", {}).get("port", 5173)
    origins = [f"http://{host}:{port}"]
    if host != "localhost":
        origins.append(f"http://localhost:{port}")
    return origins


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("POLYMAX backend started")
    yield
    logger.info("POLYMAX backend stopped")


app = FastAPI(title="POLYMAX Backend", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_build_cors_origins(),
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(markets_router)
