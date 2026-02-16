"""Aggregates price ticks into OHLCV candles of configurable timeframes."""
from __future__ import annotations
from datetime import datetime
from collections import deque


class CandleBuffer:
    def __init__(self, timeframe_minutes: int = 5, max_candles: int = 200):
        self.tf_minutes = timeframe_minutes
        self.max_candles = max_candles
        self._candles: deque[dict] = deque(maxlen=max_candles + 1)
        self._current_window: datetime | None = None

    def _window_start(self, ts: datetime) -> datetime:
        minutes = (ts.hour * 60 + ts.minute) // self.tf_minutes * self.tf_minutes
        return ts.replace(hour=minutes // 60, minute=minutes % 60, second=0, microsecond=0)

    def add_tick(self, price: float, volume: int = 0, timestamp: datetime | None = None):
        ts = timestamp or datetime.utcnow()
        window = self._window_start(ts)
        if self._current_window != window:
            self._current_window = window
            self._candles.append({
                "timestamp": window, "open": price, "high": price,
                "low": price, "close": price, "volume": volume,
            })
        else:
            candle = self._candles[-1]
            candle["high"] = max(candle["high"], price)
            candle["low"] = min(candle["low"], price)
            candle["close"] = price
            candle["volume"] += volume

    def seed(self, historical: list[dict]):
        for c in historical:
            self._candles.append(c)
            self._current_window = c["timestamp"]

    def get_candles(self) -> list[dict]:
        return list(self._candles)

    def get_completed_candles(self) -> list[dict]:
        if len(self._candles) <= 1:
            return []
        return list(self._candles)[:-1]
