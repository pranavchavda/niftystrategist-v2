# Backend Architecture

Nifty Strategist is an AI-powered trading assistant for the Indian stock market (NSE/BSE), built on FastAPI with a Pydantic AI agent system.

## High-Level Stack

```
Frontend (React Router v7 + Vite + Tailwind)
    | SSE (AG-UI protocol)
FastAPI Backend (uvicorn, port 8000)
    |-- Orchestrator Agent (Pydantic AI)
    |   |-- execute_bash -> CLI tools (nf-quote, nf-analyze, etc.)
    |   |-- call_agent -> web_search, vision sub-agents
    |   |-- HITL -> trade approval cards
    |-- 20+ API routers (conversations, dashboard, monitor, upstox, etc.)
    |-- Services (upstox_client, technical_analysis, encryption)
    |-- Monitor Daemon (separate process, WebSocket streaming)
    |-- Supabase PostgreSQL (asyncpg + SQLAlchemy)
```

## Agent System

### Orchestrator (`agents/orchestrator.py`, ~3700 lines)

The main agent using Pydantic AI. Interprets user intent, calls CLI tools via `execute_bash`, delegates to sub-agents via `call_agent`.

- Uses CLI tools instead of registered Pydantic AI tools (saves ~3-4K tokens of schema overhead per request)
- System prompt documents all CLI tools and their usage
- Supports multiple LLM providers via `base_agent.py`

### Base Agent (`agents/base_agent.py`)

Abstract base class for all agents. Supports 4 LLM providers:
- **Anthropic** (Claude with 12K thinking budget)
- **OpenRouter** (DeepSeek, Gemini, Grok)
- **Gateway** (Pydantic AI Gateway)
- **OpenAI** (GPT-5)

Default model: `glm-5` (configured in `config/models.py`).

### Sub-Agents

Only `web_search` and `vision`. Registered at startup in `main.py`.

## CLI Tools

All trading operations use CLI scripts in `backend/cli-tools/`, invoked by the orchestrator via `execute_bash`. See `cli-tools/INDEX.md` for full reference.

| Tool | Purpose |
|------|---------|
| `nf-market-status` | NSE market open/closed, time to next event |
| `nf-quote` | Live quotes, historical OHLCV, symbol search |
| `nf-analyze` | Technical analysis (RSI, MACD, signals), comparison |
| `nf-portfolio` | Holdings, positions, position size calculator |
| `nf-order` | Place/cancel/list orders (--dry-run supported) |
| `nf-watchlist` | Watchlist CRUD with price alerts |
| `nf-monitor` | Monitor rule CRUD, list/enable/disable/delete rules |

Conventions:
- `--json` for structured output on every tool
- `--help` for usage info on every tool
- `--dry-run` for orders (preview without executing)
- Subprocess env vars: `NF_ACCESS_TOKEN`, `NF_USER_ID`
- CWD is `backend/`

## Streaming & HITL

### AG-UI Protocol (`utils/ag_ui_wrapper.py`)

SSE event stream with HITL event merging. The `enhanced_ag_ui_stream()` function merges the Pydantic AI stream with a separate HITL poller task (100ms intervals).

### Human-in-the-Loop (`utils/hitl_streamer.py`)

Pauses agent execution for user approval on `place_order` and `cancel_order`. Renders approval cards in the frontend via AG-UI events.

**Awakening exception:** When `is_awakening=True` in `OrchestratorDeps`, the agent operates autonomously within pre-approved trading mandates (no HITL cards needed since no user is present).

## Database

### Connection

Supabase PostgreSQL via asyncpg + SQLAlchemy async sessions.

**Session patterns** (in `database/session.py`):
- FastAPI routes: `Depends(get_db)` — yields session via dependency injection
- Background tasks / MCP: `async with get_db_context() as session:` — context manager
- Direct use: `async with get_db_session() as session:` — returns AsyncSessionLocal

**Critical:** All datetime columns are `TIMESTAMP WITHOUT TIME ZONE`. Always use `utc_now()` from `database/models.py` or `datetime.utcnow()`. **Never** use `datetime.now(timezone.utc)`.

### Key Models (`database/models.py`)

User, Conversation, Message, Memory, Trade, WatchlistItem, AgentDecision, Note, UserMCPServer, MonitorRule, MonitorLog, WorkflowDefinition, WorkflowConfig, WorkflowRun.

## Auth System

- JWT-based, 7-day expiry (`auth.py`)
- **Dev tokens**: Prefix `dev-token-*` returns hardcoded user_id=999
- **Terminal requests**: `x-terminal-request` header returns user_id=2
- Permission-based: `requires_permission("chat.access")` decorator for routes

## Memory System

Semantic search via OpenAI embeddings. Injects top 10 matched memories per query into the orchestrator context.

Categories: `risk_tolerance`, `position_sizing`, `sector_preference`, `trading_style`, `avoid_list`, `past_learnings`, `communication`, `experience_level`, `schedule`.

## Thread Compaction

Replaces all messages in a thread with a single compressed summary (preserving thread ID for bookmarks, awakenings, and monitor links).

- **Manual:** User clicks "Compact Thread" in Actions dropdown
- **Auto-compaction:** After 100 messages, with 1-hour cooldown
- Uses hybrid LLM + TOON pipeline for summary generation

## Thread Awakening (Scheduled Follow-Ups)

Agents can schedule one-shot follow-ups bound to an existing conversation thread. APScheduler fires the job, loads thread history, runs the agent autonomously, and writes the response back.

Key files: `services/workflow_engine.py`, `cli-tools/automations/schedule_followup.py`, `routes/workflows.py`.

## Key Directories

```
backend/
|-- agents/             # Orchestrator + base agent
|-- api/                # FastAPI routers (core trading/chat)
|-- routes/             # Additional feature routers (auth, admin, notes, etc.)
|-- cli-tools/          # Trading CLI scripts (nf-quote, nf-order, etc.)
|-- monitor/            # Trade monitor daemon + rule engine
|-- database/           # Models, session, operations
|-- services/           # Upstox client, technical analysis, encryption
|-- utils/              # AG-UI wrapper, HITL, encryption, tool monitor
|-- config/             # Model config, permissions
|-- migrations/         # SQL migration files
|-- docs/               # This documentation
|-- tests/              # Test suites
```
