"""Intraday sector-flow cache — compute (cron) + read (request path) helpers.

The sensor's full-universe fetch (≈500 names × 15-min candles) is the wrong shape
for the request path: a concurrent burst trips Upstox's per-token rate limit on the
historical API and stalls (the sync SDK sleeps on Retry-After). So — exactly like
scan_cache — a ~5-min cron computes the two-layer snapshot as an isolated
subprocess and stores it; the live `nf-sector-flow` tool and any awakening read the
newest fresh row instead of fetching inline. See database.models.SectorFlowSnapshot.

Layout mirrors services/scan_cache.py. The fetch is normalized to plain tuples at
the boundary so `_shape_snapshot` is PURE (no SDK / network) and unit-testable.
"""
from __future__ import annotations

import asyncio
import logging
import statistics
from datetime import datetime, timedelta

from sqlalchemy import delete, select

from database.models import SectorFlowSnapshot, utc_now
from database.session import get_db_context
from services import instruments_cache as ic
from services.sector_flow import (
    persistent_bias,
    relative_timeline,
    sector_timeline,
)

logger = logging.getLogger(__name__)

_PRUNE_AFTER = timedelta(hours=3)
MIN_SECTOR_NAMES = 8          # breadth needs names; thinner sectors are too noisy
THIN_SECTOR_NAMES = 14        # below this a sector decouples ~2x as often (vol/few
                              # names) → tagged "thin" so its signal is discounted
FETCH_CONCURRENCY = 6         # gentler than scan_cache to ease Upstox rate-limiting
# Thresholds from a 14-session characterization (2026-06-28): the prior 2-day
# eyeball (0.06/0.08) fired far too often (roll 12.7% of bars, decouple 16.8% of
# sector-bars). These sit near p90 — the genuine tail. Refine with more tape.
MARKET_ROLL_DECIS = 0.07      # ~p90 of market bar decisiveness (~2.6 rolling bars/day)
DECOUPLE_DECIS = 0.12         # ~p89 of sector-bar rel_decisiveness (keeps the strong events)


# ── fetch boundary (normalizes SDK objects → plain (ts, open, close) tuples) ──

async def _fetch_universe(client, symbols: list[str], days: int) -> dict[str, list[tuple]]:
    sem = asyncio.Semaphore(FETCH_CONCURRENCY)

    async def one(sym):
        async with sem:
            try:
                candles = await client.get_historical_data(sym, interval="15minute", days=days)
                return sym, [(c.timestamp, c.open, c.close) for c in candles]
            except Exception:
                return sym, []
    return dict(await asyncio.gather(*[one(s) for s in symbols]))


# ── pure shaping (no I/O — testable with synthetic tuples) ───────────────────

def _build_day(symbols, results: dict[str, list[tuple]], day: str):
    """→ (times, per_open, per_closes, per_prev) for a symbol set on one date."""
    per_open, per_closes, per_prev, times = {}, {}, {}, set()
    for sym in symbols:
        rows = results.get(sym) or []
        day_rows = sorted((r for r in rows if r[0][:10] == day), key=lambda r: r[0])
        if not day_rows:
            continue
        per_open[sym] = day_rows[0][1]
        per_closes[sym] = {r[0][11:16]: r[2] for r in day_rows}
        prior = [r for r in rows if r[0][:10] < day]
        per_prev[sym] = sorted(prior, key=lambda r: r[0])[-1][2] if prior else None
        times |= set(per_closes[sym].keys())
    return sorted(times), per_open, per_closes, per_prev


def _market_gap(per_open, per_prev):
    gaps = [(op - per_prev[s]) / per_prev[s] * 100.0
            for s, op in per_open.items() if per_prev.get(s)]
    return round(statistics.median(gaps), 2) if gaps else None


def _shape_snapshot(results: dict[str, list[tuple]], universe_name: str,
                    target_date: str | None, threshold: float, window: int) -> dict:
    """Build the serializable two-layer snapshot from fetched candle tuples."""
    universe = sorted(results.keys())
    by_sector: dict[str, list[str]] = {}
    for s in universe:
        sec = ic.get_sector(s)
        if sec:
            by_sector.setdefault(sec, []).append(s)

    present = sorted({r[0][:10] for rows in results.values() for r in rows})
    if not present:
        return {"error": "No candle data."}
    target = target_date or present[-1]

    m_times, m_open, m_closes, m_prev = _build_day(universe, results, target)
    if not m_open:
        return {"error": f"No market data for {target}."}
    market_tl = sector_timeline("MARKET", m_times, m_closes, m_open,
                                threshold=threshold, window=window)
    m_last = market_tl[-1]
    recent = market_tl[-window:] if len(market_tl) >= window else market_tl
    rolling = any((s.decisiveness or 0) >= MARKET_ROLL_DECIS for s in recent)
    m_peak = max(market_tl, key=lambda s: s.decisiveness or 0)

    sectors = {}
    for label, members in by_sector.items():
        if len(members) < MIN_SECTOR_NAMES:
            continue
        s_times, s_open, s_closes, _ = _build_day(members, results, target)
        if len(s_open) < MIN_SECTOR_NAMES:
            continue
        sector_tl = sector_timeline(label, s_times, s_closes, s_open,
                                    threshold=threshold, window=window)
        rel_tl = relative_timeline(sector_tl, market_tl, window=window)
        if not rel_tl:
            continue
        bias = persistent_bias(rel_tl)
        rel_last = rel_tl[-1]
        peak = max(rel_tl, key=lambda s: s.rel_decisiveness or 0)
        sectors[label] = {
            "n": len(s_open), "bias": bias["bias"],
            "thin": len(s_open) < THIN_SECTOR_NAMES,
            "avg_rel_median": bias["avg_rel_median"],
            "last_rel_median": round(rel_last.rel_median, 3),
            "decoupling_now": (rel_last.rel_decisiveness or 0) >= DECOUPLE_DECIS,
            "peak_rel_decisiveness": round(peak.rel_decisiveness or 0, 4),
            "peak_rel_at": peak.as_of,
            "timeline": [s.as_dict() for s in rel_tl],
        }

    return {
        "date": target,
        "universe": universe_name,
        "as_of": m_last.as_of,
        "market": {
            "median_move": round(m_last.median_move, 2),
            "net_breadth": round(m_last.net_breadth, 2),
            "n": m_last.n,
            "gap": _market_gap(m_open, m_prev),
            "decisiveness": round(m_last.decisiveness or 0, 4),
            "rolling": rolling,
            "peak_decisiveness": round(m_peak.decisiveness or 0, 4),
            "peak_at": m_peak.as_of,
            "direction": "down" if m_last.median_move < 0 else "up",
        },
        "market_timeline": [s.as_dict() for s in market_tl],
        "sectors": sectors,
    }


# ── compute (live fetch + shape) ─────────────────────────────────────────────

async def compute_snapshot(universe: str = "nifty500", date: str | None = None,
                           threshold: float = 0.3, window: int = 2, client=None) -> dict:
    """Fetch the universe and compute the two-layer snapshot. ``client`` is
    injectable for tests; defaults to the public market-data client."""
    ic.ensure_loaded()
    symbols = sorted(ic.get_universe(universe))
    if date:
        delta = (datetime.now() - datetime.strptime(date, "%Y-%m-%d")).days
        days = max(4, delta + 3)
    else:
        days = 4
    if client is None:
        from base import init_market_data_client
        client = init_market_data_client()
    results = await _fetch_universe(client, symbols, days)
    return _shape_snapshot(results, universe, date, threshold, window)


# ── store + read (mirrors scan_cache) ────────────────────────────────────────

async def save_snapshot(universe: str, snapshot: dict, elapsed_ms: int | None) -> int:
    async with get_db_context() as session:
        row = SectorFlowSnapshot(
            universe=universe, snapshot=snapshot,
            session_date=snapshot.get("date"), elapsed_ms=elapsed_ms,
        )
        session.add(row)
        await session.execute(
            delete(SectorFlowSnapshot).where(SectorFlowSnapshot.created_at < utc_now() - _PRUNE_AFTER)
        )
        await session.commit()
        await session.refresh(row)
        return row.id


async def get_latest_snapshot(universe: str, max_age_seconds: float) -> tuple[dict | None, float | None]:
    """Newest cached snapshot for ``universe`` if fresher than ``max_age_seconds``.
    Returns (snapshot, age_seconds) or (None, age|None) when missing/stale."""
    async with get_db_context() as session:
        stmt = (
            select(SectorFlowSnapshot)
            .where(SectorFlowSnapshot.universe == universe)
            .order_by(SectorFlowSnapshot.created_at.desc())
            .limit(1)
        )
        row = (await session.execute(stmt)).scalar_one_or_none()
    if not row:
        return None, None
    age = (utc_now() - row.created_at).total_seconds()
    if age > max_age_seconds:
        return None, age
    return (row.snapshot or {}), age


async def run_and_store(universe: str = "nifty500") -> dict:
    """Compute the live snapshot and persist it. Used by the cron subprocess."""
    import time
    t0 = time.time()
    snapshot = await compute_snapshot(universe=universe)
    elapsed_ms = int((time.time() - t0) * 1000)
    if "error" in snapshot:
        logger.warning("sector_flow_cache: compute error: %s", snapshot["error"])
        return {"universe": universe, "error": snapshot["error"], "elapsed_ms": elapsed_ms}
    row_id = await save_snapshot(universe, snapshot, elapsed_ms)
    mkt = snapshot["market"]
    logger.info("sector_flow_cache: stored %s (%d sectors, market %s decis=%.3f) row #%d in %dms",
                snapshot["date"], len(snapshot["sectors"]),
                mkt["direction"], mkt["decisiveness"], row_id, elapsed_ms)
    return {"universe": universe, "date": snapshot["date"],
            "sectors": len(snapshot["sectors"]), "row_id": row_id, "elapsed_ms": elapsed_ms}
