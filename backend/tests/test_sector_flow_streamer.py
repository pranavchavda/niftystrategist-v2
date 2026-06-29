"""Tests for the live sector-flow streamer (monitor/sector_flow_streamer.py).

The streamer accumulates 15-min candles from shared-feed LTP ticks and computes
the same two-layer snapshot as the replay path. These tests drive it with a fake
pool and synthetic ticks at controlled timestamps — no DB, no network, no real
feed. The pure shaping/threshold maths is covered by test_sector_flow_cache; here
we cover the streaming-specific glue: pool registration, tick→buffer routing,
prev-close capture from the ltpc feed, the IST results shape, and that a full
compute produces the expected market/sector reading.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

import monitor.sector_flow_streamer as sfs
from monitor.sector_flow_streamer import SectorFlowStreamer


# ── fakes ────────────────────────────────────────────────────────────────────

class FakePool:
    """Records interest registrations; never opens a connection."""

    def __init__(self):
        self.interest: dict[int, set[str]] = {}

    async def set_interest(self, user_id, instruments):
        self.interest[user_id] = set(instruments)

    async def drop_user(self, user_id):
        self.interest.pop(user_id, None)


# 16 names: 8 "Soft" (bleed down → laggard), 8 "Steady" (flat → leader).
_SECTORS = {f"SYM{i}": ("Soft" if i < 8 else "Steady") for i in range(16)}

# Three 15-min windows, expressed in naive UTC (the grid CandleBuffer anchors
# to). 03:50 → bar 03:45 (09:15 IST); 04:05 → 04:00 (09:30); 04:20 → 04:15.
_W = [
    datetime(2026, 6, 29, 3, 50),
    datetime(2026, 6, 29, 4, 5),
    datetime(2026, 6, 29, 4, 20),
]


@pytest.fixture
def patched_ic(monkeypatch):
    """Stub instruments_cache so the universe is our 16 synthetic names. The
    streamer and _shape_snapshot share this module object, so one patch covers
    both."""
    monkeypatch.setattr(sfs.ic, "ensure_loaded", lambda: None)
    monkeypatch.setattr(sfs.ic, "get_universe", lambda u: set(_SECTORS.keys()))
    monkeypatch.setattr(sfs.ic, "get_instrument_key", lambda s: f"NSE_EQ|{s}")
    monkeypatch.setattr(sfs.ic, "get_sector", lambda s: _SECTORS.get(s))


def _key(sym: str) -> str:
    return f"NSE_EQ|{sym}"


async def _feed_day(streamer: SectorFlowStreamer):
    """Feed each name three bars: Soft bleeds 100→98, Steady stays flat."""
    for i in range(16):
        sym = f"SYM{i}"
        k = _key(sym)
        closes = [99.0, 98.5, 98.0] if i < 8 else [100.0, 100.0, 100.0]
        # bar1: open at 100 (prev-day close 100 → no gap), then close1
        await streamer.on_tick({k: {"ltp": 100.0, "close": 100.0}}, ts=_W[0])
        await streamer.on_tick({k: {"ltp": closes[0]}}, ts=_W[0])
        await streamer.on_tick({k: {"ltp": closes[1]}}, ts=_W[1])
        await streamer.on_tick({k: {"ltp": closes[2]}}, ts=_W[2])


# ── tests ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_start_registers_interest_under_sentinel(patched_ic):
    pool = FakePool()
    s = SectorFlowStreamer(pool)
    await s.start()
    try:
        assert SectorFlowStreamer.SENTINEL_UID in pool.interest
        keys = pool.interest[SectorFlowStreamer.SENTINEL_UID]
        assert keys == {_key(f"SYM{i}") for i in range(16)}
        # one buffer + reverse-map entry per resolved name
        assert len(s._buffers) == 16
        assert s._key_to_symbol[_key("SYM0")] == "SYM0"
    finally:
        await s.stop()
    assert SectorFlowStreamer.SENTINEL_UID not in pool.interest


@pytest.mark.asyncio
async def test_on_tick_routes_to_buffer_and_captures_prev_close(patched_ic):
    pool = FakePool()
    s = SectorFlowStreamer(pool)
    await s.start()
    try:
        await s.on_tick({_key("SYM0"): {"ltp": 101.5, "close": 98.0}}, ts=_W[0])
        candles = s._buffers["SYM0"].get_candles()
        assert candles and candles[-1]["close"] == 101.5
        # prior-day close captured from the ltpc 'close' (cp) field — no REST
        assert s._prev_close["SYM0"] == 98.0
        # an unknown instrument key is ignored, not an error
        await s.on_tick({"NSE_EQ|UNKNOWN": {"ltp": 5.0}}, ts=_W[0])
    finally:
        await s.stop()


@pytest.mark.asyncio
async def test_build_results_shape_ist_and_prev_row(patched_ic):
    pool = FakePool()
    s = SectorFlowStreamer(pool)
    await s.start()
    try:
        await _feed_day(s)
        results, today = s._build_results()
        assert today == "2026-06-29"
        rows = results["SYM0"]
        # synthetic prior-day row first (carries feed close), then 3 bars
        assert rows[0] == ("2026-06-28T15:30:00", 100.0, 100.0)
        # first real bar is the 09:15 IST window (03:45 UTC + 5:30)
        assert rows[1][0] == "2026-06-29T09:15:00"
        assert rows[-1][2] == 98.0  # last close
    finally:
        await s.stop()


@pytest.mark.asyncio
async def test_compute_and_store_produces_reading(patched_ic, monkeypatch):
    pool = FakePool()
    s = SectorFlowStreamer(pool)
    await s.start()
    captured = {}

    async def _fake_save(universe, snapshot, elapsed_ms):
        captured["universe"] = universe
        captured["snap"] = snapshot
        return 123

    monkeypatch.setattr(sfs, "save_snapshot", _fake_save)
    try:
        await _feed_day(s)
        await s._compute_and_store()
    finally:
        await s.stop()

    snap = captured["snap"]
    assert snap["date"] == "2026-06-29"
    assert snap["market"]["direction"] == "down"
    assert snap["market"]["median_move"] == pytest.approx(-1.0, abs=0.05)
    assert snap["sectors"]["Soft"]["bias"] == "laggard"
    assert snap["sectors"]["Steady"]["bias"] == "leader"


@pytest.mark.asyncio
async def test_compute_skips_when_empty(patched_ic, monkeypatch):
    pool = FakePool()
    s = SectorFlowStreamer(pool)
    await s.start()
    called = False

    async def _fake_save(*a, **k):
        nonlocal called
        called = True
        return 1

    monkeypatch.setattr(sfs, "save_snapshot", _fake_save)
    try:
        await s._compute_and_store()  # no ticks fed → nothing to store
    finally:
        await s.stop()
    assert called is False
