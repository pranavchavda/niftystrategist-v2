"""Per-user Telegram outbound notifier.

Process-agnostic: callable from FastAPI handlers, the monitor daemon, the
awakening scheduler, or any other process that imports the package. Uses
the Telegram Bot HTTP API directly via httpx — no python-telegram-bot
dependency here, so we stay decoupled from the inbound polling service.

Usage:

    from services.telegram_notifier import notify
    await notify(user_id, "monitor_fire", "ZEEL SL hit at 187.40")

Categories live in `api.telegram.NOTIFICATION_CATEGORIES`. Unknown / missing
keys in a user's `notification_prefs` are treated as enabled — opt-out
semantics. Failures are logged and swallowed; the notifier never raises.

See docs/plans/2026-05-20-telegram-integration.md.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from typing import Any, Optional

import httpx
from sqlalchemy import select

from database.models import User as DBUser
from database.session import get_db_session
from utils.encryption import decrypt_token

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org"

# Per-process shared httpx client. Lazy-initialised so importing this module
# never opens a connection on its own.
_client: Optional[httpx.AsyncClient] = None
_client_lock = asyncio.Lock()

# Per-user rate-limit window: max N sends per ROLLING_SECONDS. Conservative
# default — Telegram's hard limit is ~30 msg/sec/bot global, ~1/sec/chat. We
# care more about not spamming the user during a busy market session.
RATE_MAX = 60
ROLLING_SECONDS = 3600
_rate_windows: dict[int, deque[float]] = {}


async def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        async with _client_lock:
            if _client is None:
                _client = httpx.AsyncClient(
                    base_url=TELEGRAM_API_BASE,
                    timeout=15.0,
                )
    return _client


def _rate_check(user_id: int) -> bool:
    """Return True if the user is under the rate cap, otherwise False.

    Records a hit only when returning True so dropped notifications don't
    inflate the window. Cheap in-memory check; no persistence across restarts.
    """
    now = time.monotonic()
    window = _rate_windows.setdefault(user_id, deque())
    cutoff = now - ROLLING_SECONDS
    while window and window[0] < cutoff:
        window.popleft()
    if len(window) >= RATE_MAX:
        return False
    window.append(now)
    return True


async def _load_user_config(user_id: int) -> Optional[dict[str, Any]]:
    """Fetch decrypted token, chat_id, and prefs for a user.

    Returns None if the user is unpaired (no token or no chat_id), so the
    caller can short-circuit without sending.
    """
    async with get_db_session() as session:
        row = (
            await session.execute(
                select(
                    DBUser.telegram_bot_token,
                    DBUser.telegram_chat_id,
                    DBUser.notification_prefs,
                ).where(DBUser.id == user_id)
            )
        ).first()

    if not row:
        return None
    if not row.telegram_bot_token or not row.telegram_chat_id:
        return None

    token = decrypt_token(row.telegram_bot_token)
    if not token:
        logger.error(f"telegram_notifier: decrypt failed for user {user_id}")
        return None

    return {
        "token": token,
        "chat_id": row.telegram_chat_id,
        "prefs": row.notification_prefs or {},
    }


def _category_enabled(prefs: dict[str, Any], category: str) -> bool:
    """Missing keys default to enabled (opt-out semantics)."""
    value = prefs.get(category)
    if value is None:
        return True
    return bool(value)


def _to_markdown_v2(text: str) -> Optional[str]:
    """Convert agent markdown to escaped MarkdownV2; None if lib missing/throws."""
    try:
        import telegramify_markdown

        return telegramify_markdown.markdownify(text)
    except Exception:
        logger.debug("telegram_notifier: markdown conversion failed", exc_info=True)
        return None


async def notify(
    user_id: int,
    category: str,
    text: str,
    *,
    parse_mode: Optional[str] = None,
    markdown: bool = False,
    reply_markup: Optional[dict] = None,
    disable_notification: bool = False,
) -> bool:
    """Send a Telegram message to a user.

    Returns True on successful delivery, False otherwise. Never raises.

    `markdown=True` renders `text` as MarkdownV2 (for agent-authored sends like
    `message_user`); on a Telegram 400 it retries once with the ORIGINAL plain
    text so a bad escape never leaks backslashes or drops the message. Plain
    system notifications (TOTP / monitor fires) should leave it False.

    `reply_markup` is passed through as-is — pass a `InlineKeyboardMarkup`
    JSON dict here when you want approve/cancel buttons (Phase 2 trade flow).
    """
    if not text:
        return False

    config = await _load_user_config(user_id)
    if config is None:
        return False  # unpaired or decrypt failure

    if not _category_enabled(config["prefs"], category):
        return False

    if not _rate_check(user_id):
        logger.warning(
            f"telegram_notifier: rate-limited user {user_id} category={category}"
        )
        return False

    # When markdown=True, prefer a MarkdownV2 send with a plain-text fallback.
    send_text = text
    send_parse_mode = parse_mode
    if markdown:
        md = _to_markdown_v2(text)
        if md is not None:
            send_text = md
            send_parse_mode = "MarkdownV2"

    ok = await _send_once(
        config, category, user_id, send_text, send_parse_mode,
        reply_markup, disable_notification,
    )
    if ok or not markdown or send_parse_mode != "MarkdownV2":
        return ok

    # MarkdownV2 attempt failed (likely a 400 on a bad escape) — retry plain.
    logger.warning(
        "telegram_notifier: MarkdownV2 send failed user=%s; retrying plain", user_id
    )
    return await _send_once(
        config, category, user_id, text, parse_mode,
        reply_markup, disable_notification,
    )


async def _send_once(
    config: dict,
    category: str,
    user_id: int,
    text: str,
    parse_mode: Optional[str],
    reply_markup: Optional[dict],
    disable_notification: bool,
) -> bool:
    """One sendMessage attempt. Returns True only on a Telegram ok response."""
    payload: dict[str, Any] = {
        "chat_id": config["chat_id"],
        "text": text,
        "disable_notification": disable_notification,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode
    if reply_markup:
        payload["reply_markup"] = reply_markup

    client = await _get_client()
    url = f"/bot{config['token']}/sendMessage"
    try:
        resp = await client.post(url, json=payload)
    except httpx.RequestError as e:
        logger.warning(f"telegram_notifier: network error user={user_id} err={e}")
        return False

    if resp.status_code != 200:
        # 401 — token revoked. 403 — user blocked the bot. 400 — bad payload.
        # All are best-effort; log and move on.
        try:
            body = resp.json()
        except Exception:
            body = resp.text
        logger.warning(
            f"telegram_notifier: send failed user={user_id} "
            f"category={category} http={resp.status_code} body={body}"
        )
        return False

    body = resp.json()
    if not body.get("ok"):
        logger.warning(
            f"telegram_notifier: telegram not-ok user={user_id} body={body}"
        )
        return False

    return True


async def aclose() -> None:
    """Tear down the shared httpx client. Call from app shutdown hooks."""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
