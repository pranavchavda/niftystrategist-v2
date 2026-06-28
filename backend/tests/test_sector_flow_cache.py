"""Tests for the sector-flow cache compute/shape layer (services/sector_flow_cache.py).

Focuses on the deterministic logic — `_shape_snapshot` (pure, fed synthetic candle
tuples) and `compute_snapshot` (with an injected fake client). The save/get/prune
helpers are thin SQLAlchemy wrappers mirroring the proven scan_cache pattern and
need a live DB, so they're not unit-tested here (scan_cache likewise has none).
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

import services.sector_flow_cache as sfc


# ── helpers ──────────────────────────────────────────────────────────────────

DAY = "2026-06-25"
_TIMES = ["09:15", "09:30", "09:45"]


def _rows(open_, closes):
    """Candle tuples (ts, open, close) for one day."""
    return [(f"{DAY}T{t}:00+05:30", open_, c) for t, c in zip(_TIMES, closes)]


@pytest.fixture
def two_sector_results(monkeypatch):
    """10 names bleeding down ('Soft'), 10 flat ('Steady') → market ~mid, Soft is
    the laggard, Steady the leader."""
    sectors = {f"SYM{i}": ("Soft" if i < 10 else "Steady") for i in range(20)}
    monkeypatch.setattr(sfc.ic, "get_sector", lambda s: sectors.get(s))
    results = {}
    for i in range(20):
        closes = [99.0, 98.5, 98.0] if i < 10 else [100.0, 100.0, 100.0]
        results[f"SYM{i}"] = _rows(100.0, closes)
    return results


# ── _shape_snapshot ──────────────────────────────────────────────────────────

def test_shape_market_summary(two_sector_results):
    snap = sfc._shape_snapshot(two_sector_results, "test", None, 0.3, 2)
    assert snap["date"] == DAY
    m = snap["market"]
    assert m["direction"] == "down"
    assert m["median_move"] == pytest.approx(-1.0, abs=0.01)  # median of 10×-2, 10×0
    assert m["n"] == 20


def test_shape_laggard_and_leader(two_sector_results):
    snap = sfc._shape_snapshot(two_sector_results, "test", None, 0.3, 2)
    assert snap["sectors"]["Soft"]["bias"] == "laggard"
    assert snap["sectors"]["Soft"]["avg_rel_median"] < 0
    assert snap["sectors"]["Steady"]["bias"] == "leader"
    assert snap["sectors"]["Steady"]["avg_rel_median"] > 0


def test_shape_is_json_serializable(two_sector_results):
    snap = sfc._shape_snapshot(two_sector_results, "test", None, 0.3, 2)
    json.dumps(snap)  # must not raise
    # timelines are present and compact dicts
    assert isinstance(snap["market_timeline"], list)
    assert isinstance(snap["sectors"]["Soft"]["timeline"], list)
    assert snap["sectors"]["Soft"]["timeline"][0]["as_of"] == "09:15"


def test_shape_excludes_thin_sectors(monkeypatch):
    # Only 5 names in 'Tiny' (< MIN_SECTOR_NAMES) → excluded from the reading.
    sectors = {f"T{i}": "Tiny" for i in range(5)}
    monkeypatch.setattr(sfc.ic, "get_sector", lambda s: sectors.get(s))
    results = {f"T{i}": _rows(100.0, [99.0, 98.0, 97.0]) for i in range(5)}
    snap = sfc._shape_snapshot(results, "test", None, 0.3, 2)
    assert "Tiny" not in snap["sectors"]


def test_shape_gap_context(monkeypatch):
    # Prior-day close 98 → open 100 = +2% gap; intraday bleeds from open.
    monkeypatch.setattr(sfc.ic, "get_sector", lambda s: "Soft")
    results = {}
    for i in range(10):
        prior = [("2026-06-24T15:15:00+05:30", 97.0, 98.0)]
        today = _rows(100.0, [99.0, 98.5, 98.0])
        results[f"SYM{i}"] = prior + today
    snap = sfc._shape_snapshot(results, "test", DAY, 0.3, 2)
    assert snap["market"]["gap"] == pytest.approx(2.04, abs=0.05)  # (100-98)/98


def test_shape_no_data_returns_error():
    assert "error" in sfc._shape_snapshot({}, "test", None, 0.3, 2)


# ── compute_snapshot with an injected fake client ────────────────────────────

def test_compute_snapshot_with_fake_client(monkeypatch):
    monkeypatch.setattr(sfc.ic, "ensure_loaded", lambda: None)
    monkeypatch.setattr(sfc.ic, "get_universe", lambda u: {f"SYM{i}" for i in range(10)})
    monkeypatch.setattr(sfc.ic, "get_sector", lambda s: "Soft")

    class FakeClient:
        async def get_historical_data(self, symbol, interval="15minute", days=30):
            return [SimpleNamespace(timestamp=ts, open=o, close=c)
                    for ts, o, c in _rows(100.0, [99.0, 98.5, 98.0])]

    snap = pytest.importorskip("asyncio").run(
        sfc.compute_snapshot("nifty50", date=DAY, client=FakeClient())
    )
    assert snap["market"]["direction"] == "down"
    assert snap["date"] == DAY
    # 10 names in one sector, but it's the whole universe so 'Soft' rel-to-market ~0
    assert "Soft" in snap["sectors"]
