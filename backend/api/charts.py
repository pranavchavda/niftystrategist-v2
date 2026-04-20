"""Charts API — OHLC + indicator overlays for the TradingView-style charts page.

Kept separate from `api/cockpit.py` so the cockpit's chart endpoint stays
stable while this router iterates independently.

Endpoints:
  GET /api/charts/candles/{symbol}      OHLC data
  GET /api/charts/indicators/{symbol}   Indicator series (lines / panes / markers)
  GET /api/charts/symbols               Symbol search (thin wrapper around instruments_cache)
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from auth import User, get_current_user
from services.chart_overlays import compute_overlays, OVERLAY_COMPUTERS
from services.instruments_cache import (
    search_symbols,
    search_indices,
    get_instrument_key,
    get_index_key,
)

# Reuse cockpit's per-user Upstox client resolver so token handling
# (decrypt + expiry + TOTP refresh + 401 retry) stays in one place.
from api import cockpit as cockpit_api
from api.upstox_oauth import get_user_upstox_token
from monitor.streams.market_data import MarketDataStream
from monitor.streams.connection import AuthenticationError

logger = logging.getLogger(__name__)
router = APIRouter()


# Map the frontend's timeframe tokens to (upstox_interval, days_to_fetch).
# The chart page uses these short codes; Upstox only supports minute/day granularity.
# Windows are generous so a long weekend or holiday doesn't wipe out
# the response. Upstox historical 1-minute retention is ~1 month; 5 days
# still comfortably covers Fri→Mon across any weekend.
TIMEFRAME_MAP: dict[str, tuple[str, int]] = {
    "1m": ("1minute", 5),
    "5m": ("5minute", 15),
    "15m": ("15minute", 45),
    "30m": ("30minute", 90),
    "1D": ("day", 180),
    "1W": ("day", 365 * 2),
    "1M": ("day", 365 * 5),
}


def _interval_and_days(timeframe: str, override_days: Optional[int]) -> tuple[str, int]:
    if timeframe not in TIMEFRAME_MAP:
        raise HTTPException(status_code=400, detail=f"Unsupported timeframe: {timeframe}")
    interval, default_days = TIMEFRAME_MAP[timeframe]
    return interval, override_days or default_days


async def _fetch_candles(user: User, symbol: str, interval: str, days: int) -> list[dict]:
    """Fetch OHLC candles normalized to the shape the frontend expects."""
    client = await cockpit_api._get_client_for_user(user)
    raw = await client.get_historical_data(symbol.upper(), interval=interval, days=days)
    raw.sort(key=lambda c: c.timestamp)
    intraday = interval in ("1minute", "5minute", "15minute", "30minute")
    out: list[dict] = []
    for c in raw:
        if intraday:
            t: int | str = int(datetime.fromisoformat(c.timestamp).timestamp())
        else:
            t = c.timestamp[:10] if len(c.timestamp) >= 10 else c.timestamp
        out.append({
            "time": t,
            "open": c.open,
            "high": c.high,
            "low": c.low,
            "close": c.close,
            "volume": c.volume,
        })
    return out


@router.get("/symbols")
async def charts_search_symbols(
    q: str = Query(..., min_length=1, description="Search term"),
    limit: int = Query(default=15, ge=1, le=50),
    user: User = Depends(get_current_user),
):
    """Search NSE symbols and indices by name or ticker.

    Indices are prepended to equity results so queries like "NIFTY" or "BANK"
    surface the index first. Each row carries a `kind` field ("index" or
    "equity") so the UI can badge them.
    """
    index_hits = search_indices(q, limit=limit)
    for r in index_hits:
        r["kind"] = "index"

    equity_hits = search_symbols(q, limit=limit)
    for r in equity_hits:
        r["kind"] = "equity"
        r["instrument_key"] = get_instrument_key(r["symbol"])

    # Interleave: indices first (they're the user-curious shortcut), then
    # equities, capped at the requested limit.
    combined: list[dict] = []
    seen: set[str] = set()
    for r in index_hits + equity_hits:
        sym = r.get("symbol") or ""
        if sym in seen:
            continue
        seen.add(sym)
        combined.append(r)
        if len(combined) >= limit:
            break
    return {"results": combined}


@router.get("/candles/{symbol}")
async def charts_candles(
    symbol: str,
    timeframe: str = Query(default="1D"),
    days: Optional[int] = Query(default=None, ge=1, le=3650),
    user: User = Depends(get_current_user),
):
    """Return OHLCV data for a symbol at a given timeframe."""
    interval, fetch_days = _interval_and_days(timeframe, days)
    try:
        candles = await _fetch_candles(user, symbol, interval, fetch_days)
        return {"symbol": symbol.upper(), "timeframe": timeframe, "candles": candles}
    except Exception as e:
        logger.error(f"charts.candles({symbol}, {timeframe}): {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/indicators/{symbol}")
async def charts_indicators(
    symbol: str,
    indicators: str = Query(
        default="",
        description="Comma-separated list of indicator names "
                    "(e.g. sma_20,sma_50,ema_21,bbands,vwap,rsi,macd,stoch,atr,utbot)",
    ),
    timeframe: str = Query(default="1D"),
    days: Optional[int] = Query(default=None, ge=1, le=3650),
    user: User = Depends(get_current_user),
):
    """Compute indicator series for a symbol.

    Indicator name shorthand:
      - "sma"       → SMA with default period (20)
      - "sma_50"    → SMA with period=50
      - "ema_21"    → EMA with period=21
      - "bbands"    → Bollinger Bands (20, 2)
      - "vwap"      → VWAP
      - "rsi" / "rsi_14"
      - "macd"      → MACD(12,26,9)
      - "stoch"     → Stochastic(14,3,3)
      - "atr"       → ATR(14)
      - "utbot"     → UT Bot
    """
    names = [n.strip() for n in indicators.split(",") if n.strip()]
    if not names:
        return {"lines": {}, "markers": [], "panes": []}

    interval, fetch_days = _interval_and_days(timeframe, days)
    try:
        candles = await _fetch_candles(user, symbol, interval, fetch_days)
        return compute_overlays(candles, names=names)
    except Exception as e:
        logger.error(f"charts.indicators({symbol}, {indicators}): {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stream/{symbol}")
async def charts_stream(
    request: Request,
    symbol: str,
    timeframe: str = Query(default="1D"),
    user: User = Depends(get_current_user),
):
    """SSE stream of live ticks for a single instrument.

    Sends one event per tick (coalesced to ~4/s) with shape:
        data: {"ltp": 2545.50, "ltt": 1713515432000}

    Where `ltt` is Upstox's last-trade-time in milliseconds. The frontend uses
    it to decide which candle bucket to update. On client disconnect the
    underlying Upstox WebSocket is torn down.
    """
    # Resolve instrument key — equities first, then indices.
    sym = symbol.upper()
    instrument_key = get_instrument_key(sym)
    if not instrument_key:
        instrument_key = get_index_key(symbol)
    if not instrument_key:
        raise HTTPException(status_code=404, detail=f"Unknown symbol: {symbol}")

    access_token = await get_user_upstox_token(user.id)
    if not access_token:
        raise HTTPException(
            status_code=401,
            detail="No valid Upstox token. Connect your account in Settings.",
        )

    # Bounded queue — drop oldest on overflow so a slow client can't back us up.
    tick_queue: asyncio.Queue = asyncio.Queue(maxsize=50)
    auth_failed = asyncio.Event()

    async def on_tick(data: dict):
        entry = data.get(instrument_key)
        if not entry:
            return
        ltp = entry.get("ltp")
        if ltp is None:
            return
        payload = {"ltp": float(ltp), "ltt": entry.get("ltt") or int(time.time() * 1000)}
        try:
            tick_queue.put_nowait(payload)
        except asyncio.QueueFull:
            # Drop oldest, keep latest.
            try:
                tick_queue.get_nowait()
                tick_queue.put_nowait(payload)
            except Exception:
                pass

    async def on_auth_failure():
        auth_failed.set()

    stream = MarketDataStream(
        access_token=access_token,
        on_message=on_tick,
        mode="ltpc",
        on_auth_failure=on_auth_failure,
    )

    async def sse_generator():
        started = False
        try:
            await stream.start()
            # Wait briefly for the WS to come up before subscribing.
            for _ in range(20):
                if stream.connected:
                    break
                await asyncio.sleep(0.1)
            await stream.subscribe([instrument_key])
            started = True

            yield f"event: ready\ndata: {json.dumps({'symbol': sym, 'instrument_key': instrument_key, 'timeframe': timeframe})}\n\n".encode()

            latest_tick: Optional[dict] = None
            emit_interval = 0.25  # 4 Hz max
            last_heartbeat = time.monotonic()
            next_emit = time.monotonic() + emit_interval

            while True:
                if await request.is_disconnected():
                    break
                if auth_failed.is_set():
                    yield b'event: error\ndata: {"error": "auth_failed"}\n\n'
                    break

                timeout = max(0.01, next_emit - time.monotonic())
                try:
                    tick = await asyncio.wait_for(tick_queue.get(), timeout=timeout)
                    latest_tick = tick
                except asyncio.TimeoutError:
                    pass

                now = time.monotonic()
                if now >= next_emit:
                    if latest_tick is not None:
                        yield f"data: {json.dumps(latest_tick)}\n\n".encode()
                        latest_tick = None
                        last_heartbeat = now
                    elif now - last_heartbeat > 15.0:
                        yield b": ping\n\n"
                        last_heartbeat = now
                    next_emit = now + emit_interval
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"charts.stream({symbol}): {e}", exc_info=True)
            try:
                yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n".encode()
            except Exception:
                pass
        finally:
            if started:
                try:
                    await stream.stop()
                except Exception:
                    pass

    return StreamingResponse(
        sse_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/available-indicators")
async def charts_available_indicators():
    """List indicators that compute_overlays knows about (for UI menu)."""
    return {
        "indicators": [
            {"name": "sma", "label": "SMA", "kind": "overlay", "parameterized": True, "default_period": 20},
            {"name": "ema", "label": "EMA", "kind": "overlay", "parameterized": True, "default_period": 20},
            {"name": "bbands", "label": "Bollinger Bands", "kind": "overlay", "parameterized": False},
            {"name": "vwap", "label": "VWAP", "kind": "overlay", "parameterized": False},
            {"name": "utbot", "label": "UT Bot", "kind": "overlay", "parameterized": False},
            {"name": "rsi", "label": "RSI", "kind": "pane", "parameterized": True, "default_period": 14},
            {"name": "macd", "label": "MACD", "kind": "pane", "parameterized": False},
            {"name": "stoch", "label": "Stochastic", "kind": "pane", "parameterized": False},
            {"name": "atr", "label": "ATR", "kind": "pane", "parameterized": True, "default_period": 14},
        ],
        "known": sorted(OVERLAY_COMPUTERS.keys()),
    }
