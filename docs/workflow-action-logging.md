# Workflow Action Logging

## Overview

Complete audit trail for tool calls and actions executed during workflow runs (awakenings, automations, scheduled events).

**Problem it solves:** When autonomous awakenings execute `nf-order` or other tools, the execution was only visible in server logs. Now it's tracked in the database for easy querying and debugging.

**Example use case:** User reports "ADANIPOWER closed but I didn't do it" → Query `/api/workflows/actions/run/{workflow_id}` to see exactly which tool was called and when.

## Components

### 1. Database Schema
**Table:** `workflow_action_logs`

Tracks every tool invocation during a workflow run:
- `workflow_run_id` - Links to the workflow run
- `tool_name` - Name of tool ('nf-order', 'nf-portfolio', 'nf-analyze', etc.)
- `tool_args` - Arguments passed (JSON, includes command and parameters)
- `tool_result` - Output from tool execution (JSON)
- `execution_status` - 'success', 'failed', 'pending'
- `sequence_order` - Order of execution within the workflow
- `agent_reasoning` - Why the agent called this tool
- `market_context` - Market state at time of execution (optional)
- `duration_ms` - Execution time
- `started_at`, `completed_at` - Timestamps

### 2. ORM Model
**File:** `backend/database/models.py`

```python
class WorkflowActionLog(Base):
    """Log of tool calls executed during workflow runs"""
    # workflow_run_id, user_id, tool_name, tool_args, tool_result, etc.
```

### 3. Logging Service
**File:** `backend/services/workflow_action_logger.py`

Provides helper class for logging:

```python
logger = WorkflowActionLogger(session, workflow_run_id, user_id)

# Log a tool call
await logger.log_tool_call(
    tool_name="nf-order",
    tool_args={"command": "buy ADANIPOWER 487 --product I"},
    tool_result={"order_id": "260313000036772", "status": "PENDING"},
    execution_status="success",
    agent_reasoning="Entering short position based on RSI overbought signal",
    market_context={"ltp": 150.4, "rsi": 71.2}
)

# Or use specialized order logging
await logger.log_order_placement(
    symbol="ADANIPOWER",
    action="buy",
    quantity=487,
    upstox_order_id="260313000036772",
    agent_reasoning="Covering short at profit target",
)
```

### 4. API Endpoints
**File:** `backend/api/workflow_actions.py`

Register in `main.py`:
```python
from api.workflow_actions import router as workflow_actions_router
app.include_router(workflow_actions_router)
```

**Available endpoints:**
- `GET /api/workflows/actions/run/{workflow_run_id}` - All actions for a specific run
- `GET /api/workflows/actions/user/recent?limit=50&tool_name=nf-order` - Recent actions
- `GET /api/workflows/actions/symbol/{symbol}` - All actions involving a symbol

Example response:
```json
{
  "workflow_run_id": 264,
  "action_count": 5,
  "actions": [
    {
      "id": 1001,
      "sequence": 1,
      "tool": "nf-portfolio",
      "args": {"command": "python cli-tools/nf-portfolio --position ADANIPOWER --json"},
      "status": "success",
      "result": {"quantity": 487, "avg_price": 149.76, ...},
      "reasoning": "Check current position",
      "started_at": "2026-03-13T04:39:03Z",
      "duration_ms": 245
    },
    {
      "id": 1002,
      "sequence": 2,
      "tool": "nf-order",
      "args": {"command": "nf-order buy ADANIPOWER 487 --product I"},
      "status": "success",
      "result": {"order_id": "260313000036772", "status": "PENDING"},
      "reasoning": "Cover short position at resistance level",
      "started_at": "2026-03-13T04:39:03Z",
      "duration_ms": 2100
    }
  ]
}
```

## Integration into Workflow Engine

**File to modify:** `backend/services/workflow_engine.py`

In `execute_custom_workflow()`:

```python
async def execute_custom_workflow(
    user_id: int,
    workflow_def: WorkflowDefinition,
    session: AsyncSession,
):
    # ... existing setup code ...

    # Create workflow run
    workflow_run = WorkflowRun(...)
    session.add(workflow_run)
    await session.flush()

    # Initialize action logger
    action_logger = WorkflowActionLogger(session, workflow_run.id, user_id)

    # Pass to orchestrator via context
    deps = OrchestratorDeps(
        is_awakening=True,
        action_logger=action_logger,  # NEW
        # ... other deps ...
    )

    # Run agent
    orchestrator = await get_orchestrator_for_model(model_id, user_id=user_id)
    result = await orchestrator.run(prompt, deps=deps)

    # Workflow run completed, logs are already saved
```

## Integration into Orchestrator

**File to modify:** `backend/agents/orchestrator.py`

In `execute_bash()` method:

```python
async def execute_bash(self, command: str) -> str:
    logger.info(f"Executing bash command: {command}")

    # Log the action if we're in a workflow
    if self.deps and self.deps.action_logger:
        import time
        start = time.time()

    try:
        result = await run_command(command)

        if self.deps and self.deps.action_logger:
            duration = int((time.time() - start) * 1000)

            # Parse tool name from command
            tool_name = command.split()[3] if len(command.split()) > 3 else "bash"

            await self.deps.action_logger.log_tool_call(
                tool_name=tool_name,
                tool_args={"command": command},
                tool_result={"output": result},
                execution_status="success",
                duration_ms=duration,
            )

        return result

    except Exception as e:
        if self.deps and self.deps.action_logger:
            await self.deps.action_logger.log_tool_call(
                tool_name=tool_name,
                tool_args={"command": command},
                execution_status="failed",
                error_message=str(e),
            )
        raise
```

## Migration Steps

1. **Run migration:**
   ```bash
   # Apply migration to Supabase
   psql postgresql://... < backend/migrations/017_add_workflow_action_logs.sql
   ```

2. **Update ORM:** Already done in `models.py`

3. **Add service:** Already created at `backend/services/workflow_action_logger.py`

4. **Add API routes:** Already created at `backend/api/workflow_actions.py`

5. **Register routes in main.py:**
   ```python
   from api.workflow_actions import router as workflow_actions_router
   app.include_router(workflow_actions_router)
   ```

6. **Update OrchestratorDeps:** Add `action_logger: Optional[WorkflowActionLogger] = None`

7. **Integrate logging in orchestrator.py** and workflow_engine.py (see above)

## Example: Investigating the ADANIPOWER Close

**Problem:** Trade closed at 10:09 IST but no clear record of who/what closed it.

**Before:** Only visible in server logs (difficult to query)

**After:**
```bash
# Query the workflow run
curl -X GET "http://localhost:8000/api/workflows/actions/run/264" \
  -H "Authorization: Bearer {token}"

# Returns:
{
  "workflow_run_id": 264,
  "action_count": 3,
  "actions": [
    {
      "sequence": 1,
      "tool": "nf-portfolio",
      "status": "success",
      "reasoning": "Check ADANIPOWER position"
    },
    {
      "sequence": 2,
      "tool": "nf-order",
      "args": {"command": "nf-order buy ADANIPOWER 487 --product I"},
      "status": "success",
      "result": {"order_id": "260313000036772"},
      "reasoning": "Cover short at ₹150.4 - loss capped at -₹311.68",
      "started_at": "2026-03-13T04:39:03Z"
    }
  ]
}
```

**Clear answer:** The orchestrator agent called `nf-order buy ADANIPOWER 487` at 04:39:03 UTC during the autonomous awakening, with reasoning "Cover short at ₹150.4".

## Benefits

✅ **Transparency:** See exactly what agent did during each awakening
✅ **Debugging:** Trace execution order and reasoning for each tool call
✅ **Accountability:** Audit trail for autonomous trading decisions
✅ **Queryable:** API endpoints to search by workflow, symbol, tool, etc.
✅ **Performance:** Minimal overhead (async logging, indexed queries)

## Future Enhancements

- Real-time dashboard showing action logs as awakenings execute
- Webhook notifications for specific tool calls (e.g., all nf-order calls)
- Export action logs for external audit/compliance
- Rollback capability (undo recent orders based on log sequence)
