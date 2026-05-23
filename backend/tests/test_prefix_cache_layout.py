"""Phase 4 — prefix-cache layout: volatile context moves to the message tail.

Safety net per advisor: assert each volatile category appears EXACTLY ONCE
across the final message list (catches both content-dropped and double-inject),
that awakenings bypass the layout (byte-stable instruction path), and that the
hook is idempotent across the tool loop. See
docs/plans/2026-05-23-prefix-cache-memory-port.md.
"""

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import agents.capabilities.volatile_context as vc  # noqa: E402
from agents.capabilities.context_injection import (  # noqa: E402
    VolatileContextCapability,
    MemoryCapability,
    DateTimeCapability,
)


def _deps(*, is_awakening=False, memories=("I prefer EMA-cross entries",),
          paper=True):
    return SimpleNamespace(
        user_memories=list(memories),
        state=SimpleNamespace(thread_id=None, user_id="u@e.com"),
        trading_mode="paper" if paper else "live",
        paper_total_value=500000.0 if paper else None,
        paper_total_pnl=1234.5 if paper else None,
        paper_pnl_percent=0.25 if paper else None,
        is_awakening=is_awakening,
    )


@pytest.fixture(autouse=True)
def _no_db(monkeypatch):
    """Stub the two DB-backed builders so tests stay hermetic."""
    async def _empty(_deps):
        return ""
    monkeypatch.setattr(vc, "build_scratchpad_section", _empty)
    monkeypatch.setattr(vc, "build_recent_threads_section", _empty)


# ---- flag / gating -------------------------------------------------------

def test_layout_default_on():
    import os
    os.environ.pop("ENABLE_PREFIX_CACHE_LAYOUT", None)
    assert vc.prefix_cache_layout_enabled() is True


def test_layout_can_be_disabled(monkeypatch):
    monkeypatch.setenv("ENABLE_PREFIX_CACHE_LAYOUT", "0")
    assert vc.prefix_cache_layout_enabled() is False
    # And then layout_active_for is False for a normal run.
    assert vc.layout_active_for(_deps()) is False


def test_awakening_forces_layout_off(monkeypatch):
    monkeypatch.delenv("ENABLE_PREFIX_CACHE_LAYOUT", raising=False)
    assert vc.layout_active_for(_deps(is_awakening=True)) is False
    assert vc.layout_active_for(_deps(is_awakening=False)) is True


# ---- the assembled block -------------------------------------------------

@pytest.mark.asyncio
async def test_block_contains_each_section_exactly_once():
    block = await vc.build_volatile_context_block(SimpleNamespace(deps=_deps()))
    assert block.count("<volatile_context>") == 1
    assert block.count("</volatile_context>") == 1
    assert block.count("## REMEMBERED INFORMATION") == 1
    assert block.count("## ⏰ CURRENT DATE & TIME") == 1
    assert block.count("## Paper Trading Mode") == 1
    assert "EMA-cross" in block
    # fenced as reference-not-user-input
    assert "NOT new user input" in block


@pytest.mark.asyncio
async def test_block_empty_when_nothing_volatile(monkeypatch):
    # No memories, live mode -> only datetime is non-empty, so block still has content.
    # Force datetime empty too to prove the all-empty short-circuit.
    monkeypatch.setattr(vc, "build_datetime_section", lambda: "")
    block = await vc.build_volatile_context_block(
        SimpleNamespace(deps=_deps(memories=(), paper=False))
    )
    assert block == ""


# ---- the hook: exactly-once tail injection -------------------------------

@pytest.mark.asyncio
async def test_hook_injects_once_at_tail():
    cap = VolatileContextCapability()
    rc = SimpleNamespace(messages=[])
    ctx = SimpleNamespace(deps=_deps())

    out = await cap.before_model_request(ctx, rc)
    assert out is rc
    assert len(rc.messages) == 1
    injected = rc.messages[-1]
    # the appended message carries exactly one volatile block
    text = injected.parts[0].content
    assert text.count("<volatile_context>") == 1
    assert "REMEMBERED INFORMATION" in text


@pytest.mark.asyncio
async def test_hook_idempotent_across_tool_loop():
    """Second call (e.g. next model request in the same run, messages persisted)
    must NOT add a second block — the sentinel guard catches it."""
    cap = VolatileContextCapability()
    rc = SimpleNamespace(messages=[])
    ctx = SimpleNamespace(deps=_deps())

    await cap.before_model_request(ctx, rc)
    await cap.before_model_request(ctx, rc)

    blocks = sum(
        1
        for m in rc.messages
        for p in getattr(m, "parts", [])
        if isinstance(getattr(p, "content", None), str) and "<volatile_context>" in p.content
    )
    assert blocks == 1


@pytest.mark.asyncio
async def test_hook_noop_on_awakening():
    cap = VolatileContextCapability()
    rc = SimpleNamespace(messages=[])
    ctx = SimpleNamespace(deps=_deps(is_awakening=True))
    await cap.before_model_request(ctx, rc)
    assert rc.messages == []


@pytest.mark.asyncio
async def test_hook_noop_when_flag_off(monkeypatch):
    monkeypatch.setenv("ENABLE_PREFIX_CACHE_LAYOUT", "off")
    cap = VolatileContextCapability()
    rc = SimpleNamespace(messages=[])
    ctx = SimpleNamespace(deps=_deps())
    await cap.before_model_request(ctx, rc)
    assert rc.messages == []


# ---- suppression in the instruction path ---------------------------------

def test_memory_capability_suppressed_when_layout_active(monkeypatch):
    monkeypatch.delenv("ENABLE_PREFIX_CACHE_LAYOUT", raising=False)
    build = MemoryCapability().get_instructions()
    # layout active (normal chat) -> suppressed
    assert build(SimpleNamespace(deps=_deps())) == ""
    # awakening (layout off) -> emits in instructions
    assert "REMEMBERED INFORMATION" in build(SimpleNamespace(deps=_deps(is_awakening=True)))


def test_datetime_capability_suppressed_when_layout_active(monkeypatch):
    monkeypatch.delenv("ENABLE_PREFIX_CACHE_LAYOUT", raising=False)
    build = DateTimeCapability().get_instructions()
    assert build(SimpleNamespace(deps=_deps())) == ""
    assert "CURRENT DATE & TIME" in build(SimpleNamespace(deps=_deps(is_awakening=True)))
