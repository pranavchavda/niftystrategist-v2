"""Lifecycle manager for per-user Telegram Applications.

Runs inside the FastAPI event loop. On startup, scans the users table for any
user with a configured bot token and starts one python-telegram-bot
`Application` per user. Each Application gets its own update polling task
wrapped in a supervisor that restarts on failure.

API surface:

    await manager.start_all()
    await manager.stop_all()
    await manager.start_user_app(user_id)
    await manager.stop_user_app(user_id)
    await manager.reload_user_app(user_id)

The reload hook is called by the /api/telegram endpoints after the user adds
or removes a bot token via Settings.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from database.models import User as DBUser


def _is_disabled() -> bool:
    """True if NF_DISABLE_TELEGRAM_BOT is set — short-circuits all start/reload.

    Used in dev to avoid getUpdates conflicts with the prod backend that polls
    the same per-user bot tokens (Telegram allows only one poller per token).
    """
    return os.getenv("NF_DISABLE_TELEGRAM_BOT", "").lower() in ("1", "true", "yes")
from database.session import get_db_session
from utils.encryption import decrypt_token

from . import handlers

logger = logging.getLogger(__name__)


@dataclass
class _RunningApp:
    user_id: int
    application: Application
    supervisor_task: asyncio.Task


_apps: dict[int, _RunningApp] = {}
_lock = asyncio.Lock()


async def _load_token(user_id: int) -> Optional[str]:
    async with get_db_session() as session:
        row = (
            await session.execute(
                select(DBUser.telegram_bot_token).where(DBUser.id == user_id)
            )
        ).first()
    if not row or not row.telegram_bot_token:
        return None
    return decrypt_token(row.telegram_bot_token)


def _register_handlers(application: Application, user_id: int) -> None:
    """Attach Phase 1 command handlers, with user_id closed over via bot_data.

    Storing user_id on the Application means handlers never have to look it up
    by token at request time — they read it from `context.bot_data`.
    """
    application.bot_data["user_id"] = user_id
    application.add_handler(CommandHandler("start", handlers.cmd_start))
    application.add_handler(CommandHandler("confirm", handlers.cmd_confirm))
    application.add_handler(CommandHandler("unpair", handlers.cmd_unpair))
    application.add_handler(CommandHandler("status", handlers.cmd_status))
    application.add_handler(CommandHandler("help", handlers.cmd_help))
    # Phase 2a: any non-command text DM → daily mandate thread.
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.handle_message)
    )
    # Voice notes → transcribe → same daily-thread turn → voice + text reply.
    application.add_handler(
        MessageHandler(filters.VOICE, handlers.handle_voice)
    )


async def _run_application(application: Application, user_id: int) -> None:
    """Initialize, start polling, then sleep until cancelled.

    Caller is the supervisor task. When this coroutine returns (via cancel or
    a thrown exception), the supervisor decides whether to restart.
    """
    await application.initialize()
    await application.start()
    await application.updater.start_polling(
        drop_pending_updates=False,
        allowed_updates=None,  # default: messages + callbacks
    )
    logger.info(f"telegram_bot: polling started for user {user_id}")

    try:
        # Park forever — start_polling already spawned its own internal task.
        await asyncio.Event().wait()
    finally:
        try:
            await application.updater.stop()
        except Exception as e:
            logger.warning(f"telegram_bot: updater stop error user={user_id}: {e}")
        try:
            await application.stop()
        except Exception as e:
            logger.warning(f"telegram_bot: app stop error user={user_id}: {e}")
        try:
            await application.shutdown()
        except Exception as e:
            logger.warning(f"telegram_bot: shutdown error user={user_id}: {e}")
        logger.info(f"telegram_bot: stopped for user {user_id}")


async def _supervise(application: Application, user_id: int) -> None:
    """Run the application and restart with backoff on crash.

    Cancellation propagates up cleanly so stop_user_app can tear down
    deterministically.
    """
    backoff = 5.0
    while True:
        try:
            await _run_application(application, user_id)
            return  # clean exit
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(
                f"telegram_bot: application crashed for user {user_id} — "
                f"restarting in {backoff:.0f}s"
            )
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 300.0)


async def start_user_app(user_id: int) -> bool:
    """Start the Application for a single user.

    Returns True if started, False if no token configured or already running.
    """
    if _is_disabled():
        logger.debug(f"telegram_bot: disabled via env; skip user {user_id}")
        return False
    async with _lock:
        if user_id in _apps:
            logger.debug(f"telegram_bot: user {user_id} already running; skip")
            return False

        token = await _load_token(user_id)
        if not token:
            logger.debug(f"telegram_bot: no token for user {user_id}; skip")
            return False

        application = Application.builder().token(token).build()
        _register_handlers(application, user_id)

        task = asyncio.create_task(
            _supervise(application, user_id),
            name=f"telegram-app-{user_id}",
        )
        _apps[user_id] = _RunningApp(
            user_id=user_id, application=application, supervisor_task=task
        )

    return True


async def stop_user_app(user_id: int) -> bool:
    """Stop and remove the Application for a single user.

    Returns True if stopped, False if not running.
    """
    async with _lock:
        running = _apps.pop(user_id, None)

    if running is None:
        return False

    running.supervisor_task.cancel()
    try:
        await running.supervisor_task
    except asyncio.CancelledError:
        pass
    except Exception:
        logger.exception(f"telegram_bot: error while stopping user {user_id}")
    return True


async def reload_user_app(user_id: int) -> None:
    """Hot-restart the Application after a token change.

    Safe to call when no app is running — it will simply (re)start.
    """
    await stop_user_app(user_id)
    await start_user_app(user_id)


async def start_all() -> None:
    """Boot every user with a configured bot token."""
    async with get_db_session() as session:
        result = await session.execute(
            select(DBUser.id).where(DBUser.telegram_bot_token.is_not(None))
        )
        user_ids = [row.id for row in result]

    logger.info(f"telegram_bot: starting {len(user_ids)} user app(s)")
    for uid in user_ids:
        try:
            await start_user_app(uid)
        except Exception:
            logger.exception(f"telegram_bot: failed to start user {uid}")


async def stop_all() -> None:
    """Tear down every running Application."""
    async with _lock:
        user_ids = list(_apps.keys())

    for uid in user_ids:
        await stop_user_app(uid)


def list_running() -> list[int]:
    """Diagnostic: which user_ids have a live Application."""
    return list(_apps.keys())
