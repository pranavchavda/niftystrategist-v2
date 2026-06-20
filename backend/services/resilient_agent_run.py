"""Resilient wrapper around ``agent.run()`` for autonomous (awakening / workflow) runs.

## Why this exists

OpenRouter occasionally returns a malformed / partial body on an upstream
provider failover or blip. We already retry the *transport* layer twice over
(``base_agent.py``: an ``AsyncTenacityTransport`` that retries 4× on
``JSONDecodeError`` + network errors, plus AsyncOpenAI ``max_retries=5``). Those
only catch failures where **httpx itself cannot decode the bytes**.

The gap: when OpenRouter returns a **200 OK with a partial / malformed
tool-call body**, the bytes decode fine — the failure surfaces *later*, inside
pydantic-ai, as ``UnexpectedModelBehavior`` / ``IncompleteToolCall`` /
``ModelHTTPError`` at the ``agent.run()`` call. Neither transport-layer retry
sees it, so a single upstream blip crashes the whole awakening (incident
2026-06-17). The crash-relay (``awakening_scheduler._write_partial_summary_on_crash``)
is the floor that triages the orphan on the next pulse — but for a *transient*
blip we'd rather just re-run once and finish on time.

## What it does

Retries ``agent.run()`` once (configurable) on transient model-layer errors —
**but only when it is safe**. Re-running re-executes every tool call from
scratch; harmless for reads (nf-quote/nf-analyze/…), dangerous for a command
that already mutated broker/rule state (a second run could double-place an
order or duplicate a protective rule). So before retrying we inspect the
``workflow_action_logs`` for this run: if any state-mutating CLI command has
already executed, we DO NOT retry — we re-raise and let the crash-relay handle
it. If we can't tell, we err on the side of not retrying.

Origin: 2026-06-21 dev session (Pranav). See memory project_ns_agent_as_primary_user.
"""

from __future__ import annotations

import asyncio
import logging
from json import JSONDecodeError
from typing import Any, Iterable, Optional

logger = logging.getLogger(__name__)


# ── Mutation classification ──────────────────────────────────────────────────
# CLI subcommands that change broker or rule state. If one of these has already
# succeeded this run, re-running the agent could double-apply it — so we must not
# retry. Everything else (quotes, analysis, portfolio reads, option chains,
# monitor `list`, …) is idempotent and safe to repeat.
_MUTATING_SUBCMDS: dict[str, set[str]] = {
    "nf-order": {"place", "buy", "sell", "cancel", "cancel-all", "modify", "exit-all"},
    "nf-options": {"buy", "sell", "place", "spread"},
    "nf-portfolio": {"convert"},
    "nf-monitor": {
        "oco", "create", "update-trail", "update", "enable", "disable",
        "delete", "remove",
    },  # plus any `add*` subcommand, handled below
    "nf-mandate": {"set", "clear"},
}


def _command_is_mutating(command: Optional[str]) -> bool:
    """True if a CLI command string would change broker/rule/mandate state.

    Conservative on the read side (a --dry-run never mutates) and exact on the
    write side (keyed on the tool's actual subcommand verb).
    """
    if not command:
        return False
    c = " ".join(command.strip().lower().split())
    if not c:
        return False
    if "--dry-run" in c:
        return False
    toks = c.split()
    # tool may be invoked as a bare name or a path (./cli-tools/nf-order)
    tool = toks[0].rsplit("/", 1)[-1]
    sub = toks[1] if len(toks) > 1 else ""
    muts = _MUTATING_SUBCMDS.get(tool)
    if muts is None:
        return False
    if sub in muts:
        return True
    # nf-monitor add / add-oco / add-trailing / add-rule — any add* creates a rule
    if tool == "nf-monitor" and sub.startswith("add"):
        return True
    return False


def _actions_show_mutation(actions: Iterable[Any]) -> bool:
    """True if any logged WorkflowActionLog row reflects a committed mutation.

    A *failed* mutation attempt didn't commit broker-side, so it doesn't block a
    retry; a ``success`` (or status-unknown) mutation does.
    """
    for a in actions:
        status = (getattr(a, "execution_status", None) or "").lower()
        if status == "failed":
            continue  # didn't commit
        args = getattr(a, "tool_args", None) or {}
        command = args.get("command") if isinstance(args, dict) else None
        # Fall back to tool_name when no command string was logged
        if not command:
            command = getattr(a, "tool_name", None)
        if _command_is_mutating(command):
            return True
    return False


async def _broker_mutation_happened(session: Any, run_id: Any) -> bool:
    """Check the action log for a committed mutation in this run.

    Returns True (block the retry) if we find a mutation OR if we can't read the
    log — never silently allow a risky re-run.
    """
    if session is None or run_id is None:
        return False  # nothing logged to worry about (e.g. interactive/test path)
    try:
        from database.models import WorkflowActionLog
        from sqlalchemy import select

        result = await session.execute(
            select(WorkflowActionLog).where(
                WorkflowActionLog.workflow_run_id == run_id
            )
        )
        return _actions_show_mutation(result.scalars().all())
    except Exception as e:  # pragma: no cover - defensive
        logger.warning(
            "resilient_agent_run: could not read action log for run %s (%s) — "
            "assuming a mutation occurred and NOT retrying",
            run_id, e,
        )
        return True


# ── Transient-error classification ───────────────────────────────────────────

def _is_transient(exc: BaseException, _depth: int = 0) -> bool:
    """True for model-layer errors worth one retry (partial/blip), not logic errors.

    Walks ``__cause__`` once or twice because pydantic-ai sometimes wraps the
    underlying decode/HTTP error.
    """
    try:
        from pydantic_ai.exceptions import (
            UnexpectedModelBehavior,
            ModelHTTPError,
            ModelAPIError,
        )
    except Exception:  # pragma: no cover - pydantic_ai always present in prod
        UnexpectedModelBehavior = ModelHTTPError = ModelAPIError = ()  # type: ignore

    # IncompleteToolCall exists in newer pydantic-ai; import defensively.
    try:
        from pydantic_ai.exceptions import IncompleteToolCall  # type: ignore
    except Exception:  # pragma: no cover
        IncompleteToolCall = ()  # type: ignore

    if ModelHTTPError and isinstance(exc, ModelHTTPError):
        code = getattr(exc, "status_code", None)
        # Retry server-side / rate-limit only; 4xx (auth, bad request) is terminal.
        return code is None or code >= 500 or code == 429

    transient_types = tuple(
        t for t in (UnexpectedModelBehavior, IncompleteToolCall, ModelAPIError)
        if isinstance(t, type)
    )
    if transient_types and isinstance(exc, transient_types):
        return True

    if isinstance(exc, JSONDecodeError):
        return True

    if _depth < 2:
        cause = getattr(exc, "__cause__", None) or getattr(exc, "__context__", None)
        if cause is not None and cause is not exc:
            return _is_transient(cause, _depth + 1)
    return False


# ── Public entry point ───────────────────────────────────────────────────────

async def run_agent_with_retry(
    agent: Any,
    prompt: str,
    *,
    deps: Any,
    message_history: Any = None,
    session: Any = None,
    run_id: Any = None,
    max_retries: int = 1,
    backoff_seconds: float = 1.5,
    label: str = "agent-run",
) -> Any:
    """Run ``agent.run(prompt, …)`` with an order-safe retry on transient errors.

    Drop-in for ``await agent.run(prompt, deps=deps, message_history=…)`` —
    keep the caller's ``asyncio.wait_for(..., timeout=…)`` around this call so
    the schedule timeout still bounds *all* attempts combined.
    """
    attempt = 0
    while True:
        try:
            kwargs: dict[str, Any] = {"deps": deps}
            if message_history is not None:
                kwargs["message_history"] = message_history
            return await agent.run(prompt, **kwargs)
        except asyncio.CancelledError:
            raise  # cooperative cancellation / outer timeout — never swallow
        except Exception as exc:
            if attempt >= max_retries or not _is_transient(exc):
                raise
            # Order-safety gate: if anything already mutated state this run, a
            # blind re-run could double-apply it. Fall through to crash-relay.
            if await _broker_mutation_happened(session, run_id):
                logger.warning(
                    "%s: transient model error (%s) but a state mutation already "
                    "committed this run — NOT retrying; crash-relay will triage.",
                    label, type(exc).__name__,
                )
                raise
            attempt += 1
            logger.warning(
                "%s: transient model error (%s: %s) — retry %d/%d after %.1fs",
                label, type(exc).__name__, str(exc)[:200],
                attempt, max_retries, backoff_seconds,
            )
            if backoff_seconds > 0:
                await asyncio.sleep(backoff_seconds)
