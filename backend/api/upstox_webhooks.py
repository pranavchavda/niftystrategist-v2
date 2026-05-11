"""Upstox order webhook receiver.

Endpoint Upstox pushes order updates to. Per Upstox docs the endpoint MUST
NOT require authentication and MUST respond 2XX. We compensate for the lack
of auth with payload-driven validation:

  - Webhook never creates rows in monitor_logs / scalp_session_logs — only
    updates rows we already own (state updates land in Phase 2+).
  - All events are persisted into ``upstox_webhook_events`` with a unique
    index on (order_id, status, order_timestamp) — duplicates from Upstox
    retries become no-ops.
  - We accept any payload shape but log warnings on missing fields.
  - We always return 200 (even on internal error) so Upstox doesn't
    retry-spam; failures land in ``processed_outcome`` for later review.

Phase 1 (this file): passive observability. Persist events, return 200.
No state mutations to monitor / scalp tables.

Design doc: docs/plans/2026-05-11-upstox-webhook-design.md
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from database.models import UpstoxWebhookEvent, User
from database.session import get_db_context

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhooks/upstox", tags=["webhooks"])


def _parse_upstox_timestamp(value: Any) -> Optional[datetime]:
    """Upstox sends 'YYYY-MM-DD HH:MM:SS' (IST, naive). DB uses naive UTC.

    Convert IST → UTC (subtract 5h30m) so timestamps compare correctly with
    other naive-UTC columns in the schema. Returns None for null/empty/garbage.
    """
    if not value:
        return None
    if not isinstance(value, str):
        return None
    try:
        ist_naive = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        # IST is UTC+5:30. We store naive UTC, so subtract offset directly.
        from datetime import timedelta
        return ist_naive - timedelta(hours=5, minutes=30)
    except (ValueError, TypeError):
        return None


def _to_float(value: Any) -> Optional[float]:
    """Tolerant numeric coerce — Upstox sometimes sends strings, sometimes None."""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class WebhookResponse(BaseModel):
    ok: bool = True
    event_id: Optional[int] = None
    outcome: str = "stored"


@router.post("/order")
async def receive_order_update(request: Request) -> WebhookResponse:
    """Receive an order-update webhook from Upstox.

    Per Upstox: no auth, respond 2XX, accept POST. Returns 200 in all cases
    (even on internal error) so Upstox doesn't enter retry storms — internal
    failures are captured in ``upstox_webhook_events.processed_outcome``.
    """
    try:
        payload = await request.json()
    except Exception as e:
        # Malformed JSON — log + 200 (don't trigger Upstox retry).
        logger.warning("Upstox webhook: malformed JSON: %r", e)
        return WebhookResponse(ok=False, outcome="bad_json")

    if not isinstance(payload, dict):
        logger.warning("Upstox webhook: non-dict payload: %r", type(payload))
        return WebhookResponse(ok=False, outcome="bad_shape")

    upstox_user_id = payload.get("user_id") or payload.get("userId")
    update_type = payload.get("update_type", "order")
    status = payload.get("status", "")
    order_id = payload.get("order_id")
    gtt_order_id = payload.get("gtt_order_id")

    if not upstox_user_id:
        logger.warning("Upstox webhook: missing user_id — payload keys=%s",
                       list(payload.keys()))
        return WebhookResponse(ok=False, outcome="missing_user_id")

    if not status:
        logger.warning("Upstox webhook: missing status — order_id=%s", order_id)
        return WebhookResponse(ok=False, outcome="missing_status")

    # Phase 1 NOTE: ``raw_payload`` carries PII (placed_by, etc.). Don't echo
    # to stdout/journal; the DB row is the only persistence.
    try:
        async with get_db_context() as db:
            # Map upstox_user_id → local users.id (may be None for unknown users).
            # NOTE: upstox_user_id is NOT unique in our schema — dev/test users
            # can share a real user's Upstox id. Order by id ASC so the real
            # user (lowest id) wins over the dev placeholder (id=999).
            local_user_id = None
            user_row = (await db.execute(
                select(User)
                .where(User.upstox_user_id == str(upstox_user_id))
                .order_by(User.id.asc())
                .limit(1)
            )).scalar_one_or_none()
            if user_row:
                local_user_id = user_row.id
            else:
                logger.warning(
                    "Upstox webhook: unrecognized upstox_user_id=%s (order_id=%s status=%s)",
                    upstox_user_id, order_id, status,
                )

            event = UpstoxWebhookEvent(
                user_id=local_user_id,
                upstox_user_id=str(upstox_user_id),
                update_type=str(update_type)[:32],
                order_id=str(order_id)[:64] if order_id else None,
                gtt_order_id=str(gtt_order_id)[:64] if gtt_order_id else None,
                status=str(status)[:64],
                tag=(payload.get("tag") or None) and str(payload.get("tag"))[:64],
                instrument_key=(payload.get("instrument_key") or payload.get("instrument_token") or None) and str(payload.get("instrument_key") or payload.get("instrument_token"))[:64],
                trading_symbol=(payload.get("trading_symbol") or payload.get("tradingsymbol") or None) and str(payload.get("trading_symbol") or payload.get("tradingsymbol"))[:64],
                transaction_type=(payload.get("transaction_type") or None) and str(payload.get("transaction_type"))[:8],
                quantity=_to_int(payload.get("quantity")),
                filled_quantity=_to_int(payload.get("filled_quantity")),
                pending_quantity=_to_int(payload.get("pending_quantity")),
                average_price=_to_float(payload.get("average_price")),
                price=_to_float(payload.get("price")),
                trigger_price=_to_float(payload.get("trigger_price")),
                order_timestamp=_parse_upstox_timestamp(payload.get("order_timestamp")),
                exchange_timestamp=_parse_upstox_timestamp(payload.get("exchange_timestamp")),
                status_message=payload.get("status_message") or payload.get("status_message_raw"),
                raw_payload=payload,
                processed_outcome="observed",  # Phase 1: just observe, don't apply
                processed_at=None,
            )
            db.add(event)
            try:
                await db.commit()
            except IntegrityError:
                # Unique index hit — duplicate delivery of the same
                # (order_id, status, order_timestamp). Acknowledge silently.
                await db.rollback()
                logger.info(
                    "Upstox webhook: duplicate ignored (order_id=%s status=%s ts=%s)",
                    order_id, status, payload.get("order_timestamp"),
                )
                return WebhookResponse(ok=True, outcome="duplicate")

            logger.info(
                "Upstox webhook: stored event id=%d (user=%s status=%s order_id=%s tag=%s)",
                event.id, local_user_id, status, order_id, payload.get("tag"),
            )
            return WebhookResponse(ok=True, event_id=event.id, outcome="stored")
    except Exception as e:
        # Catch-all — Upstox shouldn't retry-spam on our internal bugs.
        # Log loudly so we notice in journalctl, but still return 200.
        logger.exception(
            "Upstox webhook: internal error processing payload (order_id=%s): %r",
            order_id, e,
        )
        return WebhookResponse(ok=False, outcome="error")


@router.get("/order/health")
async def health() -> dict:
    """Liveness check separate from the order POST handler.

    Useful for monitoring + for confirming Caddy routing without sending
    real Upstox payloads.
    """
    return {"ok": True, "endpoint": "upstox-order-webhook"}
