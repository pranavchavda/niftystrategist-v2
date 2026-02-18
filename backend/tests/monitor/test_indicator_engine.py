"""Tests for indicator computation from candle buffers."""
import pytest
from datetime import datetime, timedelta


def _make_candles(prices: list[float], start_minute: int = 0) -> list[dict]:
    base = datetime(2026, 2, 16, 10, 0, 0) + timedelta(minutes=start_minute)
    return [
        {
            "timestamp": base + timedelta(minutes=i * 5),
            "open": p - 1, "high": p + 2, "low": p - 2, "close": p, "volume": 1000,
        }
        for i, p in enumerate(prices)
    ]


class TestIndicatorEngine:
    def test_rsi_returns_value(self):
        from monitor.indicator_engine import compute_indicator
        prices = [100 + i * 0.5 for i in range(20)]
        candles = _make_candles(prices)
        result = compute_indicator("rsi", candles, {"period": 14})
        assert result is not None
        assert 0 <= result <= 100

    def test_rsi_oversold_region(self):
        from monitor.indicator_engine import compute_indicator
        prices = [200 - i * 2 for i in range(20)]
        candles = _make_candles(prices)
        result = compute_indicator("rsi", candles, {"period": 14})
        assert result is not None
        assert result < 40

    def test_macd_returns_value(self):
        from monitor.indicator_engine import compute_indicator
        prices = [100 + i * 0.3 for i in range(30)]
        candles = _make_candles(prices)
        result = compute_indicator("macd", candles, {})
        assert result is not None

    def test_insufficient_data_returns_none(self):
        from monitor.indicator_engine import compute_indicator
        candles = _make_candles([100, 101, 102])
        result = compute_indicator("rsi", candles, {"period": 14})
        assert result is None

    def test_volume_spike(self):
        from monitor.indicator_engine import compute_indicator
        candles = _make_candles([100 + i for i in range(20)])
        for c in candles[:-1]:
            c["volume"] = 1000
        candles[-1]["volume"] = 5000
        result = compute_indicator("volume_spike", candles, {"lookback": 20, "multiplier": 2.0})
        assert result is not None
        assert result > 2.0

    def test_ema_crossover_returns_value(self):
        from monitor.indicator_engine import compute_indicator
        prices = [100 + i * 0.5 for i in range(30)]
        candles = _make_candles(prices)
        result = compute_indicator("ema_crossover", candles, {"fast": 12, "slow": 26})
        assert result is not None
