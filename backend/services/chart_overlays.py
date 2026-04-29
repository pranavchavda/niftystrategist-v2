"""Compute full-series indicator overlays for chart rendering.

The monitor's indicator_engine and the TechnicalAnalysisService both return
only the latest-bar value of each indicator. Charts need the entire series
aligned to candle timestamps. This module produces that.

Each overlay function takes `candles` (list of dicts with timestamp/open/high/
low/close/volume) and returns a dict shaped for a frontend line/marker layer:

    {
        "lines": {
            "<line_name>": [{"time": <unix|iso>, "value": <float>}, ...],
        },
        "markers": [
            {"time": <unix|iso>, "type": "buy"|"sell", "text": "UT Bot"},
            ...
        ],
        "panes": [
            {
                "id": "rsi",
                "title": "RSI(14)",
                "lines": {"rsi": [{"time", "value"}, ...]},
                "range": [0, 100],
                "levels": [30, 70],
            },
            ...
        ],
    }

Lines in `lines` are overlaid on the main price pane. Entries in `panes` are
rendered in separate stacked panes below the price pane (e.g. RSI, MACD).
"""
from __future__ import annotations

from typing import Any

import pandas as pd
import ta


def _to_df(candles: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(candles)
    if "timestamp" in df.columns:
        df = df.sort_values("timestamp").reset_index(drop=True)
    elif "time" in df.columns:
        df = df.sort_values("time").reset_index(drop=True)
    return df


def _time_key(row: dict) -> Any:
    # API already normalized to "time" (unix int for intraday, YYYY-MM-DD str
    # for daily). Fall back to "timestamp" if a raw candle dict was passed in.
    return row.get("time") or row.get("timestamp")


def _line_from_series(df: pd.DataFrame, series: pd.Series) -> list[dict]:
    """Convert a pandas Series indexed like df to [{time, value}] dropping NaN."""
    rows = df.to_dict("records")
    out: list[dict] = []
    for i, row in enumerate(rows):
        v = series.iloc[i]
        if pd.isna(v):
            continue
        out.append({"time": _time_key(row), "value": float(v)})
    return out


# ---------------------------------------------------------------------------
# Moving averages (overlays on price pane)
# ---------------------------------------------------------------------------

def compute_sma_overlay(candles: list[dict], period: int = 20) -> dict:
    if len(candles) < period:
        return {"lines": {}, "markers": [], "panes": []}
    df = _to_df(candles)
    sma = ta.trend.SMAIndicator(df["close"].astype(float), window=period).sma_indicator()
    return {
        "lines": {f"sma_{period}": _line_from_series(df, sma)},
        "markers": [],
        "panes": [],
    }


def compute_ema_overlay(candles: list[dict], period: int = 20) -> dict:
    if len(candles) < period:
        return {"lines": {}, "markers": [], "panes": []}
    df = _to_df(candles)
    ema = ta.trend.EMAIndicator(df["close"].astype(float), window=period).ema_indicator()
    return {
        "lines": {f"ema_{period}": _line_from_series(df, ema)},
        "markers": [],
        "panes": [],
    }


def compute_bbands_overlay(candles: list[dict], period: int = 20, stddev: float = 2.0) -> dict:
    if len(candles) < period:
        return {"lines": {}, "markers": [], "panes": []}
    df = _to_df(candles)
    bb = ta.volatility.BollingerBands(df["close"].astype(float), window=period, window_dev=stddev)
    return {
        "lines": {
            "bb_upper": _line_from_series(df, bb.bollinger_hband()),
            "bb_middle": _line_from_series(df, bb.bollinger_mavg()),
            "bb_lower": _line_from_series(df, bb.bollinger_lband()),
        },
        "markers": [],
        "panes": [],
    }


def compute_vwap_overlay(candles: list[dict]) -> dict:
    df = _to_df(candles)
    if "volume" not in df.columns or df["volume"].sum() == 0:
        return {"lines": {}, "markers": [], "panes": []}
    vwap = ta.volume.VolumeWeightedAveragePrice(
        high=df["high"].astype(float),
        low=df["low"].astype(float),
        close=df["close"].astype(float),
        volume=df["volume"].astype(float),
        window=14,
    ).volume_weighted_average_price()
    return {
        "lines": {"vwap": _line_from_series(df, vwap)},
        "markers": [],
        "panes": [],
    }


# ---------------------------------------------------------------------------
# Oscillators (separate panes)
# ---------------------------------------------------------------------------

def compute_rsi_pane(candles: list[dict], period: int = 14) -> dict:
    if len(candles) < period + 1:
        return {"lines": {}, "markers": [], "panes": []}
    df = _to_df(candles)
    rsi = ta.momentum.RSIIndicator(df["close"].astype(float), window=period).rsi()
    return {
        "lines": {},
        "markers": [],
        "panes": [
            {
                "id": "rsi",
                "title": f"RSI({period})",
                "lines": {"rsi": _line_from_series(df, rsi)},
                "range": [0, 100],
                "levels": [30, 70],
            }
        ],
    }


def compute_macd_pane(
    candles: list[dict],
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> dict:
    if len(candles) < slow + signal:
        return {"lines": {}, "markers": [], "panes": []}
    df = _to_df(candles)
    macd = ta.trend.MACD(
        df["close"].astype(float),
        window_slow=slow,
        window_fast=fast,
        window_sign=signal,
    )
    rows = df.to_dict("records")
    hist_series = macd.macd_diff()
    hist_points: list[dict] = []
    for i, row in enumerate(rows):
        v = hist_series.iloc[i]
        if pd.isna(v):
            continue
        hist_points.append({"time": _time_key(row), "value": float(v)})
    return {
        "lines": {},
        "markers": [],
        "panes": [
            {
                "id": "macd",
                "title": f"MACD({fast},{slow},{signal})",
                "lines": {
                    "macd": _line_from_series(df, macd.macd()),
                    "signal": _line_from_series(df, macd.macd_signal()),
                },
                "histogram": hist_points,
                "levels": [0],
            }
        ],
    }


def compute_stoch_pane(
    candles: list[dict],
    k: int = 14,
    d: int = 3,
    smooth: int = 3,
) -> dict:
    if len(candles) < k + d:
        return {"lines": {}, "markers": [], "panes": []}
    df = _to_df(candles)
    stoch = ta.momentum.StochasticOscillator(
        high=df["high"].astype(float),
        low=df["low"].astype(float),
        close=df["close"].astype(float),
        window=k,
        smooth_window=smooth,
    )
    return {
        "lines": {},
        "markers": [],
        "panes": [
            {
                "id": "stoch",
                "title": f"Stoch({k},{d},{smooth})",
                "lines": {
                    "k": _line_from_series(df, stoch.stoch()),
                    "d": _line_from_series(df, stoch.stoch_signal()),
                },
                "range": [0, 100],
                "levels": [20, 80],
            }
        ],
    }


def compute_atr_pane(candles: list[dict], period: int = 14) -> dict:
    if len(candles) < period + 1:
        return {"lines": {}, "markers": [], "panes": []}
    df = _to_df(candles)
    atr = ta.volatility.AverageTrueRange(
        df["high"].astype(float),
        df["low"].astype(float),
        df["close"].astype(float),
        window=period,
    ).average_true_range()
    return {
        "lines": {},
        "markers": [],
        "panes": [
            {
                "id": "atr",
                "title": f"ATR({period})",
                "lines": {"atr": _line_from_series(df, atr)},
            }
        ],
    }


# ---------------------------------------------------------------------------
# UT Bot (trailing stop overlay + flip markers) — original
# ---------------------------------------------------------------------------

def compute_utbot_overlay(
    candles: list[dict],
    period: int = 10,
    sensitivity: float = 1.0,
) -> dict:
    """Compute UT Bot trailing stop line + buy/sell flip markers.

    Returns a dict with:
      - lines.utbot_stop: list of {time, value} points for the trailing stop
      - markers: list of {time, type, text} for flip signals (one per flip)
    """
    if len(candles) < period + 2:
        return {"lines": {"utbot_stop": []}, "markers": [], "panes": []}

    df = _to_df(candles)
    atr = ta.volatility.AverageTrueRange(
        df["high"], df["low"], df["close"], window=period
    ).average_true_range()
    n_loss = sensitivity * atr
    src = df["close"].astype(float)

    stops: list[float] = [0.0] * len(df)
    positions: list[int] = [0] * len(df)

    for i in range(len(df)):
        # ta's ATR returns 0.0 during warm-up instead of NaN.
        if pd.isna(n_loss.iloc[i]) or n_loss.iloc[i] == 0.0:
            if i > 0:
                stops[i] = stops[i - 1]
                positions[i] = positions[i - 1]
            continue
        prev_stop = stops[i - 1] if i > 0 else 0.0
        prev_src = src.iloc[i - 1] if i > 0 else src.iloc[i]
        cur = src.iloc[i]
        nl = n_loss.iloc[i]
        if cur > prev_stop and prev_src > prev_stop:
            stops[i] = max(prev_stop, cur - nl)
        elif cur < prev_stop and prev_src < prev_stop:
            stops[i] = min(prev_stop, cur + nl)
        elif cur > prev_stop:
            stops[i] = cur - nl
        else:
            stops[i] = cur + nl
        prev_pos = positions[i - 1] if i > 0 else 0
        if i > 0 and prev_src < prev_stop and cur > prev_stop:
            positions[i] = 1
        elif i > 0 and prev_src > prev_stop and cur < prev_stop:
            positions[i] = -1
        else:
            positions[i] = prev_pos
        if positions[i] == 0:
            positions[i] = 1 if cur > stops[i] else -1

    rows = df.to_dict("records")
    stop_line = []
    markers = []
    for i, row in enumerate(rows):
        if stops[i] == 0.0:
            continue
        t = _time_key(row)
        stop_line.append({"time": t, "value": float(stops[i])})
        if i > 0 and positions[i] != positions[i - 1] and positions[i - 1] != 0:
            markers.append(
                {
                    "time": t,
                    "type": "buy" if positions[i] == 1 else "sell",
                    "text": "UT Bot",
                }
            )

    return {"lines": {"utbot_stop": stop_line}, "markers": markers, "panes": []}


# ---------------------------------------------------------------------------
# Supertrend (trailing stop overlay + flip markers)
# ---------------------------------------------------------------------------

def compute_supertrend_overlay(
    candles: list[dict],
    period: int = 10,
    multiplier: float = 3.0,
) -> dict:
    """Port of monitor/indicator_engine.py::supertrend, full-series.

    Emits `supertrend_line` (the active band — lower band when bullish,
    upper band when bearish) and buy/sell flip markers.
    """
    if len(candles) < period + 1:
        return {"lines": {"supertrend_line": []}, "markers": [], "panes": []}

    df = _to_df(candles)
    high = df["high"].astype(float).reset_index(drop=True)
    low = df["low"].astype(float).reset_index(drop=True)
    close = df["close"].astype(float).reset_index(drop=True)
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs(),
    ], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    hl2 = (high + low) / 2
    basic_upper = hl2 + multiplier * atr
    basic_lower = hl2 - multiplier * atr
    final_upper = basic_upper.copy()
    final_lower = basic_lower.copy()
    n = len(df)
    direction = [0] * n  # +1 bullish, -1 bearish
    for i in range(period, n):
        if (
            basic_upper.iloc[i] < final_upper.iloc[i - 1]
            or close.iloc[i - 1] > final_upper.iloc[i - 1]
        ):
            final_upper.iloc[i] = basic_upper.iloc[i]
        else:
            final_upper.iloc[i] = final_upper.iloc[i - 1]
        if (
            basic_lower.iloc[i] > final_lower.iloc[i - 1]
            or close.iloc[i - 1] < final_lower.iloc[i - 1]
        ):
            final_lower.iloc[i] = basic_lower.iloc[i]
        else:
            final_lower.iloc[i] = final_lower.iloc[i - 1]
        if i == period:
            direction[i] = 1 if close.iloc[i] > final_upper.iloc[i] else -1
        else:
            prev = direction[i - 1]
            if prev == 1 and close.iloc[i] < final_lower.iloc[i]:
                direction[i] = -1
            elif prev == -1 and close.iloc[i] > final_upper.iloc[i]:
                direction[i] = 1
            else:
                direction[i] = prev

    rows = df.to_dict("records")
    line: list[dict] = []
    markers: list[dict] = []
    for i, row in enumerate(rows):
        if direction[i] == 0:
            continue
        t = _time_key(row)
        band = float(final_lower.iloc[i]) if direction[i] == 1 else float(final_upper.iloc[i])
        if pd.isna(band):
            continue
        line.append({"time": t, "value": band})
        if i > 0 and direction[i] != direction[i - 1] and direction[i - 1] != 0:
            markers.append(
                {
                    "time": t,
                    "type": "buy" if direction[i] == 1 else "sell",
                    "text": "Supertrend",
                }
            )

    return {"lines": {"supertrend_line": line}, "markers": markers, "panes": []}


# ---------------------------------------------------------------------------
# HalfTrend (trend-state overlay + flip markers)
# ---------------------------------------------------------------------------

def compute_halftrend_overlay(
    candles: list[dict],
    amplitude: int = 2,
    atr_period: int = 100,
) -> dict:
    """Port of monitor/indicator_engine.py::halftrend, full-series.

    Returns the running trend reference price (max_low_price when bullish,
    min_high_price when bearish) plus buy/sell flip markers.
    """
    if len(candles) < max(amplitude + 2, atr_period):
        return {"lines": {"halftrend_line": []}, "markers": [], "panes": []}

    df = _to_df(candles)
    high = df["high"].astype(float).reset_index(drop=True)
    low = df["low"].astype(float).reset_index(drop=True)
    close = df["close"].astype(float).reset_index(drop=True)
    high_ma = high.rolling(amplitude).mean()
    low_ma = low.rolling(amplitude).mean()
    high_price = high.rolling(amplitude).max()
    low_price = low.rolling(amplitude).min()
    n = len(close)
    trend = [0] * n        # 0 = up, 1 = down
    next_trend = [0] * n
    max_low_price = float(low.iloc[0])
    min_high_price = float(high.iloc[0])
    line_value = [float("nan")] * n
    line_value[0] = max_low_price
    for i in range(1, n):
        trend[i] = trend[i - 1]
        next_trend[i] = next_trend[i - 1]
        if next_trend[i - 1] == 1:
            max_low_price = max(
                float(low_price.iloc[i]) if not pd.isna(low_price.iloc[i]) else max_low_price,
                max_low_price,
            )
            if (
                not pd.isna(high_ma.iloc[i])
                and high_ma.iloc[i] < max_low_price
                and close.iloc[i] < low.iloc[i - 1]
            ):
                trend[i] = 1
                next_trend[i] = 0
                max_low_price = float(low.iloc[i - 1])
        else:
            min_high_price = min(
                float(high_price.iloc[i]) if not pd.isna(high_price.iloc[i]) else min_high_price,
                min_high_price,
            )
            if (
                not pd.isna(low_ma.iloc[i])
                and low_ma.iloc[i] > min_high_price
                and close.iloc[i] > high.iloc[i - 1]
            ):
                trend[i] = 0
                next_trend[i] = 1
                min_high_price = float(high.iloc[i - 1])
        line_value[i] = max_low_price if trend[i] == 0 else min_high_price

    rows = df.to_dict("records")
    line: list[dict] = []
    markers: list[dict] = []
    for i, row in enumerate(rows):
        v = line_value[i]
        if pd.isna(v):
            continue
        t = _time_key(row)
        line.append({"time": t, "value": float(v)})
        if i > 0 and trend[i] != trend[i - 1]:
            # trend==0 is bullish; flipping to 0 = buy.
            markers.append(
                {
                    "time": t,
                    "type": "buy" if trend[i] == 0 else "sell",
                    "text": "HalfTrend",
                }
            )

    return {"lines": {"halftrend_line": line}, "markers": markers, "panes": []}


# ---------------------------------------------------------------------------
# SSL Hybrid (channel overlay + flip markers)
# ---------------------------------------------------------------------------

def compute_ssl_hybrid_overlay(
    candles: list[dict],
    period: int = 10,
) -> dict:
    """Port of monitor/indicator_engine.py::ssl_hybrid, full-series.

    Emits `ssl_line` (active channel band: high-SMA when bullish, low-SMA
    when bearish) and buy/sell flip markers. Baseline gating is omitted
    because it just suppresses the indicator value on the rules side; on
    a chart we always want a continuous reference.
    """
    if len(candles) < period + 1:
        return {"lines": {"ssl_line": []}, "markers": [], "panes": []}

    df = _to_df(candles)
    high = df["high"].astype(float).reset_index(drop=True)
    low = df["low"].astype(float).reset_index(drop=True)
    close = df["close"].astype(float).reset_index(drop=True)
    ssl_up = high.rolling(period).mean()
    ssl_down = low.rolling(period).mean()
    n = len(df)
    trend = [0] * n
    for i in range(period, n):
        if pd.isna(ssl_up.iloc[i]) or pd.isna(ssl_down.iloc[i]):
            trend[i] = trend[i - 1]
            continue
        if close.iloc[i] > ssl_up.iloc[i]:
            trend[i] = 1
        elif close.iloc[i] < ssl_down.iloc[i]:
            trend[i] = -1
        else:
            trend[i] = trend[i - 1]

    rows = df.to_dict("records")
    line: list[dict] = []
    markers: list[dict] = []
    for i, row in enumerate(rows):
        if trend[i] == 0:
            continue
        band = float(ssl_up.iloc[i]) if trend[i] == 1 else float(ssl_down.iloc[i])
        if pd.isna(band):
            continue
        t = _time_key(row)
        line.append({"time": t, "value": band})
        if i > 0 and trend[i] != trend[i - 1] and trend[i - 1] != 0:
            markers.append(
                {
                    "time": t,
                    "type": "buy" if trend[i] == 1 else "sell",
                    "text": "SSL Hybrid",
                }
            )

    return {"lines": {"ssl_line": line}, "markers": markers, "panes": []}


# ---------------------------------------------------------------------------
# EMA crossover (two lines + cross markers)
# ---------------------------------------------------------------------------

def compute_ema_crossover_overlay(
    candles: list[dict],
    fast: int = 9,
    slow: int = 21,
) -> dict:
    """EMA fast/slow with buy/sell markers on cross."""
    if len(candles) < slow + 1:
        return {"lines": {"ema_fast": [], "ema_slow": []}, "markers": [], "panes": []}

    df = _to_df(candles)
    close = df["close"].astype(float)
    ema_fast = ta.trend.EMAIndicator(close, window=fast).ema_indicator()
    ema_slow = ta.trend.EMAIndicator(close, window=slow).ema_indicator()

    rows = df.to_dict("records")
    fast_line: list[dict] = []
    slow_line: list[dict] = []
    markers: list[dict] = []
    prev_diff = None
    for i, row in enumerate(rows):
        f = ema_fast.iloc[i]
        s = ema_slow.iloc[i]
        if pd.isna(f) or pd.isna(s):
            continue
        t = _time_key(row)
        fast_line.append({"time": t, "value": float(f)})
        slow_line.append({"time": t, "value": float(s)})
        diff = float(f) - float(s)
        if prev_diff is not None:
            if prev_diff <= 0 and diff > 0:
                markers.append({"time": t, "type": "buy", "text": "EMA Cross"})
            elif prev_diff >= 0 and diff < 0:
                markers.append({"time": t, "type": "sell", "text": "EMA Cross"})
        prev_diff = diff

    return {
        "lines": {"ema_fast": fast_line, "ema_slow": slow_line},
        "markers": markers,
        "panes": [],
    }


# ---------------------------------------------------------------------------
# QQE MOD (oscillator pane)
# ---------------------------------------------------------------------------

def compute_qqe_mod_pane(
    candles: list[dict],
    rsi_period: int = 6,
    smoothing: int = 5,
) -> dict:
    """QQE MOD smoothed-RSI momentum, centered at 0 (>0 bullish, <0 bearish)."""
    needed = rsi_period + smoothing + 2
    if len(candles) < needed:
        return {"lines": {}, "markers": [], "panes": []}

    df = _to_df(candles)
    close = df["close"].astype(float)
    rsi = ta.momentum.RSIIndicator(close, window=rsi_period).rsi()
    rsi_ma = ta.trend.EMAIndicator(rsi, window=smoothing).ema_indicator()
    centered = rsi_ma - 50.0
    return {
        "lines": {},
        "markers": [],
        "panes": [
            {
                "id": "qqe_mod",
                "title": f"QQE MOD({rsi_period},{smoothing})",
                "lines": {"qqe": _line_from_series(df, centered)},
                "levels": [0],
            }
        ],
    }


def compute_renko_pane(
    candles: list[dict],
    brick_size: float | None = None,
    atr_period: int | None = None,
) -> dict:
    """Renko trend as a histogram pane keyed by candle close time.

    Walks the close series forming bricks; emits the running brick direction
    (+1 bullish / -1 bearish) at every candle close so it can be plotted
    alongside the candle chart on a shared time axis. This is the chart-side
    proxy for the rules engine's Renko indicator (`monitor/indicator_engine.py:374`).

    Box-size selection priority:
      1. Explicit `brick_size`        (fixed)
      2. `atr_period`                 (ATR over first `atr_period+1` bars,
                                        frozen for the window)
      3. Auto fallback                (`round(median_close * 0.001, 2)`,
                                        i.e. 0.1% of median price)
    """
    if len(candles) < 2:
        return {"lines": {}, "markers": [], "panes": []}

    size: float | None = None
    method = "fixed"
    if brick_size is not None and brick_size > 0:
        size = float(brick_size)
    elif atr_period is not None and atr_period > 1:
        ap = int(atr_period)
        if len(candles) < ap + 1:
            return {"lines": {}, "markers": [], "panes": []}
        trs: list[float] = []
        for i in range(1, ap + 1):
            hi = float(candles[i]["high"])
            lo = float(candles[i]["low"])
            pc = float(candles[i - 1]["close"])
            trs.append(max(hi - lo, abs(hi - pc), abs(lo - pc)))
        atr_val = sum(trs) / len(trs) if trs else 0.0
        if atr_val <= 0:
            return {"lines": {}, "markers": [], "panes": []}
        size = float(atr_val)
        method = "atr"
    else:
        closes_sorted = sorted(float(c["close"]) for c in candles)
        median = closes_sorted[len(closes_sorted) // 2]
        size = round(median * 0.001, 2)
    if not size or size <= 0:
        return {"lines": {}, "markers": [], "panes": []}

    base = float(candles[0]["close"])
    trend = 0
    histogram: list[dict] = []
    for c in candles[1:]:
        close = float(c["close"])
        diff = close - base
        while diff >= size:
            base += size
            trend = 1
            diff = close - base
        while diff <= -size:
            base -= size
            trend = -1
            diff = close - base
        # Suppress points before the first brick forms — the chart's
        # whitespace handling will skip them.
        if trend == 0:
            continue
        histogram.append({
            "time": c["time"],
            "value": float(trend),
        })

    return {
        "lines": {},
        "markers": [],
        "panes": [
            {
                "id": "renko",
                "title": f"Renko Trend ({method} {size:.2f})",
                "histogram": histogram,
                "lines": {},
                "range": [-1.5, 1.5],
                "levels": [0],
            }
        ],
    }


OVERLAY_COMPUTERS = {
    "utbot": compute_utbot_overlay,
    "sma": compute_sma_overlay,
    "ema": compute_ema_overlay,
    "bbands": compute_bbands_overlay,
    "vwap": compute_vwap_overlay,
    "rsi": compute_rsi_pane,
    "macd": compute_macd_pane,
    "stoch": compute_stoch_pane,
    "atr": compute_atr_pane,
    "supertrend": compute_supertrend_overlay,
    "halftrend": compute_halftrend_overlay,
    "ssl_hybrid": compute_ssl_hybrid_overlay,
    "ema_crossover": compute_ema_crossover_overlay,
    "qqe_mod": compute_qqe_mod_pane,
    "renko": compute_renko_pane,
}


def compute_overlays(
    candles: list[dict],
    names: list[str],
    params: dict[str, dict] | None = None,
) -> dict:
    """Run the requested overlay computers and merge their output.

    `names` may contain bare indicator names ("sma") or parameterized variants
    ("sma_50"). For parameterized forms the trailing integer is treated as the
    primary period. `params` is an optional mapping from overlay name to
    kwargs, e.g. ``{"utbot": {"period": 10, "sensitivity": 2.0}}``.
    """
    params = params or {}
    lines: dict[str, list] = {}
    markers: list[dict] = []
    panes: list[dict] = []
    for raw_name in names:
        # Support "sma_50" / "ema_21" / "rsi_21" shortcuts.
        base = raw_name
        extra_kwargs: dict = {}
        if "_" in raw_name:
            head, tail = raw_name.rsplit("_", 1)
            if tail.isdigit() and head in OVERLAY_COMPUTERS:
                base = head
                extra_kwargs["period"] = int(tail)
        fn = OVERLAY_COMPUTERS.get(base)
        if fn is None:
            continue
        kwargs = {**extra_kwargs, **params.get(raw_name, {}), **params.get(base, {})}
        try:
            result = fn(candles, **kwargs)
        except TypeError:
            # Indicator doesn't accept the kwargs we derived — fall back to defaults.
            result = fn(candles)
        lines.update(result.get("lines", {}))
        markers.extend(result.get("markers", []))
        panes.extend(result.get("panes", []))
    return {"lines": lines, "markers": markers, "panes": panes}
