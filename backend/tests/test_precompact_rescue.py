"""Phase 3 — pre-compaction memory rescue safety contract.

The rescue extracts durable facts before compaction deletes messages, but its
load-bearing property is that it can NEVER block compaction: any failure must be
swallowed and returned as {"error": ...}. See
docs/plans/2026-05-23-prefix-cache-memory-port.md.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import scripts.extract_memories_daily as ed  # noqa: E402


@pytest.mark.asyncio
async def test_rescue_swallows_db_errors(monkeypatch):
    """If opening the DB session blows up, rescue returns an error dict, not a raise."""
    def _boom(*a, **k):
        raise RuntimeError("db down")

    monkeypatch.setattr(ed, "get_db_context", _boom)
    out = await ed.rescue_memories_before_compaction("thread_1", "user@example.com")
    assert isinstance(out, dict)
    assert "error" in out


@pytest.mark.asyncio
async def test_rescue_handles_missing_conversation(monkeypatch):
    """A missing conversation is reported, not raised."""
    class _FakeSession:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(ed, "get_db_context", lambda: _FakeSession())

    async def _none(*a, **k):
        return None

    monkeypatch.setattr(ed.ConversationOps, "get_conversation", _none)
    out = await ed.rescue_memories_before_compaction("missing", "user@example.com")
    assert out == {"error": "conversation_not_found"}
