"""The crash partial-summary must carry the relay payload.

When an action awakening dies (e.g. the 9:20 Morning Signal Deploy timeout,
2026-06-11), the note written to the daily thread must include the crashed
awakening's MISSION (its prompt) and the continue-or-pass instruction, so
the next pulse awakening can triage the orphaned job from thread history.
"""
from types import SimpleNamespace

import pytest

from services.awakening_scheduler import _write_partial_summary_on_crash


class FakeEngine:
    def __init__(self):
        self.written = None

    async def _write_followup_to_thread(self, *, thread_id, user_id, response_text, extra_metadata=None):
        self.written = SimpleNamespace(
            thread_id=thread_id, user_id=user_id,
            text=response_text, extra_metadata=extra_metadata,
        )


class FakeResult:
    def __init__(self, actions):
        self._actions = actions

    def scalars(self):
        return self

    def all(self):
        return self._actions


class FakeSession:
    def __init__(self, actions):
        self._actions = actions

    async def execute(self, _stmt):
        return FakeResult(self._actions)


def _action(tool, status, cmd):
    return SimpleNamespace(
        tool_name=tool, execution_status=status,
        tool_args={"command": cmd}, sequence_order=1,
    )


@pytest.mark.asyncio
async def test_relay_note_carries_mission_and_handoff():
    engine = FakeEngine()
    schedule = SimpleNamespace(
        id=154, name="Morning Signal Deploy",
        prompt="STEP 1: Read scratchpad.\nSTEP 2: Run nf-morning-scan and deploy 0-3 snipers.",
    )
    session = FakeSession([_action("execute_bash", "success", "nf-funds --json")])

    await _write_partial_summary_on_crash(
        engine=engine, session=session, thread_id="t1", user_id=1,
        schedule=schedule, run_id=99,
        error_class="TimeoutError", error_msg="Timed out after 1200s",
    )

    assert engine.written is not None
    text = engine.written.text
    # mission travels with the crash note, blockquoted line by line
    assert "The crashed awakening's mission was:" in text
    assert "> STEP 1: Read scratchpad." in text
    assert "> STEP 2: Run nf-morning-scan and deploy 0-3 snipers." in text
    # relay protocol: continue or pass forward
    assert "CONTINUE the mission" in text
    assert "PASS it forward" in text
    # state-verification warning retained
    assert "re-fetch portfolio + active rules" in text
    # tool calls still listed
    assert "nf-funds --json" in text
    # still tagged so the memory extractor skips this turn
    assert engine.written.extra_metadata == {"crashed": True}


@pytest.mark.asyncio
async def test_relay_note_without_prompt_or_actions():
    engine = FakeEngine()
    schedule = SimpleNamespace(id=1, name="X", prompt="")
    await _write_partial_summary_on_crash(
        engine=engine, session=FakeSession([]), thread_id="t1", user_id=1,
        schedule=schedule, run_id=1, error_class="RuntimeError", error_msg="boom",
    )
    text = engine.written.text
    assert "No tool calls were executed" in text
    assert "mission was:" not in text          # no empty blockquote section
    assert "PASS it forward" in text           # relay instruction always present
