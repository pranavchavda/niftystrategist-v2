# Cockpit Dashboard — Implementation Status

> Last updated: Feb 8, 2026

## What's Done

### Phase 1: Mock Data UI (Feb 7)

Built the full cockpit dashboard with 8 components, all rendering with mock data:

| Component | File | Purpose |
|---|---|---|
| TopStrip | `frontend-v2/app/components/cockpit/TopStrip.tsx` | Portfolio value, Day P&L, Overall P&L, Cash, market status, refresh |
| MarketPulse | `frontend-v2/app/components/cockpit/MarketPulse.tsx` | NIFTY/BANKNIFTY/SENSEX ticker cards |
| WatchlistPanel | `frontend-v2/app/components/cockpit/WatchlistPanel.tsx` | Multi-watchlist with symbol search, Ask AI action |
| PriceChart | `frontend-v2/app/components/cockpit/PriceChart.tsx` | Candlestick chart via lightweight-charts v5 |
| PositionsTable | `frontend-v2/app/components/cockpit/PositionsTable.tsx` | Sortable positions/holdings table with expand rows |
| DailyScorecard | `frontend-v2/app/components/cockpit/DailyScorecard.tsx` | Trade stats, process ratings, reflection |
| CockpitChat | `frontend-v2/app/components/cockpit/CockpitChat.tsx` | AI chat panel with quick prompts, context injection |
| Mock Data | `frontend-v2/app/components/cockpit/mock-data.ts` | All mock data + OHLCV generator |

**Layout**: `frontend-v2/app/components/Dashboard.jsx` — replaced the old dashboard entirely.

**Auth layout**: `frontend-v2/app/routes/_auth.tsx` — hides scratchpad sidebar when on `/dashboard` route.

**Key fix**: lightweight-charts v5 API change — use `chart.addSeries(CandlestickSeries, opts)` not `chart.addCandlestickSeries(opts)`.

### Phase 1.5: Responsive Layout (Feb 8)

Made the dashboard usable at laptop/tablet sizes by progressively collapsing side panels into drawers.

#### Breakpoint Strategy

| Width | Left Panel (Watchlist) | Center (Chart+Table) | Right Panel (Chat) |
|---|---|---|---|
| 1536px+ (2xl) | Inline 280px | flex-1 | Inline 320px |
| 1280-1535px (xl) | Inline 280px | flex-1 | Drawer via FAB |
| 1024-1279px (lg) | Drawer via FAB | full width | Drawer via FAB |
| <1024px | Drawer via FAB | full width | Drawer via FAB |

#### Changes by File

**Dashboard.jsx**:
- Added `showWatchlistDrawer` / `showChatDrawer` state
- Watchlist Drawer: Headless UI Dialog, slides from left, `xl:hidden`
- Chat Drawer: Headless UI Dialog, slides from right, `2xl:hidden`
- Left panel inline: `hidden xl:block`
- Right panel inline: `hidden 2xl:block`
- Watchlist FAB: `xl:hidden fixed bottom-6 left-6` (dark circle, ListIcon)
- Chat FAB: `2xl:hidden fixed bottom-6 right-6` (amber circle, MessageSquareIcon)
- `handleAskAI` checks `window.innerWidth < 1536` to open drawer vs inline
- Shared `watchlistContent` variable used by both inline and drawer (no duplication)

**TopStrip.tsx**:
- Data items in `flex-1 min-w-0 overflow-x-auto` scrollable container
- "Cash" section: `hidden lg:flex`
- "Overall" section: `hidden xl:flex`
- Right side (Paper badge, LIVE, Refresh) pinned with `flex-shrink-0`

**PositionsTable.tsx**:
- Qty column: `hidden lg:table-cell` / `hidden lg:block`
- Avg Price, Day %, Days columns: `hidden xl:table-cell` / `hidden xl:block`
- Summary bar: "Invested" and "Current" labels `hidden lg:inline`
- Expanded row detail: `flex-wrap` for narrow screens

**DailyScorecard.tsx**:
- PF stat + divider: `hidden lg:inline`
- Streak + divider: `hidden xl:inline-flex`
- Expanded grid: `grid-cols-1 lg:grid-cols-2 xl:grid-cols-3`

**CockpitChat.tsx**:
- Added `isDrawer` and `onClose` optional props
- Collapsed state skipped when `isDrawer` is true
- Header close button uses `onClose` in drawer mode

---

## What's Next: Phase 2 — Live Data

Wire the cockpit to real Upstox data via backend APIs. Key tasks:

1. **Backend API endpoints** — Create FastAPI routes that the dashboard can call:
   - `GET /api/cockpit/portfolio` — portfolio summary (total value, day P&L, cash)
   - `GET /api/cockpit/positions` — open positions + holdings
   - `GET /api/cockpit/indices` — NIFTY, BANKNIFTY, SENSEX live prices
   - `GET /api/cockpit/ohlcv/{symbol}` — historical OHLCV for chart
   - `GET /api/cockpit/watchlist` — user's watchlists with live prices

2. **Frontend data fetching** — Replace mock data imports with `fetch()` calls in Dashboard.jsx, loading states, error handling.

3. **SSE streaming** — Real-time price updates via Server-Sent Events for:
   - Position P&L updates
   - Watchlist price changes
   - Index ticker updates

4. **Daily thread system** — CockpitChat tied to a daily conversation thread (one per trading day), persisted in the conversations table.

5. **Market status** — Replace `useState(true)` with real market hours check (use `nf-market-status` logic or a backend endpoint).

### Design docs
- Original design: `docs/plans/2026-02-07-cockpit-dashboard-design.md`
- AI integration design: `docs/plans/2026-02-07-daily-cockpit-thread-ai-integration-design.md`
