"""Compute technical indicators from candle data for the monitor."""
from __future__ import annotations
from typing import Any
import numpy as np
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
        elif indicator == "linear_regression":
            # Linear Regression Channel. Fits a least-squares line through
            # the last `period` closes and exposes several outputs:
            #
            #   output="line"  → endpoint of fitted line (acts like a low-lag MA)
            #   output="slope" → price/bar slope (positive=up, negative=down)
            #   output="upper" → line endpoint + stdev*k
            #   output="lower" → line endpoint − stdev*k
            #   output="pctb"  → (close − lower) / (upper − lower)
            #                    0 = at lower band, 1 = at upper band,
            #                    >1 above upper, <0 below lower.
            #                    Use this with condition gte 1.0 for "touched upper"
            #                    or lte 0.0 for "touched lower" — ideal for exits.
            #   output="r2"    → fit quality 0..1 (trend strength filter)
            #
            # stdev is computed as the population standard deviation of
            # residuals (close − fitted value) over the fit window.
            period = int(params.get("period", 20))
            stdev_k = float(params.get("stdev", 2.0))
            output = params.get("output", "pctb")
            if len(df) < period:
                return None
            closes = df["close"].astype(float).iloc[-period:].to_numpy()
            x = np.arange(period, dtype=float)
            # numpy.polyfit(deg=1) → [slope, intercept]
            slope, intercept = np.polyfit(x, closes, 1)
            fitted = slope * x + intercept
            residuals = closes - fitted
            # population stdev of residuals (matches most trading platforms)
            resid_std = float(np.sqrt(np.mean(residuals ** 2)))
            endpoint = float(fitted[-1])
            upper = endpoint + stdev_k * resid_std
            lower = endpoint - stdev_k * resid_std
            last_close = float(closes[-1])

            if output == "line":
                return endpoint
            if output == "slope":
                return float(slope)
            if output == "upper":
                return upper
            if output == "lower":
                return lower
            if output == "r2":
                ss_res = float(np.sum(residuals ** 2))
                mean_y = float(np.mean(closes))
                ss_tot = float(np.sum((closes - mean_y) ** 2))
                if ss_tot == 0:
                    return 1.0  # perfectly flat → perfect fit by convention
                return 1.0 - (ss_res / ss_tot)
            # default: pctb
            band_width = upper - lower
            # Treat vanishingly small band widths as degenerate — happens
            # when the fit is effectively perfect (flat or pure-linear data).
            # Float noise otherwise produces nonzero bands that sit at the
            # sub-paisa level but still yield a wrong pctb. Return 0.5
            # (midline) so threshold triggers don't spuriously fire.
            epsilon = 1e-9 * max(abs(last_close), 1.0)
            if band_width < epsilon:
                return 0.5
            return (last_close - lower) / band_width
        elif indicator == "halftrend":
            # HalfTrend: ATR channel + pivot hybrid. Returns ±1.0 representing
            # the current trend state (bullish / bearish). Params:
            #   amplitude    (default 2)    — lookback for high/low SMA & extremes
            #   channel_dev  (default 2.0)  — ATR multiplier for channel width
            #   atr_period   (default 100)  — ATR window; halved before use
            amplitude = int(params.get("amplitude", 2))
            atr_period = int(params.get("atr_period", 100))
            if len(df) < max(amplitude + 2, atr_period):
                return None
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
            last = trend[-1]
            # +1 = bullish (trend==0), -1 = bearish (trend==1)
            return 1.0 if last == 0 else -1.0
        elif indicator == "qqe_mod":
            # QQE MOD — smoothed RSI momentum. Returns (smoothed_rsi - 50) so
            # >0 = bullish momentum, <0 = bearish. Intended primarily as a
            # confirm filter on top of a trend indicator like UT Bot or HalfTrend.
            # Params:
            #   rsi_period  (default 6)  — RSI lookback
            #   smoothing   (default 5)  — EMA smoothing on the raw RSI
            rsi_period = int(params.get("rsi_period", 6))
            smoothing = int(params.get("smoothing", 5))
            needed = rsi_period + smoothing + 2
            if len(df) < needed:
                return None
            rsi = ta.momentum.RSIIndicator(df["close"], window=rsi_period).rsi()
            rsi_ma = ta.trend.EMAIndicator(rsi, window=smoothing).ema_indicator().iloc[-1]
            if pd.isna(rsi_ma):
                return None
            return float(rsi_ma - 50.0)
        elif indicator == "ssl_hybrid":
            # SSL Hybrid: SMA of highs / SMA of lows channel. Returns ±1.0
            # state depending on whether close broke above the high-SMA
            # (bullish) or below the low-SMA (bearish); state persists
            # through the channel. Optional EMA baseline gate filters
            # trades against the longer-term direction.
            # Params:
            #   period           (default 10)   — SSL channel lookback
            #   baseline_period  (optional)     — EMA period for gate filter
            period = int(params.get("period", 10))
            baseline_period = params.get("baseline_period")
            if len(df) < period + 1:
                return None
            high = df["high"].astype(float).reset_index(drop=True)
            low = df["low"].astype(float).reset_index(drop=True)
            close = df["close"].astype(float).reset_index(drop=True)
            ssl_up = high.rolling(period).mean()
            ssl_down = low.rolling(period).mean()
            trend = [0] * len(df)
            for i in range(period, len(df)):
                if pd.isna(ssl_up.iloc[i]) or pd.isna(ssl_down.iloc[i]):
                    trend[i] = trend[i - 1]
                    continue
                if close.iloc[i] > ssl_up.iloc[i]:
                    trend[i] = 1
                elif close.iloc[i] < ssl_down.iloc[i]:
                    trend[i] = -1
                else:
                    trend[i] = trend[i - 1]
            t = trend[-1]
            if t == 0:
                return None
            if baseline_period:
                bp = int(baseline_period)
                if len(df) < bp:
                    return None
                baseline = ta.trend.EMAIndicator(close, window=bp).ema_indicator().iloc[-1]
                if pd.isna(baseline):
                    return None
                # Gate: bullish trend blocked if close below baseline; inverse for bearish.
                if t == 1 and close.iloc[-1] < baseline:
                    return None
                if t == -1 and close.iloc[-1] > baseline:
                    return None
            return float(t)
        elif indicator == "renko":
            # Candle-based Renko trend. Builds fixed- or ATR-sized bricks
            # from closes and returns ±1.0 for the latest brick's direction.
            # Params:
            #   brick_size  (default 10.0) — absolute brick size; ignored
            #                                when atr_period is set
            #   atr_period  (optional)     — ATR window; brick_size := ATR
            atr_period = params.get("atr_period")
            if atr_period:
                ap = int(atr_period)
                if len(df) < ap + 1:
                    return None
                atr_val = ta.volatility.AverageTrueRange(
                    df["high"], df["low"], df["close"], window=ap
                ).average_true_range().iloc[-1]
                if pd.isna(atr_val) or atr_val <= 0:
                    return None
                brick_size = float(atr_val)
            else:
                brick_size = float(params.get("brick_size", 10.0))
            if brick_size <= 0:
                return None
            closes = df["close"].astype(float).tolist()
            base = closes[0]
            trend = 0
            for c in closes[1:]:
                diff = c - base
                while diff >= brick_size:
                    base += brick_size
                    trend = 1
                    diff = c - base
                while diff <= -brick_size:
                    base -= brick_size
                    trend = -1
                    diff = c - base
            if trend == 0:
                return None
            return float(trend)
    except Exception:
        return None
    return None
