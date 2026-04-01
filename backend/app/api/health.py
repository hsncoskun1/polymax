from fastapi import APIRouter
from ..core.config import load_config

router = APIRouter()


@router.get("/health")
def health_check():
    cfg = load_config()
    version = cfg.get("app", {}).get("version", "unknown")
    return {"status": "ok", "service": "polymax-backend", "version": version}
