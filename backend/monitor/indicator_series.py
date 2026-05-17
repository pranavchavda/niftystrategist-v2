"""Indicator series computation for backtests.

`compute_indicator(indicator, candles, params)` returns the value at the
END of the candle list — built for the live engine, where each tick
appends one candle and we recompute the latest value on close.

For backtests we know the full candle stream upfront and want the value
at every bar. The naive approach (call compute_indicator on every prefix)
is O(n²); for indicators whose underlying math is already O(n) on the
full series, that's pure waste.

This module exposes ``compute_indicator_series(indicator, candles,
params) -> list[float | None]`` that returns a list aligned to the input
candles — element i is the indicator value for candles[:i+1].

For each indicator with a native series implementation, the math is
pulled out of ``compute_indicator`` and adapted to return the full
series in one pass. Indicators without a native impl fall back to prefix
recompute so the API still works — they're just no faster than today.

The parity guarantee (enforced by ``tests/monitor/test_indicator_series_parity.py``):
for every indicator, every params, every prefix length n,
    compute_indicator_series(ind, candles, params)[n - 1]
        == compute_indicator(ind, candles[:n], params)
"""
from __future__ import annotations

from typing import Any, Callable

import numpy as np
import pandas as pd
import ta

from monitor.indicator_engine import compute_indicator


_SeriesFn = Callable[[pd.DataFrame, dict[str, Any]], list[float | None]]


def compute_indicator_series(
    indicator: str, candles: list[dict], params: dict[str, Any]
) -> list[float | None]:
    """Return the indicator value at every prefix of ``candles``.

    Element i corresponds to ``candles[:i+1]``. Bars where the indicator
    is not yet ready (warmup) are ``None`` — same semantic as
    ``compute_indicator`` returning ``None``.
    """
    n = len(candles)
    if n == 0:
        return []

    fn = _SERIES_REGISTRY.get(indicator)
    if fn is None:
        # No native series impl — fall back to prefix recompute. Same total
        # cost as today's per-bar calls; cleaner caller API.
        return [compute_indicator(indicator, candles[: i + 1], params) for i in range(n)]

    df = pd.DataFrame(candles).sort_values("timestamp").reset_index(drop=True)
    try:
        return fn(df, params)
    except Exception:
        # Match compute_indicator's swallow-and-None contract — never let an
        # indicator failure crash a backtest. Return Nones; the run will
        # behave as if the indicator was never ready.
        return [None] * n


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────


def _series_from(values: pd.Series, n: int) -> list[float | None]:
    """Convert a pandas series to a list[float | None] of length n with NaN→None."""
    out: list[float | None] = []
    for v in values.tolist():
        if v is None or (isinstance(v, float) and np.isnan(v)):
            out.append(None)
        else:
            out.append(float(v))
    # pad/truncate to n in case caller passed a shorter df (shouldn't happen)
    if len(out) < n:
        out += [None] * (n - len(out))
    return out[:n]


def _mask_warmup(out: list[float | None], warmup: int) -> list[float | None]:
    """Set the first ``warmup`` elements of ``out`` to None.

    ``warmup`` here is the minimum prefix LENGTH at which compute_indicator
    starts returning a value — i.e. compute_indicator(candles[:k]) returns
    None for k < warmup, returns a value for k >= warmup. Translated to
    series indices: indices 0..warmup-2 → None, index warmup-1 onwards →
    real value.
    """
    n = len(out)
    last_masked = min(warmup - 1, n)
    for i in range(last_masked):
        out[i] = None
    return out


# ──────────────────────────────────────────────────────────────────────
# Native series implementations
#
# Each function takes the sorted-by-timestamp dataframe and the params
# dict, and returns a list aligned with the dataframe rows. Bars where
# the indicator can't be computed yet are ``None``.
#
# The math here mirrors compute_indicator exactly — verified by the
# parity test. When you change one, change the other.
# ──────────────────────────────────────────────────────────────────────


def _series_rsi(df: pd.DataFrame, params: dict) -> list[float | None]:
    n = len(df)
    if n < 3:
        return [None] * n
    period = int(params.get("period", 14))
    output = params.get("output", "value")
    if n < period + 1:
        return [None] * n
    rsi = ta.momentum.RSIIndicator(df["close"], window=period).rsi()
    if output == "centered":
        rsi = rsi - 50.0
    out = _series_from(rsi, n)
    # Warmup gate mirrors compute_indicator's `n < period + 1` early-return.
    return _mask_warmup(out, period + 1)


def _series_macd(df: pd.DataFrame, params: dict) -> list[float | None]:
    n = len(df)
    if n < 3:
        return [None] * n
    if n < 26:
        return [None] * n
    macd = ta.trend.MACD(df["close"])
    diff = macd.macd_diff()
    line = macd.macd()
    # compute_indicator falls back to MACD line when diff is NaN. Mirror
    # that bar-by-bar.
    out: list[float | None] = []
    diff_list = diff.tolist()
    line_list = line.tolist()
    for d, l in zip(diff_list, line_list):
        v: float | None
        if d is None or (isinstance(d, float) and np.isnan(d)):
            if l is None or (isinstance(l, float) and np.isnan(l)):
                v = None
            else:
                v = float(l)
        else:
            v = float(d)
        out.append(v)
    return _mask_warmup(out, 26)


def _series_ema_crossover(df: pd.DataFrame, params: dict) -> list[float | None]:
    n = len(df)
    if n < 3:
        return [None] * n
    # Accept both the canonical "fast"/"slow" keys and the legacy
    # "ema_fast"/"ema_slow" spelling. Some stored scalp configs (and older
    # UI versions) wrote the latter — without this they were silently
    # ignored and the indicator ran on defaults. Defaults are 9/21 to match
    # the rest of the system (frontend PARAM_DEFAULTS, chart overlays).
    fast = int(params.get("fast", params.get("ema_fast", 9)))
    slow = int(params.get("slow", params.get("ema_slow", 21)))
    if n < slow:
        return [None] * n
    ema_fast = ta.trend.EMAIndicator(df["close"], window=fast).ema_indicator()
    ema_slow = ta.trend.EMAIndicator(df["close"], window=slow).ema_indicator()
    diff = ema_fast - ema_slow
    return _mask_warmup(_series_from(diff, n), slow)


def _series_volume_spike(df: pd.DataFrame, params: dict) -> list[float | None]:
    n = len(df)
    if n < 3:
        return [None] * n
    lookback = int(params.get("lookback", 20))
    if n < lookback:
        return [None] * n
    # compute_indicator: avg over candles[i-lookback : i] / candles[i].
    # Equivalent: rolling mean over the previous (lookback-1) bars.
    # Replicate exactly: at bar i, avg = mean(volume[i-lookback : i]).
    # That's volume[i] / volume.shift(1).rolling(lookback-1)? Easier just
    # to compute it directly as a numpy loop — bounded O(n).
    vols = df["volume"].astype(float).to_numpy()
    out: list[float | None] = [None] * n
    # compute_indicator uses df["volume"].iloc[-lookback:-1].mean() — the
    # previous (lookback-1) bars EXCLUDING the current one. Slice
    # volume[i-lookback+1 : i] is exactly that.
    for i in range(lookback - 1, n):
        window = vols[i - lookback + 1 : i]
        if len(window) == 0:
            out[i] = None
            continue
        avg = window.mean()
        if avg == 0:
            out[i] = None
        else:
            out[i] = float(vols[i] / avg)
    return _mask_warmup(out, lookback)


def _series_vwap(df: pd.DataFrame, params: dict) -> list[float | None]:
    n = len(df)
    if n < 3:
        return [None] * n
    typical = (df["high"] + df["low"] + df["close"]) / 3
    cum_tpv = (typical * df["volume"]).cumsum()
    cum_vol = df["volume"].cumsum()
    out: list[float | None] = []
    for tpv, v in zip(cum_tpv.tolist(), cum_vol.tolist()):
        if v == 0 or pd.isna(tpv) or pd.isna(v):
            out.append(None)
        else:
            out.append(float(tpv / v))
    return _mask_warmup(out, 3)


def _series_bollinger(df: pd.DataFrame, params: dict) -> list[float | None]:
    n = len(df)
    if n < 3:
        return [None] * n
    period = int(params.get("period", 20))
    std_dev = float(params.get("std_dev", 2.0))
    band = params.get("band", "pctb")
    if n < period:
        return [None] * n
    bb = ta.volatility.BollingerBands(df["close"], window=period, window_dev=std_dev)
    # compute_indicator: `n < period` returns None → series indices below
    # `period` (i.e. prefix length < period) must be None too.
    if band == "upper":
        return _mask_warmup(_series_from(bb.bollinger_hband(), n), period)
    if band == "lower":
        return _mask_warmup(_series_from(bb.bollinger_lband(), n), period)
    if band == "width":
        upper = bb.bollinger_hband()
        lower = bb.bollinger_lband()
        mid = bb.bollinger_mavg()
        out: list[float | None] = []
        for u, l, m in zip(upper.tolist(), lower.tolist(), mid.tolist()):
            if pd.isna(u) or pd.isna(l) or pd.isna(m) or m == 0:
                out.append(None)
            else:
                out.append(float((u - l) / m))
        return _mask_warmup(out, period)
    # default pctb
    return _mask_warmup(_series_from(bb.bollinger_pband(), n), period)


def _series_supertrend(df: pd.DataFrame, params: dict) -> list[float | None]:
    n = len(df)
    if n < 3:
        return [None] * n
    period = int(params.get("period", 10))
    multiplier = float(params.get("multiplier", 3.0))
    if n < period + 1:
        return [None] * n
    high = df["high"].reset_index(drop=True)
    low = df["low"].reset_index(drop=True)
    close = df["close"].reset_index(drop=True)
    tr = pd.concat(
        [high - low, (high - close.shift(1)).abs(), (low - close.shift(1)).abs()],
        axis=1,
    ).max(axis=1)
    atr = tr.rolling(window=period).mean()
    hl2 = (high + low) / 2
    basic_upper = hl2 + multiplier * atr
    basic_lower = hl2 - multiplier * atr
    final_upper = basic_upper.copy()
    final_lower = basic_lower.copy()
    supertrend = pd.Series(0.0, index=df.index)
    for i in range(period, n):
        if basic_upper.iloc[i] < final_upper.iloc[i - 1] or close.iloc[i - 1] > final_upper.iloc[i - 1]:
            final_upper.iloc[i] = basic_upper.iloc[i]
        else:
            final_upper.iloc[i] = final_upper.iloc[i - 1]
        if basic_lower.iloc[i] > final_lower.iloc[i - 1] or close.iloc[i - 1] < final_lower.iloc[i - 1]:
            final_lower.iloc[i] = basic_lower.iloc[i]
        else:
            final_lower.iloc[i] = final_lower.iloc[i - 1]
        if i == period:
            supertrend.iloc[i] = 1.0 if close.iloc[i] > final_upper.iloc[i] else -1.0
        else:
            prev = supertrend.iloc[i - 1]
            if prev == 1.0 and close.iloc[i] < final_lower.iloc[i]:
                supertrend.iloc[i] = -1.0
            elif prev == -1.0 and close.iloc[i] > final_upper.iloc[i]:
                supertrend.iloc[i] = 1.0
            else:
                supertrend.iloc[i] = prev
    out: list[float | None] = []
    for v in supertrend.tolist():
        if pd.isna(v) or v == 0.0:
            out.append(None)
        else:
            out.append(float(v))
    return _mask_warmup(out, period + 1)


def _series_utbot(df: pd.DataFrame, params: dict) -> list[float | None]:
    """Compute the full UT Bot series. Mirrors compute_indicator exactly,
    including the cold-start seed (line 179 of indicator_engine.py)."""
    n = len(df)
    if n < 3:
        return [None] * n
    period = int(params.get("period", 10))
    sensitivity = float(params.get("sensitivity", 1.0))
    output = params.get("output", "trend")
    if n < period + 2:
        return [None] * n

    atr_series = ta.volatility.AverageTrueRange(
        df["high"], df["low"], df["close"], window=period
    ).average_true_range()
    n_loss = sensitivity * atr_series
    src = df["close"].astype(float).reset_index(drop=True)
    stop = pd.Series(0.0, index=df.index)
    pos = pd.Series(0.0, index=df.index)
    for i in range(n):
        if pd.isna(n_loss.iloc[i]) or n_loss.iloc[i] == 0.0:
            if i > 0:
                stop.iloc[i] = stop.iloc[i - 1]
                pos.iloc[i] = pos.iloc[i - 1]
            continue
        prev_stop = stop.iloc[i - 1] if i > 0 else 0.0
        prev_src = src.iloc[i - 1] if i > 0 else src.iloc[i]
        cur = src.iloc[i]
        nl = n_loss.iloc[i]
        if cur > prev_stop and prev_src > prev_stop:
            stop.iloc[i] = max(prev_stop, cur - nl)
        elif cur < prev_stop and prev_src < prev_stop:
            stop.iloc[i] = min(prev_stop, cur + nl)
        elif cur > prev_stop:
            stop.iloc[i] = cur - nl
        else:
            stop.iloc[i] = cur + nl
        prev_pos = pos.iloc[i - 1] if i > 0 else 0.0
        if i > 0 and prev_src < prev_stop and cur > prev_stop:
            pos.iloc[i] = 1.0
        elif i > 0 and prev_src > prev_stop and cur < prev_stop:
            pos.iloc[i] = -1.0
        else:
            pos.iloc[i] = prev_pos
        if pos.iloc[i] == 0.0:
            pos.iloc[i] = 1.0 if cur > stop.iloc[i] else -1.0

    if output == "stop":
        return _mask_warmup(_series_from(stop, n), period + 2)
    if output == "signal":
        # +1 on fresh long flip, -1 on fresh short flip, 0 otherwise.
        # Note: compute_indicator's "signal" output returns the value at
        # the LATEST bar. For series, we mirror that bar-by-bar.
        out_sig: list[float | None] = []
        for i in range(n):
            cur_pos = pos.iloc[i]
            prev_pos = pos.iloc[i - 1] if i > 0 else 0.0
            if cur_pos == 1.0 and prev_pos != 1.0:
                out_sig.append(1.0)
            elif cur_pos == -1.0 and prev_pos != -1.0:
                out_sig.append(-1.0)
            else:
                out_sig.append(0.0)
        return _mask_warmup(out_sig, period + 2)
    # default trend: ±1, None when uninitialized
    out_trend: list[float | None] = []
    for v in pos.tolist():
        if pd.isna(v) or v == 0.0:
            out_trend.append(None)
        else:
            out_trend.append(float(v))
    return _mask_warmup(out_trend, period + 2)


def _series_halftrend(df: pd.DataFrame, params: dict) -> list[float | None]:
    n = len(df)
    if n < 3:
        return [None] * n
    amplitude = int(params.get("amplitude", 2))
    atr_period = int(params.get("atr_period", 100))
    if n < max(amplitude + 2, atr_period):
        return [None] * n
    high = df["high"].astype(float).reset_index(drop=True)
    low = df["low"].astype(float).reset_index(drop=True)
    close = df["close"].astype(float).reset_index(drop=True)
    high_ma = high.rolling(amplitude).mean()
    low_ma = low.rolling(amplitude).mean()
    high_price = high.rolling(amplitude).max()
    low_price = low.rolling(amplitude).min()
    trend = [0] * n
    next_trend = [0] * n
    max_low_price = float(low.iloc[0])
    min_high_price = float(high.iloc[0])
    out: list[float | None] = [None] * n
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
    # compute_indicator returns +1 for trend==0, -1 for trend==1, but only
    # when n >= max(amplitude+2, atr_period). Below the warmup, return None.
    warmup = max(amplitude + 2, atr_period)
    for i in range(n):
        if i < warmup - 1:
            out[i] = None
        else:
            out[i] = 1.0 if trend[i] == 0 else -1.0
    return out


def _series_qqe_mod(df: pd.DataFrame, params: dict) -> list[float | None]:
    n = len(df)
    if n < 3:
        return [None] * n
    rsi_period = int(params.get("rsi_period", 6))
    smoothing = int(params.get("smoothing", 5))
    needed = rsi_period + smoothing + 2
    if n < needed:
        return [None] * n
    rsi = ta.momentum.RSIIndicator(df["close"], window=rsi_period).rsi()
    rsi_ma = ta.trend.EMAIndicator(rsi, window=smoothing).ema_indicator()
    out = (rsi_ma - 50.0)
    return _mask_warmup(_series_from(out, n), needed)


def _series_hilega_milega(df: pd.DataFrame, params: dict) -> list[float | None]:
    n = len(df)
    if n < 3:
        return [None] * n
    rsi_period = int(params.get("rsi_period", 9))
    wma_period = int(params.get("wma_period", 21))
    ema_period = int(params.get("ema_period", 3))
    buy_threshold = float(params.get("buy_threshold", 51.0))
    sell_threshold = float(params.get("sell_threshold", 49.0))
    output = params.get("output", "signal")
    needed = rsi_period + max(wma_period, ema_period) + 2
    if n < needed:
        return [None] * n
    rsi_series = ta.momentum.RSIIndicator(df["close"], window=rsi_period).rsi()
    rsi_wma = ta.trend.WMAIndicator(rsi_series, window=wma_period).wma()
    rsi_ema = ta.trend.EMAIndicator(rsi_series, window=ema_period).ema_indicator()
    if output == "rsi":
        return _mask_warmup(_series_from(rsi_series, n), needed)
    if output == "ema":
        return _mask_warmup(_series_from(rsi_ema, n), needed)
    if output == "wma":
        return _mask_warmup(_series_from(rsi_wma, n), needed)
    if output == "raw":
        return _mask_warmup(_series_from(rsi_ema - rsi_wma, n), needed)
    # default gated signal
    out: list[float | None] = []
    rsi_list = rsi_series.tolist()
    wma_list = rsi_wma.tolist()
    ema_list = rsi_ema.tolist()
    for r, w, e in zip(rsi_list, wma_list, ema_list):
        if pd.isna(r) or pd.isna(w) or pd.isna(e):
            out.append(None)
            continue
        if e > w and r >= buy_threshold:
            out.append(1.0)
        elif e < w and r <= sell_threshold:
            out.append(-1.0)
        else:
            out.append(0.0)
    return _mask_warmup(out, needed)


def _series_ssl_hybrid(df: pd.DataFrame, params: dict) -> list[float | None]:
    n = len(df)
    if n < 3:
        return [None] * n
    period = int(params.get("period", 10))
    baseline_period = params.get("baseline_period")
    if n < period + 1:
        return [None] * n
    high = df["high"].astype(float).reset_index(drop=True)
    low = df["low"].astype(float).reset_index(drop=True)
    close = df["close"].astype(float).reset_index(drop=True)
    ssl_up = high.rolling(period).mean()
    ssl_down = low.rolling(period).mean()
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

    # Optional baseline gate
    baseline = None
    if baseline_period:
        bp = int(baseline_period)
        baseline = ta.trend.EMAIndicator(close, window=bp).ema_indicator()

    out: list[float | None] = [None] * n
    for i in range(n):
        t = trend[i]
        if t == 0:
            out[i] = None
            continue
        if baseline is not None:
            bp = int(baseline_period)
            if i < bp - 1 or pd.isna(baseline.iloc[i]):
                out[i] = None
                continue
            if t == 1 and close.iloc[i] < baseline.iloc[i]:
                out[i] = None
                continue
            if t == -1 and close.iloc[i] > baseline.iloc[i]:
                out[i] = None
                continue
        out[i] = float(t)
    return _mask_warmup(out, period + 1)


# ──────────────────────────────────────────────────────────────────────
# Registry
# ──────────────────────────────────────────────────────────────────────

_SERIES_REGISTRY: dict[str, _SeriesFn] = {
    "rsi": _series_rsi,
    "macd": _series_macd,
    "ema_crossover": _series_ema_crossover,
    "volume_spike": _series_volume_spike,
    "vwap": _series_vwap,
    "bollinger": _series_bollinger,
    "supertrend": _series_supertrend,
    "utbot": _series_utbot,
    "halftrend": _series_halftrend,
    "qqe_mod": _series_qqe_mod,
    "hilega_milega": _series_hilega_milega,
    "ssl_hybrid": _series_ssl_hybrid,
    # linear_regression and renko fall back to prefix recompute (rolling-fit
    # and stateful base-price respectively — no clean single-pass impl).
}


def has_native_series(indicator: str) -> bool:
    """Whether this indicator has a native O(n) series impl. Backtest UI
    can use this to flag indicators that will be slow on long ranges."""
    return indicator in _SERIES_REGISTRY
