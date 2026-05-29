"""Aggregates price ticks into OHLCV candles of configurable timeframes."""
from __future__ import annotations
from datetime import datetime
from collections import deque


# NSE/BSE session open expressed in naive UTC (09:15 IST − 5:30 = 03:45 UTC).
# Every add_tick caller and the seeder operate in naive UTC, so bars are
# anchored to this open — making live candles line up with Upstox's official
# candles (which the backtester and the /charts page use) instead of midnight.
# Midnight-anchoring put 30m bars at :00/:30 while Upstox uses :15/:45 (a 15-min
# phase shift that made live 30m signals diverge from charts/backtests). The
# phase is timezone-invariant for the supported timeframes (1/5/15/30): the
# 330-min IST↔UTC offset divides each, so 1m/5m/15m are unchanged and only
# 30m (and 10m) shift onto the open-anchored grid.
_MARKET_OPEN_MIN_UTC = 3 * 60 + 45  # 03:45 UTC = 09:15 IST


class CandleBuffer:
    def __init__(self, timeframe_minutes: int = 5, max_candles: int = 200):
        self.tf_minutes = timeframe_minutes
        self.max_candles = max_candles
        self._candles: deque[dict] = deque(maxlen=max_candles + 1)
        self._current_window: datetime | None = None

    def _window_start(self, ts: datetime) -> datetime:
        total = ts.hour * 60 + ts.minute
        # Floor to the timeframe grid anchored at the session open, not midnight.
        offset = (total - _MARKET_OPEN_MIN_UTC) % self.tf_minutes
        binned = max(total - offset, 0)
        return ts.replace(hour=binned // 60, minute=binned % 60, second=0, microsecond=0)

    def add_tick(self, price: float, volume: int = 0, timestamp: datetime | None = None) -> bool:
        """Append a tick. Returns True iff this tick opened a NEW candle
        (i.e. the previous window's candle is now complete).

        Callers should use the return value to detect candle close instead
        of comparing len() before/after — a saturated deque (seeded buffer
        after the first live tick) keeps len() constant and hides new-candle
        transitions.
        """
        ts = timestamp or datetime.utcnow()
        window = self._window_start(ts)
        new_candle = self._current_window != window
        if new_candle:
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
        return new_candle

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
