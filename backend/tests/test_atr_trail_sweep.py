"""Tests for the ATR-trail k-sweep pure pieces (backtesting/atr_trail_sweep.py)."""
from __future__ import annotations

import pytest

from backtesting.atr_trail_sweep import (
    gap_fade_entry, group_by_day, orb_entry, regime_proxy, simulate_trail,
)
from services.atr_trail import RANGE_BOUND, TRENDING


def _c(t, o, h, l, cl):
    return {"timestamp": t, "open": o, "high": h, "low": l, "close": cl}


# ── gap_fade_entry ───────────────────────────────────────────────────────────

def test_gap_up_fades_short():
    day = [_c("2026-06-22T09:15:00+05:30", 102.0, 103, 101, 101.5)]
    out = gap_fade_entry(day, prev_close=100.0)   # +2% gap
    assert out == (0, 101.5, "short")


def test_gap_down_fades_long():
    day = [_c("2026-06-22T09:15:00+05:30", 98.0, 99, 97, 98.5)]
    out = gap_fade_entry(day, prev_close=100.0)   # -2% gap
    assert out == (0, 98.5, "long")


def test_small_gap_no_entry():
    day = [_c("2026-06-22T09:15:00+05:30", 100.5, 101, 100, 100.5)]
    assert gap_fade_entry(day, prev_close=100.0) is None   # +0.5% < 1.5%


# ── orb_entry ────────────────────────────────────────────────────────────────

def test_orb_breakout_long():
    # OR = first 2 bars (high 101). bar 2 closes 102 > 101 → long break at idx 2.
    day = [_c("2026-06-22T09:15:00", 100, 101, 99, 100),
           _c("2026-06-22T09:30:00", 100, 101, 99.5, 100.5),
           _c("2026-06-22T09:45:00", 100.5, 103, 100.5, 102)]
    assert orb_entry(day, or_bars=2) == (2, 102.0, "long")


def test_orb_breakdown_short():
    day = [_c("2026-06-22T09:15:00", 100, 101, 99, 100),
           _c("2026-06-22T09:30:00", 100, 100.5, 99, 99.5),
           _c("2026-06-22T09:45:00", 99.5, 99.5, 97, 98)]   # closes 98 < OR low 99
    assert orb_entry(day, or_bars=2) == (2, 98.0, "short")


def test_orb_no_break_returns_none():
    day = [_c("2026-06-22T09:15:00", 100, 101, 99, 100),
           _c("2026-06-22T09:30:00", 100, 101, 99, 100),
           _c("2026-06-22T09:45:00", 100, 100.9, 99.1, 100.2)]   # stays inside OR
    assert orb_entry(day, or_bars=2) is None


# ── simulate_trail ───────────────────────────────────────────────────────────

def _intraday(prices):
    """Build a day of 15-min bars from a list of (hhmm, low, high, close)."""
    out = []
    for hhmm, lo, hi, cl in prices:
        out.append(_c(f"2026-06-22T{hhmm}:00+05:30", cl, hi, lo, cl))
    return out


def test_long_trails_up_and_exits_profit():
    # enter 100, tight climb to a 111 high, then a pullback bar triggers the
    # 5% trail off 111 → 105.45. (Ratchet bar and pullback bar kept separate so
    # the fire isn't a same-bar high+low artifact.)
    day = _intraday([
        ("09:15", 99, 101, 100),    # entry bar (idx 0)
        ("09:30", 102, 104, 103),   # tight climb, anchor 104, stop 98.8 — no fire
        ("09:45", 108, 111, 110),   # high 111 → anchor 111, stop 105.45, low 108 — no fire
        ("10:00", 104, 109, 105),   # low 104 ≤ 105.45 → trail fires at 105.45
    ])
    out = simulate_trail(day, 0, 100.0, "long", 5.0, slippage_bps=0)
    assert out["exit_reason"] == "trail"
    assert out["exit_price"] == pytest.approx(111 * 0.95, abs=0.1)
    assert out["pnl_per_share"] > 0


def test_long_squareoff_exit():
    day = _intraday([
        ("09:15", 99, 101, 100),
        ("14:45", 99, 101, 100),
        ("15:15", 99, 101, 100),   # ≥ squareoff → exit at open(=100)
    ])
    out = simulate_trail(day, 0, 100.0, "long", 5.0, slippage_bps=0)
    assert out["exit_reason"] == "squareoff"


def test_splpetro_counterfactual_wide_survives_tight_whipsaws():
    """The motivating case, stylised: post-entry low ≈ -2.85%, recovers to ~flat.
    A 2% trail stops out near the low; a 3.6% trail never triggers."""
    entry = 779.18
    # path: dips to 757 (−2.85%) mid-morning, recovers to ~775 by close
    day = _intraday([
        ("09:15", 774, 783, 779.18),  # entry bar
        ("09:30", 763, 778, 765),     # dips
        ("11:15", 757, 762, 758),     # the −2.85% low
        ("13:25", 770, 778, 776),     # recovery
        ("15:15", 774, 777, 775),     # squareoff ~775
    ])
    tight = simulate_trail(day, 0, entry, "long", 2.0, slippage_bps=0)
    wide = simulate_trail(day, 0, entry, "long", 3.6, slippage_bps=0)
    assert tight["exit_reason"] == "trail"          # 2% gets whipsawed
    assert wide["exit_reason"] == "squareoff"        # 3.6% survives to close
    assert wide["pnl_per_share"] > tight["pnl_per_share"]  # wide loses far less


def test_short_trails_down_and_exits_profit():
    # enter short 100, falls to 90 then bounces; 5% trail = 90*1.05 = 94.5
    day = _intraday([
        ("09:15", 99, 101, 100),
        ("09:30", 94, 100, 95),    # low 94 → anchor 94, stop 98.7
        ("09:45", 89, 96, 90),     # low 89 → anchor 89, stop 93.45
        ("10:00", 90, 95, 94),     # high 95 ≥ 93.45 → trail fires
    ])
    out = simulate_trail(day, 0, 100.0, "short", 5.0, slippage_bps=0)
    assert out["exit_reason"] == "trail"
    assert out["pnl_per_share"] > 0


# ── regime_proxy ─────────────────────────────────────────────────────────────

def test_regime_trending_on_monotonic_climb():
    day = _intraday([(f"{9 + i // 4:02d}:{(i % 4) * 15:02d}", 100 + i, 101 + i, 100.8 + i)
                     for i in range(12)])
    out = regime_proxy(day)
    assert out["regime"] == TRENDING


def test_regime_range_bound_on_chop():
    # oscillating around 100, narrow, frequent midpoint crossings
    seq = [100, 100.6, 99.5, 100.5, 99.6, 100.4, 99.7, 100.3, 99.8, 100.2, 99.9, 100.1]
    day = _intraday([(f"{9 + i // 4:02d}:{(i % 4) * 15:02d}",
                      s - 0.3, s + 0.3, s) for i, s in enumerate(seq)])
    out = regime_proxy(day)
    assert out["regime"] == RANGE_BOUND


# ── group_by_day ─────────────────────────────────────────────────────────────

def test_group_by_day():
    candles = [_c("2026-06-20T09:15:00", 1, 1, 1, 1),
               _c("2026-06-20T09:30:00", 1, 1, 1, 1),
               _c("2026-06-22T09:15:00", 1, 1, 1, 1)]
    days = group_by_day(candles)
    assert list(days.keys()) == ["2026-06-20", "2026-06-22"]
    assert len(days["2026-06-20"]) == 2
