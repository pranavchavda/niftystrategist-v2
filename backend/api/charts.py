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
import os
import time
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from auth import User, get_current_user
from services.chart_overlays import compute_overlays, OVERLAY_COMPUTERS
from services.chart_market_stream import (
    TIMEFRAME_TO_MINUTES,
    get_chart_stream,
)
from services.instruments_cache import (
    search_symbols,
    search_indices,
    get_instrument_key,
    get_index_key,
)

# Reuse cockpit's per-user Upstox client resolver so token handling
# (decrypt + expiry + TOTP refresh + 401 retry) stays in one place.
from api import cockpit as cockpit_api

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


def _resolve_stream_backend(requested: Optional[str]) -> str:
    """Resolve which streaming backend to use for this request.

    Priority: query param > env var > "auto".
    "auto" picks "ws" if the chart stream singleton is healthy, else "poll".
    """
    raw = (requested or os.getenv("CHARTS_STREAM_BACKEND", "auto") or "auto").lower()
    if raw not in ("auto", "ws", "poll"):
        raw = "auto"
    if raw == "auto":
        cs = get_chart_stream()
        if cs is not None and cs.healthy:
            return "ws"
        return "poll"
    if raw == "ws":
        cs = get_chart_stream()
        if cs is None or not cs.healthy:
            # Caller asked for ws but it's unavailable; degrade silently.
            return "poll"
    return raw


async def _stream_via_ws(
    request: Request, sym: str, instrument_key: str, timeframe: str
):
    """SSE generator backed by the shared analytics-token WebSocket.

    Emits ticks as `data:` frames and (for intraday timeframes) server-built
    OHLC bars as `event: candle` frames. Frontend can consume either or
    both — bars-only is cleanest, but ticks remain useful for last-price
    labels and the existing client-side fold fallback.
    """
    cs = get_chart_stream()
    assert cs is not None  # guarded by _resolve_stream_backend

    tick_q = await cs.subscribe_ticks(instrument_key)
    candle_q: Optional[asyncio.Queue] = None
    if timeframe in TIMEFRAME_TO_MINUTES:
        candle_q = await cs.subscribe_candles(instrument_key, timeframe)

    yield (
        f"event: ready\n"
        f"data: {json.dumps({'symbol': sym, 'instrument_key': instrument_key, 'timeframe': timeframe, 'backend': 'ws', 'server_candles': candle_q is not None})}\n\n"
    ).encode()

    async def _next_event():
        # Wait for either a tick or a candle, whichever arrives first.
        getters = [asyncio.create_task(tick_q.get())]
        if candle_q is not None:
            getters.append(asyncio.create_task(candle_q.get()))
        try:
            done, pending = await asyncio.wait(
                getters, timeout=15.0, return_when=asyncio.FIRST_COMPLETED
            )
            for p in pending:
                p.cancel()
            if not done:
                return None  # timeout → emit heartbeat
            results: list[tuple[str, dict]] = []
            for d in done:
                payload = d.result()
                # Disambiguate by source queue.
                if candle_q is not None and getters[1] in done and d is getters[1]:
                    results.append(("candle", payload))
                else:
                    results.append(("tick", payload))
            # Drain whatever else is buffered now (lightweight) so we don't
            # accumulate latency under bursts.
            results.extend(_drain_nowait(tick_q, "tick"))
            if candle_q is not None:
                results.extend(_drain_nowait(candle_q, "candle"))
            return results
        finally:
            for g in getters:
                if not g.done():
                    g.cancel()

    try:
        while True:
            if await request.is_disconnected():
                return
            events = await _next_event()
            if events is None:
                yield b": ping\n\n"
                continue
            for kind, payload in events:
                if kind == "candle":
                    yield (
                        f"event: candle\n"
                        f"data: {json.dumps(payload)}\n\n"
                    ).encode()
                else:
                    yield f"data: {json.dumps(payload)}\n\n".encode()
    except asyncio.CancelledError:
        raise
    except Exception as e:
        logger.error(f"charts.stream({sym}) ws error: {e}", exc_info=True)
        try:
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n".encode()
        except Exception:
            pass
    finally:
        try:
            await cs.unsubscribe_ticks(instrument_key, tick_q)
        except Exception as e:
            logger.warning(f"charts.stream({sym}) tick unsubscribe failed: {e}")
        if candle_q is not None:
            try:
                await cs.unsubscribe_candles(instrument_key, timeframe, candle_q)
            except Exception as e:
                logger.warning(f"charts.stream({sym}) candle unsubscribe failed: {e}")


def _drain_nowait(q: asyncio.Queue, kind: str) -> list[tuple[str, dict]]:
    out: list[tuple[str, dict]] = []
    while True:
        try:
            out.append((kind, q.get_nowait()))
        except asyncio.QueueEmpty:
            break
    return out


async def _stream_via_polling(
    request: Request,
    user: User,
    sym: str,
    symbol: str,
    instrument_key: str,
    timeframe: str,
    interval_ms: int,
):
    """Original REST-polling fallback. Kept as a kill switch for the WS path."""
    client = await cockpit_api._get_client_for_user(user)

    yield (
        f"event: ready\n"
        f"data: {json.dumps({'symbol': sym, 'instrument_key': instrument_key, 'timeframe': timeframe, 'backend': 'poll'})}\n\n"
    ).encode()

    last_ltp: Optional[float] = None
    last_heartbeat = time.monotonic()
    interval_s = interval_ms / 1000.0
    consecutive_errors = 0

    try:
        while True:
            if await request.is_disconnected():
                break

            tick_emitted = False
            try:
                quote = await client.get_quote(symbol)
                ltp = quote.get("ltp") if isinstance(quote, dict) else None
                if ltp is not None:
                    ltp_f = float(ltp)
                    now = time.monotonic()
                    if ltp_f != last_ltp or (now - last_heartbeat) > 15.0:
                        payload = {"ltp": ltp_f, "ltt": int(time.time() * 1000)}
                        yield f"data: {json.dumps(payload)}\n\n".encode()
                        last_ltp = ltp_f
                        last_heartbeat = now
                        tick_emitted = True
                consecutive_errors = 0
            except Exception as e:
                consecutive_errors += 1
                logger.warning(f"charts.stream({symbol}) quote error #{consecutive_errors}: {e}")
                if consecutive_errors >= 5:
                    yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n".encode()
                    break

            if not tick_emitted and (time.monotonic() - last_heartbeat) > 15.0:
                yield b": ping\n\n"
                last_heartbeat = time.monotonic()

            slept = 0.0
            while slept < interval_s:
                if await request.is_disconnected():
                    return
                step = min(0.25, interval_s - slept)
                await asyncio.sleep(step)
                slept += step
    except asyncio.CancelledError:
        raise
    except Exception as e:
        logger.error(f"charts.stream({symbol}): {e}", exc_info=True)
        try:
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n".encode()
        except Exception:
            pass


@router.get("/stream/{symbol}")
async def charts_stream(
    request: Request,
    symbol: str,
    timeframe: str = Query(default="1D"),
    interval_ms: int = Query(default=2000, ge=500, le=15000),
    stream: Optional[str] = Query(default=None, description="Override: auto|ws|poll"),
    user: User = Depends(get_current_user),
):
    """SSE stream of live price + (optional) server-side OHLC bars.

    Two backends:
      - `ws`: subscribes to a shared analytics-token WebSocket (true tick
        cadence, server-side OHLC for intraday timeframes).
      - `poll`: legacy REST polling (1–3s lag, kept as a kill switch).

    Selection priority: `?stream=` query > `CHARTS_STREAM_BACKEND` env >
    `auto` (= ws if singleton healthy, else poll).

    Wire format:
        event: ready
        data:  {"symbol", "instrument_key", "timeframe", "backend", "server_candles"?}

        data:  {"ltp": 2545.50, "ltt": 1713515432000}            # tick

        event: candle
        data:  {"time": 1713515400, "open": ..., "high": ..., "low": ...,
                "close": ..., "volume": ..., "closed": false}    # ws path only,
                                                                 # intraday only

    On client disconnect both paths exit cleanly.
    """
    sym = symbol.upper()
    instrument_key = get_instrument_key(sym)
    if not instrument_key:
        instrument_key = get_index_key(symbol)
    if not instrument_key:
        raise HTTPException(status_code=404, detail=f"Unknown symbol: {symbol}")

    backend = _resolve_stream_backend(stream)

    if backend == "ws":
        gen = _stream_via_ws(request, sym, instrument_key, timeframe)
    else:
        gen = _stream_via_polling(
            request, user, sym, symbol, instrument_key, timeframe, interval_ms
        )

    return StreamingResponse(
        gen,
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
