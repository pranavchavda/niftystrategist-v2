# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI-powered trading assistant for the Indian stock market (NSE/BSE). Forked from EspressoBot (e-commerce AI assistant) — kept core infrastructure (auth, chat, memory, AG-UI streaming), replaced domain tools with trading (Upstox).

**Key Principles**: Maximum agent autonomy for analysis; HITL approval only for actual transactions; educational tone for non-technical users; memory system for personalization.

**Upstox Integration**: Not a registered multi-user Upstox app (requires separate approval). The app owner's (Pranav's) Upstox credentials are in `.env`. Other users must enter their own Upstox API key and secret via the Settings page (`/settings` → Trading Settings → Upstox API Credentials), which are stored encrypted per-user in the DB.

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
- **Service**: `niftystrategist` systemd unit, runs as `deploy` user, root needed for restart

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
| `nf-order` | Place/cancel/list orders (--dry-run supported) |
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

**Trigger types:** price, indicator (RSI/SMA/EMA/MACD), time, order_status, compound (AND/OR).
**Action types:** place_order, cancel_order, cancel_rule.
**OCO pairs:** Linked stop-loss + target rules where one firing disables the other.

**Daemon deployment (TODO):**
- Needs its own systemd unit (separate from the FastAPI service)
- Currently started manually via `nf-monitor start`
- Token loading: daemon should load Upstox access tokens from the DB (encrypted in `users` table) on each poll cycle, not via manual `set_access_token()` calls
- Upstox tokens expire daily (end of trading day) and **cannot be refreshed silently** — users must re-authenticate via OAuth each morning. Daemon skips users with expired/missing tokens.

**API datetime gotcha:** Frontend sends ISO strings with `Z` (timezone-aware). The `_strip_tz()` helper in `api/monitor.py` strips tzinfo before DB insert since columns are naive TIMESTAMP.

## Key Gotchas

- **Supabase requires Cloudflare WARP** on this machine (IPv6-only free tier, no public IPv6). Run `warp-cli connect` before starting backend.
- **Dev auth user_id=999** must exist in the DB for dev tokens to work.
- **Upstox API quirk**: `PlaceOrderV3Request` requires `disclosed_quantity=0`, `trigger_price=0`, `is_amo=False` even for basic orders.
- **Upstox is NOT multi-user approved** — the default `.env` credentials only work for the app owner. Other users must enter their own API key/secret in Settings, stored encrypted per-user.
- **`tools/trading/`** directory is DEPRECATED — kept for reference only. Active tools are in `cli-tools/`.
- **Never push to git** without user testing and confirmation first.
