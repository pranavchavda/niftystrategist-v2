# Mid-Run Steering — Port from EspressoBot

## What It Does

Users can send guidance to the orchestrator while it's mid-tool-chain, without stopping or restarting. The agent sees the message before its next model call and pivots accordingly.

**Before:** User watches agent go wrong direction → cancels → restarts → loses all progress.
**After:** User types redirect → agent sees it → pivots → keeps completed work.

## How It Works

### Architecture

```
User types steer → POST /api/agent/steer → InterruptSignal._steering_messages queue
                                              ↓
  before_tool_execute hook: pending steerings? → raise RuntimeError (skip tool)
                                              ↓
  before_model_request hook: consume steerings → inject as UserPromptPart → model pivots
```

### Key Mechanism: Two-Layer Interception

1. **`before_tool_execute` hook** — If steering is pending when a tool is about to run, raises RuntimeError to skip it. This prevents the model from blindly executing remaining tools from a stale plan.

2. **`before_model_request` hook** — Consumes all pending steerings, formats them as `[URGENT STEERING...]`, appends as `ModelRequest(parts=[UserPromptPart(...)])` to `request_context.messages`. Model sees the guidance on its next inference call.

The two layers are needed because models can emit multiple tool calls in one response. Without the tool-blocking layer, all planned tools execute before the model gets a chance to see the steering.

**Known limitation:** When there's only a single tool call, the tool executes before `before_tool_execute` can block the *next* tool (there is none). The steering is picked up on the next `before_model_request` after that tool completes. This is acceptable — the latency equals the single tool's runtime.

### Steering Message Framing

```python
steering_content = (
    f"[URGENT STEERING — The user has redirected you mid-task. "
    f"STOP your current plan. Follow this new direction immediately. "
    f"Discard any pending steps that no longer apply. "
    f"The user's latest guidance OVERRIDES your previous plan.]\n\n{combined}"
)
```

Soft framing ("adjust accordingly, don't discard work") was tested and failed — model ignored it. The forceful framing above works.

## Files Changed (EspressoBot Reference)

### Backend

**`backend/utils/interrupt_manager.py`** — InterruptSignal extended:
```python
# New fields on InterruptSignal.__init__:
self._steering_messages: List[str] = []
self._steering_lock = asyncio.Lock()

# New methods on InterruptSignal:
async def add_steering(self, message: str)      # Queue a message
async def consume_steerings(self) -> List[str]   # Pop all pending (called from hook)
def has_pending_steerings(self) -> bool           # Non-blocking check

# New method on InterruptManager:
async def steer(self, thread_id: str, message: str) -> bool  # Queue on active signal
```

**`backend/agents/orchestrator.py`** — Two hooks modified in `_get_capabilities()`:

1. `before_model_request` — check `signal.has_pending_steerings()`, consume, inject as UserPromptPart
2. `before_tool_execute` — check `signal.has_pending_steerings()`, raise RuntimeError to skip tool

**`backend/main.py`** — New endpoint:
```python
@app.post("/api/agent/steer")
async def agent_steer(request: Request, user: User = Depends(...)):
    # Accept { threadId, message }
    # Call interrupt_mgr.steer(thread_id, message)
    # With run_id fallback lookup (same pattern as /api/agent/interrupt)
```

**`backend/utils/sse_events.py`** — New event:
```python
SSEEventEmitter.steer_acknowledged(message: str) -> str
# Emits STEER_ACKNOWLEDGED event type
```

### Frontend

**`frontend-v2/app/components/ChatInput.jsx`**:
- New prop: `onSteer` callback
- Textarea stays enabled during `isLoading` (placeholder changes to "Steer the agent...")
- Enter key during loading calls `onSteer(value.trim())` instead of `onSubmit()`
- Form submit during loading also routes to `onSteer`
- Button area: shows stop button + amber Navigation icon steer button when `isLoading && value.trim()`

**`frontend-v2/app/views/ChatView.jsx`**:
- New `handleSteer(text)` — POST to `/api/agent/steer`, adds message to chat with `isSteering: true`
- Passes `onSteer={handleSteer}` to ChatInput

**`frontend-v2/app/components/MessageBubble.jsx`**:
- Detects `message.isSteering === true`
- Amber left border + amber background tint
- Label shows "Steering" instead of "You"

## Implementation Notes for NiftyStrategist

- The codebase is forked from EspressoBot so file paths and patterns should match closely
- InterruptSignal/InterruptManager are in `backend/utils/interrupt_manager.py` (same location)
- Orchestrator hooks are in `_get_capabilities()` in `backend/agents/orchestrator.py`
- The interrupt endpoint pattern is in `backend/main.py` — search for `/api/agent/interrupt` and add `/api/agent/steer` after it
- Frontend components are the same: ChatInput.jsx, ChatView.jsx, MessageBubble.jsx
- EspressoBot commit: `6dfd379` (initial) + `17a6808` (fix: strengthen steering)
