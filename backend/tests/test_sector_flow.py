"""Tests for the intraday sector-flow sensor core (services/sector_flow.py).

Covers the lessons the 06-25/06-24 backtest taught (2026-06-28):
  - breadth/threshold counting (flat names count toward neither side),
  - the DERIVATIVE-keyed decisiveness (Δmedian, not Δbreadth, since breadth
    saturates for tight correlated sectors),
  - the relief-bounce being FILTERED to 0 (breadth red but median rising),
  - the relative (sector − market) layer that strips market beta, and the
    persistent-laggard (high |rel| / low Δrel) vs decoupling-event distinction.
"""
from __future__ import annotations

import pytest

from services.sector_flow import (
    DEFAULT_WINDOW_BARS,
    RelativeSnapshot,
    SectorSnapshot,
    _attach_acceleration,
    pct_from_open,
    persistent_bias,
    relative_timeline,
    sector_snapshot,
    sector_timeline,
)


def _snap(as_of, net, median, *, sector="X", n=10):
    """Minimal SectorSnapshot for acceleration/relative tests."""
    return SectorSnapshot(sector=sector, as_of=as_of, n=n,
                          up_frac=0.0, down_frac=0.0, net_breadth=net,
                          median_move=median, mean_move=median)


# ── pct_from_open ────────────────────────────────────────────────────────────

def test_pct_from_open_basic():
    assert pct_from_open(110.0, 100.0) == pytest.approx(10.0)
    assert pct_from_open(95.0, 100.0) == pytest.approx(-5.0)


@pytest.mark.parametrize("bad_open", [0.0, -1.0])
def test_pct_from_open_rejects_nonpositive_open(bad_open):
    with pytest.raises(ValueError):
        pct_from_open(100.0, bad_open)


# ── sector_snapshot: breadth, threshold, flats ───────────────────────────────

def test_snapshot_threshold_excludes_flats_from_both_sides():
    # +1.0 and +0.5 are up; -1.0 is down; -0.2 is flat (|.2| < 0.3 threshold).
    moves = {"A": 1.0, "B": 0.5, "C": -0.2, "D": -1.0}
    s = sector_snapshot("IT", "09:30", moves, threshold=0.3)
    assert s.n == 4
    assert s.up_frac == pytest.approx(0.5)      # A, B
    assert s.down_frac == pytest.approx(0.25)   # D only (C is flat)
    assert s.net_breadth == pytest.approx(0.25)
    assert s.median_move == pytest.approx(0.15)  # median of [-1, -0.2, 0.5, 1.0]


def test_snapshot_all_flat_reads_zero_breadth():
    moves = {"A": 0.1, "B": -0.1, "C": 0.2}
    s = sector_snapshot("IT", "09:30", moves, threshold=0.3)
    assert s.net_breadth == 0.0


def test_snapshot_empty():
    s = sector_snapshot("IT", "09:30", {}, threshold=0.3)
    assert s.n == 0 and s.net_breadth == 0.0 and s.median_move == 0.0


# ── acceleration: decisiveness keys off Δmedian, filters relief ──────────────

def test_extending_down_move_is_decisive():
    # net pinned at -1 (saturated) but median extends down: -1.0 → -1.5 → -2.0.
    tl = [_snap("09:15", -1.0, -1.0), _snap("09:30", -1.0, -1.5), _snap("09:45", -1.0, -2.0)]
    _attach_acceleration(tl, window=1)
    last = tl[-1]
    assert last.d_median == pytest.approx(-0.5)
    assert last.accelerating is True
    # |net| × aligned Δmedian = 1.0 × 0.5
    assert last.decisiveness == pytest.approx(0.5)


def test_relief_bounce_is_filtered_to_zero():
    # still net-down (-1) but median RISING (-2 → -1.5 → -1.0): a relief bounce,
    # NOT a fresh down-signal → decisiveness must be 0.
    tl = [_snap("09:15", -1.0, -2.0), _snap("09:30", -1.0, -1.5), _snap("09:45", -1.0, -1.0)]
    _attach_acceleration(tl, window=1)
    last = tl[-1]
    assert last.accelerating is False
    assert last.decisiveness == pytest.approx(0.0)


def test_breadth_saturation_does_not_kill_signal():
    # The motivating lesson: net stuck at -1 the whole series, yet the magnitude
    # path still yields a non-zero decisiveness because we key off Δmedian.
    tl = [_snap(f"{9}:{m:02d}", -1.0, -1.0 - 0.3 * i) for i, m in enumerate((15, 30, 45))]
    _attach_acceleration(tl, window=1)
    assert tl[-1].decisiveness > 0


def test_first_window_bars_have_no_acceleration():
    tl = [_snap("09:15", -0.5, -0.5), _snap("09:30", -0.6, -0.7), _snap("09:45", -0.7, -0.9)]
    _attach_acceleration(tl, window=DEFAULT_WINDOW_BARS)
    assert tl[0].decisiveness is None and tl[1].decisiveness is None
    assert tl[2].decisiveness is not None


def test_up_bloc_extending_is_decisive():
    tl = [_snap("09:15", 1.0, 0.5), _snap("09:30", 1.0, 1.0), _snap("09:45", 1.0, 1.6)]
    _attach_acceleration(tl, window=1)
    assert tl[-1].accelerating is True
    assert tl[-1].decisiveness == pytest.approx(0.6)


# ── sector_timeline integration + forward-fill ───────────────────────────────

def test_timeline_forward_fills_missing_bars():
    # B is missing its 09:30 candle; its 09:15 close must carry forward so it
    # doesn't drop out of breadth at 09:30.
    times = ["09:15", "09:30"]
    opens = {"A": 100.0, "B": 100.0}
    closes = {"A": {"09:15": 99.0, "09:30": 98.0}, "B": {"09:15": 101.0}}
    tl = sector_timeline("IT", times, closes, opens, threshold=0.3, window=1)
    # at 09:30: A = -2% (down), B carried = +1% (up) → n must still be 2.
    assert tl[1].n == 2
    assert tl[1].up_frac == pytest.approx(0.5)
    assert tl[1].down_frac == pytest.approx(0.5)


def test_timeline_symbol_absent_until_first_candle():
    times = ["09:15", "09:30"]
    opens = {"A": 100.0, "B": 100.0}
    closes = {"A": {"09:15": 99.0, "09:30": 98.0}, "B": {"09:30": 102.0}}
    tl = sector_timeline("IT", times, closes, opens, threshold=0.3, window=1)
    assert tl[0].n == 1   # only A has data at 09:15
    assert tl[1].n == 2   # B appears at 09:30


# ── relative layer: strips beta, laggard vs decoupling ───────────────────────

def _market(path):
    return [_snap(f"t{i}", -0.3, m, sector="MARKET") for i, m in enumerate(path)]


def _sector(path, net=-0.6):
    return [_snap(f"t{i}", net, m, sector="IT") for i, m in enumerate(path)]


def test_relative_subtracts_market():
    market = _market([-0.2, -0.5, -0.9])
    sector = _sector([-0.5, -0.9, -1.3])
    rel = relative_timeline(sector, market, window=1)
    assert rel[0].rel_median == pytest.approx(-0.3)
    assert rel[2].rel_median == pytest.approx(-0.4)
    # rel_breadth = sector.net - market.net = -0.6 - (-0.3) = -0.3
    assert rel[0].rel_breadth == pytest.approx(-0.3)


def test_relative_persistent_gap_is_not_a_decoupling_event():
    # IT a constant 0.4 below market the whole session: high |rel| but ~0 Δrel.
    market = _market([-0.2, -0.4, -0.6, -0.8])
    sector = _sector([-0.6, -0.8, -1.0, -1.2])
    rel = relative_timeline(sector, market, window=1)
    assert all(abs(r.rel_median + 0.4) < 1e-9 for r in rel)
    # no fresh decoupling → rel_decisiveness ~0 for the post-window bars
    assert all((r.rel_decisiveness or 0) == pytest.approx(0.0) for r in rel[1:])


def test_relative_widening_gap_is_a_decoupling_event():
    market = _market([-0.2, -0.2, -0.2])     # market flat
    sector = _sector([-0.3, -0.6, -1.0])     # sector pulling away down
    rel = relative_timeline(sector, market, window=1)
    last = rel[-1]
    assert last.decoupling is True
    assert last.rel_decisiveness > 0


def test_relative_aligns_by_time_and_skips_unmatched():
    market = [_snap("t0", -0.3, -0.2), _snap("t1", -0.3, -0.4)]
    sector = [_snap("t0", -0.6, -0.5), _snap("t9", -0.6, -0.9)]  # t9 has no market match
    rel = relative_timeline(sector, market, window=1)
    assert [r.as_of for r in rel] == ["t0"]


# ── persistent_bias labels ───────────────────────────────────────────────────

def test_persistent_bias_laggard():
    rel = [RelativeSnapshot("IT", f"t{i}", rel_median=-0.4, rel_breadth=-0.3,
                            sector_median=-0.8, market_median=-0.4) for i in range(5)]
    b = persistent_bias(rel)
    assert b["bias"] == "laggard"
    assert b["avg_rel_median"] == pytest.approx(-0.4)


def test_persistent_bias_leader():
    rel = [RelativeSnapshot("RE", f"t{i}", rel_median=0.5, rel_breadth=0.3,
                            sector_median=0.2, market_median=-0.3) for i in range(5)]
    assert persistent_bias(rel)["bias"] == "leader"


def test_persistent_bias_neutral():
    rel = [RelativeSnapshot("FS", f"t{i}", rel_median=0.05, rel_breadth=0.0,
                            sector_median=-0.3, market_median=-0.35) for i in range(5)]
    assert persistent_bias(rel)["bias"] == "neutral"


def test_persistent_bias_empty():
    assert persistent_bias([])["bias"] == "neutral"
