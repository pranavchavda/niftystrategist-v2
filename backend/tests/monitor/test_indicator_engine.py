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


# ── HalfTrend ────────────────────────────────────────────────────────


class TestHalfTrend:
    def test_halftrend_bullish_on_strong_uptrend(self):
        """HalfTrend bullish confirm requires close > prev_high. _make_candles
        uses ±2 H/L offset so trend step must exceed that."""
        from monitor.indicator_engine import compute_indicator
        prices = [100.0 + i * 3.0 for i in range(150)]
        candles = _make_candles(prices)
        val = compute_indicator("halftrend", candles, {"atr_period": 20})
        assert val == 1.0

    def test_halftrend_bearish_after_flip(self):
        """HalfTrend needs a bullish confirm first before it can flip bearish
        (cold-start bias). Strong up → strong down should land on -1."""
        from monitor.indicator_engine import compute_indicator
        up = [100.0 + i * 3.0 for i in range(80)]
        down = [up[-1] - i * 3.0 for i in range(1, 80)]
        candles = _make_candles(up + down)
        val = compute_indicator("halftrend", candles, {"atr_period": 20})
        assert val == -1.0

    def test_halftrend_insufficient_data(self):
        from monitor.indicator_engine import compute_indicator
        candles = _make_candles([100.0, 101.0, 102.0])
        val = compute_indicator("halftrend", candles, {"atr_period": 100})
        assert val is None


# ── QQE MOD ──────────────────────────────────────────────────────────


class TestQQEMod:
    def test_qqe_positive_on_uptrend(self):
        from monitor.indicator_engine import compute_indicator
        prices = [100.0 + i * 0.5 for i in range(40)]
        candles = _make_candles(prices)
        val = compute_indicator("qqe_mod", candles, {"rsi_period": 6, "smoothing": 5})
        assert val is not None
        assert val > 0  # smoothed RSI well above 50 in a steady uptrend

    def test_qqe_negative_on_downtrend(self):
        from monitor.indicator_engine import compute_indicator
        prices = [200.0 - i * 0.5 for i in range(40)]
        candles = _make_candles(prices)
        val = compute_indicator("qqe_mod", candles, {"rsi_period": 6, "smoothing": 5})
        assert val is not None
        assert val < 0

    def test_qqe_insufficient_data(self):
        from monitor.indicator_engine import compute_indicator
        candles = _make_candles([100.0, 101.0, 102.0])
        val = compute_indicator("qqe_mod", candles, {"rsi_period": 6, "smoothing": 5})
        assert val is None


# ── SSL Hybrid ───────────────────────────────────────────────────────


class TestSSLHybrid:
    def test_ssl_bullish_breakout(self):
        from monitor.indicator_engine import compute_indicator
        # 20 bars of steady uptrend then a clear breakout — should read +1.
        prices = [100.0 + i * 0.5 for i in range(30)]
        candles = _make_candles(prices)
        val = compute_indicator("ssl_hybrid", candles, {"period": 10})
        assert val == 1.0

    def test_ssl_bearish_breakdown(self):
        from monitor.indicator_engine import compute_indicator
        prices = [200.0 - i * 0.5 for i in range(30)]
        candles = _make_candles(prices)
        val = compute_indicator("ssl_hybrid", candles, {"period": 10})
        assert val == -1.0

    def test_ssl_baseline_gate_passes_when_aligned(self):
        """Baseline gate passes when trend direction agrees with close vs EMA."""
        from monitor.indicator_engine import compute_indicator
        prices = [100.0 + i * 0.5 for i in range(30)]
        candles = _make_candles(prices)
        val = compute_indicator(
            "ssl_hybrid",
            candles,
            {"period": 10, "baseline_period": 20},
        )
        # Bullish breakout AND close above baseline → gate allows +1.
        assert val == 1.0


# ── Renko (candle-based) ─────────────────────────────────────────────


class TestRenko:
    def test_renko_bullish_on_clear_uptrend(self):
        from monitor.indicator_engine import compute_indicator
        prices = [100.0 + i * 2.0 for i in range(20)]
        candles = _make_candles(prices)
        val = compute_indicator("renko", candles, {"brick_size": 5.0})
        assert val == 1.0

    def test_renko_bearish_on_clear_downtrend(self):
        from monitor.indicator_engine import compute_indicator
        prices = [200.0 - i * 2.0 for i in range(20)]
        candles = _make_candles(prices)
        val = compute_indicator("renko", candles, {"brick_size": 5.0})
        assert val == -1.0

    def test_renko_none_when_no_brick_formed(self):
        from monitor.indicator_engine import compute_indicator
        # Tiny wiggle under brick_size threshold — no brick ever forms.
        prices = [100.0 + (i % 2) * 0.1 for i in range(20)]
        candles = _make_candles(prices)
        val = compute_indicator("renko", candles, {"brick_size": 10.0})
        assert val is None

    def test_renko_atr_sized(self):
        from monitor.indicator_engine import compute_indicator
        prices = [100.0 + i * 1.0 for i in range(30)]
        candles = _make_candles(prices)
        val = compute_indicator("renko", candles, {"atr_period": 14})
        # ATR-sized bricks on a steady uptrend should still be bullish.
        assert val == 1.0
