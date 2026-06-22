"""Tests for the ATR/regime-aware trail-width core (services/atr_trail.py).

Covers setup-class mapping, regime normalization, k lookup, the clamp, the
risk-invariant sizing, and the end-to-end compute — including the SPLPETRO
motivating case (a 3% trail that a flat 2% would have whipsawed).
"""
from __future__ import annotations

import math

import pytest

from services.atr_trail import (
    BASE_K,
    CEIL_PCT,
    FLOOR_PCT,
    MOMENTUM,
    NEUTRAL,
    RANGE_BOUND,
    REGIME_NUDGE,
    REVERSION,
    TRENDING,
    compute_atr_trail,
    lookup_k,
    normalize_regime,
    setup_to_class,
    size_from_trail,
    trail_pct_from_atr,
)


# ── setup_to_class ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("setup,expected", [
    ("Gap fade candidate", REVERSION),
    ("gap_fade", REVERSION),
    ("VWAP pullback", REVERSION),
    ("VWAP rejection", REVERSION),
    ("reversal", REVERSION),
    ("ORB breakout", MOMENTUM),
    ("ORB breakdown", MOMENTUM),
    ("Momentum continuation", MOMENTUM),
    ("breakout", MOMENTUM),
    ("Relative strength leader", NEUTRAL),
    ("Watching", NEUTRAL),
    ("regime", NEUTRAL),
    ("other", NEUTRAL),
    (None, NEUTRAL),
    ("", NEUTRAL),
])
def test_setup_to_class(setup, expected):
    assert setup_to_class(setup) == expected


# ── normalize_regime ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("regime,expected", [
    ("trending", TRENDING),
    ("TRENDING", TRENDING),
    ("range_bound", RANGE_BOUND),
    ("RANGE-BOUND", RANGE_BOUND),
    ("range bound", RANGE_BOUND),
    ("mixed", MIXED := "mixed"),
    ("anything else", "mixed"),
    (None, "mixed"),
])
def test_normalize_regime(regime, expected):
    assert normalize_regime(regime) == expected


# ── lookup_k ─────────────────────────────────────────────────────────────────

def test_lookup_k_is_baseline_plus_regime_nudge():
    assert lookup_k(REVERSION, RANGE_BOUND) == BASE_K + REGIME_NUDGE[RANGE_BOUND]
    assert lookup_k(MOMENTUM, TRENDING) == BASE_K + REGIME_NUDGE[TRENDING]
    # mixed has no nudge → pure baseline
    assert lookup_k(NEUTRAL, "mixed") == BASE_K


def test_lookup_k_independent_of_setup_class():
    # Sweep verdict: setup does NOT drive width. Same regime → same k regardless.
    for regime in (TRENDING, "mixed", RANGE_BOUND):
        ks = {lookup_k(cls, regime) for cls in (REVERSION, MOMENTUM, NEUTRAL)}
        assert len(ks) == 1


def test_lookup_k_trending_gets_more_room_than_range_bound():
    # The small documented lean: runners (trending) a touch wider than chop.
    assert lookup_k(NEUTRAL, TRENDING) > lookup_k(NEUTRAL, RANGE_BOUND)


def test_lookup_k_unknown_regime_falls_back_to_baseline():
    assert lookup_k("NONSENSE", "garbage") == BASE_K


# ── trail_pct_from_atr + clamp ───────────────────────────────────────────────

def test_trail_pct_basic():
    # ATR 13.3 on entry 779.18 at k=3.0 → ~5.12% raw, clamped to ceil 6.0? No: 0.0512×... check
    # raw = 3.0 × 13.3 / 779.18 × 100 = 5.12 → within [1.5, 6.0]
    assert trail_pct_from_atr(13.3, 779.18, 3.0) == pytest.approx(5.12, abs=0.02)


def test_trail_pct_clamps_to_floor():
    # Tiny ATR on a big price → below floor → clamped up.
    assert trail_pct_from_atr(0.5, 1000.0, 1.5) == FLOOR_PCT


def test_trail_pct_clamps_to_ceil():
    # Huge ATR → above ceil → clamped down.
    assert trail_pct_from_atr(100.0, 500.0, 3.0) == CEIL_PCT


@pytest.mark.parametrize("atr,entry,k", [(0, 100, 2), (10, 0, 2), (10, 100, 0)])
def test_trail_pct_rejects_nonpositive(atr, entry, k):
    with pytest.raises(ValueError):
        trail_pct_from_atr(atr, entry, k)


# ── size_from_trail (risk-invariance) ────────────────────────────────────────

def test_size_risk_bound():
    out = size_from_trail(779.18, 3.1, 5000.0)
    # sl_points = 779.18 × 3.1% = 24.15; qty = floor(5000/24.15) = 207
    assert out["sl_points"] == pytest.approx(24.15, abs=0.05)
    assert out["recommended_qty"] == 207
    assert out["actual_risk_amount"] <= 5000.0
    assert out["binding_constraint"] == "risk"


def test_size_wider_trail_fewer_shares_same_risk():
    """Risk-invariance: widening the trail reduces qty, risk stays ≤ budget."""
    narrow = size_from_trail(800.0, 2.0, 5000.0)
    wide = size_from_trail(800.0, 4.0, 5000.0)
    assert wide["recommended_qty"] < narrow["recommended_qty"]
    assert narrow["actual_risk_amount"] <= 5000.0
    assert wide["actual_risk_amount"] <= 5000.0
    # roughly half the shares for double the width
    assert wide["recommended_qty"] == pytest.approx(narrow["recommended_qty"] / 2, rel=0.02)


def test_size_capital_binds():
    # Tiny capital wall binds before risk.
    out = size_from_trail(1000.0, 3.0, 100000.0, capital=10000.0, leverage=1.0)
    assert out["binding_constraint"] == "capital"
    assert out["recommended_qty"] == 10  # floor(10000/1000)


# ── compute_atr_trail (end-to-end) ───────────────────────────────────────────

def test_compute_splpetro_case():
    """SPLPETRO: an ATR-grounded baseline yields a trail materially wider than the
    blind flat-2% that whipsawed — the FLOOR the formula provides. (The last mile
    to 'survive this exact path' is NS's tuning, not the formula's job.)"""
    out = compute_atr_trail(
        atr=13.3, entry_price=779.18, setup="Gap fade candidate",
        regime="range_bound", risk_budget=5000.0,
    )
    assert out["setup_class"] == REVERSION   # still classified (for the gate, not width)
    assert out["regime"] == RANGE_BOUND
    assert out["k"] == BASE_K + REGIME_NUDGE[RANGE_BOUND]
    # Materially wider than the blind 2% that got whipsawed.
    assert out["trail_percent"] > 2.0
    assert "baseline" in out["rationale"] and "TUNE" in out["rationale"]


def test_compute_k_override_skips_table():
    out = compute_atr_trail(
        atr=10.0, entry_price=500.0, setup="ORB breakout", regime="trending",
        risk_budget=5000.0, k_override=4.0,
    )
    assert out["k"] == 4.0
    assert out["k_source"] == "override"


def test_compute_reports_clamp_flag():
    out = compute_atr_trail(
        atr=100.0, entry_price=500.0, setup="reversal", regime="range_bound",
        risk_budget=5000.0,
    )
    assert out["trail_percent"] == CEIL_PCT
    assert out["clamped"] is True


def test_compute_momentum_trending_uses_baseline_plus_nudge():
    out = compute_atr_trail(
        atr=10.0, entry_price=500.0, setup="ORB breakout", regime="trending",
        risk_budget=5000.0,
    )
    assert out["setup_class"] == MOMENTUM            # classified, but doesn't drive width
    assert out["k"] == BASE_K + REGIME_NUDGE[TRENDING]
