"""Managed memory block — the agent's single, always-present "core memory".

A MemGPT/Letta-style living document, one per user, that the orchestrator
itself curates and rewrites in full. Distinct from:
  * auto-surfaced semantic memories (top-10 embedding matches per query), and
  * the thread-scoped scratchpad (services/scratchpad_db.py).

It is injected into EVERY request's dynamic instructions (chat AND awakenings)
and bounded to MEMORY_BLOCK_MAX_CHARS. Writes go through the nf-memory-block
CLI tool, which wraps the get/set/clear helpers here.

This module holds the core get/set/clear logic with cap enforcement so it can
be unit-tested directly (the CLI is a thin subprocess+arg-parse shell over it).
Stored in a plain TEXT column, so there is no JSON dirty-tracking pitfall here —
we always assign a brand-new value to the column on writes.
"""

from typing import Optional, Tuple

from database.session import get_db_context
from database.models import User, utc_now

# Hard cap on the block size. MemGPT-style full-rewrite semantics: the agent
# re-curates the whole document each time and must keep it condensed. Writes
# over this are REJECTED (no silent truncation) so the agent learns to prune.
MEMORY_BLOCK_MAX_CHARS = 6000


class MemoryBlockTooLargeError(ValueError):
    """Raised when a proposed block exceeds MEMORY_BLOCK_MAX_CHARS."""

    def __init__(self, length: int):
        self.length = length
        super().__init__(
            f"Memory block is {length} chars, over the "
            f"{MEMORY_BLOCK_MAX_CHARS}-char cap. Condense it (prune stale "
            f"content) and try again — the block is NOT truncated automatically."
        )


class UserNotFoundError(ValueError):
    """Raised when the target user does not exist."""

    def __init__(self, user_id: int):
        self.user_id = user_id
        super().__init__(f"User {user_id} not found")


async def get_block(user_id: int) -> Tuple[Optional[str], Optional[object]]:
    """Return (memory_block, memory_block_updated_at) for the user.

    Raises UserNotFoundError if the user does not exist.
    """
    async with get_db_context() as session:
        user = await session.get(User, user_id)
        if not user:
            raise UserNotFoundError(user_id)
        return user.memory_block, user.memory_block_updated_at


async def set_block(user_id: int, text: str) -> Tuple[str, object]:
    """Replace the ENTIRE block (full-rewrite, MemGPT-style).

    Enforces the MEMORY_BLOCK_MAX_CHARS cap (reject, no truncation). Sets
    memory_block_updated_at = utc_now(). Returns (block, updated_at).

    Raises MemoryBlockTooLargeError if over the cap, UserNotFoundError if the
    user is missing.
    """
    if text is None:
        text = ""
    if len(text) > MEMORY_BLOCK_MAX_CHARS:
        raise MemoryBlockTooLargeError(len(text))

    async with get_db_context() as session:
        user = await session.get(User, user_id)
        if not user:
            raise UserNotFoundError(user_id)
        now = utc_now()
        # Plain TEXT column — assigning a fresh string value always marks the
        # column dirty (no JSON in-place-mutation aliasing pitfall here).
        user.memory_block = text
        user.memory_block_updated_at = now
        await session.commit()
        return text, now


async def clear_block(user_id: int) -> None:
    """Empty the block. Sets memory_block=None and updated_at=utc_now().

    Raises UserNotFoundError if the user is missing.
    """
    async with get_db_context() as session:
        user = await session.get(User, user_id)
        if not user:
            raise UserNotFoundError(user_id)
        user.memory_block = None
        user.memory_block_updated_at = utc_now()
        await session.commit()


def build_memory_block_section(
    block: Optional[str], updated_at: Optional[object] = None
) -> str:
    """Render the dynamic-instructions section for the memory block.

    Always renders (it is an always-present, self-maintained block) — shows a
    placeholder when empty. `updated_at` is a naive UTC datetime; it's rendered
    as IST. Returns the section string (always non-empty).
    """
    body = (block or "").strip()
    if not body:
        body = "(empty — nothing recorded yet)"

    s = "\n\n## 🧠 Memory Block (yours to maintain)\n\n"
    s += f"{body}\n"

    if updated_at is not None:
        try:
            from datetime import timezone
            from zoneinfo import ZoneInfo

            dt = updated_at
            if getattr(dt, "tzinfo", None) is None:
                dt = dt.replace(tzinfo=timezone.utc)
            ist = dt.astimezone(ZoneInfo("Asia/Kolkata"))
            s += f"_Last updated: {ist.strftime('%Y-%m-%d %H:%M')} IST._\n"
        except Exception:
            pass

    s += (
        "\nThis is YOUR own curated working memory — a single living document "
        "that persists across ALL threads (not this conversation only). "
        "Rewrite it via `python cli-tools/nf-memory-block update --text \"...\"` "
        "(full rewrite — you re-curate the whole document) whenever durable "
        "context changes: your current strategy stance, active experiments and "
        "their tallies (e.g. tagged-trade counts per setup type under the "
        "mandate), recent lessons, and open loops worth carrying forward.\n"
        f"Keep it under {MEMORY_BLOCK_MAX_CHARS} characters by pruning stale "
        "content (over-cap writes are rejected, not truncated). "
        "This is NOT a chat scratchpad (that exists separately, per-thread) and "
        "NOT for per-session noise — record only what's worth remembering across "
        "sessions.\n"
    )
    return s
