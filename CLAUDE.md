# Nifty Strategist v2 - AI Trading Agent

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

### Phase 1: Fork & Strip - IN PROGRESS
- [x] Fork EspressoBot codebase
- [x] Remove Shopify tools and agents
- [x] Remove Google Workspace integration
- [ ] Remove e-commerce database tables (BFCM, analytics, etc.)
- [ ] Simplify User model (remove Google OAuth fields)
- [ ] Update pyproject.toml dependencies
- [ ] Set up Supabase connection
- [ ] Test basic auth flow

### Phase 2: Port Trading Core - TODO
- [ ] Port `upstox_client.py` from `/home/pranav/tradingagent/backend/services/`
- [ ] Port `technical_analysis.py`
- [ ] Port trading models (TradeProposal, MarketAnalysis, RiskValidation)
- [ ] Create `tools/trading/market_data.py`
- [ ] Create `tools/trading/analysis.py`
- [ ] Create `tools/trading/portfolio.py`
- [ ] Create `tools/trading/orders.py` (with HITL)
- [ ] Create `tools/trading/watchlist.py`
- [ ] Add trades, agent_decisions, watchlist tables

### Phase 3: Wire Up Orchestrator - TODO
- [ ] Adapt orchestrator prompt for trading
- [ ] Configure HITL for place_order tool
- [ ] Adapt memory categories for trading
- [ ] Test end-to-end flow

### Phase 4: Frontend Adaptation - TODO
- [ ] Strip e-commerce dashboard components
- [ ] Add trading dashboard
- [ ] Update branding

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
    ├── orchestrator.py       # Main agent (NEEDS TRADING ADAPTATION)
    └── memory_extractor.py   # Memory extraction (NEEDS CATEGORY ADAPTATION)
```

### To Be Created (Trading-specific)
```
backend/
├── services/
│   ├── upstox_client.py      # Upstox SDK wrapper (PORT FROM WIP)
│   └── technical_analysis.py # Indicators (PORT FROM WIP)
├── models/
│   └── trading.py            # TradeProposal, MarketAnalysis (PORT FROM WIP)
└── tools/
    └── trading/
        ├── market_data.py    # get_quote, get_historical
        ├── analysis.py       # analyze_symbol
        ├── portfolio.py      # get_portfolio, get_positions
        ├── orders.py         # place_order (HITL)
        └── watchlist.py      # watchlist management
```

### Reference Files (from original WIP)
```
/home/pranav/tradingagent/backend/
├── services/upstox_client.py      # Working Upstox SDK integration
├── services/technical_analysis.py # RSI, MACD, support/resistance
├── models/trading.py              # TradeProposal, MarketAnalysis
└── agents/orchestrator.py         # Trading prompt (extract relevant parts)
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
# Backend
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Frontend
cd frontend-v2
npm install
npm run dev
```

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

## Notes for Development

1. **Supabase Setup**: Create free project at supabase.com, get connection string
2. **Upstox App**: Register at https://api.upstox.com/ for API credentials
3. **Model Selection**: Currently DeepSeek, can switch via OPENROUTER_API_KEY
4. **Paper Trading**: Implement paper trading mode before live trading
5. **Token Encryption**: Use Fernet symmetric encryption for Upstox tokens

---

## References

- **EspressoBot (origin)**: `/home/pranav/apydanticebot/`
- **Original WIP**: `/home/pranav/tradingagent/`
- **Design Document**: `/home/pranav/tradingagent/docs/plans/2026-01-26-espressobot-fork-design.md`
- **Upstox SDK Docs**: https://upstox.com/developer/api-documentation/
- **Pydantic AI Docs**: https://ai.pydantic.dev/
