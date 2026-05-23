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
            from agents.capabilities.volatile_context import (
                layout_active_for, build_memory_section,
            )
            # Under prefix-cache layout this moves to the message tail
            # (VolatileContextCapability) — suppress here to avoid double-inject.
            if layout_active_for(ctx.deps):
                return ""
            return build_memory_section(ctx.deps)

        return build


_VOLATILE_SENTINEL = "<volatile_context>"


@dataclass
class VolatileContextCapability(AbstractCapability["OrchestratorDeps"]):
    """Phase 4: inject volatile per-turn context at the TAIL of the message list
    (current turn) instead of in the instructions block, so the prompt prefix
    stays byte-stable and the implicit prompt cache hits on the whole history.

    Active only when ENABLE_PREFIX_CACHE_LAYOUT is on AND the run is not an
    autonomous awakening. When active, the six volatile sections (memory recall,
    recent threads, scratchpad, tool-cache, paper portfolio, date/time) are
    suppressed from the instructions path (legacy inline + the other
    capabilities) and emitted here at the tail instead. When inactive, this hook
    no-ops and the instruction path runs unchanged.

    Idempotent: a `<volatile_context>` sentinel guards against injecting more
    than one block per model request across the tool loop.
    See docs/plans/2026-05-23-prefix-cache-memory-port.md.
    """

    async def before_model_request(self, ctx: RunContext["OrchestratorDeps"], request_context):
        from agents.capabilities.volatile_context import (
            layout_active_for,
            build_volatile_context_block,
        )

        if not layout_active_for(ctx.deps):
            return request_context

        messages = request_context.messages
        # Skip if a volatile block is already present (exactly-once per request).
        for msg in messages:
            for part in getattr(msg, "parts", []) or []:
                content = getattr(part, "content", None)
                if isinstance(content, str) and _VOLATILE_SENTINEL in content:
                    return request_context

        block = await build_volatile_context_block(ctx)
        if not block:
            return request_context

        from pydantic_ai.messages import ModelRequest, UserPromptPart

        request_context.messages.append(
            ModelRequest(parts=[UserPromptPart(content=block)])
        )
        logger.debug("[prefix-cache] injected volatile context block at message tail")
        return request_context

    async def after_model_request(self, ctx: RunContext["OrchestratorDeps"], *, request_context, response):
        """Validation gate: log provider cache usage so we can confirm the layout
        actually pays off. On turn 2+ of a thread, cache_read should be > 0 when
        the prefix is stable. Observe-only; never mutates the response.
        """
        try:
            from agents.capabilities.volatile_context import layout_active_for
            usage = getattr(response, "usage", None)
            if usage is not None:
                logger.info(
                    "[prefix-cache] usage: input=%s cache_read=%s cache_write=%s output=%s (layout=%s)",
                    getattr(usage, "input_tokens", None),
                    getattr(usage, "cache_read_tokens", None),
                    getattr(usage, "cache_write_tokens", None),
                    getattr(usage, "output_tokens", None),
                    layout_active_for(ctx.deps),
                )
        except Exception:
            pass
        return response


@dataclass
class UserProfileCapability(AbstractCapability["OrchestratorDeps"]):
    """Inject the auto-synthesized, curated user profile.

    Unlike MemoryCapability (per-query semantic recall, volatile), this is the
    FROZEN profile: it changes only when the nightly synthesis job re-runs, so
    it is byte-stable across every turn within a session. That stability is
    deliberate — it keeps it inside the cacheable prompt prefix (Hermes-style).

    Ported from EspressoBot. Source: `jobs/memory_profile.py` synthesizes
    `user_profiles.profile_text`; `main.py` preloads it into
    `deps.user_profile`. Keep this wording stable: drift breaks the prefix cache
    for everything after it. See docs/plans/2026-05-23-prefix-cache-memory-port.md.
    """

    def get_instructions(self) -> Callable[[RunContext["OrchestratorDeps"]], str]:
        def build(ctx: RunContext["OrchestratorDeps"]) -> str:
            profile = ctx.deps.user_profile
            if not profile:
                return ""
            return (
                "\n\n## USER PROFILE (Auto-synthesized)\n\n"
                f"{profile}"
                "\n\nThis profile is automatically synthesized from accumulated "
                "memories. Use it to personalize your assistance.\n"
            )

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
            from agents.capabilities.volatile_context import (
                layout_active_for, build_recent_threads_section,
            )
            if layout_active_for(ctx.deps):
                return ""
            return await build_recent_threads_section(ctx.deps)

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
            from agents.capabilities.volatile_context import (
                layout_active_for, build_datetime_section,
            )
            if layout_active_for(ctx.deps):
                return ""
            return build_datetime_section()

        return build
