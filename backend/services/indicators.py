"""Shared indicator helpers used across CLI tools, services, and the API.

Consolidates implementations that were previously copy-pasted (session VWAP
lived in both nf-morning-scan and technical_analysis). Keep this dependency-light
(pandas only) so any layer can import it.

NOTE: the monitor's `compute_indicator("vwap")` (monitor/indicator_engine.py)
is intentionally NOT routed through here yet — it is fed varying candle windows
by live rules, and changing its anchoring semantics needs separate validation.
The rolling-window VWAP in chart_overlays / api/charts (`vwap_14`) is a different
indicator and stays separate.
"""
from __future__ import annotations

import pandas as pd


def session_vwap(
    df: pd.DataFrame,
    anchor_latest_session: bool = True,
    min_rows: int = 1,
) -> float | None:
    """Session-anchored VWAP: cumulative Σ(typical_price × volume) / Σ(volume).

    Args:
        df: OHLCV frame with columns high/low/close/volume (and timestamp if
            anchor_latest_session is True). Need not be pre-sorted.
        anchor_latest_session: slice to the candles whose calendar date matches
            the last candle's date before accumulating — i.e. anchor at the most
            recent session open. Requires a timestamp column. Pass False to
            accumulate over every row given (e.g. when the frame is already a
            single session).
        min_rows: return None unless the (anchored) frame has at least this many
            rows. Use 2 to suppress meaningless single-bar "session VWAP" on
            daily-interval data.

    Returns:
        VWAP as a float, or None if there is no volume or too few rows.
    """
    if df is None or len(df) == 0 or "volume" not in df or df["volume"].sum() <= 0:
        return None

    work = df
    if anchor_latest_session and "timestamp" in df:
        ts = pd.to_datetime(df["timestamp"])
        work = df[ts.dt.date == ts.iloc[-1].date()]

    if len(work) < min_rows or work["volume"].sum() <= 0:
        return None

    typical_price = (work["high"] + work["low"] + work["close"]) / 3
    cum_tp_vol = (typical_price * work["volume"]).cumsum().iloc[-1]
    cum_vol = work["volume"].cumsum().iloc[-1]
    if cum_vol <= 0:
        return None
    return float(cum_tp_vol / cum_vol)
