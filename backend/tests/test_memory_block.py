"""Tests for the managed memory block (MemGPT/Letta-style core memory).

The CLI tool (cli-tools/nf-memory-block) is a thin subprocess+arg-parse shell
over services.memory_block, so the load-bearing get/set/clear + cap logic and
the section builder are unit-tested here against a fake in-memory DB session
(monkeypatching get_db_context, the pattern used by test_precompact_rescue.py).
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import services.memory_block as mb  # noqa: E402
from services.memory_block import (  # noqa: E402
    MEMORY_BLOCK_MAX_CHARS,
    MemoryBlockTooLargeError,
    UserNotFoundError,
    build_memory_block_section,
)


class _FakeUser:
    def __init__(self, memory_block=None, memory_block_updated_at=None):
        self.memory_block = memory_block
        self.memory_block_updated_at = memory_block_updated_at


class _FakeSession:
    """Minimal async session: session.get(User, id) -> the registered user."""

    def __init__(self, user):
        self._user = user
        self.committed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, model, pk):
        return self._user

    async def commit(self):
        self.committed = True


@pytest.fixture
def fake_db(monkeypatch):
    """Install a fake get_db_context backed by one mutable user.

    Returns the _FakeUser so a test can assert on the persisted columns.
    Use `fake_db.set_user(None)` to simulate a missing user.
    """
    state = {"user": _FakeUser()}

    def _ctx():
        return _FakeSession(state["user"])

    monkeypatch.setattr(mb, "get_db_context", _ctx)

    class _Handle:
        user = state["user"]

        def set_user(self, u):
            state["user"] = u
            self.user = u

    return _Handle()


# --------------------------------------------------------------------------- #
# set_block — cap enforcement
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_set_block_rejects_over_cap(fake_db):
    too_long = "x" * (MEMORY_BLOCK_MAX_CHARS + 1)
    with pytest.raises(MemoryBlockTooLargeError) as exc:
        await mb.set_block(1, too_long)
    assert exc.value.length == MEMORY_BLOCK_MAX_CHARS + 1
    # Nothing written.
    assert fake_db.user.memory_block is None


@pytest.mark.asyncio
async def test_set_block_accepts_exact_cap(fake_db):
    exact = "y" * MEMORY_BLOCK_MAX_CHARS
    block, updated_at = await mb.set_block(1, exact)
    assert block == exact
    assert len(block) == MEMORY_BLOCK_MAX_CHARS
    assert fake_db.user.memory_block == exact
    assert updated_at is not None


@pytest.mark.asyncio
async def test_set_block_full_rewrite_replaces(fake_db):
    """Update is a full rewrite, not an append."""
    await mb.set_block(1, "first version")
    block, _ = await mb.set_block(1, "second version entirely")
    assert block == "second version entirely"
    assert "first" not in fake_db.user.memory_block


@pytest.mark.asyncio
async def test_set_block_sets_updated_at(fake_db):
    assert fake_db.user.memory_block_updated_at is None
    _, updated_at = await mb.set_block(1, "hello")
    assert updated_at is not None
    assert fake_db.user.memory_block_updated_at == updated_at


@pytest.mark.asyncio
async def test_set_block_missing_user_raises(fake_db):
    fake_db.set_user(None)
    with pytest.raises(UserNotFoundError):
        await mb.set_block(42, "anything")


# --------------------------------------------------------------------------- #
# get_block / clear_block
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_get_block_returns_stored(fake_db):
    await mb.set_block(1, "stored content")
    block, updated_at = await mb.get_block(1)
    assert block == "stored content"
    assert updated_at is not None


@pytest.mark.asyncio
async def test_get_block_missing_user_raises(fake_db):
    fake_db.set_user(None)
    with pytest.raises(UserNotFoundError):
        await mb.get_block(7)


@pytest.mark.asyncio
async def test_clear_block_empties(fake_db):
    await mb.set_block(1, "to be cleared")
    await mb.clear_block(1)
    assert fake_db.user.memory_block is None
    assert fake_db.user.memory_block_updated_at is not None
    block, _ = await mb.get_block(1)
    assert block is None


@pytest.mark.asyncio
async def test_clear_block_missing_user_raises(fake_db):
    fake_db.set_user(None)
    with pytest.raises(UserNotFoundError):
        await mb.clear_block(9)


# --------------------------------------------------------------------------- #
# build_memory_block_section — rendering
# --------------------------------------------------------------------------- #

def test_section_renders_empty_placeholder():
    section = build_memory_block_section(None, None)
    assert "## 🧠 Memory Block (yours to maintain)" in section
    assert "(empty — nothing recorded yet)" in section
    # Standing instruction lines present even when empty.
    assert "nf-memory-block update" in section
    assert "NOT a chat scratchpad" in section


def test_section_renders_blank_string_as_empty():
    section = build_memory_block_section("   \n  ", None)
    assert "(empty — nothing recorded yet)" in section


def test_section_renders_filled():
    section = build_memory_block_section(
        "Stance: range-bound. Experiment: ORB long, 3 trades, 2 win.", None
    )
    assert "Stance: range-bound" in section
    assert "ORB long, 3 trades, 2 win" in section
    assert "(empty — nothing recorded yet)" not in section
    # Instruction lines still present.
    assert "persists across ALL threads" in section
    assert str(MEMORY_BLOCK_MAX_CHARS) in section


def test_section_renders_updated_at_as_ist():
    from datetime import datetime

    # Naive UTC midnight -> 05:30 IST.
    dt = datetime(2026, 6, 10, 0, 0, 0)
    section = build_memory_block_section("content", dt)
    assert "Last updated:" in section
    assert "2026-06-10 05:30 IST" in section


def test_section_no_timestamp_line_when_updated_at_none():
    section = build_memory_block_section("content", None)
    assert "Last updated:" not in section
