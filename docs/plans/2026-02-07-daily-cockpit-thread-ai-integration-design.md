# Daily Cockpit Thread System & AI Integration Design

**Date**: 2026-02-07
**Status**: Design Document
**Author**: AI Architect (Claude Opus 4.6)
**Related**: Cockpit Dashboard Planning

---

## Table of Contents

1. [Daily Thread System](#1-daily-thread-system)
2. [AI Integration Points](#2-ai-integration-points)
3. [Contextual Chat](#3-contextual-chat)
4. [Data Flow Architecture](#4-data-flow-architecture)
5. [Database Schema Changes](#5-database-schema-changes)
6. [API Endpoints](#6-api-endpoints)
7. [Background Jobs](#7-background-jobs)
8. [Implementation Priorities](#8-implementation-priorities)

---

## 1. Daily Thread System

### 1.1 Core Concept

Each trading day gets exactly one "cockpit" conversation thread. This thread serves as the day's trading journal -- every interaction with the AI about trading that day happens in this single thread. This is distinct from regular "chat" conversations which can be created freely.

### 1.2 Thread Lifecycle

```
Market Day Start (9:00 AM IST)
  |
  v
[Previous day's thread compressed] ──> compressed context saved as fork_summary
  |
  v
[New cockpit thread auto-created]
  |  - Title: "Trading Day - Feb 7, 2026"
  |  - Type: "cockpit"
  |  - forked_from_id: previous day's cockpit thread
  |  - fork_summary: compressed context from previous day
  |  - First system message: morning briefing (injected)
  |
  v
[User interacts throughout the day]
  |  - Market analysis requests
  |  - Trade proposals and approvals
  |  - Watchlist checks
  |  - P&L reviews
  |
  v
Market Day End (3:30 PM IST) or EOD (11:59 PM IST)
  |
  v
[Thread stays open, user can still chat]
[Compression happens next morning, not at market close]
```

### 1.3 Auto-Creation Logic

The cockpit thread is created **lazily** -- on the user's first interaction of the day, not at midnight or market open. This avoids creating empty threads for days the user doesn't trade.

**Trigger**: When the user navigates to the cockpit dashboard OR sends a cockpit message, the system checks if a cockpit thread exists for today (IST date). If not, it creates one.

**Thread ID Format**: `cockpit_{user_id}_{YYYY-MM-DD}` (e.g., `cockpit_1_2026-02-07`)

This deterministic ID format means:
- No need to query for "today's cockpit thread" -- we can compute the ID directly
- Simple existence check before creation
- Easy date-based lookups for browsing history

### 1.4 Conversation Model Changes

The existing `Conversation` model gets a new `conversation_type` field rather than a separate table. This keeps the existing infrastructure (messages, fork, search, sidebar) working with minimal changes.

```python
# Addition to Conversation model
conversation_type = Column(String(20), default="chat", nullable=False)
# Values: "chat" (default, existing behavior), "cockpit" (daily trading thread)

# New index for fast cockpit lookups
Index('idx_cockpit_user_type_date', 'user_id', 'conversation_type', 'created_at')
```

### 1.5 Context Compression (Day-to-Day Carry-Over)

**When**: Compression happens when the next day's cockpit thread is being created (lazy, on first interaction). NOT at midnight, NOT at market close.

**How**: Reuses the existing fork/compression pipeline (`toon_converter.create_hybrid_fork_summary`) but with a trading-specific extraction prompt.

**What Gets Kept (Verbatim)**:
- All executed trades (symbol, direction, quantity, price, P&L)
- End-of-day portfolio state (positions, total value, available cash)
- Active watchlist alerts and their current status
- Stop-losses and target prices still in play
- Any explicit "remember this" instructions from the user

**What Gets Summarized**:
- Market analysis discussions (compressed to conclusions only)
- Technical indicator deep-dives (compressed to signal + action taken)
- Rejected trade proposals (just "rejected RELIANCE BUY because...")
- General market commentary

**What Gets Dropped**:
- Tool call details (raw CLI output)
- Intermediate reasoning steps
- Repeated data lookups (e.g., checking RELIANCE price 5 times)
- Greeting/small talk exchanges

**Trading-Specific Compression Prompt** (injected into the existing summarize_conversation_to_json):

```
Extract a trading day summary with these mandatory sections:

1. TRADES_EXECUTED: [{symbol, direction, qty, price, time, pnl, status}]
2. PORTFOLIO_STATE: {total_value, cash, invested, day_pnl, positions: [{symbol, qty, avg_price, current_price, pnl}]}
3. WATCHLIST_ALERTS: [{symbol, alert_type, target_price, triggered: bool}]
4. ACTIVE_ORDERS: [{symbol, direction, qty, order_type, limit_price, status}]
5. KEY_DECISIONS: ["Decided to hold TCS despite 3% drop because...", ...]
6. LESSONS_LEARNED: ["Sold INFY too early, missed 2% upside", ...]
7. RISK_STATE: {max_position_pct, sector_exposure: {}, total_exposure_pct}
8. TOMORROW_PLAN: ["Watch RELIANCE for breakout above 2850", ...]
```

This structured extraction feeds into the existing TOON encoding pipeline for maximum compression (90-95% token reduction).

### 1.6 Thread Browsing

Cockpit threads appear in the conversation sidebar alongside regular chats, but with visual differentiation:

- **Badge**: "Cockpit" tag with a distinct color (amber/orange)
- **Grouping**: Cockpit threads are grouped under a "Trading Days" section in the sidebar, sorted by date descending
- **Title Format**: "Trading Day - Feb 7, 2026" (auto-generated, not editable)
- **Filter**: Sidebar gets a toggle to show "All" / "Chats" / "Trading Days"

The existing `ConversationSidebar.jsx` component and the `GET /api/conversations/` endpoint need a `type` filter parameter.

### 1.7 Weekend/Holiday Handling

- No cockpit thread is created on weekends or market holidays
- If the user opens the dashboard on a Saturday, the most recent cockpit thread is shown in read-only mode with a "Market Closed" banner
- The `nf-market-status` CLI tool already handles IST holidays/weekends -- reuse its logic
- Monday's cockpit thread carries compressed context from Friday's thread (skips Sat/Sun)

---

## 2. AI Integration Points

### 2.1 Proactive Alerts System

**Architecture**: Event-driven with a lightweight polling fallback.

```
                    ┌──────────────────────────────────┐
                    │       Alert Evaluator Service     │
                    │  (Background asyncio task)        │
                    │                                   │
                    │  Every 60s during market hours:   │
                    │  1. Fetch watchlist items w/alerts│
                    │  2. Get current prices (batch)    │
                    │  3. Compare against thresholds    │
                    │  4. Check position risk limits    │
                    │  5. Write to alert_queue table    │
                    └──────────┬───────────────────────┘
                               │
                               v
                    ┌──────────────────────────────────┐
                    │        alert_queue table          │
                    │  id, user_id, alert_type,         │
                    │  payload (JSON), status,          │
                    │  created_at, delivered_at          │
                    └──────────┬───────────────────────┘
                               │
                    ┌──────────┴──────────────────────┐
                    │                                   │
                    v                                   v
          ┌─────────────────┐              ┌────────────────────┐
          │  SSE Dashboard  │              │  Cockpit Thread    │
          │  (toast/badge)  │              │  (auto-message)    │
          └─────────────────┘              └────────────────────┘
```

**Alert Types**:

| Alert Type | Trigger | Urgency | Delivery |
|---|---|---|---|
| `watchlist_target_hit` | Price crosses alert_above/alert_below | High | Toast + cockpit message |
| `stop_loss_approaching` | Position within 1% of stop loss | Critical | Toast + cockpit message + sound |
| `unusual_volume` | Volume > 2x 20-day average | Medium | Cockpit message only |
| `position_risk` | Single position > 10% of portfolio | High | Toast + cockpit message |
| `sector_concentration` | Single sector > 30% exposure | Medium | Cockpit message only |
| `daily_loss_limit` | Day P&L exceeds -2% of portfolio | Critical | Toast + cockpit message + sound |

**Implementation**: A single background asyncio task that runs during market hours (9:00-15:30 IST). It polls the Upstox API for current prices in batches and evaluates alert conditions. Results go into the `alert_queue` table. The dashboard SSE endpoint picks up undelivered alerts and streams them to the frontend.

### 2.2 Position Insights

These are **computed periodically** (not real-time) and stored in the `agent_decisions` table with `decision_type = 'position_insight'`.

**Holding Period Analysis**:
```python
# Computed daily after market close (or on demand)
# Looks at trade history to find patterns
{
    "insight_type": "holding_period",
    "finding": "Average winning hold: 4.2 days. Average losing hold: 1.1 days.",
    "suggestion": "You tend to cut winners too early. Consider extending hold time for profitable trades.",
    "confidence": 0.85,
    "data": {
        "avg_winner_hold_days": 4.2,
        "avg_loser_hold_days": 1.1,
        "sample_size": 23
    }
}
```

**Pattern Recognition in User Behavior**:
- "You've bought RELIANCE 4 times in the last 30 days, all near support levels. Win rate: 75%."
- "Your Friday trades have a 30% lower win rate than Monday-Thursday trades."
- "You tend to increase position size after a losing trade (revenge trading detected in 3/5 cases)."

These insights are generated by an LLM call with the user's trade history as context. They use the existing `AgentDecision` model with a new `decision_type` value.

### 2.3 Daily Morning Briefing

**Trigger**: Injected as the first AI message when the daily cockpit thread is created.

**Content** (generated by a single LLM call with structured output):

```markdown
## Good Morning, Pranav! Trading Day - Feb 7, 2026

### Market Outlook
- Nifty 50 closed at 23,456 yesterday (+0.8%)
- SGX Nifty futures indicating a flat open
- Global cues: US markets mixed, Asia-Pacific slightly positive

### Your Positions Summary
| Stock | Qty | Avg Price | LTP | P&L | Hold Days |
|-------|-----|-----------|-----|-----|-----------|
| TCS | 10 | 4,150 | 4,220 | +1.7% | 3 |
| INFY | 15 | 1,780 | 1,755 | -1.4% | 7 |

### Watchlist Alerts Active
- RELIANCE: Alert set at 2,850 (currently 2,815, 1.2% away)
- HDFCBANK: Alert set at 1,700 (currently 1,680, 1.2% away)

### Yesterday's Carry-Over
- Sold SBIN at 780 (+2.3% gain)
- Still holding INFY despite weakness -- stop loss at 1,730

### Today's Focus
Based on your trading style and current positions:
1. Watch INFY closely -- approaching stop loss at 1,730
2. RELIANCE nearing your buy target of 2,850
```

**Data Sources**: Portfolio API (nf-portfolio), watchlist (nf-watchlist), previous day's compressed context, market status (nf-market-status).

### 2.4 Learning Nudges

These are behavioral insights derived from analyzing the user's trade history. They are NOT real-time -- they're computed in the end-of-day compression job and stored as part of the cockpit context.

**Examples**:
- "You sold too early on 3 of your last 5 profitable trades, leaving an average of 1.8% on the table."
- "Your position sizing has been inconsistent -- ranging from 2% to 12% of portfolio."
- "Strong pattern: Your technical analysis trades outperform your 'gut feeling' trades by 4.2%."

**Storage**: Part of the compressed context in `LESSONS_LEARNED` section. Also stored as memories with `category = 'past_learnings'` for long-term recall.

### 2.5 Risk Warnings

Real-time risk checks that run whenever a trade is proposed or a position changes significantly.

**Implementation**: Added as a pre-check in the trade proposal flow (before HITL approval dialog).

```python
# Risk checks evaluated before presenting trade for approval
risk_checks = [
    ConcentrationRiskCheck(),      # Single stock > 10% of portfolio
    SectorExposureCheck(),         # Single sector > 30%
    DailyLossLimitCheck(),         # Day P&L > -2%
    PositionSizeCheck(),           # Trade size vs user's risk_tolerance memory
    CorrelationCheck(),            # Adding correlated positions
]
```

When a risk warning triggers, it's shown in the HITL approval dialog as an amber/red warning banner. The user can still approve but must acknowledge the risk.

### 2.6 One-Click Actions from AI Suggestions

The AI's responses can include **actionable buttons** that map to CLI tool commands. This uses the existing AG-UI event stream with a custom event type.

**AG-UI Custom Event**: `CUSTOM_ACTION_SUGGESTION`

```json
{
    "type": "CUSTOM",
    "subtype": "ACTION_SUGGESTION",
    "data": {
        "actions": [
            {
                "id": "action_1",
                "label": "Buy 10 RELIANCE at Market",
                "command": "nf-order buy RELIANCE 10 --type MARKET",
                "risk_level": "medium",
                "requires_approval": true
            },
            {
                "id": "action_2",
                "label": "Set Stop Loss at 2,780",
                "command": "nf-order sell RELIANCE 10 --type SL --trigger 2780",
                "risk_level": "low",
                "requires_approval": true
            },
            {
                "id": "action_3",
                "label": "Add to Watchlist",
                "command": "nf-watchlist add RELIANCE --alert-above 2850",
                "risk_level": "none",
                "requires_approval": false
            }
        ]
    }
}
```

**Frontend**: Renders as styled buttons below the AI's message. Clicking a button:
1. For `requires_approval: true`: Opens the HITL approval dialog with the command pre-filled
2. For `requires_approval: false`: Executes immediately and shows result as a new message

---

## 3. Contextual Chat

### 3.1 "Ask AI" from Dashboard Context

Every data element on the cockpit dashboard has an "Ask AI" affordance (small icon button). Clicking it opens the cockpit chat with pre-filled context about what the user was looking at.

**Implementation**: The frontend sends a specially prefixed message that the orchestrator recognizes.

```
// Frontend constructs context-rich message
const askAI = (context) => {
  const prefix = `[CONTEXT: ${context.type}]\n${JSON.stringify(context.data)}\n\n`;
  // User can edit/add their question after the context
  setChatInput(prefix + "What should I do?");
  navigateToChat();
};
```

**Context Types**:

| Dashboard Element | Context Type | Pre-filled Data |
|---|---|---|
| Position row | `position` | `{symbol, qty, avg_price, current_price, pnl, pnl_pct, holding_days}` |
| Watchlist item | `watchlist` | `{symbol, current_price, alert_above, alert_below, notes}` |
| Portfolio summary | `portfolio` | `{total_value, day_pnl, positions_count, cash_available}` |
| Trade history row | `trade` | `{symbol, direction, qty, price, pnl, date, reasoning}` |
| Alert notification | `alert` | `{alert_type, symbol, trigger_price, current_price}` |

**Orchestrator Handling**: The orchestrator system prompt already receives the user message as-is. The `[CONTEXT: ...]` prefix tells it to use that data as grounding for its response, reducing the need for a separate tool call to fetch the same data.

### 3.2 Quick Action Buttons

After the AI responds with analysis or suggestions, the response includes contextual action buttons (see Section 2.6). These are generated by the orchestrator based on the conversation context.

### 3.3 Chat Awareness of Dashboard State

The cockpit chat has access to a lightweight "dashboard state" object that gets injected as part of the system prompt context (similar to how memories are injected today).

```python
# Injected into orchestrator deps for cockpit threads
dashboard_context = {
    "active_view": "positions",      # What tab the user has open
    "selected_symbol": "RELIANCE",   # If a specific stock is selected
    "time_range": "1D",              # Chart time range
    "market_status": "open",         # From nf-market-status
    "alerts_pending": 2,             # Unread alerts count
}
```

This context is NOT sent on every message (too expensive). It's sent once when the chat opens and updated only when the user explicitly interacts with a dashboard element.

---

## 4. Data Flow Architecture

### 4.1 Real-Time Updates: SSE for Dashboard

The dashboard uses **Server-Sent Events (SSE)** for real-time data, extending the existing AG-UI SSE infrastructure.

**New SSE Endpoint**: `GET /api/cockpit/stream`

```
Client (Dashboard)                         Server
     |                                        |
     |── GET /api/cockpit/stream ────────────>|
     |                                        |
     |<── event: portfolio_update ────────────|  (every 30s during market hours)
     |    data: {positions, pnl, cash}        |
     |                                        |
     |<── event: alert ──────────────────────|  (on trigger)
     |    data: {type, symbol, message}       |
     |                                        |
     |<── event: price_tick ─────────────────|  (every 5s for watchlist stocks)
     |    data: {symbol, price, change_pct}   |
     |                                        |
     |<── event: insight ────────────────────|  (on generation)
     |    data: {type, message, actions}      |
     |                                        |
     |<── event: heartbeat ──────────────────|  (every 15s)
     |    data: {timestamp}                   |
```

**Why SSE not WebSocket**: The existing codebase already uses SSE for AG-UI streaming. Adding another SSE endpoint is simpler than introducing WebSocket infrastructure. SSE is sufficient because dashboard updates are server-to-client only (client actions go through regular REST API).

**Why not Polling**: Polling at the rate needed for position updates (every 5-30 seconds) creates unnecessary HTTP overhead. SSE keeps a single connection open and pushes updates as they happen.

### 4.2 Proactive AI Insights: Background Task

```
┌──────────────────────────────────────────────────────────────┐
│                   FastAPI Lifespan                           │
│                                                              │
│  on_startup:                                                 │
│    - Start AlertEvaluatorTask (runs during market hours)     │
│    - Start InsightGeneratorTask (runs end-of-day)            │
│                                                              │
│  on_shutdown:                                                │
│    - Cancel all background tasks                             │
│    - Flush pending alerts                                    │
└──────────────────────────────────────────────────────────────┘

AlertEvaluatorTask (asyncio.create_task):
  while market_is_open():
      prices = await batch_fetch_prices(user_watchlist + user_positions)
      alerts = evaluate_alert_conditions(prices, thresholds)
      for alert in alerts:
          await insert_alert_queue(alert)
      await asyncio.sleep(60)  # 1-minute cycle

InsightGeneratorTask (asyncio.create_task):
  # Runs once after market close (15:45 IST)
  while True:
      await sleep_until(next_market_close + 15_minutes)
      for user in active_users_today:
          insights = await generate_daily_insights(user)
          await store_insights(user, insights)
```

### 4.3 Daily Compression: Lazy on Next-Day Load

The compression does NOT run as a cron job or scheduled task. It runs **lazily** when the next day's cockpit thread is created.

**Flow**:
1. User opens cockpit on Feb 8
2. System computes cockpit thread ID: `cockpit_1_2026-02-08`
3. Thread doesn't exist --> trigger creation
4. Find previous cockpit thread: query for most recent thread where `conversation_type = 'cockpit'` and `user_id = X` and `created_at < today`
5. If found, compress it using trading-specific extraction prompt (Section 1.5)
6. Create new thread with `forked_from_id` pointing to previous day
7. Store compressed context as `fork_summary`
8. Generate morning briefing as first system message

**Why Lazy, Not Cron**:
- No wasted computation for inactive users
- No dependency on cron infrastructure
- The 2-5 second compression latency is acceptable on first load (user sees a loading spinner)
- If the user never opens the dashboard, no compression is needed

### 4.4 Price Data Caching Strategy

Upstox API has rate limits. The system needs a caching layer for price data.

```python
# In-memory cache with TTL (no external cache dependency)
from functools import lru_cache
from datetime import datetime, timedelta

class PriceCache:
    """Simple in-memory price cache with TTL."""

    def __init__(self, ttl_seconds: int = 5):
        self._cache = {}  # {symbol: (price_data, timestamp)}
        self._ttl = timedelta(seconds=ttl_seconds)

    def get(self, symbol: str) -> Optional[dict]:
        if symbol in self._cache:
            data, ts = self._cache[symbol]
            if datetime.now() - ts < self._ttl:
                return data
        return None

    def set(self, symbol: str, data: dict):
        self._cache[symbol] = (data, datetime.now())

    def batch_set(self, prices: dict):
        now = datetime.now()
        for symbol, data in prices.items():
            self._cache[symbol] = (data, now)
```

This cache is shared between the SSE dashboard stream and the alert evaluator task.

---

## 5. Database Schema Changes

### 5.1 Conversation Model Addition

```python
# Add to existing Conversation model in database/models.py

# New field
conversation_type = Column(String(20), default="chat", nullable=False)
# "chat" = regular conversation (existing)
# "cockpit" = daily trading cockpit thread

# New index
Index('idx_cockpit_lookup', 'user_id', 'conversation_type', 'created_at')
```

**Migration**: `ALTER TABLE conversations ADD COLUMN conversation_type VARCHAR(20) DEFAULT 'chat' NOT NULL;`

### 5.2 Alert Queue Table (New)

```python
class AlertQueue(Base):
    """Queue for proactive alerts to be delivered to users."""
    __tablename__ = "alert_queue"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Alert classification
    alert_type = Column(String(50), nullable=False)  # watchlist_target_hit, stop_loss_approaching, etc.
    severity = Column(String(20), nullable=False, default="medium")  # low, medium, high, critical

    # Alert content
    symbol = Column(String(50), nullable=True)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    payload = Column(JSON, nullable=True)  # Additional structured data

    # Delivery tracking
    status = Column(String(20), default="pending", nullable=False)  # pending, delivered, dismissed, expired
    created_at = Column(DateTime, default=utc_now, nullable=False)
    delivered_at = Column(DateTime, nullable=True)
    dismissed_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)  # Auto-expire stale alerts

    # Link to cockpit thread where alert was delivered
    conversation_id = Column(String, ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        Index('idx_alert_queue_user_status', 'user_id', 'status'),
        Index('idx_alert_queue_created', 'created_at'),
    )
```

### 5.3 Daily Summary Table (New)

```python
class DailyTradingSummary(Base):
    """Pre-computed daily trading summary for fast dashboard loading."""
    __tablename__ = "daily_trading_summaries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    trading_date = Column(DateTime, nullable=False)  # Date of trading day (IST)

    # Portfolio snapshot at end of day
    portfolio_value = Column(Float, nullable=True)
    cash_available = Column(Float, nullable=True)
    invested_value = Column(Float, nullable=True)

    # Day's performance
    day_pnl = Column(Float, nullable=True)
    day_pnl_percentage = Column(Float, nullable=True)
    trades_executed = Column(Integer, default=0)
    trades_won = Column(Integer, default=0)
    trades_lost = Column(Integer, default=0)

    # AI-generated insights (computed after market close)
    insights = Column(JSON, nullable=True)  # List of insight objects
    lessons = Column(JSON, nullable=True)   # List of lesson strings

    # Compressed context for next-day carry-over
    compressed_context = Column(Text, nullable=True)  # TOON-encoded context

    # Link to cockpit thread
    cockpit_thread_id = Column(String, ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True)

    created_at = Column(DateTime, default=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint('user_id', 'trading_date', name='unique_daily_summary'),
        Index('idx_daily_summary_user_date', 'user_id', 'trading_date'),
    )
```

### 5.4 No Changes Required

These existing tables work as-is:
- `trades` -- Already has all fields needed for trade tracking
- `agent_decisions` -- Already flexible enough for insights (use new `decision_type` values)
- `memories` -- Already supports trading-specific categories
- `messages` -- Already supports tool_calls, reasoning, timeline
- `watchlist_items` -- Already has alert_above/alert_below fields

---

## 6. API Endpoints

### 6.1 Cockpit Thread Endpoints

```
# Get or create today's cockpit thread
GET /api/cockpit/today
  Response: { thread_id, title, created_at, is_new, morning_briefing? }

  Behavior:
  - Computes cockpit_{user_id}_{today_date_ist}
  - If exists: returns it
  - If not: creates it, compresses previous day, returns it with is_new=true
  - If is_new and market_is_open: includes morning_briefing in response

# List cockpit threads (trading day history)
GET /api/cockpit/history?limit=30&offset=0
  Response: { threads: [{id, title, date, day_pnl, trades_count}], total }

  Behavior:
  - Queries conversations where conversation_type = 'cockpit'
  - Joins with daily_trading_summaries for P&L and trade count

# Get cockpit dashboard state
GET /api/cockpit/dashboard
  Response: {
    portfolio: {...},
    watchlist: [...],
    active_alerts: [...],
    today_trades: [...],
    market_status: {...}
  }

  Behavior:
  - Aggregates multiple data sources into single response
  - Uses PriceCache for fast price lookups
```

### 6.2 SSE Stream Endpoint

```
# Real-time dashboard updates
GET /api/cockpit/stream
  Headers: Authorization: Bearer <token>
  Response: SSE stream with events:
    - portfolio_update (every 30s during market hours)
    - alert (on trigger)
    - price_tick (every 5s for watched symbols)
    - insight (when new insight is generated)
    - heartbeat (every 15s)
```

### 6.3 Alert Endpoints

```
# Get pending alerts
GET /api/cockpit/alerts?status=pending
  Response: { alerts: [...], count }

# Dismiss an alert
POST /api/cockpit/alerts/{alert_id}/dismiss
  Response: { status: "success" }

# Get alert history
GET /api/cockpit/alerts/history?limit=50
  Response: { alerts: [...], total }
```

### 6.4 Insight Endpoints

```
# Get today's insights
GET /api/cockpit/insights/today
  Response: { insights: [...], generated_at }

# Get historical insights
GET /api/cockpit/insights?days=30
  Response: { insights: [...] }
```

### 6.5 Contextual Chat Endpoint

No new endpoint needed. The existing AG-UI `/awp` (agent worker protocol) endpoint handles cockpit chat. The only change is that the orchestrator gets `conversation_type` from the thread metadata and adjusts its behavior accordingly (more trading-focused, less general chat).

---

## 7. Background Jobs

### 7.1 Job Registry (FastAPI Lifespan)

All background jobs are asyncio tasks managed by FastAPI's lifespan. No external job scheduler needed.

```python
# In main.py lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    tasks = []

    # Alert evaluator - runs during market hours
    tasks.append(asyncio.create_task(alert_evaluator_loop()))

    # Daily insight generator - runs after market close
    tasks.append(asyncio.create_task(daily_insight_generator_loop()))

    yield

    # Shutdown
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
```

### 7.2 Alert Evaluator

```python
async def alert_evaluator_loop():
    """Check alert conditions every 60 seconds during market hours."""
    while True:
        try:
            if not is_market_hours():
                # Sleep until next market open
                await sleep_until_market_open()
                continue

            # Get all users with active watchlist alerts or open positions
            async with db_manager.async_session() as db:
                users_with_alerts = await get_users_with_active_alerts(db)

                for user_id in users_with_alerts:
                    alerts = await evaluate_alerts_for_user(db, user_id)
                    for alert in alerts:
                        await insert_alert(db, alert)

            await asyncio.sleep(60)

        except Exception as e:
            logger.error(f"Alert evaluator error: {e}")
            await asyncio.sleep(60)
```

### 7.3 Daily Insight Generator

```python
async def daily_insight_generator_loop():
    """Generate end-of-day insights after market close."""
    while True:
        try:
            # Wait until 15:45 IST (15 minutes after market close)
            await sleep_until_eod_insight_time()

            async with db_manager.async_session() as db:
                # Find users who traded today
                active_users = await get_users_who_traded_today(db)

                for user_id in active_users:
                    # Generate insights using LLM
                    insights = await generate_trading_insights(db, user_id)

                    # Store in daily_trading_summaries
                    await store_daily_summary(db, user_id, insights)

                    # Also store notable insights as memories
                    for insight in insights.get('lessons', []):
                        await store_as_memory(db, user_id, insight, category='past_learnings')

        except Exception as e:
            logger.error(f"Daily insight generator error: {e}")

        # Sleep until next day
        await asyncio.sleep(3600)  # Check hourly
```

---

## 8. Implementation Priorities

### Phase 1: Foundation (Must-Have for MVP)

1. **Add `conversation_type` to Conversation model** -- Single column addition + migration
2. **Cockpit thread auto-creation** -- `GET /api/cockpit/today` endpoint with deterministic ID
3. **Sidebar filtering** -- Show cockpit threads with badge, add type filter to list endpoint
4. **Day-to-day compression** -- Trading-specific extraction prompt for existing fork pipeline
5. **Morning briefing** -- Single LLM call to generate opening message

### Phase 2: Real-Time (High Value)

6. **SSE dashboard stream** -- `/api/cockpit/stream` with portfolio updates and price ticks
7. **Alert evaluator background task** -- Watchlist alert checking during market hours
8. **Alert queue + delivery** -- Toast notifications on frontend when alerts fire
9. **Price cache** -- In-memory cache shared between SSE stream and alert evaluator

### Phase 3: Intelligence (Differentiator)

10. **Contextual "Ask AI"** -- Context prefix injection from dashboard elements
11. **One-click action buttons** -- AG-UI custom events for action suggestions
12. **Daily insights generation** -- Post-market-close analysis of trading behavior
13. **Learning nudges** -- Pattern detection in trade history
14. **Risk warnings in HITL** -- Pre-trade risk checks shown in approval dialog

### Phase 4: Polish

15. **Alert history and management UI**
16. **Weekend/holiday handling**
17. **Trading calendar view** -- Browse cockpit threads by calendar date
18. **Performance analytics** -- Win rate trends, P&L charts, sector analysis
19. **Daily summary table population**

---

## Appendix A: Key Design Decisions

### Why one thread per day, not per trading session?
- Simpler mental model for users: "everything from today is in one place"
- Avoids confusion about when sessions start/end
- Market hours are well-defined (9:00-15:30 IST) but users may want to analyze after hours
- Compression is easier with a clear daily boundary

### Why lazy compression, not scheduled?
- Zero cost for inactive users (important for free tier)
- No infrastructure dependency (no cron, no scheduler)
- The 2-5 second latency on first morning load is acceptable
- Compression is idempotent -- if it fails, it can retry on next load

### Why SSE, not WebSocket?
- Existing codebase already uses SSE for AG-UI streaming
- Dashboard updates are unidirectional (server -> client)
- SSE auto-reconnects on connection drop (browsers handle this natively)
- Simpler server implementation (no connection state management)
- WebSocket would add complexity without clear benefit for this use case

### Why alert_queue table, not in-memory?
- Alerts survive server restarts
- Enables alert history and audit trail
- Allows de-duplication (don't re-alert the same condition)
- Supports multiple delivery channels in the future (email, push notification)

### Why not a separate microservice for alerts?
- The alert evaluator is a simple polling loop (< 100 lines of code)
- It shares the same database connection pool
- It needs access to the same Upstox client and price cache
- Adding a separate service adds deployment complexity without clear benefit
- If performance becomes an issue, it can be extracted later

### Why deterministic thread IDs (`cockpit_{user}_{date}`)?
- No database query needed to find "today's thread"
- Avoids race conditions on concurrent requests
- Makes debugging trivial (thread ID tells you exactly what it is)
- Enables client-side navigation without server round-trip
