#!/usr/bin/env python3
"""Backfill trigger_snapshot for existing scalp session log rows.

Per log row missing trigger_snapshot:
1. Look up the parent session config (still useful even if disabled)
2. Fetch historical candles ending at log.created_at via Upstox HistoryV3Api
3. Recompute primary + confirm indicator series
4. UPDATE the row with the snapshot dict

Caches historical fetches by (instrument_token, timeframe, date) since
multiple log rows on the same session-day reuse the same candles. Best-
effort — failures log and skip; the live path keeps populating new rows.

Run from backend/:
    python -m scripts.backfill_scalp_snapshots         # all logs
    python -m scripts.backfill_scalp_snapshots --user 1
    python -m scripts.backfill_scalp_snapshots --since 2026-04-15
    python -m scripts.backfill_scalp_snapshots --dry-run
"""
from __future__ import annotations

import argparse
import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import String, cast, or_, select, update

from database.models import ScalpSessionDB, ScalpSessionLogDB
from database.session import get_db_context
from monitor.snapshot_builder import build_decision_snapshot

logger = logging.getLogger("backfill")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


# Map indicator_timeframe string → (Upstox unit, interval_value).
_TF_TO_UPSTOX: dict[str, tuple[str, int]] = {
    "1m": ("minutes", 1),
    "3m": ("minutes", 1),     # not natively supported; resample from 1m would be needed — fall back to 1m
    "5m": ("minutes", 5),
    "15m": ("minutes", 15),
    "30m": ("minutes", 30),
    "1h": ("minutes", 30),    # closest supported; treat as 30m
    "1d": ("days", 1),
}


def _to_naive_utc(ts: Any) -> datetime | None:
    if isinstance(ts, datetime):
        dt = ts
    elif isinstance(ts, str):
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


async def _build_user_clients(user_ids: set[int]) -> dict[int, Any]:
    """Resolve a fresh Upstox-token-bearing client per user."""
    from api.upstox_oauth import get_user_upstox_token
    from services.upstox_client import UpstoxClient

    clients: dict[int, Any] = {}
    for uid in user_ids:
        try:
            token = await get_user_upstox_token(uid)
            if not token:
                logger.warning("user=%d: no Upstox token — skipping their logs", uid)
                continue
            clients[uid] = UpstoxClient(access_token=token, user_id=uid)
        except Exception as e:
            logger.warning("user=%d: token resolution failed (%s) — skipping", uid, e)
    return clients


def _fetch_window(
    client: Any, instrument_token: str, decision_t: datetime, timeframe: str,
    *, lookback_days: int = 5,
) -> list[dict]:
    """Fetch a window of historical OHLCV ending at ``decision_t``. Returns
    candles in ascending order with the same dict shape CandleBuffer uses.
    """
    import upstox_client as upstox_sdk
    unit, interval = _TF_TO_UPSTOX.get(timeframe, ("minutes", 1))
    api_client = upstox_sdk.ApiClient(client._configuration)
    history_api = upstox_sdk.HistoryV3Api(api_client)

    to_date = decision_t.date().isoformat()
    from_date = (decision_t.date() - timedelta(days=lookback_days)).isoformat()

    try:
        resp = history_api.get_historical_candle_data1(
            instrument_key=instrument_token,
            unit=unit,
            interval=interval,
            to_date=to_date,
            from_date=from_date,
        )
    except Exception as e:
        logger.warning(
            "history fetch failed (inst=%s tf=%s %s..%s): %s",
            instrument_token, timeframe, from_date, to_date, e,
        )
        return []

    raw = resp.data.candles if resp.data else []
    if not raw:
        return []

    out: list[dict] = []
    for c in raw:
        # Upstox returns [timestamp, open, high, low, close, volume, oi]
        ts = _to_naive_utc(c[0])
        if ts is None:
            continue
        out.append({
            "timestamp": ts,
            "open": float(c[1]), "high": float(c[2]),
            "low": float(c[3]), "close": float(c[4]),
            "volume": int(c[5] or 0),
        })
    out.sort(key=lambda d: d["timestamp"])
    # Trim to candles strictly at-or-before decision_t.
    out = [c for c in out if c["timestamp"] <= decision_t]
    return out


def _decision_price_for_log(log: ScalpSessionLogDB) -> float | None:
    """Pick the most informative price for the snapshot meta."""
    if log.exit_price is not None:
        return float(log.exit_price)
    if log.entry_price is not None:
        return float(log.entry_price)
    if log.underlying_price is not None:
        return float(log.underlying_price)
    return None


async def backfill(
    user_id_filter: int | None = None,
    since: datetime | None = None,
    dry_run: bool = False,
    limit: int | None = None,
) -> None:
    async with get_db_context() as db:
        # Pull all candidate logs in one shot (snapshot=NULL, optional filters).
        # SQLAlchemy serializes Python None into the JSON column as the literal
        # JSON `null`, which is a non-NULL DB value. Match both forms.
        stmt = select(ScalpSessionLogDB).where(
            or_(
                ScalpSessionLogDB.trigger_snapshot.is_(None),
                cast(ScalpSessionLogDB.trigger_snapshot, String) == "null",
            )
        )
        if user_id_filter is not None:
            stmt = stmt.where(ScalpSessionLogDB.user_id == user_id_filter)
        if since is not None:
            stmt = stmt.where(ScalpSessionLogDB.created_at >= since)
        # Only entry/exit events get snapshots — order_failed/error/reconcile
        # don't have meaningful indicator state.
        stmt = stmt.where(
            ScalpSessionLogDB.event_type.startswith("entry_")
            | ScalpSessionLogDB.event_type.startswith("exit_")
        )
        stmt = stmt.order_by(ScalpSessionLogDB.id.desc())
        if limit is not None:
            stmt = stmt.limit(limit)

        result = await db.execute(stmt)
        logs = list(result.scalars().all())
        if not logs:
            logger.info("nothing to backfill")
            return
        logger.info("found %d log rows to backfill", len(logs))

        # Pre-load all involved sessions in one query.
        session_ids = {l.session_id for l in logs}
        sess_rows = (await db.execute(
            select(ScalpSessionDB).where(ScalpSessionDB.id.in_(session_ids))
        )).scalars().all()
        sessions: dict[int, ScalpSessionDB] = {s.id: s for s in sess_rows}

    # Build clients for involved users (outside the DB context to keep that short).
    user_ids = {s.user_id for s in sessions.values()}
    clients = await _build_user_clients(user_ids)

    # Cache: (instrument_token, timeframe, decision_date) → candles list
    candle_cache: dict[tuple[str, str, str], list[dict]] = {}
    by_inst_count: dict[str, int] = defaultdict(int)
    written = 0
    skipped = 0

    for log in logs:
        sess = sessions.get(log.session_id)
        if sess is None:
            logger.warning("log=%d: session %d missing — skip", log.id, log.session_id)
            skipped += 1
            continue
        client = clients.get(sess.user_id)
        if client is None:
            skipped += 1
            continue

        decision_t = log.created_at
        if decision_t is None:
            skipped += 1
            continue
        date_key = decision_t.date().isoformat()
        cache_key = (sess.underlying_instrument_token, sess.indicator_timeframe, date_key)

        candles = candle_cache.get(cache_key)
        if candles is None:
            candles = _fetch_window(
                client, sess.underlying_instrument_token, decision_t, sess.indicator_timeframe,
            )
            candle_cache[cache_key] = candles
            by_inst_count[sess.underlying_instrument_token] += 1

        # Filter once more for THIS log's decision_t (cache holds up to end-of-day).
        prefix = [c for c in candles if c["timestamp"] <= decision_t]
        if not prefix:
            logger.warning("log=%d: no candles ≤ %s for %s — skip",
                           log.id, decision_t, sess.underlying_instrument_token)
            skipped += 1
            continue

        snap = build_decision_snapshot(
            prefix,
            primary_indicator=sess.primary_indicator or "utbot",
            primary_params=sess.primary_params,
            confirm_indicator=sess.confirm_indicator,
            confirm_params=sess.confirm_params,
            timeframe=sess.indicator_timeframe,
            decision_price=_decision_price_for_log(log),
        )
        if snap is None:
            skipped += 1
            continue

        if dry_run:
            logger.info("DRY log=%d session=%d %s candles=%d",
                        log.id, sess.id, log.event_type, len(snap["candles"]))
            written += 1
            continue

        async with get_db_context() as db:
            await db.execute(
                update(ScalpSessionLogDB)
                .where(ScalpSessionLogDB.id == log.id)
                .values(trigger_snapshot=snap)
            )
            await db.commit()
        written += 1
        if written % 25 == 0:
            logger.info("progress: %d written, %d skipped", written, skipped)

    logger.info("done — %d written, %d skipped, %d unique fetches",
                written, skipped, sum(by_inst_count.values()))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--user", type=int, default=None, help="Filter by user_id")
    p.add_argument("--since", type=str, default=None, help="ISO date (UTC) — only logs at/after this date")
    p.add_argument("--limit", type=int, default=None, help="Max rows to process")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    since = None
    if args.since:
        since = datetime.fromisoformat(args.since)

    asyncio.run(backfill(
        user_id_filter=args.user,
        since=since,
        dry_run=args.dry_run,
        limit=args.limit,
    ))


if __name__ == "__main__":
    main()
