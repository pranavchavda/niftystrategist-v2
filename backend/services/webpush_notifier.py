"""Per-user Web Push outbound notifier (PWA).

Native replacement for the OUTBOUND half of Telegram while Telegram is banned
in India. Process-agnostic: callable from FastAPI handlers, the monitor daemon,
or the awakening scheduler — it's just HTTPS POSTs to the browser push service
plus a DB read, with no shared event-loop concern like the Telegram inbound
poller.

Usage (normally via services.notifier.notify_user, not directly):

    from services.webpush_notifier import push
    await push(user_id, "monitor_fire", "ZEEL SL hit at 187.40")

Categories live in `api.telegram.NOTIFICATION_CATEGORIES` and muting reuses the
same `users.notification_prefs` map as Telegram — opt-out semantics (missing
key = enabled). VAPID keys come from env. Failures are logged and swallowed;
push() never raises. Dead subscriptions (HTTP 404/410) are pruned.

See docs/plans/2026-06-19-web-push-notifications.md.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from collections import deque
from typing import Any, Optional

from sqlalchemy import delete, select, update

from database.models import User as DBUser, WebPushSubscription, utc_now
from database.session import get_db_session

logger = logging.getLogger(__name__)

# App-global VAPID keypair (NOT per-user). Generate once with `vapid --gen`.
VAPID_PUBLIC_KEY = os.getenv("VAPID_PUBLIC_KEY", "").strip()
VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY", "").strip()
VAPID_SUBJECT = os.getenv("VAPID_SUBJECT", "mailto:admin@niftystrategist.app").strip()

# Per-user rate-limit window — mirrors telegram_notifier. In-memory, no
# persistence across restarts. Cheap guard against spamming during a busy
# market session, not a Telegram-style hard API limit.
RATE_MAX = 60
ROLLING_SECONDS = 3600
_rate_windows: dict[int, deque[float]] = {}

# Short human title per category — push has a title slot Telegram lacks.
_CATEGORY_TITLES = {
    "monitor_fire": "📈 Monitor",
    "monitor_failure": "⚠️ Monitor",
    "awakening": "🌅 Awakening",
    "order_fill": "✅ Order",
    "system": "⚙️ Nifty Strategist",
}


def _rate_check(user_id: int) -> bool:
    """True if the user is under the rate cap. Records a hit only when True."""
    now = time.monotonic()
    window = _rate_windows.setdefault(user_id, deque())
    cutoff = now - ROLLING_SECONDS
    while window and window[0] < cutoff:
        window.popleft()
    if len(window) >= RATE_MAX:
        return False
    window.append(now)
    return True


def _category_enabled(prefs: dict[str, Any], category: str) -> bool:
    """Missing keys default to enabled (opt-out semantics) — shared with Telegram."""
    value = prefs.get(category)
    if value is None:
        return True
    return bool(value)


async def _load_subscriptions(user_id: int) -> tuple[list[WebPushSubscription], dict]:
    """Fetch a user's push subscriptions and their notification prefs.

    Returns ([], {}) when the user has no subscriptions so the caller can
    short-circuit without sending.
    """
    async with get_db_session() as session:
        prefs_row = (
            await session.execute(
                select(DBUser.notification_prefs).where(DBUser.id == user_id)
            )
        ).first()
        if prefs_row is None:
            return [], {}

        subs = (
            (
                await session.execute(
                    select(WebPushSubscription).where(
                        WebPushSubscription.user_id == user_id
                    )
                )
            )
            .scalars()
            .all()
        )
        return list(subs), (prefs_row.notification_prefs or {})


async def _prune_subscription(sub_id: int) -> None:
    """Delete a subscription whose endpoint the push service reported gone."""
    try:
        async with get_db_session() as session:
            await session.execute(
                delete(WebPushSubscription).where(WebPushSubscription.id == sub_id)
            )
            await session.commit()
        logger.info("webpush: pruned dead subscription id=%s", sub_id)
    except Exception:
        logger.exception("webpush: failed to prune subscription id=%s", sub_id)


async def _touch_subscription(sub_id: int) -> None:
    """Best-effort last_used_at bump after a successful send."""
    try:
        async with get_db_session() as session:
            await session.execute(
                update(WebPushSubscription)
                .where(WebPushSubscription.id == sub_id)
                .values(last_used_at=utc_now())
            )
            await session.commit()
    except Exception:
        logger.debug("webpush: last_used_at bump failed id=%s", sub_id, exc_info=True)


def _send_one_sync(subscription_info: dict, payload: str) -> int:
    """Blocking pywebpush send. Returns HTTP-ish status: 0=ok, else status code.

    Runs in a worker thread (pywebpush is synchronous, requests-based). Returns
    the dead-endpoint status (404/410) so the caller can prune; raises nothing
    callers can't handle — other errors are surfaced as their status or -1.
    """
    from pywebpush import WebPushException, webpush

    try:
        webpush(
            subscription_info=subscription_info,
            data=payload,
            vapid_private_key=VAPID_PRIVATE_KEY,
            # Fresh dict each call — pywebpush mutates it (adds exp/aud).
            vapid_claims={"sub": VAPID_SUBJECT},
            timeout=15,
        )
        return 0
    except WebPushException as e:
        status = getattr(getattr(e, "response", None), "status_code", None)
        if status is not None:
            return int(status)
        logger.warning("webpush: send failed (no status): %s", e)
        return -1


async def push(
    user_id: int,
    category: str,
    text: str,
    *,
    url: Optional[str] = None,
    markdown: bool = False,  # accepted for signature parity; push renders plain
) -> int:
    """Send a Web Push notification to all of a user's devices.

    Returns the number of devices delivered to. Never raises.

    `markdown` is accepted so the dispatcher can call telegram + webpush with
    one signature, but push notifications render plain text — it's ignored here.
    `url` is the path opened when the user taps the notification (default "/").
    """
    if not text or not text.strip():
        return 0
    if not VAPID_PRIVATE_KEY or not VAPID_PUBLIC_KEY:
        logger.debug("webpush: VAPID keys not configured; skipping user=%s", user_id)
        return 0

    subs, prefs = await _load_subscriptions(user_id)
    if not subs:
        return 0
    if not _category_enabled(prefs, category):
        return 0
    if not _rate_check(user_id):
        logger.warning("webpush: rate-limited user=%s category=%s", user_id, category)
        return 0

    payload = json.dumps(
        {
            "title": _CATEGORY_TITLES.get(category, "Nifty Strategist"),
            "body": text.strip(),
            "url": url or "/",
            "tag": category,
        }
    )

    delivered = 0
    for sub in subs:
        subscription_info = {
            "endpoint": sub.endpoint,
            "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
        }
        try:
            status = await asyncio.to_thread(_send_one_sync, subscription_info, payload)
        except Exception:
            logger.exception("webpush: unexpected send error user=%s", user_id)
            continue

        if status == 0:
            delivered += 1
            await _touch_subscription(sub.id)
        elif status in (404, 410):
            await _prune_subscription(sub.id)
        else:
            logger.warning(
                "webpush: send failed user=%s sub=%s status=%s",
                user_id, sub.id, status,
            )

    return delivered
