"""Per-thread asyncio locks shared across in-process orchestrator runners.

Both scheduled awakenings (services/workflow_engine.py) and inbound Telegram
chat (services/telegram_chat.py) run the orchestrator against a user's daily
mandate thread inside the FastAPI event loop. Without coordination, a 9:20
awakening still mid-run when the user DMs at 9:21 would interleave writes to the
same thread and race on `conversation.updated_at`.

Acquire `thread_lock(thread_id)` around the run+write so turns on one thread are
serialized. Locks are keyed by thread_id and never evicted — daily threads are
bounded (one per user per day), so the registry stays small.

The monitor daemon is a separate process and never runs the orchestrator on a
thread, so it does not participate here.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

_locks: dict[str, asyncio.Lock] = {}
_registry_lock = asyncio.Lock()


async def _get_lock(thread_id: str) -> asyncio.Lock:
    async with _registry_lock:
        lock = _locks.get(thread_id)
        if lock is None:
            lock = asyncio.Lock()
            _locks[thread_id] = lock
        return lock


@asynccontextmanager
async def thread_lock(thread_id: str):
    """Serialize orchestrator turns on one thread within this process."""
    lock = await _get_lock(thread_id)
    async with lock:
        yield
