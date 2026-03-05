# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI-powered trading assistant for the Indian stock market (NSE/BSE). Forked from EspressoBot (e-commerce AI assistant) — kept core infrastructure (auth, chat, memory, AG-UI streaming), replaced domain tools with trading (Upstox).

**Key Principles**: Maximum agent autonomy for analysis; HITL approval only for actual transactions; educational tone for non-technical users; memory system for personalization.

**Upstox Integration**: Not a registered multi-user Upstox app (requires separate approval). The app owner's (Pranav's) Upstox credentials are in `.env`. Other users must enter their own Upstox API key and secret via the Settings page (`/settings` → Trading Settings → Upstox API Credentials), which are stored encrypted per-user in the DB.

**TOTP Auto-Refresh**: Upstox tokens expire daily (~3:30 AM IST) and SEBI regulations prevent refresh tokens. Users can optionally save TOTP credentials (mobile, PIN, TOTP secret) in Settings to enable automatic token refresh via the `upstox-totp` library. `get_user_upstox_token()` in `api/upstox_oauth.py` handles expiry detection and auto-refresh for all callers (chat, dashboard, daemon, CLI). 30-minute cooldown after failed attempts. DB migration: `015_add_totp_credentials.sql`.

## Development Commands

```bash
# Start both backend + frontend (recommended)
./dev.sh

# Backend only / frontend only
./dev.sh --backend-only
./dev.sh --frontend-only

# Manual backend start
cd backend && source venv/bin/activate && uvicorn main:app --reload --port 8000

# Manual frontend start
cd frontend-v2 && pnpm install && pnpm run dev
```

**Frontend uses pnpm, not npm.** Node 22+ required (dev.sh handles via nvm).

## Deployment

- **CI/CD**: Push to `main` auto-deploys via GitHub Actions (`.github/workflows/deploy.yml`)
- **Manual**: `./deploy/deploy.sh <server-ip>` — builds frontend, rsyncs to prod, restarts service
- **Production server**: `172.105.40.112` — Caddy reverse proxy → uvicorn on port 8000
- **Prod path**: `/opt/niftystrategist/` (backend at `/opt/niftystrategist/backend/`, venv inside)
- **Service**: `niftystrategist` systemd unit, runs as `deploy` user, root needed for restart
- **SSH**: `ssh deploy@172.105.40.112`

## Architecture

```
Frontend (React Router v7 + Vite + Tailwind)
    ↕ SSE (AG-UI protocol)
FastAPI Backend
    ├── Orchestrator Agent (Pydantic AI)
    │   ├── execute_bash → CLI tools (nf-quote, nf-analyze, etc.)
    │   ├── call_agent → web_search, vision
    │   └── HITL → trade approval
    ├── 15+ API routers (conversations, cockpit, notes, upstox_oauth, etc.)
    ├── Services (upstox_client, technical_analysis, encryption)
    └── Supabase PostgreSQL (asyncpg + SQLAlchemy)
```

### Agent System

- **Orchestrator** (`agents/orchestrator.py`, ~3700 lines): Main agent using Pydantic AI. Interprets user intent, calls CLI tools via `execute_bash`, delegates to sub-agents via `call_agent`. System prompt documents all CLI tools.
- **Base Agent** (`agents/base_agent.py`): Abstract base class. Supports 4 LLM providers: Anthropic (Claude with 12K thinking budget), OpenRouter (DeepSeek, Gemini, Grok), Gateway (Pydantic AI Gateway), OpenAI (GPT-5).
- **Sub-agents**: `web_search` and `vision` only. Registered at startup in `main.py`.
- **Default model**: `glm-5` (configured in `config/models.py`).

### CLI Tools (How Trading Works)

All trading operations use CLI scripts in `backend/cli-tools/`, invoked by the orchestrator via `execute_bash`. This replaced 15+ registered Pydantic AI tools to save ~3-4K tokens of schema overhead per request.

| Tool | Purpose |
|------|---------|
| `nf-market-status` | NSE market open/closed, time to next event |
| `nf-quote` | Live quotes, historical OHLCV, list symbols |
| `nf-analyze` | Technical analysis (RSI, MACD, signals), comparison |
| `nf-portfolio` | Holdings, positions, position size calculator |
| `nf-funds` | Available margin, buying power, segment-wise funds |
| `nf-profile` | User profile, active segments, exchanges |
| `nf-trades` | Today's trades, historical trade P&L, charges breakdown |
| `nf-brokerage` | Pre-trade brokerage & charges estimate |
| `nf-order` | Place/cancel/list orders (--dry-run supported) |
| `nf-options` | Option chain, live chain with greeks, option greeks (v3 API), buy/sell |
| `nf-watchlist` | Watchlist CRUD with price alerts |
| `nf-monitor` | Monitor rule CRUD, list/enable/disable/delete rules |

Conventions: `--json` for structured output, `--help` on every tool, `--dry-run` for orders. Subprocess env vars: `NF_ACCESS_TOKEN`, `NF_USER_ID`. CWD is `backend/`.

### Streaming & HITL

- **AG-UI**: `utils/ag_ui_wrapper.py` — SSE event stream with HITL event merging. The `enhanced_ag_ui_stream()` function merges the Pydantic AI stream with a separate HITL poller task (100ms intervals).
- **HITL**: `utils/hitl_streamer.py` — pauses agent execution for user approval on `place_order` and `cancel_order`.

### Database Patterns

**Critical**: All datetime columns are `TIMESTAMP WITHOUT TIME ZONE`. Always use `utc_now()` from `database/models.py` or `datetime.utcnow()`. **Never** use `datetime.now(timezone.utc)`.

**Session patterns** (in `database/session.py`):
- FastAPI routes: `Depends(get_db)` — yields session via dependency injection
- Background tasks / MCP: `async with get_db_context() as session:` — context manager
- Direct use: `async with get_db_session() as session:` — returns AsyncSessionLocal

**Key models** (`database/models.py`): User, Conversation, Message, Memory, Trade, WatchlistItem, AgentDecision, Note, UserMCPServer, MonitorRule, MonitorLog.

### Auth

- JWT-based, 7-day expiry (`auth.py`)
- **Dev tokens**: Prefix `dev-token-*` returns hardcoded user_id=999
- **Terminal requests**: `x-terminal-request` header returns user_id=2
- Permission-based: `requires_permission("chat.access")` decorator for routes

### Memory System

Semantic search via OpenAI embeddings. Injects top 10 matched memories per query. Categories: `risk_tolerance`, `position_sizing`, `sector_preference`, `trading_style`, `avoid_list`, `past_learnings`, `communication`, `experience_level`, `schedule`.

## Environment Variables

Required in `backend/.env`:
```
DATABASE_URL=postgresql://...        # Supabase PostgreSQL
OPENROUTER_API_KEY=sk-or-...         # LLM provider
JWT_SECRET=...                       # Auth
ENCRYPTION_KEY=...                   # Fernet key for Upstox token encryption
UPSTOX_API_KEY=...                   # Default Upstox app credentials (owner's)
UPSTOX_API_SECRET=...                # Other users provide their own via Settings page
UPSTOX_REDIRECT_URI=http://localhost:5173/auth/upstox/callback
```

### Trade Monitor (IFTTT-style rules engine)

Background daemon that evaluates user-defined rules against live market data and executes actions automatically.

```
FastAPI (web)                    MonitorDaemon (separate process)
├── REST API: /api/monitor/*     ├── Polls DB for active rules (30s)
├── Rule Builder UI: /monitor    ├── Opens Upstox WebSocket streams
└── Symbol search autocomplete   ├── Evaluates triggers on each tick
                                 └── Fires actions (place/cancel orders)
```

**Key files:**
- Rule engine: `backend/monitor/` (rule_evaluator, daemon, streams/, crud, models)
- REST API: `backend/api/monitor.py` (7 endpoints: rules CRUD, OCO, symbol search, logs)
- Frontend UI: `frontend-v2/app/routes/monitor.tsx` (Rule Builder with 3 tabs)
- CLI: `backend/cli-tools/nf-monitor`
- DB migration: `backend/migrations/014_add_monitor_tables.sql`
- Tests: `backend/tests/monitor/` (67+ tests)

**Trigger types:** price, indicator (RSI/SMA/EMA/MACD), time, order_status, compound (AND/OR), trailing_stop.
**Action types:** place_order, cancel_order, cancel_rule.
**OCO pairs:** Linked stop-loss + target rules where one firing disables the other.

**Daemon deployment (TODO):**
- Needs its own systemd unit (separate from the FastAPI service)
- Currently started manually via `nf-monitor start`
- Token loading: daemon loads Upstox access tokens from the DB (encrypted in `users` table) via `get_user_upstox_token()` on each poll cycle
- Upstox tokens expire daily (~3:30 AM IST). If TOTP credentials are configured, tokens auto-refresh silently via `upstox-totp` library. Otherwise users must re-authenticate via OAuth each morning. Daemon skips users with expired/missing tokens and no TOTP credentials.

**API datetime gotcha:** Frontend sends ISO strings with `Z` (timezone-aware). The `_strip_tz()` helper in `api/monitor.py` strips tzinfo before DB insert since columns are naive TIMESTAMP.

## Thread Compaction (In-Place Context Compression)

Unlike forking (which creates a new thread), compaction replaces all messages in the **same thread** with a single compressed summary. This preserves the thread ID so bookmarks, awakening rules, and monitor links remain valid.

**Two modes:**
1. **Manual** — User clicks "Compact Thread" in the Actions dropdown. Confirmation dialog warns it's irreversible.
2. **Auto-compaction** — Triggers automatically after a thread exceeds 100 messages (~50 user+assistant pairs). Fires as a background task after assistant message save, with a 1-hour cooldown to prevent rapid re-compaction.

**How it works:**
1. `POST /api/conversations/{id}/compact` (manual) or `_auto_compact_conversation()` (auto) loads all messages
2. Generates summary via the same hybrid LLM→TOON pipeline used for fork (`create_hybrid_fork_summary()` in `toon_converter.py`)
3. `ConversationOps.compact_conversation()` deletes all messages and inserts a single system message with the summary
4. Sets `last_compacted_at` on the conversation record
5. Frontend reloads the thread to show the compacted version

**Key files:**
- `backend/api/conversations.py` — `compact_conversation` endpoint + `check_auto_compaction_needed()` + `COMPACTION_THRESHOLD`
- `backend/database/operations.py` — `ConversationOps.compact_conversation()`
- `backend/main.py` — `_auto_compact_conversation()` background task, triggered from `save_assistant_message_to_db()`
- `frontend-v2/app/components/ActionsDropdown.jsx` — "Compact Thread" menu item
- `frontend-v2/app/views/ChatView.jsx` — `handleCompactThread()` + auto-compaction reload detection
- `backend/migrations/016_add_thread_compaction.sql` — `last_compacted_at` column

**Constants:** `COMPACTION_THRESHOLD = 100` (messages). Auto-compaction cooldown: 1 hour.

## Thread Awakening (Scheduled Follow-Ups)

Agents can schedule one-shot follow-ups bound to an existing conversation thread. When fired, the awakening loads the full thread history and runs the agent autonomously, writing the response back into the same thread.

**How it works:**
1. Orchestrator calls `schedule_followup` CLI tool → inserts a `workflow_definitions` row with `trigger_type=one_time`, `thread_id`, and a scheduled datetime
2. APScheduler (started in `main.py` lifespan) fires the job via `POST /api/workflows/followup/activate/{workflow_id}` on localhost (no JWT required)
3. `execute_custom_workflow()` in `workflow_engine.py` detects `workflow_def.thread_id`, loads message history via `_load_thread_messages()`, runs the orchestrator with that history, and writes the result back via `_write_followup_to_thread()`
4. Frontend `MessageBubble.jsx` shows an "Auto follow-up" badge for messages with `extra_metadata.auto_followup`

**Key files:**
- `backend/services/workflow_engine.py` — `execute_custom_workflow()`, `_load_thread_messages()`, `_write_followup_to_thread()`
- `backend/cli-tools/automations/schedule_followup.py` — CLI tool the orchestrator calls
- `backend/routes/workflows.py` — `/api/workflows/followup/activate/{id}` endpoint
- `backend/database/models.py` — `WorkflowConfig`, `WorkflowRun`, `WorkflowDefinition` ORM models (with `thread_id` FK)

**Migrations applied (Supabase):**
- `backend/migrations/add_workflow_tables.sql`
- `backend/migrations/add_workflow_definitions.sql`
- `backend/migrations/add_scheduled_at.sql`
- `backend/migrations/add_thread_id_to_workflow_definitions.sql`

**pydantic-ai version note:** As of 2026-02-26, running pydantic-ai 1.47.0 (upgraded from 1.39.0). `TextPart` positional arg used (not `text=` kwarg) to stay version-agnostic.

**Critical bugs fixed in awakenings (2026-02-27):**
- **Use `agent.run()`, NOT `stream_text()`**: `stream_text()` only captures the first model response and misses all tool calls and subsequent turns. `agent.run()` completes the full tool-call loop. See `workflow_engine.py`.
- **Use `get_orchestrator_for_model()`, NOT bare `OrchestratorAgent()`**: The bare constructor doesn't register sub-agents (`web_search`, `vision`). Always call `await get_orchestrator_for_model(model_id, user_id=user_id)` from `main.py`.
- **Use `get_user_upstox_token(user.id)`, NOT `user.upstox_access_token`**: The raw DB field is an encrypted blob. `get_user_upstox_token()` handles decrypt + expiry + TOTP refresh.
- **Validate_tool_claims must NOT raise `ModelRetry`**: Raising ModelRetry from an output validator causes duplicate assistant messages in DB (via ResponseCapture). Demote to a log warning only.

**Mandate-based pre-approval for autonomous awakenings (2026-02-27):**
The HITL render_ui confirmation is useless during awakenings (no user to click). Added `is_awakening: bool = False` to `OrchestratorDeps`. `workflow_engine.py` sets it `True`. When `is_awakening=True`, `_register_dynamic_instructions()` injects a `## 🤖 AUTONOMOUS AWAKENING MODE` section into the system prompt that:
- Tells the agent the user is not present and cannot click UI buttons
- Instructs it to look for a previously-approved trading mandate in the conversation history (`[User clicked 'approve_trade']` + mandate details)
- Permits executing `nf-order` directly without a render_ui card when a mandate is found
- Lists what must still be checked (day P&L, mandate bounds, market hours, cutoff time)
- Explicitly overrides SAFETY-1 for that awakening session
This allows a user to pre-approve a bounded trading mandate once via HITL and have awakenings operate within that mandate autonomously.

**APScheduler timezone gotcha:** Server runs in EST; naive UTC datetimes stored in `scheduled_at` are interpreted as EST by APScheduler (5-hour offset). `_get_trigger()` also returns `None` for past `scheduled_at` times. For testing, set `scheduled_at` to local system time + a small delta rather than a UTC future time.

## Deploy Pipeline

`.github/workflows/deploy.yml` uses **uv** (Rust-based pip replacement) for `pip install`, which is 10-100x faster than plain pip for large requirement sets. The venv is created with plain Python but deps installed via `pip install -q uv && uv pip install -r requirements.txt`.

## Key Gotchas

- **Supabase requires Cloudflare WARP** on this machine (IPv6-only free tier, no public IPv6). Run `warp-cli connect` before starting backend.
- **Dev auth user_id=999** must exist in the DB for dev tokens to work.
- **Upstox API quirk**: `PlaceOrderV3Request` requires `disclosed_quantity=0`, `trigger_price=0`, `is_amo=False` even for basic orders.
- **Upstox is NOT multi-user approved** — the default `.env` credentials only work for the app owner. Other users must enter their own API key/secret in Settings, stored encrypted per-user.
- **`tools/trading/`** directory is DEPRECATED — kept for reference only. Active tools are in `cli-tools/`.
- **Never push to git** without user testing and confirmation first.
