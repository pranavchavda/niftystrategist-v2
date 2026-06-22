"""ATR-sized trailing-stop k-sweep — measure the trail-width table.

Answers the empirical question from the SPLPETRO whipsaw (2026-06-22): holding
entries fixed, how does trail WIDTH (as an ATR multiple k) affect a trail-only
exit, and does the best k differ by regime? Replaces the seed K_TABLE in
``services.atr_trail`` with measured values.

Design choices (and their honesty caveats):
- **ATR is read AS-OF-ENTRY** (candles up to and including the entry bar), never
  end-of-day. SPLPETRO proved this matters: its ATR-14 was 8.67 at the 09:24
  entry vs 5.28 at the calm close — a 3.6% vs 2.2% trail. Using entry-bar ATR is
  the whole point.
- **Entries held fixed while k varies** — this isolates the EXIT. v1 ships the
  gap-fade entry (the REVERSION class, SPLPETRO's class); ORB/momentum is a fast
  follow.
- **Regime is a candle-derived PROXY** computed from the market index's own
  intraday structure (day-range / trend / oscillation), because live nf-regime
  (VIX, PCR, tier-1 scan counts) can't be reconstructed historically. Labelled
  as a proxy; directionally aligned with nf-regime's structural signals, not
  identical.
- **Fill is optimistic minus slippage** — exit at the trail level less
  ``slippage_bps`` (mirrors backtesting/engine.py). Real gaps/slippage are worse,
  so prefer the *relative* k-ranking and bias k a touch wider than the optimum.
- **Constant-risk comparison** — each trade is sized to a fixed ₹ risk budget at
  its own trail width (wider trail → fewer shares), so ₹/trade across k values is
  apples-to-apples (the risk-invariance property).

Origin: docs/plans/2026-06-22-atr-regime-trail-width.md.
"""
from __future__ import annotations

import logging
import math
import statistics
from typing import Optional

from services.atr_trail import (
    RANGE_BOUND, TRENDING, MIXED,
    trail_pct_from_atr, FLOOR_PCT, CEIL_PCT,
)

logger = logging.getLogger(__name__)

DEFAULT_K_GRID = [1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
SQUAREOFF = "15:15"
RISK_BUDGET = 5000.0   # constant ₹ risk per trade for comparison
MIN_GAP_PCT = 1.5      # gap-fade entry threshold (matches detect_setup)


def _val(c, k):
    return c.get(k) if isinstance(c, dict) else getattr(c, k, None)


def _ts(c) -> str:
    return str(_val(c, "timestamp") or "")


def _hhmm(c) -> str:
    """'HH:MM' from an ISO timestamp like 2026-06-22T09:15:00+05:30."""
    t = _ts(c)
    return t[11:16] if len(t) >= 16 else ""


def _date(c) -> str:
    return _ts(c)[:10]


def group_by_day(candles: list) -> dict:
    """Ordered {date_str: [candles]} preserving sequence."""
    days: dict = {}
    for c in candles:
        days.setdefault(_date(c), []).append(c)
    return days


# ── entry: gap-fade (REVERSION) ──────────────────────────────────────────────

def gap_fade_entry(day_candles: list, prev_close: float,
                   min_gap_pct: float = MIN_GAP_PCT) -> Optional[tuple]:
    """Enter at the first 15-min bar CLOSE if |gap| ≥ threshold; fade the gap.

    Returns (entry_idx_in_day, entry_price, direction) or None.
    """
    if not day_candles or not prev_close or prev_close <= 0:
        return None
    day_open = _val(day_candles[0], "open")
    if not day_open:
        return None
    gap_pct = (day_open - prev_close) / prev_close * 100.0
    if abs(gap_pct) < min_gap_pct:
        return None
    direction = "short" if gap_pct > 0 else "long"   # fade
    entry_price = _val(day_candles[0], "close")
    if not entry_price or entry_price <= 0:
        return None
    return 0, float(entry_price), direction


# ── entry: opening-range breakout (MOMENTUM) ─────────────────────────────────

def orb_entry(day_candles: list, *, or_bars: int = 2,
              min_break_pct: float = 0.0) -> Optional[tuple]:
    """Opening-range breakout: enter on the first bar that CLOSES beyond the
    first ``or_bars`` bars' range. Long above the OR high, short below the OR low.

    Returns (entry_idx_in_day, entry_price, direction) or None (no break that day).
    Does not use prev_close (signature kept compatible via **ignored kwargs).
    """
    if len(day_candles) <= or_bars:
        return None
    or_high = max(_val(c, "high") for c in day_candles[:or_bars] if _val(c, "high"))
    or_low = min(_val(c, "low") for c in day_candles[:or_bars] if _val(c, "low"))
    if not or_high or not or_low or or_low <= 0:
        return None
    for i in range(or_bars, len(day_candles)):
        cl = _val(day_candles[i], "close")
        if not cl:
            continue
        if cl > or_high * (1 + min_break_pct / 100.0):
            return i, float(cl), "long"
        if cl < or_low * (1 - min_break_pct / 100.0):
            return i, float(cl), "short"
    return None


# ── ATR as-of-entry ──────────────────────────────────────────────────────────

def atr_at(series_up_to_entry: list) -> Optional[float]:
    """ATR-14 from the candle series ending at (and including) the entry bar.

    Computes ATR directly (ta.volatility.AverageTrueRange, window=14) rather than
    a full calculate_indicators — numerically identical to production's atr_14 but
    far cheaper, which matters across hundreds of entries in a sweep.
    """
    if len(series_up_to_entry) < 50:
        return None
    import pandas as pd
    import ta
    highs = [_val(c, "high") for c in series_up_to_entry]
    lows = [_val(c, "low") for c in series_up_to_entry]
    closes = [_val(c, "close") for c in series_up_to_entry]
    if any(v is None for v in (highs[-1], lows[-1], closes[-1])):
        return None
    df = pd.DataFrame({"high": highs, "low": lows, "close": closes}).astype(float)
    atr = ta.volatility.AverageTrueRange(
        df["high"], df["low"], df["close"], window=14
    ).average_true_range().iloc[-1]
    return float(atr) if (atr and atr > 0 and not math.isnan(atr)) else None


# ── trail-only exit simulator (mirrors engine.py model) ──────────────────────

def simulate_trail(day_candles: list, entry_idx: int, entry_price: float,
                   direction: str, trail_pct: float, *,
                   slippage_bps: float = 5.0, squareoff: str = SQUAREOFF) -> dict:
    """Bar-by-bar trail-only exit from entry. Returns exit + path metrics.

    pnl_per_share is signed for direction. Exit at the trail level less slippage
    (optimistic, matches engine.py). Forced squareoff at the first bar ≥ squareoff
    time (exit at that bar's open ≈ the cutoff).
    """
    slip = slippage_bps / 10000.0
    is_long = direction == "long"
    anchor = entry_price  # highest (long) / lowest (short), ratchets from entry
    exit_price = None
    exit_reason = "eod"
    mfe = 0.0  # max favourable excursion (₹/share)
    mae = 0.0  # max adverse excursion (₹/share)

    for c in day_candles[entry_idx + 1:]:
        hi, lo = _val(c, "high"), _val(c, "low")
        if hi is None or lo is None:
            continue
        # path excursions
        if is_long:
            mfe = max(mfe, hi - entry_price)
            mae = min(mae, lo - entry_price)
        else:
            mfe = max(mfe, entry_price - lo)
            mae = min(mae, entry_price - hi)
        # forced squareoff
        if squareoff and _hhmm(c) >= squareoff:
            exit_price = _val(c, "open") or _val(c, "close")
            exit_reason = "squareoff"
            break
        # ratchet + trail check
        if is_long:
            anchor = max(anchor, hi)
            stop = anchor * (1 - trail_pct / 100.0)
            if lo <= stop:
                exit_price = stop * (1 - slip)
                exit_reason = "trail"
                break
        else:
            anchor = min(anchor, lo)
            stop = anchor * (1 + trail_pct / 100.0)
            if hi >= stop:
                exit_price = stop * (1 + slip)
                exit_reason = "trail"
                break

    if exit_price is None:  # ran to end of day with no squareoff bar seen
        exit_price = _val(day_candles[-1], "close")
        exit_reason = "eod"

    pnl_per_share = (exit_price - entry_price) if is_long else (entry_price - exit_price)
    return {
        "exit_price": round(float(exit_price), 2),
        "exit_reason": exit_reason,
        "pnl_per_share": round(float(pnl_per_share), 2),
        "mfe": round(float(mfe), 2),
        "mae": round(float(mae), 2),
    }


# ── regime proxy from the index's own intraday structure ─────────────────────

def regime_proxy(market_day_candles: list) -> dict:
    """Candle-derived regime label for one day (trending/mixed/range_bound).

    A simplified composite of nf-regime's *structural* (candle-derivable) signals:
    day-range, first-2h trend quality, and midpoint oscillation. NOT the live
    nf-regime (no VIX/PCR/scan inputs) — a historical proxy.
    """
    closes = [float(_val(c, "close")) for c in market_day_candles if _val(c, "close")]
    highs = [float(_val(c, "high")) for c in market_day_candles if _val(c, "high")]
    lows = [float(_val(c, "low")) for c in market_day_candles if _val(c, "low")]
    op = float(_val(market_day_candles[0], "open") or (closes[0] if closes else 0))
    if len(closes) < 6 or op <= 0:
        return {"regime": MIXED, "composite": 0.0, "n": len(closes)}

    day_high, day_low = max(highs), min(lows)
    rng_pct = (day_high - day_low) / op * 100.0
    if rng_pct >= 0.8:
        s_range = 1.0
    elif rng_pct >= 0.5:
        s_range = 0.3
    elif rng_pct >= 0.3:
        s_range = -0.3
    else:
        s_range = -1.0

    # trend quality over first ~2h (8 × 15-min bars): R² + slope of closes
    seg = closes[:8] if len(closes) >= 8 else closes
    n = len(seg)
    xs = list(range(n))
    mx = sum(xs) / n
    my = sum(seg) / n
    sxx = sum((x - mx) ** 2 for x in xs) or 1e-9
    sxy = sum((xs[i] - mx) * (seg[i] - my) for i in range(n))
    slope = sxy / sxx
    yhat = [my + slope * (x - mx) for x in xs]
    ss_res = sum((seg[i] - yhat[i]) ** 2 for i in range(n))
    ss_tot = sum((y - my) ** 2 for y in seg) or 1e-9
    r2 = max(0.0, 1 - ss_res / ss_tot)
    slope_pct = slope / op * 100.0  # % of price per bar
    if abs(slope_pct) > 0.06 and r2 > 0.5:
        s_trend = 1.0
    elif abs(slope_pct) > 0.025 and r2 > 0.3:
        s_trend = 0.5
    elif r2 > 0.1:
        s_trend = -0.3
    else:
        s_trend = -1.0

    # oscillation: fraction of bars whose close crosses the day midpoint
    mid = (day_high + day_low) / 2.0
    crossings = sum(1 for i in range(1, len(closes))
                    if (closes[i - 1] - mid) * (closes[i] - mid) < 0)
    osc = crossings / max(1, len(closes) - 1)
    if osc > 0.25:
        s_osc = -1.0
    elif osc > 0.12:
        s_osc = -0.5
    elif osc > 0.05:
        s_osc = 0.0
    else:
        s_osc = 0.5

    composite = (s_range + s_trend + s_osc) / 3.0
    if composite > 0.3:
        regime = TRENDING
    elif composite < -0.15:
        regime = RANGE_BOUND
    else:
        regime = MIXED
    return {"regime": regime, "composite": round(composite, 3),
            "range_pct": round(rng_pct, 2), "r2": round(r2, 2),
            "osc": round(osc, 2), "n": len(closes)}
