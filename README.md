# Nifty Strategist v2

**AI-powered trading assistant for Indian stock markets (NSE/BSE)**

An intelligent trading companion that helps you analyze stocks, understand market opportunities, and execute trades with human-in-the-loop approval. Built for people who want to learn trading while leveraging AI assistance.

---

## Features

### Market Analysis
- **Real-time quotes** for Nifty 50 stocks
- **Technical analysis** with RSI, MACD, Bollinger Bands, support/resistance levels
- **Stock comparison** to evaluate multiple opportunities
- **Historical data** with customizable timeframes

### Portfolio Management
- **Paper trading** with ₹10 lakh virtual portfolio (default)
- **Position tracking** with P&L calculations
- **Position sizing** based on risk tolerance
- **Trade history** and performance analytics

### Smart Assistance
- **Natural language interface** - ask questions like "Should I buy RELIANCE?"
- **Personalized memory** - learns your risk tolerance, preferred sectors, trading style
- **Educational explanations** - explains reasoning in beginner-friendly language
- **Human-in-the-loop** - requires your approval before executing any trade

### Watchlist & Alerts
- **Custom watchlists** for tracking interesting stocks
- **Price alerts** for entry/exit points
- **Technical alerts** (RSI overbought/oversold, MACD crossovers)

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | React 18, TypeScript, Tailwind CSS, React Router 7 |
| Backend | Python 3.11+, FastAPI, Pydantic AI |
| Database | PostgreSQL (Supabase) |
| LLM | OpenRouter (model-agnostic) |
| Market Data | Upstox API |
| Streaming | AG-UI Protocol (SSE) |

---

## Quick Start

```bash
# Clone the repo
git clone git@github.com:pranavchavda/niftystrategist-v2.git
cd niftystrategist-v2

# Start development servers
./dev.sh
```

This starts:
- Backend at http://localhost:8000
- Frontend at http://localhost:5173
- API docs at http://localhost:8000/docs

### Requirements
- Python 3.11+
- Node.js 22+ (dev.sh handles this via nvm)
- PostgreSQL database (Supabase recommended)

### Environment Variables

Create `backend/.env`:
```bash
DATABASE_URL=postgresql://...
OPENROUTER_API_KEY=sk-or-...
JWT_SECRET=your-secret

# Optional - for live trading
UPSTOX_API_KEY=...
UPSTOX_API_SECRET=...
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    React Frontend                            │
│  ┌────────────────┐  ┌────────────────────────────────────┐ │
│  │ Chat Interface │  │       Trading Dashboard            │ │
│  │                │  │  Watchlist | Positions | History   │ │
│  └───────┬────────┘  └──────────────┬─────────────────────┘ │
│          │      SSE Event Stream     │                      │
└──────────┴───────────────────────────┴──────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────┐
│                    FastAPI Backend                           │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │            Trading Orchestrator Agent                  │ │
│  │  • Interprets user intent                              │ │
│  │  • Calls trading tools                                 │ │
│  │  • HITL for order execution                            │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │                   Trading Tools                        │ │
│  │  market_data | analysis | portfolio | orders | watchlist│ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │                   Services Layer                       │ │
│  │  upstox_client | technical_analysis | memory           │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

---

## Supported Stocks

All Nifty 50 constituents including:

RELIANCE, TCS, HDFCBANK, INFY, ICICIBANK, HINDUNILVR, ITC, SBIN, BHARTIARTL, KOTAKBANK, LT, AXISBANK, ASIANPAINT, MARUTI, TITAN, SUNPHARMA, ULTRACEMCO, BAJFINANCE, WIPRO, HCLTECH, NESTLEIND, TECHM, POWERGRID, NTPC, M&M, TATAMOTORS, INDUSINDBK, BAJAJFINSV, ONGC, JSWSTEEL, TATASTEEL, ADANIENT, ADANIPORTS, COALINDIA, GRASIM, CIPLA, DRREDDY, BPCL, BRITANNIA, EICHERMOT, HEROMOTOCO, DIVISLAB, APOLLOHOSP, SBILIFE, TATACONSUM, BAJAJ-AUTO, HINDALCO, UPL, LTIM, SHRIRAMFIN

---

## Paper Trading

The system starts in **paper trading mode** by default:
- Virtual portfolio: ₹10,00,000 (10 lakh)
- Simulated order execution
- No real money at risk
- Full feature parity with live trading

Connect your Upstox account in Settings to enable live trading.

---

## Example Conversations

```
You: What's happening with RELIANCE today?

Nifty Strategist: RELIANCE is trading at ₹2,847.50, up 1.2% today.
The RSI is at 58 (neutral), and it's above its 20-day moving average
which suggests bullish momentum. The stock found support at ₹2,780
last week. Would you like me to do a deeper technical analysis?
```

```
You: Buy 10 shares of TCS

Nifty Strategist: I'll place an order to buy 10 shares of TCS at the
current market price of ₹4,125.00. Total value: ₹41,250.

⚠️ This requires your approval. Confirm this trade?
[Approve] [Reject]
```

---

## Development

```bash
# Backend only
./dev.sh --backend-only

# Frontend only
./dev.sh --frontend-only

# CLI mode
./dev.sh --cli

# Verbose logging
./dev.sh --verbose
```

See [PROJECT_STATUS.md](./PROJECT_STATUS.md) for detailed development status.

---

## Origin

Forked from [EspressoBot](https://github.com/pranavchavda/apydanticebot), an AI assistant for e-commerce. We kept the battle-tested infrastructure (auth, chat, memory, streaming) and replaced the domain-specific tools (Shopify → Upstox trading).

---

## License

Private repository. All rights reserved.

---

## Disclaimer

This software is for educational purposes. Paper trading mode is enabled by default. When using live trading:
- Past performance does not guarantee future results
- Only trade with money you can afford to lose
- The AI provides analysis, not financial advice
- Always do your own research before trading
