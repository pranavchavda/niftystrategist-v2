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
    get_isin,
    get_company_name,
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
    """Fetch OHLC candles normalized to the shape the frontend expects.

    Upstox's historical endpoint excludes today, so the bare multi-day result
    ends at yesterday's close. We tack on today's data per timeframe:
      - intraday (1m/5m/15m/30m): re-fetch via days=1 (routes to intraday API)
        and concat after stripping any same-day rows already in `raw`.
      - daily (interval=="day"): synthesize today's bar from the live quote
        (open/high/low/ltp/volume) and append.
    Without this the chart's last bar is yesterday and the header price
    (which reads lastCandle.close when not Live) is stale.
    """
    # Charts pull only public market data (OHLC + quote) — prefer the shared
    # analytics token, which doesn't expire daily, over the caller's per-user
    # token. Falls back to user token automatically when env var isn't set.
    client = await cockpit_api.get_market_data_client(user)
    raw = await client.get_historical_data(symbol.upper(), interval=interval, days=days)
    raw.sort(key=lambda c: c.timestamp)
    intraday = interval in ("1minute", "5minute", "15minute", "30minute")

    # Tack on today's data so the chart and header reflect current session.
    if intraday:
        try:
            today_raw = await client.get_historical_data(symbol.upper(), interval=interval, days=1)
        except Exception as e:
            logger.warning(f"charts.candles({symbol}, {interval}) intraday tail fetch failed: {e}")
            today_raw = []
        if today_raw:
            today_raw.sort(key=lambda c: c.timestamp)
            today_date = today_raw[0].timestamp[:10]
            # Drop any same-day rows from the historical pull to avoid dupes.
            raw = [c for c in raw if c.timestamp[:10] != today_date]
            raw.extend(today_raw)
            raw.sort(key=lambda c: c.timestamp)
    elif interval == "day":
        try:
            quote = await client.get_quote(symbol.upper())
        except Exception as e:
            logger.warning(f"charts.candles({symbol}, day) quote fetch failed: {e}")
            quote = None
        if quote and quote.get("ltp") is not None and quote.get("open") is not None:
            today_iso = datetime.now().strftime("%Y-%m-%d")
            # Drop any synthetic same-day bar already present (defensive).
            raw = [c for c in raw if c.timestamp[:10] != today_iso]
            from models.analysis import OHLCVData
            raw.append(OHLCVData(
                timestamp=today_iso,
                open=float(quote["open"]),
                high=float(quote.get("high") or quote["ltp"]),
                low=float(quote.get("low") or quote["ltp"]),
                close=float(quote["ltp"]),
                volume=int(quote.get("volume") or 0),
            ))
            raw.sort(key=lambda c: c.timestamp)

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
    """Return OHLCV data for a symbol at a given timeframe.

    Also returns a `quote` payload (live LTP + prior-day close) so the
    header price is consistent across timeframes. Without it, lower TFs
    show fresher prices than higher TFs because each TF's last bar is
    the most recently *closed* bucket — up to 30 min stale on a 30m
    chart, but 0–1 min on a 1m chart, and effectively live on 1D
    (which synthesizes today's bar from the quote).
    """
    interval, fetch_days = _interval_and_days(timeframe, days)
    try:
        candles = await _fetch_candles(user, symbol, interval, fetch_days)
        quote_payload: Optional[dict] = None
        try:
            client = await cockpit_api.get_market_data_client(user)
            q = await client.get_quote(symbol.upper())
            if q and q.get("ltp") is not None:
                def _f(v):
                    return float(v) if v is not None else None
                ltp = float(q["ltp"])
                # Upstox's `ohlc.close` (returned as `close` here) is the
                # *current bar's* close, which during/after the session
                # can equal `ltp` — using it as prior-day close gives a
                # zero change. The authoritative day-change source is
                # `net_change`, so derive prev_close from it when
                # available and fall back to `ohlc.close` otherwise.
                net_change = _f(q.get("net_change"))
                pct_change = _f(q.get("pct_change"))
                prev_close = (ltp - net_change) if net_change is not None else _f(q.get("close"))
                quote_payload = {
                    "ltp": ltp,
                    "prev_close": prev_close,
                    "net_change": net_change,
                    "pct_change": pct_change,
                    "open": _f(q.get("open")),
                    "high": _f(q.get("high")),
                    "low": _f(q.get("low")),
                }
        except Exception as e:
            logger.warning(f"charts.candles({symbol}) quote for header failed: {e}")
        return {
            "symbol": symbol.upper(),
            "timeframe": timeframe,
            "candles": candles,
            "quote": quote_payload,
        }
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
    params: Optional[str] = Query(
        default=None,
        description='Optional JSON object mapping indicator name → kwargs. '
                    'E.g. {"utbot":{"period":12,"sensitivity":2.0},"bbands":{"stddev":2.5}}',
    ),
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

    Per-indicator overrides via `params` (e.g. MACD fast/slow/signal,
    UT Bot sensitivity, Bollinger stddev) take priority over the
    shorthand suffix.
    """
    names = [n.strip() for n in indicators.split(",") if n.strip()]
    if not names:
        return {"lines": {}, "markers": [], "panes": []}

    parsed_params: dict[str, dict] = {}
    if params:
        try:
            raw = json.loads(params)
            if isinstance(raw, dict):
                for k, v in raw.items():
                    if isinstance(v, dict):
                        parsed_params[str(k)] = v
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid params JSON: {e}")

    interval, fetch_days = _interval_and_days(timeframe, days)
    try:
        candles = await _fetch_candles(user, symbol, interval, fetch_days)
        return compute_overlays(candles, names=names, params=parsed_params or None)
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
    client = await cockpit_api.get_market_data_client(user)

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


@router.get("/technicals/{symbol}")
async def charts_technicals(
    symbol: str,
    timeframe: str = Query(default="1D"),
    days: Optional[int] = Query(default=None, ge=1, le=3650),
    user: User = Depends(get_current_user),
):
    """Latest-bar technical snapshot for the chart's at-a-glance panel.

    Returns price plus current values + state badges for RSI(14),
    EMA(20/50/200), MACD(12,26,9), Bollinger Bands(20,2), ATR(14),
    Stochastic(14,3,3), and VWAP. State strings are: bullish | bearish |
    neutral | overbought | oversold. The summary tally counts the four
    momentum/trend signals (RSI, MACD, EMA-50 trend, Stoch).
    """
    import numpy as np
    import pandas as pd
    import ta

    interval, fetch_days = _interval_and_days(timeframe, days)
    try:
        candles = await _fetch_candles(user, symbol, interval, fetch_days)
        if len(candles) < 30:
            raise HTTPException(status_code=400, detail="Not enough candles for technicals")
        df = pd.DataFrame(candles).sort_values("time").reset_index(drop=True)
        close = df["close"].astype(float)
        high = df["high"].astype(float)
        low = df["low"].astype(float)
        last_price = float(close.iloc[-1])

        def _last(s: pd.Series) -> Optional[float]:
            v = s.iloc[-1]
            if pd.isna(v):
                return None
            return float(v)

        # Trend EMAs — fall back if window > history
        ema20_s = ta.trend.EMAIndicator(close, window=20).ema_indicator() if len(df) >= 20 else None
        ema50_s = ta.trend.EMAIndicator(close, window=50).ema_indicator() if len(df) >= 50 else None
        ema200_s = ta.trend.EMAIndicator(close, window=200).ema_indicator() if len(df) >= 200 else None
        ema20 = _last(ema20_s) if ema20_s is not None else None
        ema50 = _last(ema50_s) if ema50_s is not None else None
        ema200 = _last(ema200_s) if ema200_s is not None else None

        # RSI
        rsi_s = ta.momentum.RSIIndicator(close, window=14).rsi()
        rsi = _last(rsi_s)
        rsi_state = (
            "overbought" if rsi is not None and rsi >= 70
            else "oversold" if rsi is not None and rsi <= 30
            else "bullish" if rsi is not None and rsi > 55
            else "bearish" if rsi is not None and rsi < 45
            else "neutral"
        )

        # MACD
        macd_obj = ta.trend.MACD(close, window_slow=26, window_fast=12, window_sign=9)
        macd_v = _last(macd_obj.macd())
        macd_signal = _last(macd_obj.macd_signal())
        macd_hist = _last(macd_obj.macd_diff())
        macd_state = (
            "neutral" if macd_v is None or macd_signal is None
            else "bullish" if macd_v > macd_signal
            else "bearish"
        )

        # Bollinger Bands
        bb = ta.volatility.BollingerBands(close, window=20, window_dev=2)
        bb_upper = _last(bb.bollinger_hband())
        bb_middle = _last(bb.bollinger_mavg())
        bb_lower = _last(bb.bollinger_lband())
        bb_pct_b = None
        if bb_upper is not None and bb_lower is not None and bb_upper != bb_lower:
            bb_pct_b = (last_price - bb_lower) / (bb_upper - bb_lower)

        # ATR
        atr_s = ta.volatility.AverageTrueRange(high, low, close, window=14).average_true_range()
        atr = _last(atr_s)
        atr_pct = (atr / last_price * 100) if atr and last_price else None

        # Stochastic
        stoch = ta.momentum.StochasticOscillator(high=high, low=low, close=close, window=14, smooth_window=3)
        stoch_k = _last(stoch.stoch())
        stoch_d = _last(stoch.stoch_signal())
        stoch_state = (
            "overbought" if stoch_k is not None and stoch_k >= 80
            else "oversold" if stoch_k is not None and stoch_k <= 20
            else "bullish" if stoch_k is not None and stoch_d is not None and stoch_k > stoch_d
            else "bearish" if stoch_k is not None and stoch_d is not None and stoch_k < stoch_d
            else "neutral"
        )

        # VWAP — only meaningful with volume. Skip otherwise.
        vwap = None
        if "volume" in df.columns and df["volume"].astype(float).sum() > 0:
            try:
                vwap = _last(ta.volume.VolumeWeightedAveragePrice(
                    high=high, low=low, close=close,
                    volume=df["volume"].astype(float), window=14,
                ).volume_weighted_average_price())
            except Exception:
                vwap = None

        # Price-vs-EMA states
        def _vs(level: Optional[float]) -> str:
            if level is None:
                return "n/a"
            return "above" if last_price > level else "below"

        # Summary tally — count bullish/bearish among the four core signals.
        signals = {
            "rsi": "bullish" if rsi_state in ("bullish", "oversold") else "bearish" if rsi_state in ("bearish", "overbought") else "neutral",
            "macd": macd_state,
            "ema50_trend": "bullish" if ema50 is not None and last_price > ema50 else "bearish" if ema50 is not None else "neutral",
            "stoch": "bullish" if stoch_state in ("bullish", "oversold") else "bearish" if stoch_state in ("bearish", "overbought") else "neutral",
        }
        bullish = sum(1 for v in signals.values() if v == "bullish")
        bearish = sum(1 for v in signals.values() if v == "bearish")
        neutral = sum(1 for v in signals.values() if v == "neutral")
        verdict = "bullish" if bullish > bearish + 1 else "bearish" if bearish > bullish + 1 else "neutral"

        return {
            "symbol": symbol.upper(),
            "timeframe": timeframe,
            "price": last_price,
            "indicators": {
                "rsi": {"value": rsi, "state": rsi_state, "label": "RSI(14)"},
                "macd": {
                    "value": macd_v,
                    "signal": macd_signal,
                    "hist": macd_hist,
                    "state": macd_state,
                    "label": "MACD(12,26,9)",
                },
                "ema_20": {"value": ema20, "state": _vs(ema20), "label": "EMA(20)"},
                "ema_50": {"value": ema50, "state": _vs(ema50), "label": "EMA(50)"},
                "ema_200": {"value": ema200, "state": _vs(ema200), "label": "EMA(200)"},
                "bbands": {
                    "upper": bb_upper,
                    "middle": bb_middle,
                    "lower": bb_lower,
                    "pct_b": bb_pct_b,
                    "label": "BB(20,2)",
                },
                "atr": {"value": atr, "pct": atr_pct, "label": "ATR(14)"},
                "stoch": {"k": stoch_k, "d": stoch_d, "state": stoch_state, "label": "Stoch(14,3)"},
                "vwap": {"value": vwap, "state": _vs(vwap), "label": "VWAP"},
            },
            "summary": {
                "bullish": bullish,
                "bearish": bearish,
                "neutral": neutral,
                "verdict": verdict,
                "signals": signals,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"charts.technicals({symbol}, {timeframe}): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


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
            {"name": "halftrend", "label": "HalfTrend", "kind": "overlay", "parameterized": False},
            {"name": "ssl_hybrid", "label": "SSL Hybrid", "kind": "overlay", "parameterized": False},
            {"name": "ema_crossover", "label": "EMA Cross 9/21", "kind": "overlay", "parameterized": False},
            {"name": "supertrend", "label": "Supertrend", "kind": "overlay", "parameterized": False},
            {"name": "qqe_mod", "label": "QQE MOD", "kind": "pane", "parameterized": False},
            {"name": "renko", "label": "Renko Trend", "kind": "pane", "parameterized": False},
        ],
        "known": sorted(OVERLAY_COMPUTERS.keys()),
    }


def _shareholding_trend(history: list[dict]) -> dict | None:
    """Pull the latest two quarters from a shareholding history list.

    The API returns rows in most-recent-first order. Returns
    ``{latest_period, latest, prev, delta}`` or None if data is insufficient.
    """
    if not history or len(history) < 1:
        return None
    latest = history[0]
    prev = history[1] if len(history) >= 2 else None
    try:
        latest_v = float(latest.get("value"))
    except (TypeError, ValueError):
        return None
    prev_v = None
    if prev is not None:
        try:
            prev_v = float(prev.get("value"))
        except (TypeError, ValueError):
            prev_v = None
    return {
        "latest_period": latest.get("period"),
        "latest": latest_v,
        "prev": prev_v,
        "delta": (latest_v - prev_v) if prev_v is not None else None,
    }


@router.get("/fundamentals/{symbol}")
async def charts_fundamentals(
    symbol: str,
    user: User = Depends(get_current_user),
):
    """Aggregate fundamentals snapshot for the chart's right-side panel.

    Concurrently fetches profile / key-ratios / shareholding / latest
    quarterly income / corporate actions and shapes the result for a
    compact UI. Returns ``available=False`` (200, not 4xx) when the
    instrument is an index / ETF / unknown so the panel can render an
    "n/a" state without an error toast.
    """
    isin = get_isin(symbol)
    if not isin:
        return {
            "symbol": symbol.upper(),
            "available": False,
            "reason": "no_isin",
            "message": "Fundamentals are NSE-equity only (indices, ETFs, F&O contracts have no ISIN).",
        }

    try:
        client = await cockpit_api.get_market_data_client(user)
    except Exception as e:
        logger.error(f"charts.fundamentals: client init failed: {e}")
        raise HTTPException(status_code=500, detail=f"Upstox client unavailable: {e}")

    inst_key = get_instrument_key(symbol)
    name = get_company_name(symbol) or symbol.upper()

    async def _safe(coro):
        """Return None on failure so one bad endpoint doesn't kill the panel."""
        try:
            return await coro
        except Exception as e:
            logger.info(f"charts.fundamentals({symbol}) partial-fail: {e}")
            return None

    # Fan out — competitors omitted from the chart panel (not visually useful in a sidebar).
    profile_d, ratios_d, sh_d, income_d, actions_d = await asyncio.gather(
        _safe(client.get_company_profile(isin)),
        _safe(client.get_key_ratios(isin)),
        _safe(client.get_shareholding(isin)),
        _safe(client.get_income_statement(isin, time_period="quarterly")),
        _safe(client.get_corporate_actions(isin)),
    )

    # ── Profile (sector only — business description is too long for sidebar) ──
    sector = (profile_d or {}).get("sector") if isinstance(profile_d, dict) else None
    smc_inr = (profile_d or {}).get("sector_market_cap_inr") if isinstance(profile_d, dict) else None
    sector_cap_formatted = (smc_inr or {}).get("formatted") if isinstance(smc_inr, dict) else None

    # ── Ratios (list of {name, company_value, sector_value}) ──
    ratios = ratios_d if isinstance(ratios_d, list) else []

    # ── Shareholding: pluck FII + promoter trend ──
    sh_list = sh_d if isinstance(sh_d, list) else []
    sh_by_cat = {row.get("category"): row.get("history") or [] for row in sh_list}
    shareholding = {
        "promoter": _shareholding_trend(sh_by_cat.get("promoters", [])),
        "fii": _shareholding_trend(sh_by_cat.get("fii", [])),
        "mutual_funds": _shareholding_trend(sh_by_cat.get("mutual_funds", [])),
    }

    # ── Income: most recent quarter for revenue + net profit ──
    income_categories = []
    if isinstance(income_d, dict):
        income_categories = income_d.get("income_statement") or []
    income_by_cat = {row.get("category"): row.get("history") or [] for row in income_categories}
    latest_quarter = {}
    for cat in ("revenue", "operating_profit", "net_profit"):
        series = income_by_cat.get(cat) or []
        if series:
            row = series[0]  # most recent
            latest_quarter[cat] = {
                "period": row.get("period"),
                "value": row.get("value"),
                "change": row.get("change"),
            }
    income_units = income_d.get("units_in") if isinstance(income_d, dict) else "crore"

    # ── Corporate actions: upcoming + recent (next 90 days window for badge) ──
    actions_list = actions_d if isinstance(actions_d, list) else []
    parsed_actions = []
    now_dt = datetime.utcnow()
    for a in actions_list[:20]:
        ex_str = a.get("expiry_date") or ""
        try:
            ex_dt = datetime.strptime(ex_str, "%d %b %Y") if ex_str else None
        except ValueError:
            ex_dt = None
        days_until = (ex_dt - now_dt).days if ex_dt else None
        parsed_actions.append({
            "name": a.get("name"),
            "expiry_date": ex_str,
            "days_until": days_until,
            "amount": a.get("amount"),
            "ratio": a.get("ratio"),
            "details": next(
                (d.get("value") for d in (a.get("event_details") or [])
                 if d.get("name") == "Details"),
                None,
            ),
        })
    # Closest upcoming action within 30 days (for the chart badge)
    upcoming = next(
        (
            a for a in sorted(
                (x for x in parsed_actions if x["days_until"] is not None and x["days_until"] >= 0),
                key=lambda x: x["days_until"],
            )
            if a["days_until"] <= 30
        ),
        None,
    )

    return {
        "symbol": symbol.upper(),
        "isin": isin,
        "instrument_key": inst_key,
        "name": name,
        "available": True,
        "sector": sector,
        "sector_market_cap_inr_formatted": sector_cap_formatted,
        "ratios": ratios,
        "shareholding": shareholding,
        "latest_quarter": latest_quarter,
        "income_units": income_units,
        "upcoming_action": upcoming,
        "recent_actions": parsed_actions[:5],
    }
