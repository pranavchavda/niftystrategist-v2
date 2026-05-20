# Cockpit UI kit

A high-fidelity recreation of the Nifty Strategist **trading cockpit** (`/dashboard` in production). This is the dense, Bloomberg-terminal-flavored surface — three zones (left-rail watchlist + center hub + right chat drawer), a top portfolio strip, KPI cards, sortable positions table, daily scorecard, and floating action buttons.

## What's inside

- `index.html` — the entry point. Boots React + Babel and assembles every component below into the full dashboard. Open this to see the kit live.
- `mockData.jsx` — the same dataset shape used by the production code (`frontend-v2/app/components/cockpit/mock-data.ts`), with ticker symbols, P&L values, watchlists, and Nifty/BankNifty/VIX index quotes.
- `TopStrip.jsx` — sticky portfolio summary strip with Portfolio / Day P&L / Overall / Margin and the LIVE pill + auto-refresh toggle.
- `PortfolioOverview.jsx` — the six KPI cards (Total value, Day P&L, Total P&L, Invested, Available, Margin used).
- `QuickLinks.jsx` — the six secondary-nav tiles (Charts / Monitor / Mandates / Scalp / Notes / Strategies).
- `MarketPulse.jsx` — Nifty / BankNifty / India VIX index quote pills with up/down tint.
- `WatchlistPanel.jsx` — tabbed watchlist with sparkline rows, alert bell, hover actions.
- `PositionsTable.jsx` — segmented tabs (Open / Holdings / Trades / Mutual funds) + sortable dense table with expandable row footer (stop loss, target, charges).
- `DailyScorecard.jsx` — end-of-day win/loss summary card.

## Coverage

The kit covers the **Cockpit dashboard only**. It is not a storybook — `index.html` lays everything out as a real `/dashboard` view would render. Drawers (mobile watchlist, mobile chat) are present in the production code; this kit shows only the inline xl+ layout for clarity.

## How to extend

To recreate other surfaces (e.g. `/charts`, `/monitor`, `/strategies`), follow the same conventions used here:

1. Always import `colors_and_type.css` for tokens.
2. Use `.ns-eyebrow` above every dense panel.
3. Use `.ns-num` (tabular numerals) on every price / qty / P&L value.
4. `bg-white/70 backdrop-blur-xl` for chrome (topbar/sidebar), opaque `bg-white dark:bg-zinc-900` for card bodies.
5. Green = profit/BUY, Red = loss/SELL — never mix semantics.
