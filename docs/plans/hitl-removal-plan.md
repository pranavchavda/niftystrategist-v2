# HITL Programmatic Infrastructure Removal Plan

**Status:** Deferred (researched 2026-03-06, not yet executed)

## Context

NS has two overlapping trade confirmation systems:

1. **`render_ui` (system prompt based)** — The agent shows a confirmation card via `render_ui` before placing orders. The user clicks approve/cancel. This is the **active** system and should be kept. It's overridable per-user via system prompt (e.g., awakening mandates bypass it).

2. **Programmatic HITL (vestigial)** — A full approval infrastructure from EspressoBot that gates `execute_bash`, `write_file`, and `edit_file` behind a programmatic approval flow. Controlled by `hitl_enabled` boolean on `user_preferences` DB table. **Never actually used in production** — `hitl_enabled` defaults to `False` and no user has enabled it. Should be removed.

## Files to Delete

| File | Purpose |
|------|---------|
| `backend/utils/hitl_manager.py` | Singleton approval manager (request/respond/cancel/timeout) |
| `backend/utils/hitl_decorator.py` | `@requires_approval` decorator for tool functions |
| `backend/utils/hitl_streamer.py` | SSE event queue for streaming HITL events to frontend |
| `backend/utils/stream_merger.py` | Merges HITL event poller with main AG-UI stream |
| `backend/routes/hitl.py` | API endpoints: `POST /api/hitl/respond`, `/cancel`, `GET /pending` |
| `frontend-v2/app/components/HITLToggle.jsx` | Toggle component in actions dropdown |
| `frontend-v2/app/components/ApprovalDialog.jsx` | Modal dialog for approve/reject |

## Files to Edit

### `backend/agents/orchestrator.py`
- Remove `hitl_enabled: bool = False` from `OrchestratorDeps` (line ~241)
- Remove HITL approval block in `execute_bash` (lines ~1565-1587)
- Remove HITL approval block in `write_file` (lines ~2951-2972)
- Remove HITL approval block in `edit_file` (lines ~3029-3049)

### `backend/main.py`
- Remove HITL preference loading block (lines ~2130-2145)
- Remove `hitl_enabled=hitl_enabled` from `OrchestratorDeps()` construction (line ~2189)
- Remove `hitl_enabled` from log metadata dicts (lines ~2210, 2219)
- Remove `hitl.router` from router includes (line ~816)
- Remove `hitl` from import (line ~787)

### `backend/utils/ag_ui_wrapper.py`
- Remove HITL stream creation (lines ~50-53)
- Remove `hitl_event_poller` async generator (lines ~56-74)
- Remove HITL event handling in merge loop (lines ~83-101)
- Remove HITL stream cleanup (lines ~534-537)
- Replace `merge_streams()` usage with direct iteration over `original_stream`

### `backend/utils/sse_events.py`
- Remove 4 static methods: `hitl_approval_request`, `hitl_approved`, `hitl_rejected`, `hitl_timeout` (lines ~104-137)

### `backend/routes/auth_routes.py`
- Remove `PATCH /api/auth/preferences/hitl` endpoint (lines ~77-114)
- Remove `hitl_enabled` from preferences GET response (line ~65)
- Remove `hitl_enabled` from default `UserPreference` creation (line ~57)

### `backend/database/models.py`
- Remove `hitl_enabled` column from `UserPreference` model (line ~330)
- Note: Don't drop the DB column immediately — just stop reading/writing it. Can clean up with a migration later.

### `backend/config/logfire_config.py`
- Remove `hitl_enabled` from log metadata (lines ~264-265)

### `frontend-v2/app/views/ChatView.jsx`
- Remove `HITLToggle` import (line ~19)
- Remove HITL approval state variables (line ~81)
- Remove HITL SSE event handling: `HITL_APPROVAL_REQUEST`, `HITL_APPROVED`, `HITL_REJECTED`, `HITL_TIMEOUT` (lines ~1044-1069)
- Remove `handleApprove` / `handleReject` handlers (lines ~1595-1638)
- Remove `hitlComponent` prop passed to ActionsDropdown (line ~1939)
- Remove HITL Dialog render section (line ~1980)

### `frontend-v2/app/components/ActionsDropdown.jsx`
- Remove `hitlComponent` prop (line ~32)
- Remove "Approval Mode" toggle section (lines ~170-185)

### `frontend-v2/app/components/Settings.jsx`
- Remove `hitlEnabled` state (line ~49)
- Remove `fetchHITLPreference` effect (lines ~101-117)
- Remove `handleToggleHITL` handler (lines ~163-187)
- Remove HITL toggle UI section (lines ~658-680)

## Migration Note

The `hitl_enabled` column on `user_preferences` and the two migrations (`add_hitl_enabled.sql`, `set_hitl_default_true.sql`) can be left in place. Just stop reading/writing the column. A future migration can `DROP COLUMN` it.

## What Stays

- `render_ui` tool in orchestrator — the system-prompt-based confirmation card for trades
- SAFETY-1 rule in system prompt — "always show render_ui before placing/cancelling trades"
- Awakening mandate override — `is_awakening` flag bypasses render_ui when mandate is pre-approved
- The concept of per-user overridability via system prompt instructions (not DB flags)
