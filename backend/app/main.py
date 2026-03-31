from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api.health import router as health_router
from .api.markets import router as markets_router
from .core.logger import setup_logger

logger = setup_logger("polymax.backend")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("POLYMAX backend started")
    yield
    logger.info("POLYMAX backend stopped")


app = FastAPI(title="POLYMAX Backend", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(markets_router)
