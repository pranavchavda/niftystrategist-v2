"""Cached candidate scan — write (cron) + read (snapshot) helpers.

The slow nf-morning-scan runs on its own ~3-min cron as an isolated subprocess
and stores its result here; the snapshot reads the newest fresh row instead of
scanning inline. See ``database.models.ScanSnapshot``.
"""
from __future__ import annotations

import logging
from datetime import timedelta

from sqlalchemy import select, delete

from database.models import ScanSnapshot, utc_now
from database.session import get_db_context

logger = logging.getLogger(__name__)

# Keep a short trail of recent scans for debugging; prune older than this.
_PRUNE_AFTER = timedelta(hours=2)


async def save_scan(universe: str, rows: list[dict], nifty_pct: float | None,
                    elapsed_ms: int | None) -> int:
    """Insert a scan row and prune old rows. Returns the new row id."""
    async with get_db_context() as session:
        row = ScanSnapshot(
            universe=universe, rows=rows, nifty_pct=nifty_pct, elapsed_ms=elapsed_ms,
        )
        session.add(row)
        await session.execute(
            delete(ScanSnapshot).where(ScanSnapshot.created_at < utc_now() - _PRUNE_AFTER)
        )
        await session.commit()
        await session.refresh(row)
        return row.id


async def get_latest_scan(universe: str, max_age_seconds: float) -> tuple[list[dict] | None, float | None]:
    """Newest cached scan for ``universe`` if fresher than ``max_age_seconds``.

    Returns (rows, age_seconds), or (None, None) when missing/stale so the
    caller can fall back to an inline scan.
    """
    async with get_db_context() as session:
        stmt = (
            select(ScanSnapshot)
            .where(ScanSnapshot.universe == universe)
            .order_by(ScanSnapshot.created_at.desc())
            .limit(1)
        )
        row = (await session.execute(stmt)).scalar_one_or_none()
    if not row:
        return None, None
    age = (utc_now() - row.created_at).total_seconds()
    if age > max_age_seconds:
        return None, age
    return (row.rows or []), age


async def run_and_store(universe: str = "nifty500") -> dict:
    """Run the candidate scan and persist it. Used by the cron subprocess."""
    from services.trading_snapshot import _run_live_scan

    rows, _source = await _run_live_scan(universe, top_n=10)

    # Fold the full nf-analyze technical read (signal/MACD/supertrend/UTBot/
    # Renko/BB/ATR/S-R) into the top candidates so the snapshot can render it
    # inline — sparing NS the per-candidate `nf-analyze` tool calls it would
    # otherwise hand-run (~40 on a busy session). Off the request path here, so
    # the cost is hidden from interactive latency. Best-effort: a failure leaves
    # rows un-enriched, the agent just falls back to fetching them itself.
    try:
        from services.candidate_analysis import enrich_rows_with_analysis
        await enrich_rows_with_analysis(rows, deep_n=10)
    except Exception as e:
        logger.warning("scan_cache: candidate-analysis enrichment failed: %s", e)

    nifty_pct = None
    row_id = await save_scan(universe, rows, nifty_pct, None)
    n_enriched = sum(1 for r in rows if r.get("analysis"))
    logger.info("scan_cache: stored %d rows (%d deep-analyzed) for %s (row #%d)",
                len(rows), n_enriched, universe, row_id)
    return {"universe": universe, "rows": len(rows),
            "analyzed": n_enriched, "row_id": row_id}
