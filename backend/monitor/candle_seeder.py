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

# How many trading days of history to request per timeframe. Picked to
# fill ~200 candles (CandleBuffer default max) with headroom for weekends.
_DAYS_MAP: dict[int, int] = {
    1: 2,
    5: 5,
    15: 10,
    30: 20,
}


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
    days = _DAYS_MAP.get(tf_minutes, 2)
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
