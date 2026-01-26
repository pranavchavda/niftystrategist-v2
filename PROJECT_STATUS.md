# Nifty Strategist v2 - Project Status

**Last Updated**: 2026-01-26
**Current Phase**: Phase 4 Complete, Ready for Testing
**Next Session**: EndeavourOS Desktop

---

## Quick Start

```bash
cd /home/pranav/niftystrategist-v2
./dev.sh
```

This will:
1. Activate Python venv and install dependencies if needed
2. Start backend on http://localhost:8000
3. Switch to Node 22 via nvm
4. Start frontend on http://localhost:5173

---

## What's Been Done

### Phase 1: Fork & Strip ✅
- Forked from EspressoBot (`/home/pranav/apydanticebot/`)
- Removed all Shopify/e-commerce tools and agents
- Removed Google Workspace integration
- Cleaned up database models (dropped 37 e-commerce tables)
- Added trading-specific models (Trade, AgentDecision, WatchlistItem)

### Phase 2: Trading Tools ✅
Created in `backend/tools/trading/`:

| File | Tools | Description |
|------|-------|-------------|
| `market_data.py` | `get_stock_quote`, `get_historical_data`, `list_supported_stocks` | Real-time and historical market data |
| `analysis.py` | `analyze_stock`, `compare_stocks` | Technical analysis with RSI, MACD, support/resistance |
| `portfolio.py` | `get_portfolio`, `get_position`, `calculate_position_size` | Paper trading portfolio (₹10L starting) |
| `orders.py` | `place_order`, `cancel_order`, `get_open_orders`, `get_order_history` | Order execution with HITL approval |
| `watchlist.py` | `add_to_watchlist`, `get_watchlist`, `remove_from_watchlist`, `check_watchlist_alerts` | Watchlist management |

### Phase 3: Orchestrator ✅
- Adapted `backend/agents/orchestrator.py` with trading persona
- Registered all trading tools via `register_all_trading_tools()`
- HITL configured for `place_order` and `cancel_order`
- Memory categories updated for trading (risk_tolerance, position_sizing, sector_preference, etc.)

### Phase 4: Frontend ✅
- Removed e-commerce routes (BFCM, Boxing Week, Price Monitor, CMS, Flock, Inventory)
- Updated branding to "Nifty Strategist"
- Rewrote `Dashboard.jsx` for trading (portfolio stats, positions, P&L)
- Updated landing page with trading-focused applications
- Created `dev.sh` for easy development startup

---

## What's NOT Done Yet

### Immediate (Next Session)
1. **Test the full stack** - Run `./dev.sh` and verify:
   - Backend starts without errors
   - Frontend builds and loads
   - Chat works with trading tools
   - Paper trading executes correctly

2. **Upstox Integration** - Currently using mock data:
   - `services/upstox_client.py` has the client but needs API keys
   - Set `UPSTOX_API_KEY`, `UPSTOX_API_SECRET` in `.env`
   - OAuth flow for user token storage

3. **Database Migration** - Tables exist but may need:
   - Verify schema matches models
   - Test CRUD operations

### Later
- Real Upstox OAuth flow (redirect, token storage)
- Live trading mode toggle
- Watchlist alerts (background job)
- Trade history visualization
- Mobile responsiveness polish

---

## Key Files to Know

```
backend/
├── agents/
│   ├── orchestrator.py      # Main trading agent (modified)
│   └── memory_extractor.py  # Memory categories (modified)
├── tools/trading/           # NEW - All trading tools
│   ├── __init__.py
│   ├── market_data.py
│   ├── analysis.py
│   ├── portfolio.py
│   ├── orders.py
│   └── watchlist.py
├── services/
│   ├── upstox_client.py     # NEW - Upstox SDK wrapper
│   └── technical_analysis.py # NEW - RSI, MACD, etc.
├── models/
│   ├── analysis.py          # NEW - Pydantic models
│   └── trading.py           # NEW - TradeProposal, etc.
├── database/models.py       # Trade, AgentDecision, WatchlistItem added
├── requirements.txt         # NEW - Copied from EspressoBot + trading deps
└── main.py                  # Imports updated

frontend-v2/
├── app/
│   ├── components/
│   │   ├── Dashboard.jsx    # Rewritten for trading
│   │   └── Sidebar.jsx      # E-commerce links removed
│   └── routes/
│       ├── _index.tsx       # Landing page (trading focus)
│       ├── login.tsx        # Rebranded
│       └── _auth.tsx        # Page titles updated
└── public/manifest.json     # PWA metadata updated

dev.sh                       # NEW - Development startup script
```

---

## Environment Setup

### Required in `backend/.env`:
```bash
# Database (Supabase)
DATABASE_URL=postgresql://...

# LLM
OPENROUTER_API_KEY=sk-or-...

# Auth
JWT_SECRET=...

# Upstox (for live trading - optional for paper trading)
UPSTOX_API_KEY=...
UPSTOX_API_SECRET=...
UPSTOX_REDIRECT_URI=http://localhost:5173/callback
```

### Node.js
- Requires Node 22+ (dev.sh handles this via nvm)

### Python
- Requires Python 3.11+
- Dependencies in `requirements.txt`

---

## Paper Trading

The system starts in **paper trading mode** by default:
- Virtual portfolio: ₹10,00,000 (10 lakh)
- Simulated order execution
- No real money at risk

To enable live trading:
1. Connect Upstox account in Settings
2. Toggle "Live Trading" mode
3. HITL will require approval for all real orders

---

## Supported Stocks

50 stocks supported (Nifty 50 constituents). See `services/upstox_client.py`:
- RELIANCE, TCS, HDFCBANK, INFY, ICICIBANK
- HINDUNILVR, ITC, SBIN, BHARTIARTL, KOTAKBANK
- ... and 40 more

---

## Known Issues

1. **WSL Database Latency** - Remote Supabase can be slow on WSL
2. **Upstox SDK** - Not tested with real credentials yet
3. **Frontend Build** - Requires Node 22+ (crypto.hash issue with older versions)

---

## Session Notes

### 2026-01-26 (WSL Session)
- Completed Phase 4 frontend adaptation
- Created dev.sh script
- Fixed icon imports (ArrowTrendingUpIcon, not TrendingUpIcon)
- Discovered venv didn't have FastAPI - was using system Python
- Added requirements.txt, removed Google packages (conflict)
- Ready for full testing on EndeavourOS desktop

---

## References

- **EspressoBot (origin)**: `/home/pranav/apydanticebot/`
- **Original WIP**: `/home/pranav/tradingagent/`
- **Upstox API Docs**: https://upstox.com/developer/api-documentation/
- **Pydantic AI Docs**: https://ai.pydantic.dev/
