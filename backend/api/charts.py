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
    interval_ms: int = Query(default=2000, ge=500, le=15000),
    user: User = Depends(get_current_user),
):
    """SSE stream of the latest trade price for a single instrument.

    Backed by polling Upstox's REST market-quote endpoint rather than the
    WebSocket market-data feed. The feed is limited to ~1 concurrent WS per
    user access token, and the monitor/scalp daemon already owns that WS,
    so a second WS from this web process gets 403. Polling avoids the
    contention at the cost of coarser tick cadence (1–3s).

    Emits events of shape:
        data: {"ltp": 2545.50, "ltt": 1713515432000}

    On client disconnect the polling loop exits.
    """
    sym = symbol.upper()
    instrument_key = get_instrument_key(sym)
    if not instrument_key:
        instrument_key = get_index_key(symbol)
    if not instrument_key:
        raise HTTPException(status_code=404, detail=f"Unknown symbol: {symbol}")

    # Resolve once — reuse the same per-user client on every poll iteration.
    client = await cockpit_api._get_client_for_user(user)

    async def sse_generator():
        try:
            yield f"event: ready\ndata: {json.dumps({'symbol': sym, 'instrument_key': instrument_key, 'timeframe': timeframe})}\n\n".encode()

            last_ltp: Optional[float] = None
            last_heartbeat = time.monotonic()
            interval_s = interval_ms / 1000.0
            consecutive_errors = 0

            while True:
                if await request.is_disconnected():
                    break

                tick_emitted = False
                try:
                    quote = await client.get_quote(symbol)
                    ltp = quote.get("ltp") if isinstance(quote, dict) else None
                    if ltp is not None:
                        ltp_f = float(ltp)
                        # Only emit on change or after 15s of no emission (heartbeat).
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

                # SSE keep-alive comment if nothing emitted in >15s.
                if not tick_emitted and (time.monotonic() - last_heartbeat) > 15.0:
                    yield b": ping\n\n"
                    last_heartbeat = time.monotonic()

                # Sleep in small slices so disconnect is noticed quickly.
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
