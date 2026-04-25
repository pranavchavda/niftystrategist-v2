"""Shared market-data WebSocket for the charts product.

One process-wide WebSocket connection authorized with Pranav's Upstox
Analytics Token (read-only, 1-year validity, no daily refresh, can't place
orders). Fans live ticks out to N chart SSE clients per instrument and
builds server-side OHLC candles for intraday timeframes.

Why analytics token: tied to the app owner's account, so this single
connection serves all logged-in users without burning per-user WS quota.
The 5-conn Plus cap counts against Pranav's account; today 2 are used by
his own monitor + scalp, so charts adds 1 with headroom to spare.

Refcount semantics: an instrument stays subscribed on the upstream WS as
long as ANY consumer (tick subscriber or candle subscriber at any
timeframe) holds a queue for it. Last consumer leaving issues `unsub`.

The stream is started eagerly at FastAPI startup (lifespan) when
UPSTOX_ANALYTICS_TOKEN is set; absence falls back to REST polling in
api/charts.py.
"""
from __future__ import annotations

import asyncio
import logging
import os
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from monitor.candle_buffer import CandleBuffer
from monitor.streams.market_data import MarketDataStream

logger = logging.getLogger(__name__)


# Intraday-only — daily/weekly/monthly bars are fetched from REST and
# folded by the existing client-side LTP path. Server-side aggregation
# only makes sense for windows that actually close during a session.
TIMEFRAME_TO_MINUTES: dict[str, int] = {
    "1m": 1,
    "5m": 5,
    "15m": 15,
    "30m": 30,
}


@dataclass
class _InstrumentState:
    tick_queues: set[asyncio.Queue] = field(default_factory=set)
    # (timeframe_minutes) -> set of queues subscribed to candles at that tf
    candle_queues: dict[int, set[asyncio.Queue]] = field(default_factory=lambda: defaultdict(set))
    # (timeframe_minutes) -> CandleBuffer aggregator
    buffers: dict[int, CandleBuffer] = field(default_factory=dict)

    @property
    def total_consumers(self) -> int:
        n = len(self.tick_queues)
        for qs in self.candle_queues.values():
            n += len(qs)
        return n


class ChartMarketStream:
    """Singleton wrapper around MarketDataStream for chart fan-out."""

    def __init__(self, access_token: str, mode: str = "ltpc"):
        # ltpc is plenty for charts — depth/greeks aren't needed and would
        # bloat the per-tick payload pushed to dozens of SSE clients.
        self._access_token = access_token
        self._mode = mode
        self._stream: Optional[MarketDataStream] = None
        self._instruments: dict[str, _InstrumentState] = {}
        self._lock = asyncio.Lock()
        self._started = False

    async def start(self):
        if self._started:
            return
        self._stream = MarketDataStream(
            access_token=self._access_token,
            on_message=self._on_message,
            mode=self._mode,
            fallback_mode=None,
        )
        await self._stream.start()
        self._started = True
        logger.info("[ChartMarketStream] Started (mode=%s)", self._mode)

    async def stop(self):
        if not self._started:
            return
        try:
            if self._stream:
                await self._stream.stop()
        finally:
            self._stream = None
            self._instruments.clear()
            self._started = False
            logger.info("[ChartMarketStream] Stopped")

    @property
    def healthy(self) -> bool:
        """True iff the WS is up and ready to receive subscriptions."""
        return self._started and self._stream is not None and self._stream.connected

    @property
    def started(self) -> bool:
        return self._started

    # ------------------------------------------------------------------
    # Subscription API used by the SSE handler
    # ------------------------------------------------------------------

    async def subscribe_ticks(self, instrument_key: str) -> asyncio.Queue:
        """Register a tick consumer. Returns a queue that yields tick dicts.

        Caller MUST call unsubscribe_ticks(instrument_key, queue) on
        disconnect to release the slot and (eventually) free the upstream
        instrument subscription.
        """
        queue: asyncio.Queue = asyncio.Queue(maxsize=200)
        async with self._lock:
            state = self._instruments.setdefault(instrument_key, _InstrumentState())
            was_empty = state.total_consumers == 0
            state.tick_queues.add(queue)
            need_subscribe = was_empty
        if need_subscribe and self._stream:
            await self._stream.subscribe([instrument_key])
        return queue

    async def unsubscribe_ticks(self, instrument_key: str, queue: asyncio.Queue):
        async with self._lock:
            state = self._instruments.get(instrument_key)
            if not state:
                return
            state.tick_queues.discard(queue)
            need_unsubscribe = state.total_consumers == 0
            if need_unsubscribe:
                self._instruments.pop(instrument_key, None)
        if need_unsubscribe and self._stream:
            await self._stream.unsubscribe([instrument_key])

    async def subscribe_candles(
        self, instrument_key: str, timeframe: str
    ) -> Optional[asyncio.Queue]:
        """Register a candle consumer for an intraday timeframe.

        Returns None if the timeframe isn't intraday (caller should skip
        candle events and rely on tick folding for daily+ bars).
        """
        tf_min = TIMEFRAME_TO_MINUTES.get(timeframe)
        if tf_min is None:
            return None
        queue: asyncio.Queue = asyncio.Queue(maxsize=200)
        async with self._lock:
            state = self._instruments.setdefault(instrument_key, _InstrumentState())
            was_empty = state.total_consumers == 0
            state.candle_queues[tf_min].add(queue)
            if tf_min not in state.buffers:
                state.buffers[tf_min] = CandleBuffer(timeframe_minutes=tf_min)
            need_subscribe = was_empty
        if need_subscribe and self._stream:
            await self._stream.subscribe([instrument_key])
        return queue

    async def unsubscribe_candles(
        self, instrument_key: str, timeframe: str, queue: asyncio.Queue
    ):
        tf_min = TIMEFRAME_TO_MINUTES.get(timeframe)
        if tf_min is None:
            return
        async with self._lock:
            state = self._instruments.get(instrument_key)
            if not state:
                return
            qs = state.candle_queues.get(tf_min)
            if qs:
                qs.discard(queue)
                if not qs:
                    state.candle_queues.pop(tf_min, None)
                    state.buffers.pop(tf_min, None)
            need_unsubscribe = state.total_consumers == 0
            if need_unsubscribe:
                self._instruments.pop(instrument_key, None)
        if need_unsubscribe and self._stream:
            await self._stream.unsubscribe([instrument_key])

    # ------------------------------------------------------------------
    # Inbound tick handler
    # ------------------------------------------------------------------

    async def _on_message(self, parsed: dict):
        # parsed is {instrument_key -> tick_dict}
        for instrument_key, tick in parsed.items():
            state = self._instruments.get(instrument_key)
            if not state:
                continue

            ltp = tick.get("ltp")
            if ltp is None:
                continue
            ltt = tick.get("ltt")
            ltt_ms = int(ltt) if ltt is not None else int(datetime.utcnow().timestamp() * 1000)
            ltq = tick.get("ltq", 0) or 0

            tick_payload = {"ltp": float(ltp), "ltt": ltt_ms}
            self._fanout(state.tick_queues, tick_payload)

            if state.buffers:
                # Upstox `ltt` is epoch milliseconds.
                tick_dt = datetime.utcfromtimestamp(ltt_ms / 1000.0)
                ltp_f = float(ltp)
                for tf_min, buf in state.buffers.items():
                    closed = buf.add_tick(price=ltp_f, volume=int(ltq), timestamp=tick_dt)
                    candles = buf.get_candles()
                    if not candles:
                        continue
                    live = candles[-1]
                    candle_payload = {
                        "time": int(live["timestamp"].timestamp()),
                        "open": live["open"],
                        "high": live["high"],
                        "low": live["low"],
                        "close": live["close"],
                        "volume": live["volume"],
                        "closed": closed,
                    }
                    qs = state.candle_queues.get(tf_min)
                    if qs:
                        self._fanout(qs, candle_payload)

    @staticmethod
    def _fanout(queues: set[asyncio.Queue], payload: dict):
        """Drop oldest on full instead of blocking the WS receive loop."""
        for q in list(queues):
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                try:
                    q.put_nowait(payload)
                except asyncio.QueueFull:
                    pass


# ----------------------------------------------------------------------
# Module-level singleton accessor — set by main.py lifespan.
# ----------------------------------------------------------------------

_singleton: Optional[ChartMarketStream] = None


def get_chart_stream() -> Optional[ChartMarketStream]:
    return _singleton


def set_chart_stream(instance: Optional[ChartMarketStream]) -> None:
    global _singleton
    _singleton = instance


def analytics_token_from_env() -> Optional[str]:
    tok = os.getenv("UPSTOX_ANALYTICS_TOKEN", "").strip()
    return tok or None
