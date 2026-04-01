"""Contract tests for CORS origin derivation (v0.5.29).

Locks the behaviour of _build_cors_origins() in backend/app/main.py:
- Origins are derived from config/default.toml [frontend] host and port
- The localhost alias is always appended when host != "localhost"
- Fallback values produce the same two origins as the previous hardcoded list
"""
from unittest.mock import patch

from backend.app.main import _build_cors_origins


def test_cors_origins_match_config_defaults():
    """With default config the origins must match the previously hardcoded list."""
    # config/default.toml: [frontend] host = "127.0.0.1", port = 5173
    origins = _build_cors_origins()
    assert "http://127.0.0.1:5173" in origins
    assert "http://localhost:5173" in origins


def test_cors_origins_follow_config_port():
    """If config port changes, origins follow without touching main.py."""
    fake_cfg = {"frontend": {"host": "127.0.0.1", "port": 9999}}
    with patch("backend.app.main.load_config", return_value=fake_cfg):
        origins = _build_cors_origins()
    assert "http://127.0.0.1:9999" in origins
    assert "http://localhost:9999" in origins
    assert "http://127.0.0.1:5173" not in origins


def test_cors_origins_localhost_alias_not_duplicated():
    """When config host is already 'localhost', no duplicate localhost entry."""
    fake_cfg = {"frontend": {"host": "localhost", "port": 5173}}
    with patch("backend.app.main.load_config", return_value=fake_cfg):
        origins = _build_cors_origins()
    assert origins.count("http://localhost:5173") == 1


def test_cors_origins_count():
    """Exactly two origins with standard config (127.0.0.1 host)."""
    origins = _build_cors_origins()
    assert len(origins) == 2
