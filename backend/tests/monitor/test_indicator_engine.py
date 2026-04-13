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


class TestUTBot:
    def test_utbot_uptrend_returns_long(self):
        from monitor.indicator_engine import compute_indicator
        # Strong, sustained uptrend — should end in long (+1)
        prices = [100 + i * 1.5 for i in range(40)]
        candles = _make_candles(prices)
        result = compute_indicator("utbot", candles, {"period": 10, "sensitivity": 1.0})
        assert result == 1.0

    def test_utbot_downtrend_returns_short(self):
        from monitor.indicator_engine import compute_indicator
        # Strong, sustained downtrend — should eventually flip to short.
        # Pine UT Bot's nz(prev, 0) seed biases the first stop below price,
        # so a downtrend needs enough room for a genuine cross.
        prices = [300 - i * 3.0 for i in range(40)]
        candles = _make_candles(prices)
        result = compute_indicator("utbot", candles, {"period": 10, "sensitivity": 1.0})
        assert result == -1.0

    def test_utbot_flip_after_reversal(self):
        from monitor.indicator_engine import compute_indicator
        # Down then hard reversal up — should end in long (+1)
        down = [300 - i * 3.0 for i in range(30)]
        up = [down[-1] + i * 5 for i in range(1, 20)]
        candles = _make_candles(down + up)
        result = compute_indicator("utbot", candles, {"period": 10, "sensitivity": 1.0})
        assert result == 1.0

    def test_utbot_insufficient_data(self):
        from monitor.indicator_engine import compute_indicator
        candles = _make_candles([100, 101, 102, 103])
        result = compute_indicator("utbot", candles, {"period": 10})
        assert result is None

    def test_utbot_stop_output(self):
        from monitor.indicator_engine import compute_indicator
        prices = [100 + i * 1.5 for i in range(40)]
        candles = _make_candles(prices)
        stop = compute_indicator(
            "utbot", candles, {"period": 10, "sensitivity": 1.0, "output": "stop"}
        )
        assert stop is not None
        # Long trend → stop should be below current price
        assert stop < prices[-1]

    def test_utbot_signal_output(self):
        from monitor.indicator_engine import compute_indicator
        prices = [100 + i * 1.5 for i in range(40)]
        candles = _make_candles(prices)
        # Signal output is 0 once the trend is established (not a fresh flip)
        sig = compute_indicator(
            "utbot", candles, {"period": 10, "sensitivity": 1.0, "output": "signal"}
        )
        assert sig in (0.0, 1.0, -1.0)
