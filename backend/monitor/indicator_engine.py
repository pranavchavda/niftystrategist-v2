"""Compute technical indicators from candle data for the monitor."""
from __future__ import annotations
from typing import Any
import pandas as pd
import ta


def compute_indicator(indicator: str, candles: list[dict], params: dict[str, Any]) -> float | None:
    if len(candles) < 3:
        return None
    df = pd.DataFrame(candles)
    df = df.sort_values("timestamp").reset_index(drop=True)
    try:
        if indicator == "rsi":
            period = params.get("period", 14)
            if len(df) < period + 1:
                return None
            rsi = ta.momentum.RSIIndicator(df["close"], window=period)
            val = rsi.rsi().iloc[-1]
            return None if pd.isna(val) else float(val)
        elif indicator == "macd":
            if len(df) < 26:
                return None
            macd = ta.trend.MACD(df["close"])
            val = macd.macd_diff().iloc[-1]
            if pd.isna(val):
                # Fall back to MACD line when diff (histogram) needs more data
                val = macd.macd().iloc[-1]
            return None if pd.isna(val) else float(val)
        elif indicator == "ema_crossover":
            fast = params.get("fast", 12)
            slow = params.get("slow", 26)
            if len(df) < slow:
                return None
            ema_fast = ta.trend.EMAIndicator(df["close"], window=fast).ema_indicator().iloc[-1]
            ema_slow = ta.trend.EMAIndicator(df["close"], window=slow).ema_indicator().iloc[-1]
            return float(ema_fast - ema_slow)
        elif indicator == "volume_spike":
            lookback = params.get("lookback", 20)
            if len(df) < lookback:
                return None
            avg_vol = df["volume"].iloc[-lookback:-1].mean()
            if avg_vol == 0:
                return None
            return float(df["volume"].iloc[-1] / avg_vol)
    except Exception:
        return None
    return None
