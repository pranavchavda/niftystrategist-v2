"""Phase 2a: route inbound Telegram DMs into the user's daily mandate thread.

The Telegram command handlers (telegram_bot/handlers.py) stay thin; this module
owns the heavy lifting:

  1. Resolve the user and verify the chat is the one they confirmed (only the
     paired chat may chat — a stranger who knows the bot username must not be
     able to drive the orchestrator as the owner).
  2. get-or-create today's daily mandate thread (IST date — same thread the
     awakenings write to, so morning-awakening context is already present).
  3. Replay recent thread history.
  4. Run the orchestrator to completion with `agent.run()` (NOT stream_text —
     stream_text only captures the first model call and drops tool turns; same
     trap documented for awakenings).
  5. Persist the user turn + assistant reply back to the thread and bump
     updated_at so it surfaces in the web sidebar (cross-surface mirror).
  6. Return the reply text for the handler to send over Telegram.

`is_telegram=True` is set on OrchestratorDeps so the system prompt switches to a
mobile-friendly, read/analysis-only mode. Order placement is deferred to the web
UI until Phase 2b adds a Telegram-native approval gate.
"""

from __future__ import annotations

import asyncio
import logging
import re
import uuid
from datetime import timedelta
from typing import Awaitable, Callable, Optional

from sqlalchemy import select, update as sa_update

from database.models import (
    Conversation,
    Message,
    User as DBUser,
    utc_now,
)
from database.session import get_db_session
from services.thread_locks import thread_lock

logger = logging.getLogger(__name__)

# Keep replayed history bounded — matches the awakening loader.
_HISTORY_LIMIT = 50

# Ceiling for a single inbound turn. A stalled model must not hold the
# per-thread lock forever (it would block every later DM + any awakening on the
# same thread). Mirrors the awakening heavy-turn default.
_TURN_TIMEOUT_S = 300


async def _load_thread_messages(session, thread_id: str) -> list:
    """Replay up to the last _HISTORY_LIMIT messages as pydantic-ai history.

    System messages are skipped — they're injected via the system prompt, not
    replayed as turns.
    """
    from pydantic_ai.messages import (
        ModelRequest,
        ModelResponse,
        UserPromptPart,
        TextPart,
    )

    result = await session.execute(
        select(Message)
        .where(Message.conversation_id == thread_id)
        .order_by(Message.timestamp.desc())
        .limit(_HISTORY_LIMIT)
    )
    rows = list(reversed(result.scalars().all()))

    history: list = []
    for msg in rows:
        if msg.role == "user":
            history.append(ModelRequest(parts=[UserPromptPart(content=msg.content)]))
        elif msg.role == "assistant" and msg.content:
            history.append(ModelResponse(parts=[TextPart(msg.content)]))
    return history


async def _persist_turn(
    session, thread_id: str, user_text: str, assistant_text: str, is_voice: bool = False
) -> None:
    """Write the user message + assistant reply to the thread, bump updated_at.

    Tagged source=telegram so the web UI can badge the turn later. When the user
    spoke, the user message also carries voice=True (content is the transcript).
    """
    now = utc_now()

    user_meta = {"source": "telegram"}
    if is_voice:
        user_meta["voice"] = True

    user_msg = Message(
        conversation_id=thread_id,
        message_id=f"tg_user_{uuid.uuid4().hex}",
        role="user",
        content=user_text,
        timestamp=now,
        extra_metadata=user_meta,
    )
    session.add(user_msg)

    assistant_msg = Message(
        conversation_id=thread_id,
        message_id=f"tg_asst_{uuid.uuid4().hex}",
        role="assistant",
        content=assistant_text,
        # 1µs after the user msg to guarantee ordering on equal timestamps.
        timestamp=now + timedelta(microseconds=1),
        extra_metadata={"source": "telegram"},
    )
    session.add(assistant_msg)

    await session.execute(
        sa_update(Conversation)
        .where(Conversation.id == thread_id)
        .values(updated_at=now + timedelta(microseconds=2))
    )
    await session.commit()


# --- Live activity indicators (tool calls + reasoning) ----------------------
#
# The web chat streams tool-call pills and reasoning blocks so the user can see
# what the agent is actually doing (and catch a hallucinated answer that skipped
# the tools). Telegram runs `agent.run()` to completion, so we hook pydantic-ai's
# `event_stream_handler` to surface the same trail: each tool invocation and each
# reasoning turn is reported to an `on_activity(kind, detail)` callback the caller
# renders as a live-edited Telegram message.

# Activity callback: (kind, detail) -> awaitable. kind is "tool" or "thinking".
ActivityCallback = Callable[[str, str], Awaitable[None]]


def _clean_command(cmd: str) -> str:
    """Reduce an execute_bash command to the readable tool invocation.

    `python cli-tools/nf-quote RELIANCE` -> `nf-quote RELIANCE`. Keeps only the
    first line and strips the python/cli-tools wrapper so the indicator reads like
    the tool the agent ran.
    """
    if not cmd:
        return ""
    first = cmd.strip().splitlines()[0].strip()
    first = re.sub(r"^python3?\s+", "", first)
    first = re.sub(r"^(\./)?cli-tools/", "", first)
    return first


def _describe_tool_call(part) -> tuple[str, str]:
    """Map a pydantic-ai ToolCallPart to (kind, detail) for the indicator."""
    name = getattr(part, "tool_name", "") or "tool"
    try:
        args = part.args_as_dict()
    except Exception:
        args = {}

    if name == "execute_bash":
        return "tool", _clean_command(args.get("command") or "") or "command"
    if name == "call_agent":
        return "tool", (args.get("agent_name") or "agent").strip() or "agent"
    if name == "render_ui":
        return "tool", "preparing confirmation"
    return "tool", name.replace("_", " ")


def _build_event_handler(on_activity: ActivityCallback):
    """Return a pydantic-ai event_stream_handler that drives `on_activity`.

    Reports a tool invocation on each FunctionToolCallEvent (args are complete by
    then) and a reasoning turn on each ThinkingPart start. Bulletproof: any error
    is swallowed so a status-update failure can never abort the actual turn.
    """
    from pydantic_ai.messages import (
        FunctionToolCallEvent,
        PartStartEvent,
        ThinkingPart,
    )

    async def handler(ctx, event_stream) -> None:
        async for event in event_stream:
            try:
                if isinstance(event, FunctionToolCallEvent):
                    kind, detail = _describe_tool_call(event.part)
                    await on_activity(kind, detail)
                elif isinstance(event, PartStartEvent) and isinstance(
                    event.part, ThinkingPart
                ):
                    await on_activity("thinking", "")
            except Exception:
                logger.debug("telegram activity handler error", exc_info=True)

    return handler


async def run_telegram_turn(
    user_id: int,
    chat_id: int,
    text: str,
    is_voice: bool = False,
    on_activity: Optional[ActivityCallback] = None,
) -> str:
    """Process one inbound Telegram message; return the reply text.

    `text` is the message text, or the transcript when `is_voice=True` (the
    caller transcribes the voice note before calling). `is_voice` switches the
    orchestrator into spoken-friendly mode so the reply reads well aloud.

    Raises nothing the caller can't show — on internal failure returns a short
    user-facing error string. Returns "" only if the chat is unauthorized (the
    caller should stay silent in that case, handled separately).
    """
    text = (text or "").strip()
    if not text:
        return ""

    async with get_db_session() as session:
        user = (
            await session.execute(select(DBUser).where(DBUser.id == user_id))
        ).scalar_one_or_none()
        if user is None:
            logger.warning("telegram_chat: no user row for id=%s", user_id)
            return ""

        # Only the confirmed chat may drive the orchestrator. A stranger who
        # learned the bot username and DMs it must never run as the owner.
        if user.telegram_chat_id != chat_id:
            logger.info(
                "telegram_chat: unauthorized chat_id=%s for user=%s (paired=%s)",
                chat_id,
                user_id,
                user.telegram_chat_id,
            )
            return ""

        user_email = user.email
        mandate = user.trading_mandate

        # get-or-create today's daily mandate thread (IST date).
        from services.daily_thread import get_or_create_daily_thread

        thread_id = await get_or_create_daily_thread(
            session,
            user_id=user.id,
            user_email=user_email,
            mandate=mandate,
        )

        # Resolve live Upstox token (decrypt + expiry + TOTP refresh).
        from api.upstox_oauth import get_user_upstox_token

        upstox_token = await get_user_upstox_token(user.id)
        order_node_url = user.order_node_url
        trading_mode = user.trading_mode or "live"
        model_id = user.preferred_model
        user_name = getattr(user, "name", None)
        user_bio = getattr(user, "bio", None)  # not a column on User; safe default

    # Select model + orchestrator (registers sub-agents + user MCP toolsets).
    from config.models import DEFAULT_MODEL_ID
    from main import get_orchestrator_for_model, get_user_memories_for_context

    model_id = model_id or DEFAULT_MODEL_ID
    orchestrator = await get_orchestrator_for_model(model_id, user_id=user_id)

    # Context parity with the web chat path (main.py): same semantic-memory
    # injection + identity, so the agent behaves identically regardless of
    # surface. Only the transport (Telegram vs AG-UI SSE) differs.
    user_memories = await get_user_memories_for_context(
        user_email,
        current_message=text,
        limit=10,
        similarity_threshold=0.35,
    )

    from agents.orchestrator import OrchestratorDeps
    from models.state import ConversationState

    state = ConversationState(user_id=user_email, thread_id=thread_id)
    deps = OrchestratorDeps(
        state=state,
        available_agents=orchestrator.specialized_agents,
        user_memories=user_memories,
        user_name=user_name,
        user_bio=user_bio,
        upstox_access_token=upstox_token,
        order_node_url=order_node_url,
        user_id=user_id,
        trading_mode=trading_mode,
        is_telegram=True,  # mobile-friendly, read/analysis-only mode
        is_voice=is_voice,  # spoken-friendly reply when the user sent a voice note
    )

    # Serialize against a concurrent awakening on the same thread.
    async with thread_lock(thread_id):
        async with get_db_session() as session:
            history = await _load_thread_messages(session, thread_id)

        try:
            kwargs = {"deps": deps}
            if history:
                kwargs["message_history"] = history
            if on_activity is not None:
                kwargs["event_stream_handler"] = _build_event_handler(on_activity)
            run_result = await asyncio.wait_for(
                orchestrator.agent.run(text, **kwargs),
                timeout=_TURN_TIMEOUT_S,
            )
            reply = run_result.output or ""
        except asyncio.TimeoutError:
            logger.warning(
                "telegram_chat: turn timed out after %ss user=%s",
                _TURN_TIMEOUT_S,
                user_id,
            )
            return (
                "⏳ That took too long and I had to stop. Try a simpler question, "
                "or use the NS web app."
            )
        except Exception:
            logger.exception("telegram_chat: orchestrator run failed user=%s", user_id)
            return (
                "⚠️ Something went wrong handling that. Try again in a moment, "
                "or use the NS web app."
            )

        if not reply.strip():
            reply = "(no response)"

        async with get_db_session() as session:
            try:
                await _persist_turn(session, thread_id, text, reply, is_voice=is_voice)
            except Exception:
                logger.exception(
                    "telegram_chat: failed to persist turn thread=%s", thread_id
                )

    # Best-effort cross-thread embedding so this turn is searchable later.
    try:
        from services.thread_embedder import embed_thread_immediately

        await embed_thread_immediately(thread_id)
    except Exception:
        logger.debug("telegram_chat: embed skipped", exc_info=True)

    return reply
