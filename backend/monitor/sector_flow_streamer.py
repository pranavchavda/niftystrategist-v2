"""Intraday sector-flow streamer — computes the sensor snapshot from the LIVE
shared market feed instead of a periodic full-universe historical fetch.

Why this exists (2026-06-29 incident): the original cache writer pulled ~500
names × 15-min candles every ~5 min over Upstox's *historical REST* API. That
burst shares one rate bucket with the app's live chart/quote reads and, on
2026-06-29, saturated it (Cloudflare 1015) and hung production. The fix is to
stop pulling. This streamer subscribes the ~500 nifty500 names to the daemon's
already-running shared ``MarketStreamPool`` (ltpc mode, analytics token, ONE
connection — ZERO new connections), accumulates 15-min candles from LTP ticks
in-process, and recomputes the two-layer snapshot every few minutes from those
live buffers. No historical burst, so the incident cannot recur.

Prior-day close (for the gap calc) is read from the ltpc feed's ``cp`` field
(surfaced as ``close`` in the tick dict), so there is NO REST call anywhere in
the live path.

The snapshot is written to the same ``sector_flow_snapshots`` cache row that
``nf-sector-flow`` reads, via the same pure ``_shape_snapshot`` shaper used by
the inline/replay path — so live output matches replay output exactly.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, time as dt_time, timedelta, timezone

from monitor.candle_buffer import CandleBuffer
from services import instruments_cache as ic
from services.sector_flow_cache import _shape_snapshot, save_snapshot

logger = logging.getLogger(__name__)

_IST = timezone(timedelta(hours=5, minutes=30))
_IST_OFFSET = timedelta(hours=5, minutes=30)


def _market_open_ist(now_ist: datetime | None = None) -> bool:
    """NSE trading hours (9:15–15:30 IST, weekdays). Holiday-agnostic — on a
    holiday no ticks arrive, so the compute simply finds nothing new."""
    now_ist = now_ist or datetime.now(_IST)
    if now_ist.weekday() >= 5:
        return False
    return dt_time(9, 15) <= now_ist.time() <= dt_time(15, 30)


class SectorFlowStreamer:
    """Accumulates 15-min candles for the nifty500 off the shared feed and
    periodically computes + stores the sector-flow snapshot.

    Wiring: the daemon registers this streamer's interest under a reserved
    sentinel ``user_id`` with the ``MarketStreamPool`` and routes pool ticks
    tagged with that uid here, branching *before* the per-user rule path. The
    money path (rule evaluation / order placement) is never touched.
    """

    # Reserved pseudo-user id for the sector feed's pool interest. Negative so
    # it can never collide with a real DB user id.
    SENTINEL_UID = -7

    def __init__(
        self,
        market_pool,
        *,
        universe: str = "nifty500",
        compute_interval_s: float = 300.0,
        timeframe_min: int = 15,
        threshold: float = 0.3,
        window: int = 2,
    ):
        self._pool = market_pool
        self._universe = universe
        self._compute_interval = compute_interval_s
        self._tf = timeframe_min
        self._threshold = threshold
        self._window = window
        self._buffers: dict[str, CandleBuffer] = {}    # symbol -> buffer
        self._key_to_symbol: dict[str, str] = {}        # instrument_key -> symbol
        self._prev_close: dict[str, float] = {}         # symbol -> prior-day close (feed cp)
        self._task: asyncio.Task | None = None
        self._running = False

    # ── Lifecycle ─────────────────────────────────────────────────────

    async def start(self) -> None:
        """Resolve the universe, register interest with the shared pool, and
        launch the periodic compute loop. Adds ZERO new WS connections."""
        ic.ensure_loaded()
        symbols = sorted(ic.get_universe(self._universe))
        keys: set[str] = set()
        for sym in symbols:
            k = ic.get_instrument_key(sym)
            if not k:
                continue
            self._key_to_symbol[k] = sym
            self._buffers[sym] = CandleBuffer(timeframe_minutes=self._tf, max_candles=200)
            keys.add(k)
        if not keys:
            logger.warning(
                "[sector-flow] no instrument keys resolved for %s — not starting",
                self._universe,
            )
            return
        # Refcounted interest on the shared pool — coexists with real users'
        # rule interest on the same instruments; subscribes the union over ONE
        # connection. No new connection, no historical REST.
        await self._pool.set_interest(self.SENTINEL_UID, keys)
        self._running = True
        self._task = asyncio.create_task(self._compute_loop())
        logger.info(
            "[sector-flow] streaming %d instruments via shared pool "
            "(%dm bars, compute every %.0fs)",
            len(keys), self._tf, self._compute_interval,
        )

    async def stop(self) -> None:
        """Cancel the compute loop and drop the sentinel's pool interest."""
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        try:
            await self._pool.drop_user(self.SENTINEL_UID)
        except Exception:
            logger.exception("[sector-flow] drop_user on stop raised; ignoring")
        logger.info("[sector-flow] stopped")

    # ── Tick ingestion ────────────────────────────────────────────────

    async def on_tick(self, tick_data: dict, ts: datetime | None = None) -> None:
        """Route a pool tick (single-instrument dict) into its candle buffer.

        Deliberately cheap — this runs inside the pool's fan-out loop, so it
        does only in-memory work (no I/O, no compute). ``ts`` is injectable
        for tests; production passes none and uses naive UTC now (the grid the
        ``CandleBuffer`` anchors to)."""
        ts = ts or datetime.utcnow()
        for key, data in tick_data.items():
            sym = self._key_to_symbol.get(key)
            if sym is None:
                continue
            ltp = data.get("ltp")
            if ltp is None:
                continue
            buf = self._buffers.get(sym)
            if buf is not None:
                buf.add_tick(float(ltp), timestamp=ts)
            # Capture prior-day close from the ltpc feed (cp) once — no REST.
            if sym not in self._prev_close:
                cp = data.get("close")
                if cp:
                    self._prev_close[sym] = float(cp)

    # ── Periodic compute ──────────────────────────────────────────────

    async def _compute_loop(self) -> None:
        while self._running:
            try:
                await asyncio.sleep(self._compute_interval)
            except asyncio.CancelledError:
                break
            if not _market_open_ist():
                continue
            try:
                await self._compute_and_store()
            except Exception:
                logger.exception("[sector-flow] compute cycle failed")

    def _build_results(self) -> tuple[dict[str, list[tuple]], str | None]:
        """Build the ``{symbol: [(iso, open, close), ...]}`` shape that
        ``_shape_snapshot`` expects.

        Timestamps are rendered in IST (matching the replay/display path), and
        a synthetic prior-day row carries the feed-sourced close so the gap
        calc works. ``today`` is derived from the latest candle's IST date (not
        wall-clock) so the snapshot's session date always matches the data we
        actually hold. Returns ``(results, today_ist_date)`` (``(_, None)`` when
        there are no candles yet)."""
        per_sym: dict[str, list[dict]] = {}
        latest: str | None = None
        for sym, buf in self._buffers.items():
            candles = buf.get_candles()  # includes the in-progress bar → fresh
            if not candles:
                continue
            per_sym[sym] = candles
            d = (candles[-1]["timestamp"] + _IST_OFFSET).strftime("%Y-%m-%d")
            if latest is None or d > latest:
                latest = d
        if not per_sym:
            return {}, None
        today = latest
        prev_day = (
            datetime.strptime(today, "%Y-%m-%d") - timedelta(days=1)
        ).strftime("%Y-%m-%d")
        results: dict[str, list[tuple]] = {}
        for sym, candles in per_sym.items():
            rows: list[tuple] = []
            pc = self._prev_close.get(sym)
            if pc is not None:
                rows.append((f"{prev_day}T15:30:00", pc, pc))
            for c in candles:
                ist = c["timestamp"] + _IST_OFFSET  # naive UTC window → IST
                rows.append(
                    (ist.strftime("%Y-%m-%dT%H:%M:%S"), c["open"], c["close"])
                )
            results[sym] = rows
        return results, today

    async def _compute_and_store(self) -> None:
        results, today = self._build_results()
        if not results:
            logger.debug("[sector-flow] no buffered candles yet — skipping compute")
            return
        # Pure CPU over ~500×N bars (~tens of ms). Off-thread it so a compute
        # cycle never stalls the daemon's event loop / tick processing.
        snap = await asyncio.to_thread(
            _shape_snapshot, results, self._universe, today,
            self._threshold, self._window,
        )
        if not snap or "error" in snap:
            logger.warning(
                "[sector-flow] compute produced no snapshot: %s",
                (snap or {}).get("error"),
            )
            return
        row_id = await save_snapshot(self._universe, snap, None)
        mkt = snap["market"]
        logger.info(
            "[sector-flow] stored %s (%d sectors, market %s decis=%.3f "
            "as_of %s) row #%d",
            snap["date"], len(snap["sectors"]), mkt["direction"],
            mkt["decisiveness"], snap["as_of"], row_id,
        )
