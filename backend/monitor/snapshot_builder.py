"""Build a JSON-safe decision snapshot from a candle list + session config.

Pure function — no daemon state, no I/O — so it can be called both from the
live ScalpSessionManager (using its in-memory CandleBuffer) and from the
backfill script (using historical candles fetched from Upstox).
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from monitor.indicator_engine import compute_indicator

logger = logging.getLogger(__name__)


def _ts(t: Any) -> str:
    if isinstance(t, datetime):
        return t.isoformat()
    return str(t)


def build_decision_snapshot(
    candles: list[dict],
    *,
    primary_indicator: str,
    primary_params: dict | None,
    confirm_indicator: str | None,
    confirm_params: dict | None,
    timeframe: str,
    decision_price: float | None,
    window: int = 30,
) -> dict | None:
    """Slice the last ``window`` candles, recompute primary + confirm
    indicator series on growing prefixes, return a JSON-safe snapshot dict
    matching the format the frontend's SnapshotChart expects.

    Returns None when there are no candles. Indicator computation errors
    fall back to None per-bar so a single bad bar doesn't kill the snapshot.
    """
    if not candles:
        return None
    sliced = candles[-window:]
    offset = len(candles) - len(sliced)

    primary_series: list[float | None] = []
    confirm_series: list[float | None] = []
    for i in range(len(sliced)):
        sub = candles[: offset + i + 1]
        try:
            pv = compute_indicator(primary_indicator, sub, primary_params or {})
        except Exception:
            pv = None
        primary_series.append(None if pv is None else float(pv))
        if confirm_indicator:
            try:
                cv = compute_indicator(confirm_indicator, sub, confirm_params or {})
            except Exception:
                cv = None
            confirm_series.append(None if cv is None else float(cv))

    return {
        "v": 1,
        "timeframe": timeframe,
        "primary_indicator": primary_indicator,
        "primary_series": primary_series,
        "confirm_indicator": confirm_indicator,
        "confirm_series": confirm_series if confirm_indicator else None,
        "decision_price": decision_price,
        "candles": [
            {
                "t": _ts(c["timestamp"]),
                "o": float(c["open"]), "h": float(c["high"]),
                "l": float(c["low"]), "c": float(c["close"]),
                "v": int(c.get("volume") or 0),
            }
            for c in sliced
        ],
    }
