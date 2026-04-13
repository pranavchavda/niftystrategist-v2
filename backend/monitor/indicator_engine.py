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
        elif indicator == "vwap":
            # VWAP: cumulative(typical_price * volume) / cumulative(volume)
            typical_price = (df["high"] + df["low"] + df["close"]) / 3
            cum_tp_vol = (typical_price * df["volume"]).cumsum()
            cum_vol = df["volume"].cumsum()
            if cum_vol.iloc[-1] == 0:
                return None
            val = cum_tp_vol.iloc[-1] / cum_vol.iloc[-1]
            return None if pd.isna(val) else float(val)
        elif indicator == "bollinger":
            period = params.get("period", 20)
            std_dev = params.get("std_dev", 2.0)
            band = params.get("band", "pctb")
            if len(df) < period:
                return None
            bb = ta.volatility.BollingerBands(df["close"], window=period, window_dev=std_dev)
            if band == "upper":
                val = bb.bollinger_hband().iloc[-1]
            elif band == "lower":
                val = bb.bollinger_lband().iloc[-1]
            elif band == "width":
                mid = bb.bollinger_mavg().iloc[-1]
                if pd.isna(mid) or mid == 0:
                    return None
                val = (bb.bollinger_hband().iloc[-1] - bb.bollinger_lband().iloc[-1]) / mid
            else:  # pctb
                val = bb.bollinger_pband().iloc[-1]
            return None if pd.isna(val) else float(val)
        elif indicator == "supertrend":
            period = params.get("period", 10)
            multiplier = params.get("multiplier", 3.0)
            if len(df) < period + 1:
                return None
            # Compute ATR
            high, low, close = df["high"], df["low"], df["close"]
            tr = pd.concat([
                high - low,
                (high - close.shift(1)).abs(),
                (low - close.shift(1)).abs(),
            ], axis=1).max(axis=1)
            atr = tr.rolling(window=period).mean()
            hl2 = (high + low) / 2
            # Upper and lower basic bands
            basic_upper = hl2 + multiplier * atr
            basic_lower = hl2 - multiplier * atr
            # Initialize final bands and supertrend direction
            final_upper = basic_upper.copy()
            final_lower = basic_lower.copy()
            supertrend = pd.Series(0.0, index=df.index)
            for i in range(period, len(df)):
                # Final upper band: use previous if current basic <= previous final
                if basic_upper.iloc[i] < final_upper.iloc[i - 1] or close.iloc[i - 1] > final_upper.iloc[i - 1]:
                    final_upper.iloc[i] = basic_upper.iloc[i]
                else:
                    final_upper.iloc[i] = final_upper.iloc[i - 1]
                # Final lower band: use previous if current basic >= previous final
                if basic_lower.iloc[i] > final_lower.iloc[i - 1] or close.iloc[i - 1] < final_lower.iloc[i - 1]:
                    final_lower.iloc[i] = basic_lower.iloc[i]
                else:
                    final_lower.iloc[i] = final_lower.iloc[i - 1]
                # Determine trend
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
            val = supertrend.iloc[-1]
            return None if pd.isna(val) or val == 0.0 else float(val)
        elif indicator == "utbot":
            # UT Bot: ATR-based trailing stop trend follower.
            # Params: period (ATR window, default 10), sensitivity (nLoss multiplier,
            # default 1.0), output ("trend" | "stop" | "signal", default "trend").
            # "trend" returns +1 (long) / -1 (short) — use crosses_above 0 to detect flip.
            # "stop" returns the trailing stop price level.
            # "signal" returns +1 on fresh long flip, -1 on fresh short flip, 0 otherwise.
            period = params.get("period", 10)
            sensitivity = params.get("sensitivity", 1.0)
            output = params.get("output", "trend")
            if len(df) < period + 2:
                return None
            atr_series = ta.volatility.AverageTrueRange(
                df["high"], df["low"], df["close"], window=period
            ).average_true_range()
            n_loss = sensitivity * atr_series
            src = df["close"].astype(float)
            stop = pd.Series(0.0, index=df.index)
            pos = pd.Series(0.0, index=df.index)
            for i in range(len(df)):
                # ta's ATR returns 0.0 for the first `period-1` bars (warm-up)
                # rather than NaN — treat both as "not ready".
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
                # Cold start: a steady trend never "crosses" the stop, so pos
                # would stay 0 forever. Seed it from price-vs-stop the first
                # bar ATR is available (and keep it seeded until an actual flip).
                if pos.iloc[i] == 0.0:
                    pos.iloc[i] = 1.0 if cur > stop.iloc[i] else -1.0
            if output == "stop":
                val = stop.iloc[-1]
                return None if pd.isna(val) else float(val)
            if output == "signal":
                cur_pos = pos.iloc[-1]
                prev_pos = pos.iloc[-2] if len(pos) > 1 else 0.0
                if cur_pos == 1.0 and prev_pos != 1.0:
                    return 1.0
                if cur_pos == -1.0 and prev_pos != -1.0:
                    return -1.0
                return 0.0
            # default: "trend" — +1 (long) or -1 (short)
            val = pos.iloc[-1]
            if pd.isna(val) or val == 0.0:
                return None
            return float(val)
    except Exception:
        return None
    return None
