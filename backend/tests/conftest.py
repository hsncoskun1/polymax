"""Root conftest for backend tests.

Custom pytest markers:
  live — tests that require a live Polymarket Gamma API connection.
          Skipped by default; enable with: pytest -m live
"""
import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "live: marks tests that require live Polymarket API access (skipped by default)",
    )


def pytest_collection_modifyitems(config, items):
    """Skip @pytest.mark.live tests unless -m live is explicitly passed."""
    if "live" not in (config.option.markexpr or ""):
        skip_live = pytest.mark.skip(reason="Live API test — run with: pytest -m live")
        for item in items:
            if item.get_closest_marker("live"):
                item.add_marker(skip_live)
