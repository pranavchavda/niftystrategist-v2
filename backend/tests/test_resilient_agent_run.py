"""Tests for the order-safe transient-error retry around agent.run().

Covers: mutation classification of CLI commands, the action-log mutation gate,
transient vs terminal error classification, and the retry loop's behaviour
(retry once on transient, no retry after a mutation, no retry on terminal).
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from services.resilient_agent_run import (
    _actions_show_mutation,
    _command_is_mutating,
    _is_transient,
    run_agent_with_retry,
)


# ── Command mutation classification ──────────────────────────────────────────

@pytest.mark.parametrize("cmd", [
    "nf-order place RELIANCE 10 --price 1300",
    "nf-order buy TCS 5",
    "nf-order sell INFY 12",
    "nf-order cancel 250612000123",
    "nf-order cancel-all",
    "nf-order modify 250612000123 --price 100",
    "nf-order exit-all",
    "nf-options buy NIFTY 24000 CE",
    "nf-options sell BANKNIFTY 48000 PE",
    "nf-options spread --legs ...",
    "nf-portfolio convert COFORGE 174 --from I --to D",
    "nf-monitor add-trailing COFORGE --trail-percent 4",
    "nf-monitor add-oco LT --sl 4020 --target 4200",
    "nf-monitor add-rule ...",
    "nf-monitor update-trail 4547 --trail-percent 3",
    "nf-monitor delete 4547",
    "nf-monitor disable 4547",
    "nf-mandate set --risk 5000",
    "nf-mandate clear",
    "./cli-tools/nf-order place RELIANCE 10",  # path-prefixed invocation
])
def test_mutating_commands_detected(cmd):
    assert _command_is_mutating(cmd) is True


@pytest.mark.parametrize("cmd", [
    "nf-quote RELIANCE",
    "nf-analyze TCS --json",
    "nf-market-status",
    "nf-portfolio",
    "nf-portfolio positions",
    "nf-funds",
    "nf-trades report",
    "nf-options chain NIFTY",
    "nf-options greeks NIFTY 24000 CE",
    "nf-options live-chain BANKNIFTY",
    "nf-options positions",
    "nf-options plan --bias bullish",
    "nf-monitor list",
    "nf-watchlist",
    "nf-order list",
    "nf-order detail 250612000123",
    "nf-order history 250612000123",
    "nf-order place RELIANCE 10 --dry-run",   # dry-run never mutates
    "nf-options buy NIFTY 24000 CE --dry-run",
    "",
    None,
    "some-unrelated-command --flag",
])
def test_nonmutating_commands_pass(cmd):
    assert _command_is_mutating(cmd) is False


# ── Action-log mutation gate ─────────────────────────────────────────────────

def _action(tool, status, cmd):
    return SimpleNamespace(
        tool_name=tool, execution_status=status, tool_args={"command": cmd},
    )


def test_actions_show_mutation_true_on_successful_order():
    actions = [
        _action("nf-quote", "success", "nf-quote RELIANCE"),
        _action("nf-order", "success", "nf-order place RELIANCE 10"),
    ]
    assert _actions_show_mutation(actions) is True


def test_actions_show_mutation_false_when_only_reads():
    actions = [
        _action("nf-quote", "success", "nf-quote RELIANCE"),
        _action("nf-analyze", "success", "nf-analyze TCS"),
        _action("nf-order", "success", "nf-order list"),
    ]
    assert _actions_show_mutation(actions) is False


def test_actions_show_mutation_ignores_failed_order():
    # A failed order attempt didn't commit broker-side → safe to retry.
    actions = [_action("nf-order", "failed", "nf-order place RELIANCE 10")]
    assert _actions_show_mutation(actions) is False


def test_actions_show_mutation_uses_tool_name_when_no_command():
    a = SimpleNamespace(tool_name="nf-order place", execution_status="success", tool_args={})
    assert _actions_show_mutation([a]) is True


# ── Transient vs terminal classification ─────────────────────────────────────

def test_is_transient_unexpected_model_behavior():
    from pydantic_ai.exceptions import UnexpectedModelBehavior
    assert _is_transient(UnexpectedModelBehavior("partial body")) is True


def test_is_transient_jsondecode():
    from json import JSONDecodeError
    assert _is_transient(JSONDecodeError("x", "doc", 0)) is True


def test_is_transient_wrapped_cause():
    from pydantic_ai.exceptions import UnexpectedModelBehavior
    outer = RuntimeError("wrapper")
    outer.__cause__ = UnexpectedModelBehavior("partial")
    assert _is_transient(outer) is True


def test_is_transient_model_http_5xx_yes_4xx_no():
    from pydantic_ai.exceptions import ModelHTTPError
    assert _is_transient(ModelHTTPError(status_code=503, model_name="m", body=None)) is True
    assert _is_transient(ModelHTTPError(status_code=429, model_name="m", body=None)) is True
    assert _is_transient(ModelHTTPError(status_code=401, model_name="m", body=None)) is False
    assert _is_transient(ModelHTTPError(status_code=400, model_name="m", body=None)) is False


def test_is_transient_terminal_errors():
    assert _is_transient(ValueError("logic bug")) is False
    assert _is_transient(KeyError("missing")) is False


# ── Retry loop behaviour ─────────────────────────────────────────────────────

class _FakeAgent:
    """Agent stub whose .run raises a queued sequence then returns a result."""
    def __init__(self, behaviours):
        self._behaviours = list(behaviours)
        self.calls = 0

    async def run(self, prompt, **kwargs):
        self.calls += 1
        b = self._behaviours.pop(0)
        if isinstance(b, BaseException):
            raise b
        return b


@pytest.mark.asyncio
async def test_retry_recovers_on_transient_then_success():
    from pydantic_ai.exceptions import UnexpectedModelBehavior
    result = SimpleNamespace(output="done")
    agent = _FakeAgent([UnexpectedModelBehavior("partial"), result])
    out = await run_agent_with_retry(
        agent, "prompt", deps=None, backoff_seconds=0,
    )
    assert out is result
    assert agent.calls == 2


@pytest.mark.asyncio
async def test_retry_gives_up_after_max_retries():
    from pydantic_ai.exceptions import UnexpectedModelBehavior
    agent = _FakeAgent([UnexpectedModelBehavior("a"), UnexpectedModelBehavior("b")])
    with pytest.raises(UnexpectedModelBehavior):
        await run_agent_with_retry(agent, "p", deps=None, backoff_seconds=0)
    assert agent.calls == 2  # initial + one retry, then give up


@pytest.mark.asyncio
async def test_no_retry_on_terminal_error():
    agent = _FakeAgent([ValueError("logic"), SimpleNamespace(output="x")])
    with pytest.raises(ValueError):
        await run_agent_with_retry(agent, "p", deps=None, backoff_seconds=0)
    assert agent.calls == 1  # never retried


@pytest.mark.asyncio
async def test_no_retry_after_broker_mutation(monkeypatch):
    from pydantic_ai.exceptions import UnexpectedModelBehavior
    import services.resilient_agent_run as mod

    async def _mutated(session, run_id):
        return True

    monkeypatch.setattr(mod, "_broker_mutation_happened", _mutated)
    agent = _FakeAgent([UnexpectedModelBehavior("partial"), SimpleNamespace(output="x")])
    with pytest.raises(UnexpectedModelBehavior):
        await run_agent_with_retry(
            agent, "p", deps=None, session=object(), run_id=1, backoff_seconds=0,
        )
    assert agent.calls == 1  # mutation gate blocked the retry


@pytest.mark.asyncio
async def test_retry_proceeds_when_no_mutation(monkeypatch):
    from pydantic_ai.exceptions import UnexpectedModelBehavior
    import services.resilient_agent_run as mod

    async def _clean(session, run_id):
        return False

    monkeypatch.setattr(mod, "_broker_mutation_happened", _clean)
    result = SimpleNamespace(output="ok")
    agent = _FakeAgent([UnexpectedModelBehavior("partial"), result])
    out = await run_agent_with_retry(
        agent, "p", deps=None, session=object(), run_id=1, backoff_seconds=0,
    )
    assert out is result
    assert agent.calls == 2


@pytest.mark.asyncio
async def test_cancellederror_never_swallowed():
    # Catch inside the coroutine — asserting CancelledError via pytest.raises at
    # the task boundary collides with pytest-asyncio's own cancellation handling.
    import asyncio
    agent = _FakeAgent([asyncio.CancelledError()])
    raised = False
    try:
        await run_agent_with_retry(agent, "p", deps=None, backoff_seconds=0)
    except asyncio.CancelledError:
        raised = True
    assert raised  # propagated, not retried or swallowed
    assert agent.calls == 1
