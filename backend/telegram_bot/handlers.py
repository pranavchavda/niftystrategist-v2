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
from telegram.error import BadRequest
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
    "Once paired, just DM me anything — text or a voice note — and I'll answer as "
    "your NS agent in today's daily thread (positions, quotes, analysis, trade "
    "planning). Send a voice note and I'll reply with one too. You can place "
    "trades here: I'll show the order details and you reply YES to confirm. "
    "(Setting up monitor/entry rules still happens in the web app.)"
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


def _to_markdown_v2(text: str) -> str | None:
    """Convert agent markdown to escaped Telegram MarkdownV2.

    telegramify-markdown handles the ~18 chars MarkdownV2 requires escaped and
    renders tables/code as monospace blocks. Returns None if the lib is missing
    or conversion throws, so the caller falls back to plain text.
    """
    try:
        import telegramify_markdown

        return telegramify_markdown.markdownify(text)
    except Exception:
        logger.debug("telegramify-markdown conversion failed", exc_info=True)
        return None


async def _send_reply(message, text: str) -> None:
    """Send a reply, preferring MarkdownV2, always able to fall back to plain.

    Strategy:
    - Short replies (the common case on Telegram): convert the whole thing to
      MarkdownV2 and send as one message. On a Telegram BadRequest (escape edge
      case) re-send the ORIGINAL plain text — never the escaped version, which
      would leak backslashes.
    - Over-limit replies: skip MarkdownV2 entirely and send plain split chunks.
      Splitting escaped MarkdownV2 can cut a code fence (tables render as code
      blocks) and corrupt rendering, so we don't risk it for long messages.
    """
    md = _to_markdown_v2(text)
    if md is not None and len(md) <= _TG_MAX:
        try:
            await message.reply_text(md, parse_mode="MarkdownV2")
            return
        except BadRequest:
            logger.warning("MarkdownV2 send rejected; falling back to plain text")

    for chunk in _split_message(text):
        await message.reply_text(chunk)


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

    await _send_reply(update.effective_message, reply)


# Cap a single voice-note synthesis to the OpenAI TTS per-call limit. The full
# text is always sent as text too, so a long reply just gets a clipped voice.
_VOICE_TTS_CAP = 4096


async def _send_voice_reply(message, reply_text: str) -> None:
    """Synthesize `reply_text` and send it as a Telegram voice note.

    Sent AFTER the text reply so the voice bubble is the last message — it's the
    notification + landing message (Hermes-style voice-primary feel). Best-effort:
    on any synth/send failure we log and move on (the text already carried the
    content). Tries OGG/Opus as a true voice bubble first, falls back to an mp3
    audio attachment if Telegram rejects the voice payload.
    """
    import io

    from services import voice as voice_service

    spoken = reply_text.strip()
    if not spoken:
        return
    if len(spoken) > _VOICE_TTS_CAP:
        spoken = spoken[:_VOICE_TTS_CAP]

    try:
        await message.chat.send_action(ChatAction.RECORD_VOICE)
    except Exception:
        pass

    try:
        ogg = voice_service.synthesize_bytes(spoken, response_format="opus")
    except Exception:
        logger.exception("voice reply: TTS synthesis failed")
        return

    buf = io.BytesIO(ogg)
    buf.name = "reply.ogg"
    try:
        await message.reply_voice(voice=buf)
        return
    except Exception:
        logger.warning("voice reply: reply_voice failed, trying mp3 audio fallback")

    # Fallback: mp3 as an audio attachment (not a voice bubble, but plays).
    try:
        mp3 = voice_service.synthesize_bytes(spoken, response_format="mp3")
        mbuf = io.BytesIO(mp3)
        mbuf.name = "reply.mp3"
        await message.reply_audio(audio=mbuf, title="Nifty Strategist")
    except Exception:
        logger.exception("voice reply: mp3 audio fallback also failed")


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Voice note → transcribe → run the daily-thread turn → voice + text reply."""
    if not update.effective_chat or not update.effective_message:
        return
    if update.effective_chat.type != "private":
        return
    voice = update.effective_message.voice
    if voice is None:
        return

    chat_id = update.effective_chat.id
    user_id = _owning_user_id(context)

    # Auth gate BEFORE any download/STT cost. run_telegram_turn re-checks this,
    # but transcription bills OpenAI per call — a stranger who knows the bot
    # username must not be able to drain that by DMing voice notes. (The text
    # path has no pre-run cost, so it relies on run_telegram_turn's check.)
    async with get_db_session() as session:
        paired_chat_id = (
            await session.execute(
                select(DBUser.telegram_chat_id).where(DBUser.id == user_id)
            )
        ).scalar_one_or_none()
    if paired_chat_id != chat_id:
        logger.info(
            "handle_voice: unauthorized chat_id=%s for user=%s (paired=%s) — silent",
            chat_id, user_id, paired_chat_id,
        )
        return  # silent — same as run_telegram_turn does for unauthorized chats

    typing_task = asyncio.create_task(_keep_typing(context.bot, chat_id))
    try:
        from services import voice as voice_service
        from services.telegram_chat import run_telegram_turn

        # Download the OGG/Opus voice note. OpenAI transcription accepts it as-is.
        tg_file = await voice.get_file()
        audio_bytes = bytes(await tg_file.download_as_bytearray())
        transcript = voice_service.transcribe_bytes(audio_bytes, filename="voice.oga")

        if not transcript.strip():
            typing_task.cancel()
            await update.effective_message.reply_text(
                "🎙️ I couldn't make out any speech in that. Try again?"
            )
            return

        reply = await run_telegram_turn(user_id, chat_id, transcript, is_voice=True)
    except Exception:
        logger.exception("telegram handle_voice failed user=%s", user_id)
        reply = "⚠️ Something went wrong with that voice note. Try again, or use the NS web app."
    finally:
        typing_task.cancel()

    # Empty reply == unauthorized chat — stay silent (don't leak bot ownership).
    if not reply:
        return

    # Text first, then the voice note last (voice = the ping + landing message).
    await _send_reply(update.effective_message, reply)
    await _send_voice_reply(update.effective_message, reply)
