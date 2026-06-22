"""ATR / regime-aware trail-width sizing — the pure core.

Computes a from-entry trailing-stop width as an ATR multiple, modulated by the
trade's setup class and the market regime, then sizes quantity so the rupee risk
stays pinned to the budget (wider trail → fewer shares, risk invariant).

Pure — no I/O. Both `nf-size --atr-trail` (live data) and the backtest k-sweep
import this so the width logic is identical in production and in validation.

Origin: docs/plans/2026-06-22-atr-regime-trail-width.md (Pranav, 2026-06-22).
The SPLPETRO whipsaw (a flat 2% trail fired at the morning low; a wider stop
never triggers) showed that trail WIDTH must scale to instrument volatility
(ATR), not a fixed percent.

The k-sweep (~8k entries) then found NO durable per-cell width edge — width is
second-order to the entry-regime gate, and best-k is marginal/OOS-unstable. So
this module is deliberately a FLOOR: an ATR-grounded baseline + risk-invariant
sizing that prevents the blind-flat-2% error. The real edge is NS's per-situation
tuning of the width (especially managing runners in trending), which no formula
captures. Output is a "baseline to tune," not an authority.
"""
from __future__ import annotations

import math
from typing import Optional

# Width clamp (% of entry price). FLOOR stops over-tightening a dead-quiet
# largecap; CEIL is a "needs more room than this → thesis is probably wrong /
# share count too small to bother" cutoff. Seeds — tune via the sweep.
FLOOR_PCT = 1.5
CEIL_PCT = 6.0

# Setup noise-tolerance classes. A trade's setup determines how much room the
# trail must give before the thesis is genuinely invalidated.
#   REVERSION — the snapback IS the thesis (gap fade, VWAP pullback): widest.
#   MOMENTUM  — a reversal means the thesis is dead fast (ORB, breakout): tightest.
#   NEUTRAL   — everything else: middle.
REVERSION = "REVERSION"
MOMENTUM = "MOMENTUM"
NEUTRAL = "NEUTRAL"

# Regimes (canonical, matching nf-regime output).
TRENDING = "trending"
MIXED = "mixed"
RANGE_BOUND = "range_bound"

# Baseline ATR multiple. The k-sweep (2026-06-22, ~8k entries) found NO durable
# per-cell width edge: width is second-order (~10×) to the entry-regime gate and
# marginal / out-of-sample-unstable. So k is a single sane BASELINE that NS tunes
# per trade — not a per-cell oracle. The formula is the FLOOR (prevents the
# blind-flat-2% SPLPETRO whipsaw); NS's per-situation tuning is the edge.
# See docs/plans/2026-06-22-atr-regime-trail-width.md §10a.
BASE_K = 2.75
# A gentle, DOCUMENTED lean — not a measured edge: give trending runners a touch
# more room, clean range-bound reversions a touch less. Deliberately small; the
# tuning that matters is NS's, per situation.
REGIME_NUDGE = {TRENDING: 0.25, MIXED: 0.0, RANGE_BOUND: -0.25}

# v1 = intraday ATR-14 "as-is" (spec §7). The opening 15-min bars inflate ATR on
# gap days; a future iteration may bump k or read a stabilized ATR in the first
# ~30 min. Kept as a hook, no bump by default so v1 is pure ATR-as-is.
OPENING_K_BUMP = 0.0

# Keyword → setup class. Covers both nf-morning-scan detect_setup() strings
# ("Gap fade candidate", "VWAP pullback", "ORB breakout", ...) and the mandate
# tagging enum (gap_fade|orb|momentum|reversal|regime|fno_structure|other).
_SETUP_KEYWORDS = [
    (REVERSION, ("gap fade", "gap_fade", "fade", "vwap pullback", "vwap_pullback",
                 "vwap rejection", "vwap_rejection", "mean_reversion", "mean reversion",
                 "reversion", "reversal", "bounce")),
    (MOMENTUM, ("orb", "breakout", "breakdown", "momentum", "continuation",
                "trend_following", "trend following")),
    # NEUTRAL is the default (relative strength/weakness, "watching", regime, other).
]


def setup_to_class(setup: Optional[str]) -> str:
    """Map a free-form setup string to a noise-tolerance class. Default NEUTRAL."""
    if not setup:
        return NEUTRAL
    s = setup.strip().lower()
    for cls, keywords in _SETUP_KEYWORDS:
        if any(kw in s for kw in keywords):
            return cls
    return NEUTRAL


def normalize_regime(regime: Optional[str]) -> str:
    """Normalize a regime label to one of trending/mixed/range_bound. Default MIXED."""
    if not regime:
        return MIXED
    r = regime.strip().lower().replace("-", "_").replace(" ", "_")
    if r in ("trending", "trend", "uptrend", "downtrend"):
        return TRENDING
    if r in ("range_bound", "rangebound", "range", "ranging"):
        return RANGE_BOUND
    return MIXED


def lookup_k(setup_class: str, regime: str, *, opening: bool = False) -> float:
    """Baseline ATR multiple = BASE_K + a small regime lean. NS tunes from here.

    ``setup_class`` is accepted for signature/context compatibility but no longer
    drives width — the sweep showed the setup×width split doesn't hold; setup
    matters for the entry-regime GATE (mandate), not the trail width.
    """
    k = BASE_K + REGIME_NUDGE.get(normalize_regime(regime), 0.0)
    if opening:
        k += OPENING_K_BUMP
    return k


def trail_pct_from_atr(atr: float, entry_price: float, k: float,
                       *, floor_pct: float = FLOOR_PCT,
                       ceil_pct: float = CEIL_PCT) -> float:
    """trail_pct = clamp(k × ATR / entry × 100, floor, ceil). Rounded to 2dp."""
    if entry_price <= 0 or atr <= 0 or k <= 0:
        raise ValueError("entry_price, atr, and k must all be > 0")
    raw = k * atr / entry_price * 100.0
    return round(min(max(raw, floor_pct), ceil_pct), 2)


def size_from_trail(entry_price: float, trail_pct: float, risk_budget: float,
                    *, capital: Optional[float] = None,
                    leverage: float = 1.0) -> dict:
    """Quantity such that a trail-distance stop hit ≈ ``risk_budget``.

    Mirrors nf-size's equity formula: qty_by_risk vs qty_by_capital, whichever
    binds. ``sl_points`` is the trail distance in absolute price.
    """
    if entry_price <= 0 or trail_pct <= 0:
        raise ValueError("entry_price and trail_pct must be > 0")
    sl_points = entry_price * trail_pct / 100.0
    qty_by_risk = math.floor(risk_budget / sl_points) if sl_points > 0 else 0
    if capital is not None and capital > 0:
        qty_by_capital = math.floor(capital * leverage / entry_price)
        qty = max(0, min(qty_by_risk, qty_by_capital))
        binding = "risk" if qty_by_risk <= qty_by_capital else "capital"
    else:
        qty_by_capital = None
        qty = max(0, qty_by_risk)
        binding = "risk"
    return {
        "sl_points": round(sl_points, 2),
        "qty_by_risk": qty_by_risk,
        "qty_by_capital": qty_by_capital,
        "recommended_qty": qty,
        "actual_risk_amount": round(qty * sl_points, 2),
        "binding_constraint": binding,
    }


def compute_atr_trail(*, atr: float, entry_price: float, setup: Optional[str],
                      regime: Optional[str], risk_budget: float,
                      capital: Optional[float] = None, leverage: float = 1.0,
                      opening: bool = False, k_override: Optional[float] = None,
                      floor_pct: float = FLOOR_PCT,
                      ceil_pct: float = CEIL_PCT) -> dict:
    """End-to-end pure computation: (atr, entry, setup, regime, risk) → sized trail.

    Returns the full decision dict the CLI and the sweep both consume. ``k_override``
    skips the table (used for NS overrides and for sweeping k).
    """
    setup_class = setup_to_class(setup)
    reg = normalize_regime(regime)
    k = k_override if k_override is not None else lookup_k(setup_class, reg, opening=opening)
    trail_pct = trail_pct_from_atr(atr, entry_price, k, floor_pct=floor_pct, ceil_pct=ceil_pct)
    sizing = size_from_trail(entry_price, trail_pct, risk_budget,
                             capital=capital, leverage=leverage)
    atr_pct = round(atr / entry_price * 100.0, 2)
    clamped = (trail_pct in (floor_pct, ceil_pct)
               and round(k * atr / entry_price * 100.0, 2) != trail_pct)
    return {
        "atr_14": round(atr, 2),
        "atr_pct": atr_pct,
        "regime": reg,
        "setup_class": setup_class,
        "k": round(k, 3),
        "k_source": "override" if k_override is not None else "baseline",
        "trail_percent": trail_pct,
        "clamped": clamped,
        "rationale": (f"baseline k={round(k, 2)} ({reg}); ATR {round(atr, 2)} "
                      f"({atr_pct}%) → {trail_pct}% trail. TUNE to the tape — this "
                      f"is a floor, not a verdict; the width judgment is yours."),
        **sizing,
    }
