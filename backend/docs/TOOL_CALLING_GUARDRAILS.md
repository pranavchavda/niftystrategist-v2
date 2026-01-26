# Tool Calling Guardrails

This document explains the multi-layered guardrail system that ensures the LLM actually executes tool calls instead of just describing what it would do.

## The Problem

LLMs sometimes "role-play" using tools rather than actually calling them:

❌ **Bad Behavior (Role-Playing):**
```
User: "Update price for product X to $99"
LLM: "I will now call execute_bash to run update_pricing.py for product X..."
     [No actual tool call happens]
```

✓ **Good Behavior (Actually Using Tools):**
```
User: "Update price for product X to $99"
LLM: [Immediately calls execute_bash]
LLM: "Done! Product X price updated to $99."
```

## Four-Layer Guardrail System

### Layer 1: System Prompt Instructions ⚠️

**Location:** `backend/agents/orchestrator.py` - `_get_system_prompt()`

**What it does:** Explicitly instructs the model to NEVER describe tool calls, only make them.

**Key instructions:**
- Lists forbidden phrases: "I will call...", "Let me execute...", etc.
- Emphasizes that tool calls are visible to the user
- Provides clear examples of wrong vs. right behavior

**Example from prompt:**
```
## ⚠️ TOOL EXECUTION DISCIPLINE (CRITICAL)

**NEVER describe what you will do with tools - ACTUALLY USE THEM:**

❌ WRONG - Role-playing/Describing:
- "I will now call execute_bash..."
- "Let me execute the update_pricing script..."

✓ CORRECT - Actually calling tools:
- Just call execute_bash() directly
- NO narration - let your actions speak
```

### Layer 2: Result Validator 🛡️

**Location:** Specialized agents only (NOT the orchestrator)

**⚠️ IMPORTANT LIMITATION:** Pydantic AI does not allow using both `output_type` and output validators on the same agent. Since the orchestrator needs flexibility to use custom output types, **Layer 2 should only be applied to specialized agents**, not the orchestrator.

**What it does:** Inspects model output BEFORE returning it to the user. If role-playing is detected, raises `ModelRetry` to force the model to try again.

**Detection mechanism:**
- Scans output for phrases like "i will call", "let me execute", etc.
- Extracts context around the violation
- Provides specific feedback to the model about what went wrong

**Example (for specialized agents only):**
```python
# Create a specialized agent with output validator
from pydantic_ai import Agent, RunContext, ModelRetry

specialist_agent = Agent(
    'gpt-5',
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

### Layer 3: Structured Outputs 📊

**Location:** `backend/models/tool_execution.py`

**What it does:** For critical operations, forces the model to return structured data proving tools were executed.

**Available models:**
- `ActionResult` - Generic verification that tools were called
- `PricingUpdateResult` - Specific to pricing updates
- `ProductCreationResult` - Specific to product creation

**Usage example:**
```python
from models.tool_execution import PricingUpdateResult

# Create an agent that MUST return structured proof of execution
pricing_agent = Agent(
    'gpt-5',
    output_type=PricingUpdateResult,
    instructions='You must actually update prices and return verification'
)

result = await pricing_agent.run("Update product X price to $99", deps=deps)

# Result MUST have:
# - products_updated: List of product IDs actually modified
# - update_commands_executed: Bash commands that were run
# - verification_results: Results from fetching updated product
```

**Why this works:**
- Model **cannot** complete without calling tools (needs data to fill fields)
- Pydantic validation ensures all required fields are present
- Type safety prevents hallucinated data

### Layer 4: Event Monitoring 📈

**Location:** `backend/utils/tool_call_monitor.py`

**What it does:** Tracks all tool calls in real-time and detects suspicious patterns.

**How it works:**
```python
from utils.tool_call_monitor import get_monitor

monitor = get_monitor()

# Start monitoring
await monitor.start_run(thread_id="conv_123")

# Record tool calls as they happen (integrate in tools)
await monitor.record_tool_call(
    thread_id="conv_123",
    tool_name="execute_bash",
    arguments={"command": "python bash-tools/search_products.py"}
)

# Mark when output is generated
await monitor.mark_output_generated(thread_id="conv_123")

# Get analysis
analysis = await monitor.finish_run(thread_id="conv_123")

if analysis.is_suspicious():
    logger.warning(f"⚠️ Run generated output without calling tools!")
    # Alert, log to monitoring system, etc.
```

**Suspicious patterns detected:**
- Output generated but no tools called
- Long response time but no tool execution
- Specific tools mentioned in output but not actually called

**Statistics available:**
```python
stats = monitor.get_stats()
# {
#   'total_runs': 156,
#   'total_tool_calls': 432,
#   'suspicious_runs': 3,
#   'tool_execute_bash': 287,
#   'tool_read_docs': 145,
#   ...
# }
```

## Integration Guide

### For Existing Code

**Orchestrator guardrails:**

1. ✅ System prompt instructions - automatically included (Layer 1)
2. ⚠️ Result validator - NOT used on orchestrator (Pydantic AI limitation)
3. ⚠️ Structured outputs - optional, use for critical ops (Layer 3)
4. ⚠️ Event monitoring - optional, integrate manually (Layer 4)

**For specialized agents**, you CAN add result validators (Layer 2) IF they don't need custom output types.

### Adding Monitoring to a Tool

To track tool calls in monitoring:

```python
@self.agent.tool
async def execute_bash(ctx: RunContext[OrchestratorDeps], command: str) -> str:
    from utils.tool_call_monitor import get_monitor

    monitor = get_monitor()
    thread_id = ctx.deps.state.thread_id

    # Record tool call
    await monitor.record_tool_call(
        thread_id=thread_id,
        tool_name="execute_bash",
        arguments={"command": command}
    )

    # Execute command...
    result = await execute_command(command)

    return result
```

### Using Structured Outputs for Critical Operations

For operations where you **must** ensure tools are called:

```python
from models.tool_execution import PricingUpdateResult

# Create a specialized agent for this critical operation
pricing_agent = Agent(
    'gpt-5',
    deps_type=OrchestratorDeps,
    output_type=PricingUpdateResult,  # Force structured output
    instructions='''
    You MUST actually update product pricing using execute_bash.
    Return the PricingUpdateResult with proof of execution:
    - products_updated: IDs of products you modified
    - update_commands_executed: Exact bash commands you ran
    - verification_results: Results from fetching updated product
    '''
)

result = await pricing_agent.run("Update product X to $99", deps=deps)

# Type-safe access to verified data
assert len(result.products_updated) > 0  # Must have updated something
assert len(result.update_commands_executed) > 0  # Must have run commands
```

## Testing the Guardrails

### Test Case 1: Role-Playing Detection

```python
# This should be caught by the validator
response = await orchestrator.orchestrate(
    "Update price for product X to $99",
    state=conversation_state
)

# If model tried to role-play:
# - Validator catches it
# - Raises ModelRetry with specific message
# - Model retries with corrected behavior
# - Should ultimately succeed with actual tool calls
```

### Test Case 2: Monitoring Statistics

```python
from utils.tool_call_monitor import get_monitor

monitor = get_monitor()

# Run several operations
for i in range(10):
    await orchestrator.orchestrate(f"Task {i}", state)

# Check statistics
stats = monitor.get_stats()
print(f"Total runs: {stats['total_runs']}")
print(f"Total tool calls: {stats['total_tool_calls']}")
print(f"Suspicious runs: {stats.get('suspicious_runs', 0)}")

# Investigate suspicious runs
suspicious = monitor.get_suspicious_runs()
for run in suspicious:
    print(f"Run {run.thread_id}: Output without tools!")
    print(f"  Duration: {run.total_duration_ms}ms")
```

## Monitoring and Alerts

### Production Monitoring

Integrate with your observability stack:

```python
from utils.tool_call_monitor import get_monitor
import logfire  # or your monitoring service

monitor = get_monitor()

# Periodic check (every 5 minutes)
async def check_guardrails():
    stats = monitor.get_stats()

    if stats.get('suspicious_runs', 0) > 0:
        # Alert
        logfire.error(
            "tool_calling_guardrail_violation",
            suspicious_count=stats['suspicious_runs'],
            total_runs=stats['total_runs'],
            violation_rate=stats['suspicious_runs'] / stats['total_runs']
        )

        # Get details
        suspicious_runs = monitor.get_suspicious_runs(limit=5)
        for run in suspicious_runs:
            logfire.warn(
                "suspicious_run_details",
                thread_id=run.thread_id,
                duration_ms=run.total_duration_ms,
                had_output=run.output_generated
            )
```

### Metrics to Track

- **Violation Rate**: `suspicious_runs / total_runs`
- **Tool Call Rate**: `total_tool_calls / total_runs`
- **Retry Rate**: Count of `ModelRetry` exceptions
- **Success Rate**: Runs that complete without violations

## Troubleshooting

### Model Still Role-Playing Despite Guardrails

**For the orchestrator (relies on Layer 1 only):**

1. **Check system prompt is being used:**
   - Verify `_get_system_prompt()` includes anti-role-playing instructions in `backend/agents/orchestrator.py`
   - Look for the `## ⚠️ TOOL EXECUTION DISCIPLINE (CRITICAL)` section
   - Check logs for prompt content

2. **Strengthen system prompt:**
   - Add more explicit examples of wrong vs. right behavior
   - Include specific use cases relevant to your domain
   - Make the consequences clear (tool calls are visible)

3. **Consider using structured outputs:**
   - For critical operations, create specialized agents with `output_type`
   - Forces the model to provide proof of execution
   - See Layer 3 documentation above

**For specialized agents (with validators):**

1. **Check validator is registered:**
   - Look for `@agent.output_validator` decorator
   - Verify no exceptions during validator registration
   - Check that agent does NOT have custom `output_type`

2. **Increase max_retries:**
   ```python
   config = AgentConfig(
       name="specialist",
       max_retries=2,  # Allow more retries
       ...
   )
   ```

3. **Add more specific phrases to validator:**
   ```python
   role_play_phrases = [
       "i will call",
       "your_specific_pattern_here",
       ...
   ]
   ```

### High Retry Rate

If the model is retrying too often:

1. **Strengthen system prompt** - be more explicit
2. **Use examples** - show correct vs. incorrect behavior
3. **Try different model** - some models follow instructions better
4. **Add structured outputs** - force compliance via schema

### False Positives

If legitimate output is being flagged:

1. **Review flagged phrases** - may need to refine detection
2. **Add exceptions** - for specific contexts where phrases are OK
3. **Adjust validator logic** - be more surgical in detection

## Summary

The four-layer approach provides defense-in-depth:

1. **System Prompt** - Primary instruction (used on orchestrator)
2. **Result Validator** - Catches violations, forces retry (specialized agents only, not orchestrator)
3. **Structured Outputs** - Forces proof of execution (optional, for critical operations)
4. **Event Monitoring** - Detects patterns, provides metrics (optional, for production observability)

**Important:** Pydantic AI does not allow using both output validators and custom `output_type` on the same agent. Since the orchestrator needs flexibility for custom output types, it uses only Layer 1 (system prompt). Specialized agents can use Layer 2 (validators) OR Layer 3 (structured outputs), but not both.

**Result:** LLM cannot complete tasks without actually calling tools.

**Monitoring:** Real-time detection of violations with detailed metrics.

**Recovery:** Automatic retry with specific feedback to the model (for agents with validators).
