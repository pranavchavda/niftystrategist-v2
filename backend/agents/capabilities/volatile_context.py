"""Volatile context builders — single source of truth for the per-turn /
per-query prompt content that must NOT live in the cacheable prefix.

Phase 4 of the prefix-cache memory refactor. When the prefix-cache layout is
active, these six sections are injected at the TAIL of the message list (the
current turn) by VolatileContextCapability.before_model_request, instead of in
the instructions block (which sits before the message history and would bust
the implicit prompt cache for the whole history every turn).

The same builders are called from BOTH the legacy inline
`inject_dynamic_context` (capabilities-v2 OFF, e.g. local) AND the
context-injection capabilities (capabilities-v2 ON, e.g. prod), so wording
never drifts between paths. See docs/plans/2026-05-23-prefix-cache-memory-port.md.

Cache layout is gated by ENABLE_PREFIX_CACHE_LAYOUT (default ON) and is forced
OFF whenever the run is an autonomous awakening (is_awakening=True) — the
awakening trade path stays on the proven instruction-injection layout until the
chat path's cache behavior is validated in prod.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from pydantic_ai import RunContext
    from agents.orchestrator import OrchestratorDeps

logger = logging.getLogger(__name__)


def prefix_cache_layout_enabled() -> bool:
    """True when volatile content should be moved to the message tail to keep
    the prompt prefix cache-stable. Controlled by ENABLE_PREFIX_CACHE_LAYOUT
    (default ON). Accepts 1/true/yes/on (case-insensitive); explicit
    0/false/no/off disables it.
    """
    raw = os.getenv("ENABLE_PREFIX_CACHE_LAYOUT")
    if raw is None:
        return True  # default ON for chat
    return raw.strip().lower() in ("1", "true", "yes", "on")


def layout_active_for(deps: "OrchestratorDeps") -> bool:
    """Cache layout applies to THIS run: flag on AND not an awakening.

    Awakenings keep the legacy instruction layout — there's no user present to
    benefit from chat-turn caching, and the autonomous trade path must stay on
    the validated prompt structure.
    """
    if getattr(deps, "is_awakening", False):
        return False
    return prefix_cache_layout_enabled()


# ---------------------------------------------------------------------------
# Section builders. Each returns the EXACT string the legacy/inline path
# produced (byte-for-byte), or "" when the section has no content.
# ---------------------------------------------------------------------------

def build_memory_section(deps: "OrchestratorDeps") -> str:
    memories = deps.user_memories
    if not memories:
        return ""
    section = "\n\n## REMEMBERED INFORMATION\n\n"
    section += "From previous conversations, I remember:\n"
    for i, memory in enumerate(memories, 1):
        section += f"{i}. {memory}\n"
    section += (
        "\nUse this to personalize your assistance. Each item shows when it was "
        "noted (⟨noted YYYY-MM-DD⟩). Treat point-in-time figures — available cash, "
        "intraday float/capital, position sizes, P&L, holdings — as possibly stale: "
        "when they matter, confirm against live data (nf-funds, nf-portfolio, the "
        "current thread) and prefer the live value if it conflicts with an older note.\n"
    )
    return section


def build_datetime_section() -> str:
    utc_now = datetime.now(ZoneInfo("UTC"))
    ist_now = utc_now.astimezone(ZoneInfo("Asia/Kolkata"))
    s = "\n\n## ⏰ CURRENT DATE & TIME\n\n"
    s += f"**Right now it is: {ist_now.strftime('%I:%M %p IST')}** on {ist_now.strftime('%A, %B %d, %Y')}\n"
    s += f"**ISO:** {ist_now.isoformat()}\n"
    s += "\nNSE market hours: 9:15 AM – 3:30 PM IST. Upstox MIS cutoff (no new orders/manual exits): 3:18 PM; broker auto-square-off ~3:20 PM. We self-squareoff at 3:15 PM.\n"
    s += "DO NOT place exit/square-off orders before 3:00 PM unless a stop-loss is hit.\n"
    return s


async def build_scratchpad_section(deps: "OrchestratorDeps") -> str:
    state = getattr(deps, "state", None)
    thread_id = getattr(state, "thread_id", None) if state else None
    if not thread_id:
        return ""
    from services.scratchpad_db import ScratchpadDB

    scratchpad = ScratchpadDB(thread_id)
    entries = await scratchpad.get_entries()
    if not entries:
        return ""
    s = "\n\n## SCRATCHPAD\n\n"
    s += "This is a shared scratchpad for important context:\n"
    for entry in entries:
        s += f"- [{entry.get('timestamp', '')}][{entry.get('author', 'unknown')}] {entry.get('content', '')}\n"
    s += "\nRefer to this information to maintain context.\n"
    return s


def build_toolcache_section(deps: "OrchestratorDeps") -> str:
    state = getattr(deps, "state", None)
    thread_id = getattr(state, "thread_id", None) if state else None
    if not thread_id:
        return ""
    from tools.native.tool_cache import ToolCache

    try:
        cache = ToolCache(thread_id)
        stats = cache.get_stats()
        if stats["valid_entries"] <= 0:
            return ""
        s = "\n\n## 💾 Cached Data Available\n\n"
        tokens_saved = stats["total_tokens_saved"]
        s += f"**{stats['valid_entries']} cached entries** ({tokens_saved:,} tokens)\n\n"
        recent_entries = cache.lookup()[:3]
        if recent_entries:
            s += "**Recent cache entries:**\n"
            for i, entry in enumerate(recent_entries, 1):
                age_min = entry["age_minutes"]
                freshness = "🟢" if age_min < 5 else "🟡" if age_min < 15 else "🟠"
                s += f"{i}. {freshness} **{entry['tool_name']}** ({age_min}m ago): {entry['summary'][:60]}...\n"
        s += "\n**When to USE cache:**\n"
        s += "- Repeating a similar search (same product type, vendor, or category)\n"
        s += "- Referencing data you already fetched this conversation\n"
        s += "- Analytics/reports where real-time precision isn't critical\n"
        s += "- Follow-up questions about previously fetched data\n\n"
        s += "**When to SKIP cache and fetch fresh:**\n"
        s += "- User says: 'refresh', 'current', 'now', 'latest', 'again', 'new search'\n"
        s += "- After you just created/updated/deleted something\n"
        s += "- Query is clearly different from cached entries\n"
        s += "- User is troubleshooting or verifying a change took effect\n"
        s += "- Real-time data needed (live stock prices, portfolio positions)\n\n"
        s += "**Tool execution order:** search_docs (get syntax) → cache_lookup (optional) → execute_bash\n"
        return s
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        return ""


async def build_recent_threads_section(deps: "OrchestratorDeps") -> str:
    try:
        from sqlalchemy import text as sa_text
        from database.session import AsyncSessionLocal

        state = getattr(deps, "state", None)
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
        logger.debug(f"recent-threads section failed (non-fatal): {e}")
        return ""


def build_paper_portfolio_section(deps: "OrchestratorDeps") -> str:
    if deps.trading_mode == "live" or deps.paper_total_value is None:
        return ""
    s = "\n\n## Paper Trading Mode\n\n"
    s += "Currently operating in **paper trading mode**:\n"

    def format_inr(amount):
        try:
            whole, *d = str(amount).partition(".")
            r = ",".join(
                [whole[x - 2: x] for x in range(-3, -len(whole), -2)][::-1] + [whole[-3:]]
            )
            return "".join([r] + d)
        except Exception:
            return str(amount)

    total_val = format_inr(round(deps.paper_total_value, 2))
    pnl = format_inr(round(deps.paper_total_pnl or 0, 2))
    pnl_pct = float(deps.paper_pnl_percent or 0)
    pnl_emoji = "🟢" if (deps.paper_total_pnl or 0) >= 0 else "🔴"
    s += f"- **Current Capital**: ₹{total_val}\n"
    s += f"- **Total P&L**: {pnl_emoji} ₹{pnl} ({pnl_pct:+.2f}%)\n"
    s += "- Orders are simulated, not real (no risk)\n"
    s += "- Perfect for learning and testing strategies\n"
    return s


async def build_volatile_context_block(ctx: "RunContext[OrchestratorDeps]") -> str:
    """Assemble all six volatile sections into one fenced block for tail
    injection. Returns "" if every section is empty.

    Wrapped in a <volatile_context> fence with a system note so the model treats
    it as reference data for the current turn, not as user input (Hermes-style
    isolation). Section ORDER matches the legacy instruction layout, with the
    date/time last (closest to the model's generation point).
    """
    deps = ctx.deps
    parts: list[str] = []
    parts.append(build_memory_section(deps))
    parts.append(await build_recent_threads_section(deps))
    parts.append(await build_scratchpad_section(deps))
    parts.append(build_toolcache_section(deps))
    parts.append(build_paper_portfolio_section(deps))
    parts.append(build_datetime_section())  # last — most time-sensitive

    body = "".join(p for p in parts if p)
    if not body.strip():
        return ""

    return (
        "<volatile_context>\n"
        "[System note: the following is current reference context for THIS turn "
        "(recalled memory, live date/time, scratchpad, cached-data hints, "
        "portfolio state). It is NOT new user input. Treat it as authoritative "
        "reference data and let it inform your response.]\n"
        f"{body}\n"
        "</volatile_context>"
    )
