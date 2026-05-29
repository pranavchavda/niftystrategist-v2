"""Seed CandleBuffer instances from Upstox historical OHLCV.

Without seeding, every daemon restart leaves candle buffers empty, and
indicators silently return None until enough live ticks accumulate.
For an atr_period=100 halftrend on 1m candles that's >1.5 hours of
dead time per restart.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from monitor.candle_buffer import CandleBuffer

logger = logging.getLogger(__name__)

# Map buffer timeframe (minutes) → Upstox historical interval string.
# Upstox supports a fixed set; anything else we skip (seeding is best-effort).
_INTERVAL_MAP: dict[int, str] = {
    1: "1minute",
    5: "5minute",
    15: "15minute",
    30: "30minute",
}

# Seed enough history that indicators are already CONVERGED before the session
# acts on live ticks. ATR / stateful-stop indicators (UTBot, SuperTrend) need
# ~150 bars to converge their state — far more than the textbook 5×period — so
# we target a fixed BAR count, not a per-timeframe day count.
#
# The old day-based map under-seeded minute intervals: days<=1 routed to the
# *intraday* endpoint (today-only → ~75 bars for 5m, fewer if the session was
# enabled early in the day), so 5m and morning-started 1m sessions began INSIDE
# the cold-start zone and traded on wrong signals for hours. Targeting bars —
# and always using days>=2 so the multi-day historical endpoint is hit (which
# also appends today's candles) — keeps the cold zone entirely in the past,
# independent of what time of day the session was switched on.
_TARGET_SEED_BARS = 200  # > the ~150-bar convergence floor, with margin

# Approx regular-session bars per trading day (NSE 09:15–15:30 = 375 min).
_BARS_PER_DAY: dict[int, int] = {1: 375, 5: 75, 15: 25, 30: 13}


def _seed_days(tf_minutes: int) -> int:
    """Calendar days to fetch so the seed yields >= _TARGET_SEED_BARS bars."""
    bpd = _BARS_PER_DAY.get(tf_minutes) or max(1, 375 // tf_minutes)
    trading_days = -(-_TARGET_SEED_BARS // bpd)  # ceil division
    # Trading→calendar (~5/7) + holiday cushion; >=2 forces the historical
    # endpoint (days<=1 hits the intraday/today-only path).
    return max(2, round(trading_days * 7 / 5) + 3)


def _to_naive_utc(ts: Any) -> datetime | None:
    """Coerce an Upstox timestamp (str or datetime) to naive UTC datetime."""
    if isinstance(ts, datetime):
        dt = ts
    elif isinstance(ts, str):
        try:
            dt = datetime.fromisoformat(ts)
        except ValueError:
            return None
    else:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


async def seed_candle_buffer(
    buf: CandleBuffer,
    upstox_client: Any,
    instrument_token: str,
    tf_minutes: int,
    max_candles: int = 200,
) -> int:
    """Seed ``buf`` with recent historical candles for ``instrument_token``.

    Returns the number of candles seeded (0 if seeding was skipped or
    failed). All errors are swallowed with a warning — seeding is an
    optimization, not a correctness requirement.
    """
    if len(buf.get_candles()) > 0:
        return 0  # already has data, don't clobber
    interval = _INTERVAL_MAP.get(tf_minutes)
    if interval is None:
        return 0  # unsupported timeframe for Upstox historical API
    days = _seed_days(tf_minutes)
    try:
        bars = await upstox_client.get_historical_data(
            symbol="",  # unused when instrument_key provided
            interval=interval,
            days=days,
            instrument_key=instrument_token,
        )
    except Exception as e:
        logger.warning(
            "Candle seed failed for %s tf=%dm: %s",
            instrument_token, tf_minutes, e,
        )
        return 0
    if not bars:
        return 0

    # Upstox sometimes returns newest-first; normalize to oldest-first.
    if len(bars) >= 2:
        t0 = _to_naive_utc(bars[0].timestamp)
        t1 = _to_naive_utc(bars[-1].timestamp)
        if t0 is not None and t1 is not None and t0 > t1:
            bars = list(reversed(bars))

    candles: list[dict] = []
    for b in bars:
        ts = _to_naive_utc(b.timestamp)
        if ts is None:
            continue
        candles.append({
            "timestamp": ts,
            "open": float(b.open),
            "high": float(b.high),
            "low": float(b.low),
            "close": float(b.close),
            "volume": int(b.volume or 0),
        })

    # Trim to max_candles so the buffer's deque doesn't immediately
    # evict seeded history on the first live tick.
    if len(candles) > max_candles:
        candles = candles[-max_candles:]

    buf.seed(candles)
    logger.info(
        "Seeded %s tf=%dm with %d historical candles",
        instrument_token, tf_minutes, len(candles),
    )
    return len(candles)
