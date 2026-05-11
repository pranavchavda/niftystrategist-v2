"""Apply Upstox order-webhook events to local state (Phase 2 backfill).

For each ``upstox_webhook_events`` row, identify what the event refers to
via the ``tag`` field and the ``order_id``, then patch the corresponding
``monitor_logs`` or ``scalp_session_logs`` row with the broker-authoritative
fill data (``filled_quantity``, ``average_price``, ``exchange_timestamp``).

Phase 1 (passive) just stored events. Phase 2 (this module) annotates DB
rows in-place so audit/analytics see the real numbers without polling
Upstox via ``_backfill_fill_price``. Phase 3 will add the retroactive
``fire_count`` revert when the webhook resolves a previously-ambiguous
SDK timeout as ``rejected``/``cancelled``.

Design constraints:

  - No record creation from webhook input — only updates to rows whose
    ``order_id`` (or matching tag) we already own. Compensates for the
    no-auth Upstox webhook requirement.
  - Idempotent on the upstream event row: processing the same event twice
    is harmless (overwrite is fine; output rows are not appended).
  - Tolerant of out-of-order delivery: ``complete`` is sticky — once a log
    row has fill data, later non-complete events don't roll it back.
  - Best-effort: errors are logged + recorded in ``processed_error``;
    the webhook handler always returns 200 so Upstox doesn't retry-spam.

Wired into ``api/upstox_webhooks.py`` as a background task right after
INSERT. A periodic sweep (TBD) will catch events that were stored but
failed processing (e.g. before the matching ``monitor_log`` existed).
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import (
    MonitorLog,
    ScalpSessionLogDB,
    UpstoxWebhookEvent,
)

logger = logging.getLogger(__name__)


# Statuses that carry useful fill data we want to surface into log tables.
# - 'complete' → average_price / filled_quantity → fill backfill.
# - 'rejected' / 'cancelled' → final negative outcome, recorded for audit.
# Other statuses (open, pending, validation pending, …) are informational
# and don't change the log row.
INTERESTING_STATUSES = {"complete", "rejected", "cancelled"}

_RULE_TAG_RE = re.compile(r"^rule:(\d+):fire:(\d+)$")
_SCALP_TAG_RE = re.compile(r"^scalp:[^:]+:[a-f0-9]+", re.IGNORECASE)


async def process_event(
    db: AsyncSession,
    event: UpstoxWebhookEvent,
) -> tuple[str, Optional[str]]:
    """Apply one webhook event to the right log table.

    Returns ``(outcome, error_message)`` where outcome is one of:
      - ``applied``       — found a target row and updated it
      - ``skipped``       — status not interesting; no work needed
      - ``unknown_order`` — no matching monitor_log / scalp_session_log
      - ``mismatch``      — found a row but it's already in a terminal state
      - ``error``         — exception while applying (also logs traceback)

    Caller is responsible for setting ``event.processed_at`` /
    ``event.processed_outcome`` on the event row.
    """
    status = (event.status or "").strip().lower()
    if status not in INTERESTING_STATUSES:
        return "skipped", None

    if event.order_id is None:
        return "skipped", "no order_id"

    tag = (event.tag or "").strip()
    try:
        if _RULE_TAG_RE.match(tag):
            return await _apply_to_monitor_log(db, event, status)
        if _SCALP_TAG_RE.match(tag):
            return await _apply_to_scalp_log(db, event, status)
        # No tag or unknown tag pattern. Try a fallback: hunt for any
        # scalp_session_log row carrying this exact order_id (entries set
        # order_id even when the tag wasn't preserved). Cheap because of
        # the new index in migration 037.
        return await _apply_to_scalp_log(db, event, status)
    except Exception as e:
        logger.exception(
            "webhook_processor: error applying event id=%s order_id=%s: %r",
            event.id, event.order_id, e,
        )
        return "error", str(e)[:500]


async def _apply_to_monitor_log(
    db: AsyncSession,
    event: UpstoxWebhookEvent,
    status: str,
) -> tuple[str, Optional[str]]:
    """Patch the monitor_log row whose action_result.order_id matches.

    ``monitor_logs.action_result`` is a JSON column; we read it, mutate, and
    write back the whole thing so this works regardless of the original
    structure produced by ``action_executor._place_order_via_node``.
    """
    # Postgres JSON access: action_result->>'order_id' returns text.
    row_res = await db.execute(
        text(
            "SELECT id, action_result FROM monitor_logs "
            "WHERE action_result->>'order_id' = :oid "
            "ORDER BY created_at DESC LIMIT 1"
        ),
        {"oid": event.order_id},
    )
    row = row_res.mappings().first()
    if not row:
        return "unknown_order", None

    current = dict(row["action_result"] or {})
    # Don't roll back fill data once written.
    if status == "complete" and current.get("filled_quantity"):
        return "mismatch", "already has fill data"

    patch = {
        "broker_status": event.status,
        "filled_quantity": event.filled_quantity,
        "average_price": float(event.average_price) if event.average_price is not None else None,
        "exchange_timestamp": (
            event.exchange_timestamp.isoformat()
            if event.exchange_timestamp else None
        ),
        "webhook_event_id": event.id,
    }
    # Preserve any keys already there (success, order_id, message); overlay
    # the broker-authoritative fields. ``None`` values are filtered so we
    # don't blank out previously-set fields.
    for k, v in patch.items():
        if v is not None:
            current[k] = v
        else:
            current.setdefault(k, None)

    await db.execute(
        text("UPDATE monitor_logs SET action_result = :ar WHERE id = :lid"),
        {"ar": _json_dumps(current), "lid": row["id"]},
    )
    return "applied", None


async def _apply_to_scalp_log(
    db: AsyncSession,
    event: UpstoxWebhookEvent,
    status: str,
) -> tuple[str, Optional[str]]:
    """Patch the latest scalp_session_log row whose order_id matches.

    Entry events update ``entry_price``; exit events update ``exit_price``
    and recompute P&L using the row's stored ``entry_price`` (entries and
    exits share an order_id only when the daemon reused it, which doesn't
    happen for scalp). ``filled_quantity`` from Upstox replaces the
    daemon-time ``quantity`` if larger (partial fills).
    """
    log_q = await db.execute(
        select(ScalpSessionLogDB)
        .where(ScalpSessionLogDB.order_id == event.order_id)
        .order_by(ScalpSessionLogDB.created_at.desc())
        .limit(1)
    )
    log = log_q.scalar_one_or_none()
    if not log:
        return "unknown_order", None

    avg = float(event.average_price) if event.average_price is not None else None
    qty = event.filled_quantity

    if status != "complete":
        # rejected/cancelled: stamp a marker into trigger_snapshot for audit.
        snap = dict(log.trigger_snapshot or {})
        snap.setdefault("webhook", {})
        snap["webhook"].update({
            "status": event.status,
            "event_id": event.id,
            "status_message": event.status_message,
        })
        log.trigger_snapshot = snap
        await db.commit()
        return "applied", None

    # status == complete from here on.
    if avg is None:
        return "mismatch", "complete event with no average_price"

    event_type = (log.event_type or "").lower()
    if event_type.startswith("entry") or event_type == "entry":
        # Don't roll back a fill once written (out-of-order safety).
        if log.entry_price and abs(log.entry_price - avg) < 0.01:
            return "mismatch", "entry_price already matches"
        log.entry_price = avg
        if qty:
            log.quantity = qty
    elif event_type.startswith("exit") or event_type == "exit":
        if log.exit_price and abs(log.exit_price - avg) < 0.01:
            return "mismatch", "exit_price already matches"
        log.exit_price = avg
        if qty:
            log.quantity = qty
        # Recompute P&L if entry_price is known. is_short heuristic: option_type
        # alone doesn't tell direction (buy/sell), so use stored P&L sign or
        # leave the daemon's polled value when ambiguous.
        if log.entry_price:
            raw = avg - log.entry_price
            # Heuristic: if daemon already wrote a negative pnl_points and our
            # raw is positive, this is a short cover. Conservative — only
            # update P&L magnitude, not sign-flip.
            prev_pnl = log.pnl_points
            if prev_pnl is None or (prev_pnl >= 0) == (raw >= 0):
                log.pnl_points = raw
                if qty:
                    log.pnl_amount = raw * qty
    else:
        # signal/error/reconcile events — no fill expected. Stamp webhook
        # data into trigger_snapshot for audit.
        snap = dict(log.trigger_snapshot or {})
        snap.setdefault("webhook", {})
        snap["webhook"].update({
            "status": event.status,
            "average_price": avg,
            "filled_quantity": qty,
            "event_id": event.id,
        })
        log.trigger_snapshot = snap

    await db.commit()
    return "applied", None


def _json_dumps(obj) -> str:
    """Local json.dumps used in raw SQL UPDATE (asyncpg needs str for jsonb)."""
    import json
    return json.dumps(obj, default=str)


async def mark_event_processed(
    db: AsyncSession,
    event_id: int,
    outcome: str,
    error: Optional[str] = None,
) -> None:
    """Set processed_at / processed_outcome / processed_error on the event row."""
    await db.execute(
        update(UpstoxWebhookEvent)
        .where(UpstoxWebhookEvent.id == event_id)
        .values(
            processed_at=text("(NOW() AT TIME ZONE 'UTC')"),
            processed_outcome=outcome,
            processed_error=error,
        )
    )
    await db.commit()


async def process_event_and_mark(
    db: AsyncSession,
    event: UpstoxWebhookEvent,
) -> str:
    """Convenience: run process_event() and persist the outcome onto the event.

    Returns the outcome string. Errors during the marking phase are logged
    but not re-raised — the event was either applied or not, marking is
    audit-only.
    """
    outcome, err = await process_event(db, event)
    try:
        await mark_event_processed(db, event.id, outcome, err)
    except Exception as e:
        logger.warning(
            "webhook_processor: failed to mark event %d as %s: %r",
            event.id, outcome, e,
        )
    return outcome
