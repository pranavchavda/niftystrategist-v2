"""Command handlers for per-user Telegram Applications.

The user_id this Application belongs to is stored at construction time in
`context.bot_data['user_id']`, so handlers never need to look up which user
owns the incoming token.

Phase 1 surface: /start, /confirm, /unpair, /status, /help. Phase 2 will add
arbitrary-text routing into the daily mandate thread.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from sqlalchemy import select
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from database.models import User as DBUser
from database.session import get_db_session

logger = logging.getLogger(__name__)

# Telegram hard-caps a message at 4096 chars; stay under it with headroom.
_TG_MAX = 4000


HELP_TEXT = (
    "Nifty Strategist bot commands:\n"
    "  /start   — begin pairing this chat with your NS account\n"
    "  /confirm — confirm pairing after /start\n"
    "  /unpair  — disconnect this chat from NS\n"
    "  /status  — show pairing state\n"
    "  /help    — this message\n\n"
    "Once paired, just DM me anything — I'll answer as your NS agent in today's "
    "daily thread (positions, quotes, analysis, trade planning). Order placement "
    "still happens in the web app for now."
)


def _owning_user_id(context: ContextTypes.DEFAULT_TYPE) -> int:
    return int(context.bot_data["user_id"])


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Begin pairing. Records the incoming chat_id as pending; user must /confirm."""
    if not update.effective_chat or not update.effective_message:
        return

    chat_id = update.effective_chat.id
    user_id = _owning_user_id(context)

    async with get_db_session() as session:
        row = (
            await session.execute(select(DBUser).where(DBUser.id == user_id))
        ).scalar_one_or_none()
        if row is None:
            await update.effective_message.reply_text(
                "Account not found. Re-add your bot token via NS Settings."
            )
            return

        if row.telegram_chat_id == chat_id:
            await update.effective_message.reply_text(
                "This chat is already paired with your NS account."
            )
            return

        if row.telegram_chat_id is not None and row.telegram_chat_id != chat_id:
            await update.effective_message.reply_text(
                "Your NS account is already paired with a different chat. "
                "Unpair via NS Settings, or run /unpair in the other chat first."
            )
            return

        row.telegram_pending_chat_id = chat_id
        await session.commit()

    await update.effective_message.reply_text(
        "Send /confirm in this chat to lock the pairing.\n\n"
        "This extra step protects against someone else binding their chat "
        "to your bot."
    )


async def cmd_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Promote the pending chat_id to the active binding."""
    if not update.effective_chat or not update.effective_message:
        return

    chat_id = update.effective_chat.id
    user_id = _owning_user_id(context)

    async with get_db_session() as session:
        row = (
            await session.execute(select(DBUser).where(DBUser.id == user_id))
        ).scalar_one_or_none()
        if row is None:
            await update.effective_message.reply_text(
                "Account not found. Re-add your bot token via NS Settings."
            )
            return

        if row.telegram_chat_id == chat_id:
            await update.effective_message.reply_text("Already paired. Nothing to do.")
            return

        if row.telegram_pending_chat_id != chat_id:
            await update.effective_message.reply_text(
                "No pending pairing for this chat. Send /start first."
            )
            return

        row.telegram_chat_id = chat_id
        row.telegram_pending_chat_id = None
        row.telegram_paired_at = datetime.utcnow()
        await session.commit()

    logger.info(f"telegram_bot: paired user {user_id} to chat {chat_id}")
    await update.effective_message.reply_text(
        "Paired. NS will start sending notifications here.\n"
        "Use /status to check state; /unpair to disconnect."
    )


async def cmd_unpair(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Disconnect this chat from the NS user."""
    if not update.effective_chat or not update.effective_message:
        return

    chat_id = update.effective_chat.id
    user_id = _owning_user_id(context)

    async with get_db_session() as session:
        row = (
            await session.execute(select(DBUser).where(DBUser.id == user_id))
        ).scalar_one_or_none()
        if row is None:
            return

        # Only let the currently-paired chat (or a pending one) unpair, so a
        # random chat that happens to know the bot can't undo someone else's
        # pairing.
        if row.telegram_chat_id != chat_id and row.telegram_pending_chat_id != chat_id:
            await update.effective_message.reply_text(
                "This chat is not paired with the NS account."
            )
            return

        row.telegram_chat_id = None
        row.telegram_pending_chat_id = None
        row.telegram_paired_at = None
        await session.commit()

    logger.info(f"telegram_bot: unpaired user {user_id} from chat {chat_id}")
    await update.effective_message.reply_text(
        "Unpaired. Notifications stopped. Re-pair anytime with /start."
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat or not update.effective_message:
        return

    chat_id = update.effective_chat.id
    user_id = _owning_user_id(context)

    async with get_db_session() as session:
        row = (
            await session.execute(
                select(
                    DBUser.telegram_chat_id,
                    DBUser.telegram_pending_chat_id,
                    DBUser.telegram_paired_at,
                ).where(DBUser.id == user_id)
            )
        ).first()
        if row is None:
            await update.effective_message.reply_text("Account not found.")
            return

    if row.telegram_chat_id == chat_id:
        when = (
            row.telegram_paired_at.strftime("%Y-%m-%d %H:%M UTC")
            if row.telegram_paired_at
            else "unknown"
        )
        await update.effective_message.reply_text(f"Paired since {when}.")
    elif row.telegram_pending_chat_id == chat_id:
        await update.effective_message.reply_text(
            "Pairing pending. Send /confirm to lock it."
        )
    elif row.telegram_chat_id is not None:
        await update.effective_message.reply_text(
            "Your NS account is paired with a different chat."
        )
    else:
        await update.effective_message.reply_text(
            "Not paired. Send /start to begin."
        )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message:
        await update.effective_message.reply_text(HELP_TEXT)


def _split_message(text: str, limit: int = _TG_MAX) -> list[str]:
    """Split a long reply into <=limit chunks, preferring newline boundaries."""
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    remaining = text
    while len(remaining) > limit:
        cut = remaining.rfind("\n", 0, limit)
        if cut <= 0:
            cut = limit
        chunks.append(remaining[:cut])
        remaining = remaining[cut:].lstrip("\n")
    if remaining:
        chunks.append(remaining)
    return chunks


async def _keep_typing(bot, chat_id: int) -> None:
    """Re-send the 'typing…' chat action every 4s until cancelled.

    A single send_chat_action lasts ~5s; orchestrator turns can take far longer,
    so loop it for the lifetime of the run.
    """
    try:
        while True:
            try:
                await bot.send_chat_action(chat_id, ChatAction.TYPING)
            except Exception:
                pass
            await asyncio.sleep(4)
    except asyncio.CancelledError:
        pass


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Phase 2a: route a plain-text DM into the user's daily mandate thread."""
    if not update.effective_chat or not update.effective_message:
        return
    # Only private chats. If the bot is added to a group, never act there —
    # it would reply as the owner to whatever anyone in the group asks.
    if update.effective_chat.type != "private":
        return
    text = update.effective_message.text
    if not text or not text.strip():
        return

    chat_id = update.effective_chat.id
    user_id = _owning_user_id(context)

    typing_task = asyncio.create_task(_keep_typing(context.bot, chat_id))
    try:
        from services.telegram_chat import run_telegram_turn

        reply = await run_telegram_turn(user_id, chat_id, text)
    except Exception:
        logger.exception("telegram handle_message failed user=%s", user_id)
        reply = "⚠️ Something went wrong. Try again, or use the NS web app."
    finally:
        typing_task.cancel()

    # Empty reply == unauthorized chat (not the paired one) or empty input —
    # stay silent rather than leaking that this bot belongs to someone.
    if not reply:
        return

    for chunk in _split_message(reply):
        await update.effective_message.reply_text(chunk)
