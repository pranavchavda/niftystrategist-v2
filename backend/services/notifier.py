"""Outbound notification dispatcher — the channel-agnostic seam.

The single entry point every outbound notification flows through. Fans out to
each configured channel; each is independently best-effort and never raises.

Channels:
  - Telegram (services.telegram_notifier) — dormant while banned in India, but
    untouched and ready: no-ops for unpaired users, so it costs nothing here.
  - Web Push  (services.webpush_notifier) — native PWA notifications.

Both channels read the same `users.notification_prefs` map, so muting a
category mutes it everywhere. Callers pass one signature and don't know or
care which channels are live.

    from services.notifier import notify_user
    await notify_user(user_id, "monitor_fire", "ZEEL SL hit at 187.40")

See docs/plans/2026-06-19-web-push-notifications.md.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)


async def notify_user(
    user_id: int,
    category: str,
    text: str,
    *,
    markdown: bool = False,
    url: Optional[str] = None,
) -> dict:
    """Send a notification to a user across all configured channels.

    Args:
        user_id: NS user id.
        category: One of api.telegram.NOTIFICATION_CATEGORIES. Muting reuses
            `users.notification_prefs`.
        text: Message body. Keep short — it must survive a phone notification
            preview.
        markdown: Render as markdown where the channel supports it (Telegram).
            Ignored by plain-text channels (Web Push).
        url: Path opened when a Web Push notification is tapped (default "/").
            Telegram ignores it.

    Returns a per-channel delivery summary, e.g. {"telegram": True, "webpush": 2}.
    Never raises — channel failures are logged and swallowed.
    """
    async def _telegram() -> bool:
        try:
            from services.telegram_notifier import notify
            return await notify(
                user_id=user_id, category=category, text=text, markdown=markdown
            )
        except Exception:
            logger.exception("notifier: telegram channel raised user=%s", user_id)
            return False

    async def _webpush() -> int:
        try:
            from services.webpush_notifier import push
            return await push(
                user_id=user_id, category=category, text=text, url=url
            )
        except Exception:
            logger.exception("notifier: webpush channel raised user=%s", user_id)
            return 0

    tg_ok, wp_count = await asyncio.gather(_telegram(), _webpush())
    return {"telegram": tg_ok, "webpush": wp_count}
