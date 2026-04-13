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
    }
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
        return {"lines": {"utbot_stop": []}, "markers": []}

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

    return {"lines": {"utbot_stop": stop_line}, "markers": markers}


OVERLAY_COMPUTERS = {
    "utbot": compute_utbot_overlay,
}


def compute_overlays(
    candles: list[dict],
    names: list[str],
    params: dict[str, dict] | None = None,
) -> dict:
    """Run the requested overlay computers and merge their output.

    params is an optional mapping from overlay name to kwargs, e.g.
    ``{"utbot": {"period": 10, "sensitivity": 2.0}}``.
    """
    params = params or {}
    lines: dict[str, list] = {}
    markers: list[dict] = []
    for name in names:
        fn = OVERLAY_COMPUTERS.get(name)
        if fn is None:
            continue
        result = fn(candles, **params.get(name, {}))
        lines.update(result.get("lines", {}))
        markers.extend(result.get("markers", []))
    return {"lines": lines, "markers": markers}
