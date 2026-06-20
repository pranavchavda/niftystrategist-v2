"""Pre-compute the full nf-analyze technical read for scan candidates.

## Why

The 3-min scan-cache cron already produces candidate rows with a *scan*-level
read (RSI, VWAP, RVOL, setup classification). But when NS seriously evaluates a
candidate it runs ``nf-analyze SYMBOL`` for the deeper picture — overall signal,
MACD, supertrend, UT Bot, Renko, Bollinger, ATR, support/resistance. On a busy
session that's ~40 hand-run evaluations (06-18), each several tool calls.

This module computes that same deep read (via the identical
``TechnicalAnalysisService.analyze`` engine ``nf-analyze`` uses) for the top
candidates inside the cron subprocess, and folds a compact summary into each
row. The snapshot then renders it inline, so the agent's decision surface
already shows what it would otherwise fetch — "the /charts screen, but for NS."

Warmup-faithful by construction: same TA engine, same default candle source as
``nf-analyze`` (15-minute, 10 days), ATR-sized Renko brick (mirrors the
snapshot's own ``_tape_read``).

Origin: 2026-06-21 dev session (Pranav). See project_ns_agent_as_primary_user.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Optional

from services.technical_analysis import TechnicalAnalysisService

logger = logging.getLogger(__name__)

# Match nf-analyze's intraday default (cli-tools/nf-analyze: --interval 15minute,
# days_to_fetch=10 for non-daily). Keeps the precomputed read identical to what
# the agent sees when it runs the tool by hand.
_DEFAULT_INTERVAL = "15minute"
_DEFAULT_DAYS = 10
# analyze() needs ≥50 candles for stable indicators (per its own docstring).
_MIN_CANDLES = 50


def compact_analysis(analysis: Any) -> dict:
    """Reduce a ``MarketAnalysis`` to a compact, JSON-safe decision dict.

    Pure (no I/O) so it is unit-testable with a stub analysis object. Keeps only
    the fields NS actually reads off nf-analyze when deciding.
    """
    ind = analysis.indicators

    def _r(x, n=2):
        return round(x, n) if isinstance(x, (int, float)) else None

    supertrend = None
    if ind.supertrend is not None:
        supertrend = "bull" if ind.supertrend > 0 else "bear"

    renko = None
    if ind.renko_trend:
        arrow = "↑" if ind.renko_trend == "up" else "↓"
        renko = f"{arrow}{ind.renko_brick_count or 0}"

    vwap_pos = None
    if ind.vwap is not None and analysis.current_price is not None:
        vwap_pos = "above" if analysis.current_price >= ind.vwap else "below"

    return {
        "signal": analysis.overall_signal,        # strong_buy/buy/hold/sell/strong_sell
        "conf": _r(analysis.confidence, 2),
        "rsi": _r(ind.rsi_14, 1),
        "macd_hist": _r(ind.macd_histogram, 2),
        "macd_trend": analysis.macd_trend,         # bullish/bearish/neutral
        "supertrend": supertrend,                  # bull/bear
        "utbot": ind.utbot_trend,                  # long/short
        "renko": renko,                            # e.g. "↑3"
        "vwap_pos": vwap_pos,                       # above/below
        "bb_pctb": _r(ind.bb_pctb, 2),
        "atr": _r(ind.atr_14, 2),
        "trend": analysis.price_trend,             # uptrend/downtrend/sideways
        "sup": _r(analysis.support_level, 1),
        "res": _r(analysis.resistance_level, 1),
    }


def _market_data_client():
    """An UpstoxClient for non-user-specific market reads (mirrors
    cli-tools/base.init_market_data_client without importing the CLI runtime).

    Prefers the exchange-wide analytics token (doesn't expire daily) over the
    per-process access token, so the cron's enrichment doesn't 401 when a user
    token is stale.
    """
    from services.upstox_client import UpstoxClient
    token = (
        os.environ.get("UPSTOX_ANALYTICS_TOKEN")
        or os.environ.get("NF_ACCESS_TOKEN")
        or os.environ.get("UPSTOX_ACCESS_TOKEN")
        or ""
    ).strip()
    return UpstoxClient(access_token=token, paper_trading=False)


async def analyze_symbol(
    client: Any,
    symbol: str,
    *,
    interval: str = _DEFAULT_INTERVAL,
    days: int = _DEFAULT_DAYS,
) -> Optional[dict]:
    """Fetch candles and return the compact deep analysis, or None on failure."""
    if not symbol:
        return None
    try:
        candles = await client.get_historical_data(symbol, interval=interval, days=days)
    except Exception as e:
        logger.debug("candidate analysis candle fetch failed for %s: %s", symbol, e)
        return None
    if not candles or len(candles) < _MIN_CANDLES:
        return None
    try:
        # ATR-sized Renko brick so brick counts are comparable across symbols
        # (same treatment as the snapshot's _tape_read).
        base = TechnicalAnalysisService().calculate_indicators(candles)
        ta = TechnicalAnalysisService()
        if base.atr_14 and base.atr_14 > 0:
            ta = TechnicalAnalysisService(renko_brick_size=round(base.atr_14, 2))
        return compact_analysis(ta.analyze(symbol, candles))
    except Exception as e:
        logger.debug("candidate analysis failed for %s: %s", symbol, e)
        return None


async def enrich_rows_with_analysis(
    rows: list[dict],
    client: Any = None,
    *,
    deep_n: int = 10,
    interval: str = _DEFAULT_INTERVAL,
    days: int = _DEFAULT_DAYS,
    batch_size: int = 5,
) -> list[dict]:
    """Attach ``row['analysis']`` (compact deep read) to the top ``deep_n`` rows.

    Mutates and returns ``rows``. Best-effort per row — a symbol whose analysis
    fails is simply left without an ``analysis`` key. Batches concurrent reads to
    avoid hammering the quote API. Runs in the cron subprocess (off the request
    path), so the cost is hidden from interactive latency.
    """
    if not rows:
        return rows
    if client is None:
        client = _market_data_client()
    targets = rows[:deep_n]
    for i in range(0, len(targets), batch_size):
        batch = targets[i:i + batch_size]
        results = await asyncio.gather(
            *[analyze_symbol(client, r.get("symbol"), interval=interval, days=days)
              for r in batch],
            return_exceptions=True,
        )
        for r, res in zip(batch, results):
            if isinstance(res, dict):
                r["analysis"] = res
    n = sum(1 for r in targets if r.get("analysis"))
    logger.info("candidate_analysis: enriched %d/%d candidates", n, len(targets))
    return rows
