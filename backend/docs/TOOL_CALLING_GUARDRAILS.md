# Tool Calling Guardrails

This document explains the multi-layered guardrail system that ensures the LLM actually executes tool calls instead of just describing what it would do.

## The Problem

LLMs sometimes "role-play" using tools rather than actually calling them:

**Bad Behavior (Role-Playing):**
```
User: "Buy 10 shares of RELIANCE"
LLM: "I will now call execute_bash to run nf-order buy RELIANCE 10..."
     [No actual tool call happens]
```

**Good Behavior (Actually Using Tools):**
```
User: "Buy 10 shares of RELIANCE"
LLM: [Immediately calls execute_bash]
LLM: "Done! Market buy order placed for 10 shares of RELIANCE."
```

## Four-Layer Guardrail System

### Layer 1: System Prompt Instructions

**Location:** `backend/agents/orchestrator.py` - `_get_system_prompt()`

Explicitly instructs the model to NEVER describe tool calls, only make them.

**Key instructions:**
- Lists forbidden phrases: "I will call...", "Let me execute...", etc.
- Emphasizes that tool calls are visible to the user
- Provides clear examples of wrong vs. right behavior

**Example from prompt:**
```
## TOOL EXECUTION DISCIPLINE (CRITICAL)

**NEVER describe what you will do with tools - ACTUALLY USE THEM:**

WRONG - Role-playing/Describing:
- "I will now call execute_bash..."
- "Let me execute the nf-quote script..."

CORRECT - Actually calling tools:
- Just call execute_bash() directly
- NO narration - let your actions speak
```

### Layer 2: Result Validator

**Location:** Specialized agents only (NOT the orchestrator)

**IMPORTANT LIMITATION:** Pydantic AI does not allow using both `output_type` and output validators on the same agent. Since the orchestrator needs flexibility to use custom output types, **Layer 2 should only be applied to specialized agents**, not the orchestrator.

**What it does:** Inspects model output BEFORE returning it to the user. If role-playing is detected, raises `ModelRetry` to force the model to try again.

**Detection mechanism:**
- Scans output for phrases like "i will call", "let me execute", etc.
- Extracts context around the violation
- Provides specific feedback to the model about what went wrong

**Example (for specialized agents only):**
```python
from pydantic_ai import Agent, RunContext, ModelRetry

specialist_agent = Agent(
    'glm-5',
    deps_type=SpecialistDeps,
    # NO output_type specified - allows validator to work
)

@specialist_agent.output_validator
async def validate_no_role_playing(ctx: RunContext[SpecialistDeps], output: str) -> str:
    role_play_phrases = ["i will call", "let me execute", ...]

    for phrase in role_play_phrases:
        if phrase in output.lower():
            raise ModelRetry(
                f"STOP DESCRIBING ACTIONS - TAKE THEM!\n"
                f"You said: '{context}...'\n"
                f"This is WRONG. Just call the tool directly."
            )

    return output  # Only returns if no role-playing detected
```

**Retry behavior:**
- Model gets 1 retry by default (configurable in `AgentConfig.max_retries`)
- On retry, model receives the specific violation message
- If still failing, raises `UnexpectedModelBehavior` exception

**Why NOT on the orchestrator:**
- The orchestrator needs to support custom `output_type` for different operations
- Pydantic AI enforces: output validators XOR custom output_type, not both
- The orchestrator relies primarily on Layer 1 (system prompt) for guardrails

### Layer 3: Structured Outputs

**Location:** `backend/models/tool_execution.py`

For critical operations, forces the model to return structured data proving tools were executed.

**Available models:**
- `ActionResult` - Generic verification that tools were called

**Usage example:**
```python
from models.tool_execution import ActionResult

# Create an agent that MUST return structured proof of execution
order_agent = Agent(
    'glm-5',
    output_type=ActionResult,
    instructions='You must actually place the order and return verification'
)

result = await order_agent.run("Buy 10 RELIANCE at market", deps=deps)
```

**Why this works:**
- Model **cannot** complete without calling tools (needs data to fill fields)
- Pydantic validation ensures all required fields are present
- Type safety prevents hallucinated data

### Layer 4: Event Monitoring

**Location:** `backend/utils/tool_call_monitor.py`

Tracks all tool calls in real-time and detects suspicious patterns.

**How it works:**
```python
from utils.tool_call_monitor import get_monitor

monitor = get_monitor()

await monitor.start_run(thread_id="conv_123")

await monitor.record_tool_call(
    thread_id="conv_123",
    tool_name="execute_bash",
    arguments={"command": "python cli-tools/nf-quote RELIANCE --json"}
)

await monitor.mark_output_generated(thread_id="conv_123")

analysis = await monitor.finish_run(thread_id="conv_123")

if analysis.is_suspicious():
    logger.warning("Run generated output without calling tools!")
```

**Suspicious patterns detected:**
- Output generated but no tools called
- Long response time but no tool execution
- Specific tools mentioned in output but not actually called

## Integration Guide

### Orchestrator guardrails:

1. System prompt instructions - automatically included (Layer 1)
2. Result validator - NOT used on orchestrator (Pydantic AI limitation)
3. Structured outputs - optional, use for critical ops (Layer 3)
4. Event monitoring - optional, integrate manually (Layer 4)

**For specialized agents**, you CAN add result validators (Layer 2) IF they don't need custom output types.

### Adding Monitoring to a Tool

```python
@self.agent.tool
async def execute_bash(ctx: RunContext[OrchestratorDeps], command: str) -> str:
    from utils.tool_call_monitor import get_monitor

    monitor = get_monitor()
    thread_id = ctx.deps.state.thread_id

    await monitor.record_tool_call(
        thread_id=thread_id,
        tool_name="execute_bash",
        arguments={"command": command}
    )

    result = await execute_command(command)
    return result
```

## Summary

The four-layer approach provides defense-in-depth:

1. **System Prompt** - Primary instruction (used on orchestrator)
2. **Result Validator** - Catches violations, forces retry (specialized agents only, not orchestrator)
3. **Structured Outputs** - Forces proof of execution (optional, for critical operations)
4. **Event Monitoring** - Detects patterns, provides metrics (optional, for production observability)

**Important:** Pydantic AI does not allow using both output validators and custom `output_type` on the same agent. Since the orchestrator needs flexibility for custom output types, it uses only Layer 1 (system prompt). Specialized agents can use Layer 2 (validators) OR Layer 3 (structured outputs), but not both.
