# Trading Cockpit Dashboard - Unified Design

**Date**: 2026-02-07
**Status**: Design Document - Awaiting Approval
**Replaces**: `frontend-v2/app/components/Dashboard.jsx`

---

## 1. Vision

A "Daily Cockpit" that replaces the basic dashboard with an interactive trading command center. It combines real-time portfolio data, watchlists, charts, and an AI chat companion into a single view. One cockpit thread per trading day creates an automatic trading journal that carries compressed context forward daily.

**For whom**: A learner-trader actively trading Nifty 50 stocks who wants to improve through structured reflection and AI-powered insights.

---

## 2. Layout Architecture

### Desktop (Three-Zone + Top Strip)

```
+--------------------------------------------------------------+
| TOP STRIP (sticky): Portfolio Value | Day P&L | Total P&L |  |
|                     Cash Balance | Market Status indicator    |
+-------------------+------------------------+-----------------+
|                   |                        |                 |
| LEFT PANEL        | CENTER PANEL           | RIGHT PANEL     |
| (280px,           | (flexible)             | (320px,         |
|  collapsible)     |                        |  collapsible)   |
|                   |                        |                 |
| [Market Pulse]    | [Chart - TradingView   | [Cockpit Chat]  |
|  Nifty/BankNifty  |  Lightweight Charts]   |  Daily thread   |
|  mini cards       |                        |  with streaming |
|                   | [Positions Table]      |  Quick prompts  |
| [Watchlist]       |  Open + Holdings tabs  |  Ask AI context |
|  Multiple lists   |                        |  Action buttons |
|  Sparklines       | [Daily Scorecard]      |                 |
|  Quick actions    |  Collapsed summary bar |                 |
|                   |  Expandable detail     |                 |
+-------------------+------------------------+-----------------+
```

### Mobile (Single Column + Bottom Tabs)

```
[Chart | Portfolio | Watchlist | Scorecard | Chat]
```

Bottom tab navigation, swipe between sections. Chat as floating action button opening bottom sheet.

---

## 3. Component Breakdown

### 3.1 Top Strip - Account Summary

**Always visible, sticky header.**

| Metric | Format | Color Logic |
|--------|--------|-------------|
| Portfolio Value | Rs XX,XXX | Neutral (white/zinc) |
| Day P&L | +/- Rs X,XXX (+X.X%) | Green if positive, red if negative |
| Total P&L | +/- Rs X,XXX (+X.X%) | Green if positive, red if negative |
| Cash Available | Rs XX,XXX | Neutral |
| Market Status | Badge: "Open" / "Closed" / "Pre-Open" | Green/red/amber |

**Data source**: `GET /api/cockpit/dashboard` + SSE `portfolio_update` events
**Components**: Custom `StatCard` (exists) + Tailwind flex layout

### 3.2 Left Panel - Market Pulse + Watchlist

#### Market Pulse Widget
- Mini cards for Nifty 50 index, Bank Nifty, VIX (when index data available)
- Fallback (MVP): Top 5 movers from user's positions/watchlist
- Each: value, change%, subtle green/red background tint
- **Data**: SSE `price_tick` events

#### Watchlist Panel
- Tabbed for multiple named watchlists ("Momentum", "Swing", etc.)
- Row format: `Symbol | LTP | Change% | 7-day Sparkline`
- 12-15 rows visible without scroll
- Hover actions: "Buy", "Analyze", "Set Alert", "Ask AI"
- Sortable by change%, volume, name
- Search/filter bar at top
- **Data**: `GET /api/cockpit/dashboard` (watchlist field) + SSE `price_tick`
- **Charts**: Recharts `<Sparkline>` (tiny, inline)

### 3.3 Center Panel - Chart + Positions + Scorecard

#### Chart Panel (Primary - 50-60% of center)
- **Library**: TradingView Lightweight Charts (`lightweight-charts`)
- Candlestick default, switchable to line/area
- Timeframes: 1m, 5m, 15m, 1H, 1D, 1W
- Indicators: SMA, EMA, RSI, MACD, Bollinger Bands, Volume
- Click any position/watchlist item to load its chart
- **Data**: Historical from `nf-quote --historical`, live updates via SSE

#### Positions Table (Below chart)
- Two tabs: "Open Positions" | "Holdings"
- **Open Positions**: Symbol | Qty | Avg Price | LTP | P&L (Rs) | P&L (%) | Day Change | [Exit] [Ask AI]
- **Holdings**: Symbol | Qty | Avg Cost | Current Value | P&L | Allocation % | Hold Days
- Subtle row tint (green-50/red-50) based on P&L
- Expandable row: entry date, stop loss, target, notes
- Summary row: Total Investment, Current Value, Total P&L
- Click symbol -> loads chart, click "Ask AI" -> prefills cockpit chat
- **Data**: `GET /api/cockpit/dashboard` + SSE `portfolio_update`

#### Daily Scorecard (Bottom, expandable)

**Collapsed (summary bar - always visible):**
```
Today: 5 trades | Win Rate: 60% | P&L: +Rs 1,240 | Streak: 3 days
```

**Expanded sections:**
1. **Trade Stats**: Trades, win rate, avg winner/loser, profit factor, biggest win/loss
2. **Process Ratings** (self-rated 1-5 stars):
   - Plan adherence
   - Risk management
   - Emotional discipline
   - Entry quality
   - Exit quality
3. **Reflection**: Text area + AI-suggested prompts
4. **Streak Tracker**: Calendar heatmap (react-calendar-heatmap) colored by P&L
5. **Monthly Goal**: Single goal with progress bar

**Data**: `daily_trading_summaries` table + user input for ratings/reflection

### 3.4 Right Panel - Cockpit Chat

**Design**: Collapsible sidebar (320px default, 0px collapsed with floating icon)

- **Daily thread**: Auto-creates `cockpit_{userId}_{date}` on first interaction
- **Morning briefing**: First message when thread is new (positions, watchlist, yesterday carry-over)
- **Message rendering**: Same as main chat (markdown, tool calls, reasoning) but compact
- **Quick prompts** (chips above input):
  - "Analyze my positions"
  - "What's moving in my watchlist?"
  - "Review today's trades"
  - "Explain [concept]"
- **Contextual input**: "Ask AI" from positions/watchlist pre-fills `[CONTEXT: position] {...}`
- **Action buttons**: AI responses can include one-click actions (Buy, Set SL, Add to Watchlist)
- **Streaming**: Reuses AG-UI SSE protocol, posts to `/api/agent/ag-ui` with cockpit thread ID
- **HITL**: Trade approvals surface inline in the chat panel

**When collapsed**: Small floating chat icon at bottom-right with unread badge

---

## 4. Daily Thread System

### 4.1 Thread Lifecycle
1. User opens cockpit -> system computes `cockpit_{userId}_{YYYY-MM-DD}` (IST)
2. If thread doesn't exist: compress previous day's thread, create new one, inject morning briefing
3. All cockpit chat interactions go to this thread
4. Thread stays open after market close (user can review/reflect)
5. Next trading day: lazy compression on first interaction

### 4.2 Compression Strategy
- **Reuses existing TOON fork pipeline** with trading-specific extraction prompt
- **Kept verbatim**: Executed trades, portfolio state, active orders, stop-losses
- **Summarized**: Market analysis, technical discussions
- **Dropped**: Raw tool output, repeated price checks, greetings

### 4.3 Conversation Model Change
```sql
ALTER TABLE conversations ADD COLUMN conversation_type VARCHAR(20) DEFAULT 'chat' NOT NULL;
CREATE INDEX idx_cockpit_lookup ON conversations(user_id, conversation_type, created_at);
```

### 4.4 Sidebar Integration
- Cockpit threads show with amber "Cockpit" badge
- Grouped under "Trading Days" section
- Filter toggle: All / Chats / Trading Days
- Title: "Trading Day - Feb 7, 2026" (auto-generated, not editable)

---

## 5. AI Integration

### 5.1 Proactive Alerts
- **Background task**: Polls prices every 60s during market hours (9:00-15:30 IST)
- **Alert types**: Watchlist target hit, stop-loss approaching, position risk, sector concentration, daily loss limit
- **Delivery**: SSE `alert` event -> toast notification + cockpit chat message
- **Storage**: `alert_queue` table for persistence and history

### 5.2 Morning Briefing
- Auto-generated first message in new daily cockpit thread
- Contains: market outlook, positions summary, active watchlist alerts, yesterday carry-over, today's focus
- **Trigger**: Lazy, when cockpit thread is created

### 5.3 Learning Nudges
- Computed post-market-close by InsightGeneratorTask
- Pattern detection: holding periods, win rates by day/time, position sizing consistency, revenge trading
- Stored as `past_learnings` memories + in `daily_trading_summaries.insights`

### 5.4 Risk Warnings
- Pre-trade checks shown in HITL approval dialog: concentration risk, sector exposure, daily loss limit, position size vs risk tolerance
- Amber/red warning banners - user can still approve but must acknowledge

### 5.5 One-Click Actions
- AG-UI custom event `ACTION_SUGGESTION` renders buttons below AI messages
- Actions: "Buy X at Market", "Set Stop Loss", "Add to Watchlist"
- `requires_approval: true` -> opens HITL dialog
- `requires_approval: false` -> executes immediately

### 5.6 Contextual "Ask AI"
- Every dashboard element has an "Ask AI" icon
- Clicking prefills cockpit chat with `[CONTEXT: {type}] {data}`
- Orchestrator uses context as grounding, skips redundant tool calls

---

## 6. Data Flow

### 6.1 Initial Load
```
Dashboard Mount -> GET /api/cockpit/dashboard
                     -> { portfolio, watchlist, alerts, trades, market_status }
                -> GET /api/cockpit/today
                     -> { thread_id, is_new, morning_briefing? }
                -> Connect SSE: GET /api/cockpit/stream
```

### 6.2 Real-Time Updates (SSE)
| Event | Frequency | Data |
|-------|-----------|------|
| `portfolio_update` | 30s (market hours) | positions, P&L, cash |
| `price_tick` | 5s (watched symbols) | symbol, price, change% |
| `alert` | On trigger | type, symbol, message, severity |
| `insight` | On generation | type, message, actions |
| `heartbeat` | 15s | timestamp |

### 6.3 Price Cache
- In-memory with 5s TTL, shared between SSE stream + alert evaluator
- Prevents Upstox API rate limit issues

---

## 7. New Backend Requirements

### 7.1 New Endpoints
| Endpoint | Purpose |
|----------|---------|
| `GET /api/cockpit/today` | Get/create today's cockpit thread |
| `GET /api/cockpit/dashboard` | Aggregated dashboard data |
| `GET /api/cockpit/stream` | SSE real-time updates |
| `GET /api/cockpit/history` | List cockpit threads by date |
| `GET /api/cockpit/alerts` | Pending/historical alerts |
| `POST /api/cockpit/alerts/{id}/dismiss` | Dismiss alert |
| `GET /api/cockpit/insights/today` | Today's AI insights |

### 7.2 New Database Tables
- `alert_queue` - Alert delivery queue with status tracking
- `daily_trading_summaries` - Pre-computed daily stats + compressed context

### 7.3 Background Tasks (FastAPI lifespan)
- `AlertEvaluatorTask` - Price monitoring during market hours (60s cycle)
- `InsightGeneratorTask` - Post-market-close analysis (15:45 IST)

---

## 8. Tech Choices

| Component | Library | Rationale |
|-----------|---------|-----------|
| Price chart | TradingView Lightweight Charts (45KB) | Purpose-built for financial data, Canvas rendering |
| Other charts | Recharts (already installed) | Portfolio donut, P&L bars, sparklines |
| Calendar heatmap | react-calendar-heatmap (~5KB) | Streak/consistency tracker |
| State management | Zustand (new) | Shared cockpit state across components |
| Animations | framer-motion (installed) | Widget transitions |
| Icons | lucide-react (installed) | Consistent with existing codebase |
| UI components | Catalyst UI + custom Card/StatCard (existing) | Already built and themed |

---

## 9. Implementation Phases

### Phase 1: Static Cockpit (Frontend MVP)
- Replace Dashboard.jsx with three-zone layout
- Top strip with portfolio stats
- Positions table with tabs
- Watchlist panel (fetched from new REST endpoint)
- Chart panel with TradingView Lightweight Charts
- Cockpit chat panel (reuse AG-UI streaming)
- Zustand stores for state

### Phase 2: Daily Thread System (Backend)
- `conversation_type` column migration
- `GET /api/cockpit/today` endpoint with lazy compression
- Morning briefing generation
- Sidebar filtering for cockpit threads
- Direct REST watchlist endpoint

### Phase 3: Real-Time (SSE)
- `GET /api/cockpit/stream` SSE endpoint
- Price cache service
- Live portfolio/price updates
- Alert evaluator background task
- Toast notifications for alerts

### Phase 4: AI Intelligence
- Contextual "Ask AI" from dashboard elements
- One-click action buttons in chat
- Daily insight generation (post-market)
- Learning nudges and pattern detection
- Risk warnings in HITL dialog

### Phase 5: Polish
- Daily scorecard with self-ratings
- Calendar heatmap / streak tracker
- Alert history management
- Weekend/holiday handling
- Mobile responsive layout
- Portfolio analytics (treemap, sector donut)

---

## 10. Color Conventions

| Element | Positive | Negative | Neutral |
|---------|----------|----------|---------|
| P&L text | `green-600` (#16a34a) | `red-600` (#dc2626) | `gray-500` (#6b7280) |
| P&L background | `green-50` (#f0fdf4) | `red-50` (#fef2f2) | `gray-50` (#f9fafb) |
| Candle up/down | `green-600` | `red-600` | - |
| Status badges | `green-500` (active) | `red-500` (alert) | `amber-500` (pending) |
| Cockpit badge | `amber-500` | - | - |

Always pair color with icons (arrows) or text (+/-) for accessibility.
