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
