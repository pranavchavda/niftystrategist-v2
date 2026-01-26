"""Models for market analysis."""

from typing import Literal

from pydantic import BaseModel, Field


class TechnicalIndicators(BaseModel):
    """Technical indicators calculated from OHLCV data."""

    rsi_14: float = Field(description="14-period Relative Strength Index (0-100)")
    macd_value: float = Field(description="MACD line value")
    macd_signal: float = Field(description="MACD signal line value")
    macd_histogram: float = Field(description="MACD histogram (macd - signal)")
    sma_20: float = Field(description="20-period Simple Moving Average")
    sma_50: float = Field(description="50-period Simple Moving Average")
    ema_12: float = Field(description="12-period Exponential Moving Average")
    ema_26: float = Field(description="26-period Exponential Moving Average")
    atr_14: float = Field(description="14-period Average True Range (for volatility)")
    volume_avg_20: float = Field(description="20-period average volume")
    current_volume: float = Field(description="Current/latest volume")


class MarketAnalysis(BaseModel):
    """Result of technical analysis on a symbol."""

    symbol: str = Field(description="Stock symbol (e.g., RELIANCE, INFY)")
    current_price: float = Field(description="Current market price")
    indicators: TechnicalIndicators = Field(description="Calculated technical indicators")

    # Interpretations
    rsi_signal: Literal["oversold", "neutral", "overbought"] = Field(
        description="RSI interpretation: oversold (<30), overbought (>70), or neutral"
    )
    macd_trend: Literal["bullish", "bearish", "neutral"] = Field(
        description="MACD trend based on histogram and crossovers"
    )
    price_trend: Literal["uptrend", "downtrend", "sideways"] = Field(
        description="Overall price trend based on moving averages"
    )
    volume_signal: Literal["high", "normal", "low"] = Field(
        description="Volume compared to 20-day average"
    )

    # Key levels
    support_level: float | None = Field(
        default=None, description="Nearest support level"
    )
    resistance_level: float | None = Field(
        default=None, description="Nearest resistance level"
    )

    # Overall assessment
    overall_signal: Literal["strong_buy", "buy", "hold", "sell", "strong_sell"] = Field(
        description="Combined signal from all indicators"
    )
    confidence: float = Field(
        ge=0.0, le=1.0, description="Confidence in the analysis (0.0 to 1.0)"
    )
    reasoning: str = Field(
        description="Beginner-friendly explanation of the analysis"
    )


class OHLCVData(BaseModel):
    """OHLCV (Open, High, Low, Close, Volume) candlestick data."""

    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: int
