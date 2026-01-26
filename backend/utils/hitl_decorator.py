"""
Human-in-the-Loop (HITL) Tool Decorator

Wraps tool functions to request user approval before execution when HITL mode is enabled.
"""

import functools
import logging
import asyncio
from typing import Callable, Any
from pydantic_ai import RunContext

from .hitl_manager import get_hitl_manager
from .sse_events import SSEEventEmitter

logger = logging.getLogger(__name__)


def requires_approval(
    explanation_fn: Callable[[dict], str] = None,
    tool_name_override: str = None
):
    """
    Decorator to add HITL approval to a tool function.

    When HITL is enabled for the user, this decorator will:
    1. Pause execution before calling the tool
    2. Emit an approval request event via SSE
    3. Wait for user approval/rejection
    4. Continue with tool execution if approved, or return rejection message

    Args:
        explanation_fn: Optional function that takes tool args and returns
                       a human-readable explanation of what the tool will do
        tool_name_override: Optional override for the tool name in approval UI

    Example:
        @requires_approval(
            explanation_fn=lambda args: f"Execute bash command: {args['command']}"
        )
        async def execute_bash(ctx, command, timeout=None):
            # ... tool implementation
    """
    def decorator(tool_func: Callable) -> Callable:
        @functools.wraps(tool_func)
        async def wrapper(*args, **kwargs):
            # Extract RunContext from args (always first param for Pydantic AI tools)
            ctx = args[0] if args else None
            if not isinstance(ctx, RunContext):
                logger.warning("[HITL] Tool called without RunContext, skipping approval")
                return await tool_func(*args, **kwargs)

            # Check if HITL is enabled for this user
            deps = ctx.deps
            hitl_enabled = getattr(deps, 'hitl_enabled', False)

            if not hitl_enabled:
                # HITL not enabled, execute tool normally
                return await tool_func(*args, **kwargs)

            # HITL is enabled - request approval
            tool_name = tool_name_override or tool_func.__name__

            # Build arguments dict (skip RunContext)
            tool_args = {}
            func_params = tool_func.__annotations__.keys()
            param_list = list(func_params)[1:]  # Skip ctx parameter

            # Map positional args (skip ctx)
            for i, param_name in enumerate(param_list):
                if i + 1 < len(args):
                    tool_args[param_name] = args[i + 1]

            # Add keyword args
            tool_args.update(kwargs)

            # Generate explanation
            if explanation_fn:
                try:
                    explanation = explanation_fn(tool_args)
                except Exception as e:
                    logger.error(f"[HITL] Error generating explanation: {e}")
                    explanation = f"Execute {tool_name}"
            else:
                # Default explanation
                explanation = f"Execute {tool_name} with arguments: {tool_args}"

            logger.info(f"[HITL] Requesting approval for {tool_name}")

            # Get HITL manager and request approval
            hitl_manager = get_hitl_manager()

            # Extract thread_id from deps if available
            thread_id = getattr(deps, 'state', None)
            if thread_id and hasattr(thread_id, 'thread_id'):
                thread_id = thread_id.thread_id
            else:
                thread_id = None
                logger.warning("[HITL] No thread_id available for event streaming")

            try:
                # Request approval (with 60s timeout)
                approval_result = await hitl_manager.request_approval(
                    tool_name=tool_name,
                    tool_args=tool_args,
                    explanation=explanation,
                    timeout_seconds=60,
                    thread_id=thread_id
                )

                if approval_result["approved"]:
                    logger.info(f"[HITL] User approved {tool_name}")
                    # Execute the tool
                    return await tool_func(*args, **kwargs)
                else:
                    # User rejected or timed out
                    reason = approval_result.get("reason", "User rejected")
                    logger.info(f"[HITL] User rejected {tool_name}: {reason}")
                    return f"❌ Action not approved: {reason}. The tool '{tool_name}' was not executed."

            except Exception as e:
                logger.error(f"[HITL] Error during approval process: {e}")
                # On error, reject the tool execution for safety
                return f"❌ Approval process failed: {str(e)}. The tool '{tool_name}' was not executed."

        return wrapper
    return decorator


async def emit_approval_request_event(
    approval_id: str,
    tool_name: str,
    tool_args: dict,
    explanation: str,
    stream_queue: asyncio.Queue = None
):
    """
    Emit an approval request event to the SSE stream.

    This should be called by the AG-UI wrapper when an approval request is detected.

    Args:
        approval_id: Unique ID for this approval request
        tool_name: Name of the tool requiring approval
        tool_args: Arguments for the tool
        explanation: Human-readable explanation
        stream_queue: Optional queue to send the event to
    """
    if stream_queue:
        event_data = SSEEventEmitter.hitl_approval_request(
            tool_name=tool_name,
            tool_args=tool_args,
            explanation=explanation,
            approval_id=approval_id
        )
        await stream_queue.put(event_data.encode())
