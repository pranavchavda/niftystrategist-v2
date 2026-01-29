# Nifty Strategist v2 - AI Trading Agent

> **Quick Start**: See [PROJECT_STATUS.md](./PROJECT_STATUS.md) for current status, what's done, and next steps.

## Project Overview

An AI-powered trading assistant for the Indian stock market (NSE/BSE) that helps users analyze stocks, understand market opportunities, and execute trades with human-in-the-loop approval.

**Target Audience**: Non-technical users who want to learn trading while leveraging AI assistance.

**Key Principles**:
- Maximum agent autonomy for analysis and recommendations
- HITL approval required ONLY for actual transactions
- Educational focus: explain reasoning in beginner-friendly language
- Memory system for personalized experience

---

## Origin

This codebase is forked from **EspressoBot** (`/home/pranav/apydanticebot/`), a battle-tested AI assistant for e-commerce. We kept the core infrastructure (auth, chat, memory, streaming) and swapped out the domain-specific tools (Shopify → Upstox trading).

**Reference for patterns**: Check EspressoBot for examples of how things were done.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      React Frontend                              │
│  ┌──────────────────┐  ┌──────────────────────────────────────┐ │
│  │  Chat Interface  │  │         Trading Dashboard            │ │
│  │  - Message list  │  │  ┌──────────┐ ┌──────────┐ ┌───────┐│ │
│  │  - Input box     │  │  │Watchlist │ │ Pending  │ │ Trade ││ │
│  │  - Agent status  │  │  │  Panel   │ │Approvals │ │History││ │
│  └────────┬─────────┘  └──────────────────┬──────────────────┘ │
│           │         SSE Event Stream       │                    │
│           └───────────────┬────────────────┘                    │
└───────────────────────────┼─────────────────────────────────────┘
                            │
┌───────────────────────────┴───────────────────────────────────────┐
│                   FastAPI Backend                                  │
│                                                                    │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │              Trading Orchestrator Agent                      │  │
│  │  - Interprets user intent                                    │  │
│  │  - Uses tools for market data, analysis, trading             │  │
│  │  - Emits AG-UI events for streaming                          │  │
│  │  - HITL for trade execution                                  │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │                    Trading Tools                             │  │
│  │  market_data | analysis | portfolio | orders | watchlist     │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │                    Services Layer                            │  │
│  │  upstox_client | technical_analysis | encryption             │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │              Supabase PostgreSQL Database                    │  │
│  │  users | conversations | messages | memories | trades        │  │
│  └─────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

### Backend
- **Python 3.11+**
- **FastAPI** - Web framework
- **Pydantic AI** - Agent framework with AG-UI adapter
- **OpenRouter** - LLM provider (DeepSeek for now, model-agnostic)
- **Upstox SDK** - Indian stock market data and trading (`upstox-python-sdk`)
- **PostgreSQL** - Via Supabase (free tier)
- **SQLAlchemy + asyncpg** - Async ORM
- **pandas + ta** - Technical indicator calculations

### Frontend
- **React 18+ with TypeScript**
- **AG-UI client** - For SSE streaming
- **Tailwind CSS** - Styling
- **Zustand** - State management

---

## Current Implementation Status

### Phase 1: Fork & Strip - COMPLETED
- [x] Fork EspressoBot codebase
- [x] Remove Shopify tools and agents
- [x] Remove Google Workspace integration
- [x] Remove e-commerce database tables (BFCM, analytics, etc.)
- [x] Simplify User model (remove Google OAuth, add Upstox fields)
- [x] Add trading-specific models (Trade, AgentDecision, WatchlistItem)
- [x] Fix broken imports in main.py and agents/__init__.py
- [x] Set up Supabase connection (22 tables created, 37 old tables dropped)
- [ ] Update pyproject.toml dependencies
- [ ] Test basic auth flow

### Phase 2: Port Trading Core - COMPLETED
- [x] Port `upstox_client.py` → `services/upstox_client.py` (50 stocks supported)
- [x] Port `technical_analysis.py` → `services/technical_analysis.py`
- [x] Port Pydantic models → `models/analysis.py`, `models/trading.py`
- [x] Add trading SQLAlchemy models (Trade, AgentDecision, WatchlistItem) in database/models.py
- [x] Create `tools/trading/market_data.py` (get_stock_quote, get_historical_data, list_supported_stocks)
- [x] Create `tools/trading/analysis.py` (analyze_stock, compare_stocks)
- [x] Create `tools/trading/portfolio.py` (get_portfolio, get_position, calculate_position_size)
- [x] Create `tools/trading/orders.py` with HITL (place_order, cancel_order, get_open_orders, get_order_history)
- [x] Create `tools/trading/watchlist.py` (add_to_watchlist, get_watchlist, remove_from_watchlist, update_watchlist, check_watchlist_alerts)

### Phase 3: Wire Up Orchestrator - COMPLETED
- [x] Adapt orchestrator prompt for trading (Nifty Strategist persona, trading tools documentation)
- [x] Register trading tools with orchestrator (register_all_trading_tools)
- [x] Configure HITL for place_order and cancel_order tools (@requires_approval decorator)
- [x] Adapt memory categories for trading (risk_tolerance, position_sizing, sector_preference, trading_style, etc.)
- [x] Test end-to-end flow (paper trading verified with ₹10 lakh starting capital)

### Phase 4: Frontend Adaptation - COMPLETED
- [x] Strip e-commerce dashboard components (removed BFCM, Boxing Week, Price Monitor, CMS, Flock routes)
- [x] Add trading dashboard (Dashboard.jsx with portfolio stats, positions table, P&L tracking)
- [x] Update branding (Nifty Strategist, trading-focused copy, ArrowTrendingUpIcon logo)
- [x] Update manifest.json for PWA
- [x] Update login.tsx (trading messaging, paper trading notice)
- [x] Update _index.tsx landing page (trading-focused applications grid)
- [x] Create dev.sh script (backend + frontend startup with nvm)

---

## Key Files

### Core Infrastructure (kept from EspressoBot)
```
backend/
├── auth.py                    # JWT auth, User model
├── main.py                    # FastAPI app
├── database/
│   ├── models.py             # SQLAlchemy models
│   ├── operations.py         # DB operations (ConversationOps, etc.)
│   └── session.py            # Async PostgreSQL connection
├── api/
│   └── conversations.py      # Chat history endpoints
├── utils/
│   ├── ag_ui_wrapper.py      # AG-UI streaming
│   └── hitl_streamer.py      # Human-in-the-loop
└── agents/
    ├── orchestrator.py       # Main agent (ADAPTED for trading)
    └── memory_extractor.py   # Memory extraction (needs category adaptation)
```

### Trading-Specific Files (CREATED)
```
backend/
├── services/
│   ├── upstox_client.py      # Upstox SDK wrapper (50 Nifty stocks, paper trading)
│   └── technical_analysis.py # RSI, MACD, SMA, EMA, ATR indicators
├── models/
│   ├── analysis.py           # OHLCVData, TechnicalIndicators, MarketAnalysis
│   └── trading.py            # TradeProposal, RiskValidation, Portfolio, TradeResult
└── tools/
    └── trading/
        ├── __init__.py       # register_all_trading_tools
        ├── market_data.py    # get_stock_quote, get_historical_data, list_supported_stocks
        ├── analysis.py       # analyze_stock, compare_stocks
        ├── portfolio.py      # get_portfolio, get_position, calculate_position_size
        ├── orders.py         # place_order (HITL), cancel_order (HITL), get_open_orders, get_order_history
        └── watchlist.py      # add_to_watchlist, get_watchlist, remove_from_watchlist, update_watchlist, check_watchlist_alerts
```

---

## Database Schema

### User Model (Simplified from EspressoBot)
```python
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    name = Column(String(255))
    password_hash = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utc_now)

    # Upstox OAuth (encrypted)
    upstox_access_token = Column(Text, nullable=True)
    upstox_refresh_token = Column(Text, nullable=True)
    upstox_token_expiry = Column(DateTime, nullable=True)

    # Preferences
    preferred_model = Column(String(100), default="deepseek/deepseek-chat")
```

### Tables to KEEP (from EspressoBot)
- `users` - User accounts (simplified)
- `conversations` - Chat threads with forking
- `messages` - Chat messages with tool_calls, reasoning
- `memories` - Extracted facts with categories
- `user_preferences` - Settings

### Tables to REMOVE
- `bfcm_*` - Black Friday analytics
- `boxing_week_*` - Boxing week analytics
- `daily_analytics_cache` - E-commerce analytics
- `hourly_analytics_cache`
- `analytics_sync_status`
- `skuvault_*` - Inventory management
- `workflow_*` - E-commerce workflows
- `doc_chunks` - Shopify docs
- `inventory_alerts`

### Tables to ADD (Trading-specific)
- `trades` - Executed trades
- `agent_decisions` - Analysis audit trail
- `watchlist` - User watchlists

---

## Memory System

### Categories (Trading-focused)
```python
MEMORY_CATEGORIES = [
    # Trading-specific (primary)
    "risk_tolerance",      # "User is conservative, max 2% risk per trade"
    "position_sizing",     # "User prefers small positions, max 5% of portfolio"
    "sector_preference",   # "User likes IT and banking stocks"
    "trading_style",       # "User is a swing trader, holds 2-5 days"
    "avoid_list",          # "User doesn't want to trade Adani stocks"
    "past_learnings",      # "User lost money on TATAMOTORS, prefers to avoid"

    # General (secondary)
    "communication",       # "User prefers concise explanations"
    "experience_level",    # "User is a beginner, explain technical terms"
    "schedule",            # "User trades only in first hour of market"
]
```

### Memory Injection
- Inject up to 10 semantically matched memories per query
- Plus structured profile (risk, style, preferences)

---

## Environment Variables

```bash
# Database (Supabase PostgreSQL)
DATABASE_URL=postgresql://user:pass@db.xxx.supabase.co:5432/postgres

# LLM
OPENROUTER_API_KEY=sk-or-...

# Upstox (per-user tokens stored encrypted in DB, but need app credentials)
UPSTOX_API_KEY=...
UPSTOX_API_SECRET=...
UPSTOX_REDIRECT_URI=http://localhost:3000/callback

# Auth
JWT_SECRET=your-secret-key

# Encryption (for Upstox tokens in DB)
ENCRYPTION_KEY=your-32-byte-key
```

---

## Development Commands

```bash
# Quick start (recommended) - starts both backend and frontend
./dev.sh

# Start only backend
./dev.sh --backend-only

# Start only frontend
./dev.sh --frontend-only

# Start CLI interface
./dev.sh --cli

# Verbose mode (show logs in terminal)
./dev.sh --verbose

# Manual startup (if dev.sh doesn't work)

# Backend
cd backend
source venv/bin/activate
uvicorn main:app --reload --port 8000

# Frontend (requires Node 22+)
cd frontend-v2
nvm use 22
npm install
npm run dev
```

**Note**: The frontend requires Node.js 22+. The `dev.sh` script automatically handles this via nvm.

---

## Key Patterns (from EspressoBot)

### AG-UI Streaming
See `utils/ag_ui_wrapper.py` - handles SSE events for real-time chat

### HITL (Human-in-the-Loop)
See `utils/hitl_streamer.py` - pause execution for user approval

### Memory Extraction
See `agents/memory_extractor.py` - extract facts from conversations

### Conversation Forking
See `api/conversations.py` fork endpoint - compress old context

---

## Planned: CLI-Based Trading Tools (Next Phase)

> **Status**: Planned for implementation. This replaces the current Pydantic AI tool-based approach.

### Concept

Instead of registering many trading tools with the orchestrator (which increases token overhead), we use a single `execute_bash` tool and create CLI scripts the agent invokes. This is inspired by EspressoBot's bash tool pattern.

**Benefits:**
- **Token efficiency** - One tool definition instead of 15+ trading tools with full schemas
- **Self-documenting** - Agent calls `nf-quote --help` to learn usage on-demand
- **Composable** - Can chain commands: `nf-quote RELIANCE | nf-analyze --quick`
- **Easy to extend** - Add new tool = add new script, no agent code changes
- **Testable** - Debug tools directly from terminal
- **Discoverable** - Agent reads index, picks the right tool

### Proposed Structure

```
backend/
└── cli-tools/
    ├── index.md              # Tool catalog for agent to read
    ├── nf-quote              # Get live/historical quotes
    ├── nf-order              # Place/modify/cancel orders (supports AMO)
    ├── nf-portfolio          # View holdings, P&L, positions
    ├── nf-watchlist          # Manage watchlist
    ├── nf-analyze            # Technical analysis (RSI, MACD, etc.)
    ├── nf-market-status      # Check market hours, holidays, circuit breakers
    ├── nf-search             # Search stocks by name/sector/criteria
    ├── nf-account            # Account info, margins, funds
    ├── nf-alerts             # Price alerts, notifications
    └── nf-history            # Trade history, order book
```

### Tool Conventions

Each tool will:
- Have `--help` with usage examples
- Support `--json` flag for structured output (default: human-readable)
- Read user context from environment (`NF_USER_ID`, `NF_TRADING_MODE`)
- Use consistent error format: `❌ Error: <message>`
- Use consistent success format: `✅ <result>`
- Support `--dry-run` for order tools

### Example Usage

```bash
# Agent checks what tools are available
cat cli-tools/index.md

# Agent learns about a specific tool
nf-order --help

# Get a quote
nf-quote RELIANCE --json

# Place an AMO (After Market Order)
nf-order buy INDUSINDBK 1 --type LIMIT --price 898.4 --amo

# Check market status before trading
nf-market-status

# Analyze a stock
nf-analyze HDFCBANK --indicators rsi,macd,sma

# View portfolio
nf-portfolio --json
```

### Implementation Priority

1. **nf-market-status** - Check if market is open (simple, immediately useful)
2. **nf-quote** - Get stock quotes (core functionality)
3. **nf-order** - Place/cancel orders with AMO support
4. **nf-portfolio** - View holdings and P&L
5. **nf-analyze** - Technical analysis
6. **nf-watchlist** - Watchlist management
7. **nf-search** - Stock discovery
8. **nf-account** - Account/margin info

### Migration Plan

1. Create `cli-tools/` directory with base framework
2. Implement tools one by one, starting with market-status
3. Create `index.md` documenting all tools
4. Update orchestrator to use `execute_bash` instead of registered tools
5. Deprecate `tools/trading/` module once CLI tools are complete

---

## Notes for Development

1. **Supabase Setup**: Create free project at supabase.com, get connection string
2. **Upstox App**: Register at https://api.upstox.com/ for API credentials
3. **Model Selection**: Currently DeepSeek, can switch via OPENROUTER_API_KEY
4. **Paper Trading**: Implement paper trading mode before live trading
5. **Token Encryption**: Use Fernet symmetric encryption for Upstox tokens

---

## References

- **EspressoBot (origin)**: `/home/pranav/apydanticebot/`
- **Original WIP on Pranav's WSL dev environment**: `/home/pranav/tradingagent/`
- If working on desktop dev environment (EndevourOS): `/home/pranav/niftystrategist-v2`
- **Design Document**: `/home/pranav/tradingagent/docs/plans/2026-01-26-espressobot-fork-design.md`
- **Upstox SDK Docs**: https://upstox.com/developer/api-documentation/
- **Upstox API Docs**: available locally at upstox-api-docs.txt
- **Pydantic AI Docs**: https://ai.pydantic.dev/
---
## Notes:
dev.sh is the way to start the dev server
the project uses pnpm and not npm
