"""Technical analysis service using pandas and ta library."""

from typing import Literal

import numpy as np
import pandas as pd
import ta

from models.analysis import MarketAnalysis, OHLCVData, TechnicalIndicators


class TechnicalAnalysisService:
    """Service for calculating technical indicators from OHLCV data."""

    def __init__(
        self,
        rsi_oversold: float = 30.0,
        rsi_overbought: float = 70.0,
    ):
        """Initialize the service with configurable thresholds."""
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought

    def calculate_indicators(self, ohlcv_data: list[OHLCVData]) -> TechnicalIndicators:
        """Calculate technical indicators from OHLCV data."""
        # Convert to DataFrame
        df = pd.DataFrame([d.model_dump() for d in ohlcv_data])
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.sort_values("timestamp").reset_index(drop=True)

        # Calculate indicators
        # RSI
        rsi = ta.momentum.RSIIndicator(df["close"], window=14)
        rsi_14 = rsi.rsi().iloc[-1]

        # MACD
        macd = ta.trend.MACD(df["close"])
        macd_value = macd.macd().iloc[-1]
        macd_signal = macd.macd_signal().iloc[-1]
        macd_histogram = macd.macd_diff().iloc[-1]

        # Moving Averages
        sma_20 = ta.trend.SMAIndicator(df["close"], window=20).sma_indicator().iloc[-1]
        sma_50 = ta.trend.SMAIndicator(df["close"], window=50).sma_indicator().iloc[-1]
        ema_12 = ta.trend.EMAIndicator(df["close"], window=12).ema_indicator().iloc[-1]
        ema_26 = ta.trend.EMAIndicator(df["close"], window=26).ema_indicator().iloc[-1]

        # ATR for volatility
        atr = ta.volatility.AverageTrueRange(
            df["high"], df["low"], df["close"], window=14
        )
        atr_14 = atr.average_true_range().iloc[-1]

        # Volume
        volume_avg_20 = df["volume"].rolling(window=20).mean().iloc[-1]
        current_volume = float(df["volume"].iloc[-1])

        # Validate all indicators - fail if any are NaN (indicates insufficient data)
        nan_indicators = []
        if np.isnan(rsi_14):
            nan_indicators.append("RSI")
        if np.isnan(macd_value) or np.isnan(macd_signal):
            nan_indicators.append("MACD")
        if np.isnan(sma_20):
            nan_indicators.append("SMA20")
        if np.isnan(sma_50):
            nan_indicators.append("SMA50")
        if np.isnan(atr_14):
            nan_indicators.append("ATR")

        if nan_indicators:
            raise ValueError(
                f"Insufficient data to calculate indicators: {', '.join(nan_indicators)}. "
                "Need more historical data for accurate analysis."
            )

        return TechnicalIndicators(
            rsi_14=float(rsi_14),
            macd_value=float(macd_value),
            macd_signal=float(macd_signal),
            macd_histogram=float(macd_histogram),
            sma_20=float(sma_20),
            sma_50=float(sma_50),
            ema_12=float(ema_12),
            ema_26=float(ema_26),
            atr_14=float(atr_14),
            volume_avg_20=float(volume_avg_20) if not np.isnan(volume_avg_20) else current_volume,
            current_volume=current_volume,
        )

    def interpret_rsi(self, rsi: float) -> Literal["oversold", "neutral", "overbought"]:
        """Interpret RSI value."""
        if rsi < self.rsi_oversold:
            return "oversold"
        elif rsi > self.rsi_overbought:
            return "overbought"
        return "neutral"

    def interpret_macd(
        self, macd_value: float, macd_signal: float, macd_histogram: float
    ) -> Literal["bullish", "bearish", "neutral"]:
        """Interpret MACD signals."""
        # Bullish: MACD above signal and histogram positive/increasing
        # Bearish: MACD below signal and histogram negative/decreasing
        if macd_value > macd_signal and macd_histogram > 0:
            return "bullish"
        elif macd_value < macd_signal and macd_histogram < 0:
            return "bearish"
        return "neutral"

    def interpret_trend(
        self, current_price: float, sma_20: float, sma_50: float
    ) -> Literal["uptrend", "downtrend", "sideways"]:
        """Interpret price trend from moving averages."""
        # Uptrend: Price > SMA20 > SMA50
        # Downtrend: Price < SMA20 < SMA50
        if current_price > sma_20 > sma_50:
            return "uptrend"
        elif current_price < sma_20 < sma_50:
            return "downtrend"
        return "sideways"

    def interpret_volume(
        self, current_volume: float, avg_volume: float
    ) -> Literal["high", "normal", "low"]:
        """Interpret volume relative to average."""
        ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
        if ratio > 1.5:
            return "high"
        elif ratio < 0.5:
            return "low"
        return "normal"

    def find_support_resistance(
        self, ohlcv_data: list[OHLCVData], current_price: float
    ) -> tuple[float | None, float | None]:
        """Find nearest support and resistance levels."""
        df = pd.DataFrame([d.model_dump() for d in ohlcv_data])

        # Find swing lows (support) and swing highs (resistance)
        # Using a simple approach: local minima and maxima over last 20 periods
        lows = df["low"].rolling(window=5, center=True).min()
        highs = df["high"].rolling(window=5, center=True).max()

        # Find levels below current price (support)
        support_levels = df[df["low"] == lows]["low"].unique()
        support_levels = support_levels[support_levels < current_price]
        support = float(support_levels.max()) if len(support_levels) > 0 else None

        # Find levels above current price (resistance)
        resistance_levels = df[df["high"] == highs]["high"].unique()
        resistance_levels = resistance_levels[resistance_levels > current_price]
        resistance = float(resistance_levels.min()) if len(resistance_levels) > 0 else None

        return support, resistance

    def calculate_overall_signal(
        self,
        rsi_signal: Literal["oversold", "neutral", "overbought"],
        macd_trend: Literal["bullish", "bearish", "neutral"],
        price_trend: Literal["uptrend", "downtrend", "sideways"],
    ) -> tuple[Literal["strong_buy", "buy", "hold", "sell", "strong_sell"], float]:
        """
        Calculate overall signal and confidence from individual indicators.

        Returns (signal, confidence) tuple.
        """
        # Score each indicator
        score = 0

        # RSI scoring
        if rsi_signal == "oversold":
            score += 2  # Bullish
        elif rsi_signal == "overbought":
            score -= 2  # Bearish

        # MACD scoring
        if macd_trend == "bullish":
            score += 2
        elif macd_trend == "bearish":
            score -= 2

        # Trend scoring
        if price_trend == "uptrend":
            score += 2
        elif price_trend == "downtrend":
            score -= 2

        # Convert score to signal
        # Score range: -6 to +6
        if score >= 4:
            signal = "strong_buy"
            confidence = min(0.9, 0.6 + (score - 4) * 0.1)
        elif score >= 2:
            signal = "buy"
            confidence = 0.5 + (score - 2) * 0.1
        elif score <= -4:
            signal = "strong_sell"
            confidence = min(0.9, 0.6 + (abs(score) - 4) * 0.1)
        elif score <= -2:
            signal = "sell"
            confidence = 0.5 + (abs(score) - 2) * 0.1
        else:
            signal = "hold"
            confidence = 0.3

        return signal, confidence

    def analyze(self, symbol: str, ohlcv_data: list[OHLCVData]) -> MarketAnalysis:
        """
        Perform full technical analysis on a symbol.

        Args:
            symbol: Stock symbol (e.g., "RELIANCE")
            ohlcv_data: List of OHLCV candles (at least 50 for accurate indicators)

        Returns:
            MarketAnalysis with all indicators and interpretations
        """
        if len(ohlcv_data) < 50:
            raise ValueError("Need at least 50 candles for accurate analysis")

        # Data comes from API with newest first, so index 0 is the latest candle
        current_price = ohlcv_data[0].close
        indicators = self.calculate_indicators(ohlcv_data)

        # Interpret indicators
        rsi_signal = self.interpret_rsi(indicators.rsi_14)
        macd_trend = self.interpret_macd(
            indicators.macd_value, indicators.macd_signal, indicators.macd_histogram
        )
        price_trend = self.interpret_trend(current_price, indicators.sma_20, indicators.sma_50)
        volume_signal = self.interpret_volume(indicators.current_volume, indicators.volume_avg_20)

        # Find support/resistance
        support, resistance = self.find_support_resistance(ohlcv_data, current_price)

        # Calculate overall signal
        overall_signal, confidence = self.calculate_overall_signal(
            rsi_signal, macd_trend, price_trend
        )

        # Generate reasoning
        reasoning = self._generate_reasoning(
            symbol=symbol,
            current_price=current_price,
            indicators=indicators,
            rsi_signal=rsi_signal,
            macd_trend=macd_trend,
            price_trend=price_trend,
            volume_signal=volume_signal,
            overall_signal=overall_signal,
        )

        return MarketAnalysis(
            symbol=symbol,
            current_price=current_price,
            indicators=indicators,
            rsi_signal=rsi_signal,
            macd_trend=macd_trend,
            price_trend=price_trend,
            volume_signal=volume_signal,
            support_level=support,
            resistance_level=resistance,
            overall_signal=overall_signal,
            confidence=confidence,
            reasoning=reasoning,
        )

    def _generate_reasoning(
        self,
        symbol: str,
        current_price: float,
        indicators: TechnicalIndicators,
        rsi_signal: str,
        macd_trend: str,
        price_trend: str,
        volume_signal: str,
        overall_signal: str,
    ) -> str:
        """Generate beginner-friendly reasoning text."""
        parts = [f"{symbol} is currently trading at ₹{current_price:.2f}."]

        # RSI explanation
        rsi_val = indicators.rsi_14
        if rsi_signal == "oversold":
            parts.append(
                f"The RSI (Relative Strength Index) is at {rsi_val:.1f}, which is below 30. "
                "This suggests the stock may be oversold and could be due for a bounce."
            )
        elif rsi_signal == "overbought":
            parts.append(
                f"The RSI is at {rsi_val:.1f}, which is above 70. "
                "This suggests the stock may be overbought and could see a pullback."
            )
        else:
            parts.append(f"The RSI is at {rsi_val:.1f}, in neutral territory.")

        # MACD explanation
        if macd_trend == "bullish":
            parts.append(
                "The MACD indicator shows bullish momentum, with the MACD line above the signal line."
            )
        elif macd_trend == "bearish":
            parts.append(
                "The MACD indicator shows bearish momentum, with the MACD line below the signal line."
            )

        # Trend explanation
        if price_trend == "uptrend":
            parts.append(
                f"The stock is in an uptrend, trading above both the 20-day (₹{indicators.sma_20:.2f}) "
                f"and 50-day (₹{indicators.sma_50:.2f}) moving averages."
            )
        elif price_trend == "downtrend":
            parts.append(
                f"The stock is in a downtrend, trading below both the 20-day (₹{indicators.sma_20:.2f}) "
                f"and 50-day (₹{indicators.sma_50:.2f}) moving averages."
            )
        else:
            parts.append("The stock is moving sideways without a clear trend.")

        # Volume explanation
        if volume_signal == "high":
            parts.append("Volume is higher than average, indicating strong interest.")
        elif volume_signal == "low":
            parts.append("Volume is lower than average, suggesting weak conviction.")

        # Overall signal
        signal_text = overall_signal.replace("_", " ").title()
        parts.append(f"Overall signal: {signal_text}.")

        return " ".join(parts)
