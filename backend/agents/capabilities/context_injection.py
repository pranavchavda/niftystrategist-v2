"""Context-injection capabilities migrated from the orchestrator's
`_register_dynamic_instructions()` block.

Each capability's `get_instructions()` returns a RunContext-aware builder.
Pydantic AI merges all capability instructions into the agent's system prompt
at run time.

The emitted strings preserve **exact wording** from the original dynamic
instruction blocks so prompt-cache behavior and model responses stay identical
across the cutover. These capabilities are gated behind ENABLE_CAPABILITIES_V2
(see `agents.capabilities.capabilities_v2_enabled`); when the flag is off the
orchestrator's legacy inline path runs instead.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Callable
from zoneinfo import ZoneInfo

from pydantic_ai import RunContext
from pydantic_ai.capabilities.abstract import AbstractCapability

if TYPE_CHECKING:
    from agents.orchestrator import OrchestratorDeps

logger = logging.getLogger(__name__)


@dataclass
class MemoryCapability(AbstractCapability["OrchestratorDeps"]):
    """Inject user memories pre-loaded via pgvector semantic search.

    Wording is byte-for-byte identical to the legacy `## REMEMBERED
    INFORMATION` block in `_register_dynamic_instructions()`.
    """

    def get_instructions(self) -> Callable[[RunContext["OrchestratorDeps"]], str]:
        def build(ctx: RunContext["OrchestratorDeps"]) -> str:
            memories = ctx.deps.user_memories
            if not memories:
                return ""
            section = "\n\n## REMEMBERED INFORMATION\n\n"
            section += "From previous conversations, I remember:\n"
            for i, memory in enumerate(memories, 1):
                section += f"{i}. {memory}\n"
            section += (
                "\nUse this information to provide personalized assistance.\n"
            )
            return section

        return build


@dataclass
class RecentThreadsCapability(AbstractCapability["OrchestratorDeps"]):
    """Inject recent thread titles for cross-thread awareness.

    Owns its own DB fetch (same query the legacy inline block ran), so no
    `main.py` deps-preload change is needed. Wording is byte-for-byte
    identical to the legacy `## RECENT CONVERSATION THREADS` block.
    """

    def get_instructions(self) -> Callable[[RunContext["OrchestratorDeps"]], str]:
        async def build(ctx: RunContext["OrchestratorDeps"]) -> str:
            try:
                from sqlalchemy import text as sa_text
                from database.session import AsyncSessionLocal

                state = ctx.deps.state
                if not state:
                    return ""
                user_email = state.user_id
                current_thread = state.thread_id

                async with AsyncSessionLocal() as _db:
                    _result = await _db.execute(sa_text(
                        "SELECT c.id, c.title, "
                        "  (SELECT MAX(m.timestamp) FROM messages m WHERE m.conversation_id = c.id) AS last_message_at "
                        "FROM conversations c "
                        "WHERE c.user_id = :user_id AND c.id != :current_thread "
                        "AND c.is_archived = false AND c.title IS NOT NULL "
                        "ORDER BY last_message_at DESC NULLS LAST LIMIT 15"
                    ), {"user_id": user_email, "current_thread": current_thread})
                    recent_threads = _result.fetchall()

                if not recent_threads:
                    return ""

                now_naive = datetime.now(ZoneInfo("UTC")).replace(tzinfo=None)
                thread_section = "\n\n## RECENT CONVERSATION THREADS\n\n"
                thread_section += 'Use `python cli-tools/nf-threads search "query" --json` to find context from past conversations.\n\n'
                for t_id, t_title, t_updated in recent_threads:
                    if t_updated:
                        ts = t_updated if t_updated.tzinfo is None else t_updated.replace(tzinfo=None)
                        delta = now_naive - ts
                        if delta.days == 0:
                            age = "today"
                        elif delta.days == 1:
                            age = "yesterday"
                        else:
                            age = f"{delta.days}d ago"
                    else:
                        age = ""
                    thread_section += f"- \"{t_title}\" ({age})\n"
                return thread_section
            except Exception as e:
                logger.debug(f"RecentThreadsCapability injection failed (non-fatal): {e}")
                return ""

        return build


@dataclass
class DateTimeCapability(AbstractCapability["OrchestratorDeps"]):
    """Inject the current IST date/time + NSE market-hours reminder.

    MUST be registered LAST among instruction-emitting capabilities so the
    date/time section stays at the bottom of the system prompt — closest to
    the conversation history (needle-in-haystack attention). Capability
    instructions concatenate in capability-list order, with no repositioning
    API, so list position is the only ordering knob.

    Wording is byte-for-byte identical to the legacy `## ⏰ CURRENT DATE &
    TIME` block in `_register_dynamic_instructions()`.
    """

    def get_instructions(self) -> Callable[[RunContext["OrchestratorDeps"]], str]:
        def build(ctx: RunContext["OrchestratorDeps"]) -> str:
            utc_now = datetime.now(ZoneInfo("UTC"))
            ist_now = utc_now.astimezone(ZoneInfo("Asia/Kolkata"))

            date_section = "\n\n## ⏰ CURRENT DATE & TIME\n\n"
            date_section += f"**Right now it is: {ist_now.strftime('%I:%M %p IST')}** on {ist_now.strftime('%A, %B %d, %Y')}\n"
            date_section += f"**ISO:** {ist_now.isoformat()}\n"
            date_section += "\nNSE market hours: 9:15 AM – 3:30 PM IST. Broker auto-square-off: 3:15–3:25 PM IST.\n"
            date_section += "DO NOT place exit/square-off orders before 3:00 PM unless a stop-loss is hit.\n"
            return date_section

        return build
