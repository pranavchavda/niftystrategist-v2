"""Telegram bot management API.

Each user creates their own bot via BotFather and pastes the token here.
The bot token is Fernet-encrypted at the application level. Pairing the chat_id
happens out-of-band when the user DMs their bot `/start` then `/confirm`
(handled by the telegram_bot service, not by this router).

See docs/plans/2026-05-20-telegram-integration.md.
"""

import logging
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from auth import get_current_user, User
from database.session import get_db_session
from database.models import User as DBUser
from utils.encryption import encrypt_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/telegram", tags=["telegram"])

TELEGRAM_API_BASE = "https://api.telegram.org"

# Notification categories — kept here so the Settings page and the notifier
# stay in sync on the keys. All default to enabled when missing from prefs.
NOTIFICATION_CATEGORIES = (
    "monitor_fire",
    "monitor_failure",
    "awakening",
    "order_fill",
    "system",
)


class BotTokenRequest(BaseModel):
    token: str


class NotificationPrefsRequest(BaseModel):
    prefs: dict


class TelegramStatusResponse(BaseModel):
    configured: bool
    paired: bool
    bot_username: Optional[str] = None
    chat_id: Optional[int] = None
    notification_prefs: dict = {}


async def _validate_bot_token(token: str) -> dict:
    """Call Telegram getMe to validate a bot token.

    Returns the bot's user object on success. Raises HTTPException on failure.
    """
    url = f"{TELEGRAM_API_BASE}/bot{token}/getMe"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
    except httpx.RequestError as e:
        logger.warning(f"Telegram getMe network error: {e}")
        raise HTTPException(status_code=502, detail="Could not reach Telegram API")

    if resp.status_code == 401:
        raise HTTPException(status_code=400, detail="Invalid bot token")
    if resp.status_code != 200:
        raise HTTPException(
            status_code=400,
            detail=f"Telegram rejected token: HTTP {resp.status_code}",
        )

    body = resp.json()
    if not body.get("ok") or not body.get("result"):
        raise HTTPException(status_code=400, detail="Telegram getMe returned not-ok")

    return body["result"]


async def _notify_telegram_service_reload(user_id: int) -> None:
    """Hot-reload the per-user Telegram Application after token change."""
    try:
        from telegram_bot import manager
    except ImportError:
        logger.debug("telegram_bot package missing; skip reload")
        return

    try:
        await manager.reload_user_app(user_id)
    except Exception:
        logger.exception(f"telegram_bot reload failed for user {user_id}")


@router.post("/bot-token")
async def save_bot_token(
    request: BotTokenRequest,
    user: User = Depends(get_current_user),
):
    """Validate and store a per-user Telegram bot token.

    Validates by calling Telegram's getMe. On success: stores Fernet-encrypted
    token + bot username, clears any previous chat_id binding (a new token =
    a new bot = old chat_id is meaningless), and asks the telegram service to
    reload the user's Application.
    """
    token = request.token.strip()
    if not token:
        raise HTTPException(status_code=400, detail="Token is required")

    bot_info = await _validate_bot_token(token)
    bot_username = bot_info.get("username")
    if not bot_username:
        raise HTTPException(status_code=400, detail="Bot has no username")

    async with get_db_session() as session:
        result = await session.execute(select(DBUser).where(DBUser.id == user.id))
        db_user = result.scalar_one_or_none()
        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")

        db_user.telegram_bot_token = encrypt_token(token)
        db_user.telegram_bot_username = bot_username
        # New bot — drop any prior chat binding; user must re-/start their new bot.
        db_user.telegram_chat_id = None
        db_user.telegram_pending_chat_id = None
        db_user.telegram_paired_at = None
        await session.commit()

    logger.info(f"Saved Telegram bot @{bot_username} for user {user.id}")
    await _notify_telegram_service_reload(user.id)

    return {
        "status": "success",
        "bot_username": bot_username,
        "next_step": f"DM your bot at https://t.me/{bot_username} with /start",
    }


@router.delete("/bot-token")
async def delete_bot_token(user: User = Depends(get_current_user)):
    """Unpair: clear bot token, username, and chat_id."""
    async with get_db_session() as session:
        result = await session.execute(select(DBUser).where(DBUser.id == user.id))
        db_user = result.scalar_one_or_none()
        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")

        db_user.telegram_bot_token = None
        db_user.telegram_bot_username = None
        db_user.telegram_chat_id = None
        db_user.telegram_pending_chat_id = None
        db_user.telegram_paired_at = None
        await session.commit()

    logger.info(f"Cleared Telegram bot for user {user.id}")
    await _notify_telegram_service_reload(user.id)

    return {"status": "success"}


@router.get("/status", response_model=TelegramStatusResponse)
async def get_status(user: User = Depends(get_current_user)):
    """Return whether the user has a bot configured and a chat paired.

    Never returns the token itself.
    """
    async with get_db_session() as session:
        result = await session.execute(
            select(
                DBUser.telegram_bot_token,
                DBUser.telegram_bot_username,
                DBUser.telegram_chat_id,
                DBUser.notification_prefs,
            ).where(DBUser.id == user.id)
        )
        row = result.first()

    if not row:
        raise HTTPException(status_code=404, detail="User not found")

    return TelegramStatusResponse(
        configured=bool(row.telegram_bot_token),
        paired=bool(row.telegram_chat_id),
        bot_username=row.telegram_bot_username,
        chat_id=row.telegram_chat_id,
        notification_prefs=row.notification_prefs or {},
    )


@router.put("/notification-prefs")
async def update_notification_prefs(
    request: NotificationPrefsRequest,
    user: User = Depends(get_current_user),
):
    """Replace the user's notification preferences map.

    Expected shape: {category: bool}. Unknown categories are kept (forward-compat)
    but the Settings UI should only present keys from NOTIFICATION_CATEGORIES.
    Missing keys are treated as enabled by the notifier.
    """
    prefs = request.prefs
    if not isinstance(prefs, dict):
        raise HTTPException(status_code=400, detail="prefs must be an object")

    # Coerce values to bool; reject non-bool-coercible inputs.
    cleaned: dict[str, bool] = {}
    for key, value in prefs.items():
        if not isinstance(key, str):
            raise HTTPException(status_code=400, detail="prefs keys must be strings")
        cleaned[key] = bool(value)

    async with get_db_session() as session:
        result = await session.execute(select(DBUser).where(DBUser.id == user.id))
        db_user = result.scalar_one_or_none()
        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")

        db_user.notification_prefs = cleaned
        await session.commit()

    return {"status": "success", "notification_prefs": cleaned}
