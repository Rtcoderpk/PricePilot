"""Phase 5 worker tests — monitoring disabled / provider unavailable early
returns, and price-source honest states. No network, no DB needed for these
branch tests (the cycle returns before touching the DB in both cases).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from pricepilot.config import settings
from pricepilot.monitoring.price_source import PriceSource, price_source_status

_WORKER_PATH = Path(__file__).resolve().parents[2] / "worker" / "main.py"
_API_PATH = Path(__file__).resolve().parents[1]


@pytest.fixture
def worker_mod():
    """Import services/worker/main.py as a module (no asyncio.run side effects)."""
    spec = importlib.util.spec_from_file_location("_pp_worker", _WORKER_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    # add service dir to sys.path so `pricepilot` resolves
    sys.path.insert(0, str(_API_PATH))
    spec.loader.exec_module(mod)
    yield mod
    sys.path.remove(str(_API_PATH))


async def test_cycle_disabled(worker_mod, monkeypatch):
    monkeypatch.setattr(settings, "monitor_enabled", False)
    summary = await worker_mod.run_monitoring_cycle()
    assert summary["status"] == "monitoring_disabled"


async def test_cycle_provider_unavailable(worker_mod, monkeypatch):
    monkeypatch.setattr(settings, "monitor_enabled", True)
    monkeypatch.setattr(settings, "pricepilot_search_provider", "")
    summary = await worker_mod.run_monitoring_cycle()
    assert summary["status"] == "provider_unavailable"


# ---------- price source honest states ----------

async def test_price_source_fetch_no_barcode():
    src = PriceSource()
    r = await src.fetch_current_price("")
    assert r.status == "provider_failed"
    assert "no barcode" in r.reason


def test_price_source_status_unavailable_when_no_provider(monkeypatch):
    monkeypatch.setattr(settings, "pricepilot_search_provider", "")
    assert price_source_status() == "unavailable"


def test_price_source_status_available_for_openfoodfacts(monkeypatch):
    monkeypatch.setattr(settings, "pricepilot_search_provider", "openfoodfacts")
    assert price_source_status() == "available"