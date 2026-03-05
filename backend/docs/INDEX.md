# Nifty Strategist Backend Documentation

Documentation for the Nifty Strategist backend — an AI-powered trading assistant for the Indian stock market (NSE/BSE).

## Documentation

| Document | Description |
|----------|-------------|
| [Architecture](./architecture.md) | Backend architecture overview — agent system, CLI tools, streaming, database, auth |
| [API Endpoints](./api-endpoints.md) | Complete REST API reference — all 200+ endpoints across 20+ routers |
| [Upstox Integration](./upstox-integration.md) | OAuth flow, token management, daily expiry, TOTP auto-refresh, per-user credentials |
| [Monitor System](./monitor-system.md) | IFTTT-style trade monitor — triggers, actions, daemon, WebSocket streaming, OCO pairs |
| [CLI Tools](../cli-tools/INDEX.md) | Trading CLI tools reference (nf-quote, nf-order, nf-analyze, etc.) |
| [Code Execution Tool](./code_execution_tool.md) | Anthropic's CodeExecutionTool integration for in-conversation Python execution |
| [Tool Calling Guardrails](./TOOL_CALLING_GUARDRAILS.md) | Multi-layer system to ensure LLM executes tools rather than role-playing |

## Quick Reference

### Starting Development

```bash
# Start both backend + frontend
./dev.sh

# Backend only
./dev.sh --backend-only

# Manual backend
cd backend && source venv/bin/activate && uvicorn main:app --reload --port 8000
```

### Key Directories

```
backend/
|-- agents/         # Orchestrator + base agent (Pydantic AI)
|-- api/            # Core API routers (conversations, dashboard, monitor, upstox)
|-- routes/         # Additional routers (auth, admin, notes, workflows, etc.)
|-- cli-tools/      # Trading CLI scripts (nf-quote, nf-order, nf-analyze, etc.)
|-- monitor/        # Trade monitor daemon + rule engine
|-- database/       # Models, session management, operations
|-- services/       # Upstox client, technical analysis, encryption
|-- utils/          # AG-UI wrapper, HITL, encryption, tool monitor
|-- config/         # Model config, permissions
|-- migrations/     # SQL migration files
|-- tests/          # Test suites
```

### Common Tasks

| Task | Where to look |
|------|---------------|
| Add a new API endpoint | `api/` or `routes/`, register in `main.py` |
| Add a new CLI tool | `cli-tools/`, document in `cli-tools/INDEX.md` |
| Add a monitor trigger type | `monitor/models.py` + `monitor/rule_evaluator.py` |
| Debug Upstox token issues | `api/upstox_oauth.py` — `get_user_upstox_token()` |
| Modify the agent system prompt | `agents/orchestrator.py` — `_get_system_prompt()` |
| Add a new database model | `database/models.py`, create migration in `migrations/` |
| Debug AG-UI streaming | `utils/ag_ui_wrapper.py` |
| Debug HITL approval flow | `utils/hitl_streamer.py` + `routes/hitl.py` |

### Environment Variables

Required in `backend/.env`:
```
DATABASE_URL=postgresql://...
OPENROUTER_API_KEY=sk-or-...
JWT_SECRET=...
ENCRYPTION_KEY=<Fernet key>
UPSTOX_API_KEY=...
UPSTOX_API_SECRET=...
UPSTOX_REDIRECT_URI=http://localhost:5173/auth/upstox/callback
```

See also: project-level `CLAUDE.md` for comprehensive development guidance.
