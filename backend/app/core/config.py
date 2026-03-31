import tomli
from pathlib import Path

_config_cache: dict | None = None


def load_config() -> dict:
    global _config_cache
    if _config_cache is None:
        config_path = Path(__file__).resolve().parents[3] / "config" / "default.toml"
        with open(config_path, "rb") as f:
            _config_cache = tomli.load(f)
    return _config_cache
