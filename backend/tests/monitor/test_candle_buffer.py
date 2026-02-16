"""Tests for tick-to-candle aggregation."""
from datetime import datetime


class TestCandleBuffer:
    def test_first_tick_creates_candle(self):
        from monitor.candle_buffer import CandleBuffer
        buf = CandleBuffer(timeframe_minutes=5)
        buf.add_tick(100.0, volume=1000, timestamp=datetime(2026, 2, 16, 10, 1, 0))
        candles = buf.get_candles()
        assert len(candles) == 1
        assert candles[0]["open"] == 100.0
        assert candles[0]["high"] == 100.0
        assert candles[0]["low"] == 100.0
        assert candles[0]["close"] == 100.0

    def test_ticks_in_same_window_update_candle(self):
        from monitor.candle_buffer import CandleBuffer
        buf = CandleBuffer(timeframe_minutes=5)
        buf.add_tick(100.0, volume=1000, timestamp=datetime(2026, 2, 16, 10, 1, 0))
        buf.add_tick(105.0, volume=500, timestamp=datetime(2026, 2, 16, 10, 2, 0))
        buf.add_tick(98.0, volume=800, timestamp=datetime(2026, 2, 16, 10, 3, 0))
        candles = buf.get_candles()
        assert len(candles) == 1
        assert candles[0]["open"] == 100.0
        assert candles[0]["high"] == 105.0
        assert candles[0]["low"] == 98.0
        assert candles[0]["close"] == 98.0
        assert candles[0]["volume"] == 2300

    def test_new_window_creates_new_candle(self):
        from monitor.candle_buffer import CandleBuffer
        buf = CandleBuffer(timeframe_minutes=5)
        buf.add_tick(100.0, volume=1000, timestamp=datetime(2026, 2, 16, 10, 1, 0))
        buf.add_tick(110.0, volume=500, timestamp=datetime(2026, 2, 16, 10, 6, 0))
        candles = buf.get_candles()
        assert len(candles) == 2

    def test_completed_candles(self):
        from monitor.candle_buffer import CandleBuffer
        buf = CandleBuffer(timeframe_minutes=5)
        buf.add_tick(100.0, volume=1000, timestamp=datetime(2026, 2, 16, 10, 1, 0))
        buf.add_tick(110.0, volume=500, timestamp=datetime(2026, 2, 16, 10, 6, 0))
        completed = buf.get_completed_candles()
        assert len(completed) == 1
        assert completed[0]["close"] == 100.0

    def test_seed_with_historical(self):
        from monitor.candle_buffer import CandleBuffer
        buf = CandleBuffer(timeframe_minutes=5)
        historical = [
            {"open": 95, "high": 100, "low": 94, "close": 98, "volume": 5000,
             "timestamp": datetime(2026, 2, 16, 9, 15, 0)},
            {"open": 98, "high": 102, "low": 97, "close": 101, "volume": 3000,
             "timestamp": datetime(2026, 2, 16, 9, 20, 0)},
        ]
        buf.seed(historical)
        assert len(buf.get_candles()) == 2

    def test_max_candles_limit(self):
        from monitor.candle_buffer import CandleBuffer
        buf = CandleBuffer(timeframe_minutes=1, max_candles=3)
        for i in range(5):
            buf.add_tick(100.0 + i, volume=100, timestamp=datetime(2026, 2, 16, 10, i, 0))
        assert len(buf.get_candles()) <= 4  # 3 completed + 1 in-progress max
