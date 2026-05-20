# Nifty Strategist Design System

A design system distilled from **Nifty Strategist** — an AI-powered, conversational trading assistant for the Indian stock market (NSE/BSE). Forked from "EspressoBot" but trading-domain everywhere; the codebase still contains a handful of legacy commit references.

> **Tagline**: AI-powered trading assistant for Indian stock markets (NSE/BSE)
> **Manifest description**: "Upstox connected AI-powered trading assistant for the Indian stock market (NSE/BSE). Analyze stocks, track portfolios, and execute trades with intelligent recommendations."

## Sources used to build this system

- **Source repo**: <https://github.com/pranavchavda/niftystrategist-v2> (`main`)
  - `frontend-v2/app/styles/design-tokens.ts` — canonical token table (colors, typography, spacing, shadows, glass, animations, presets)
  - `frontend-v2/app/index.css` — Tailwind v4 `@theme` block, global keyframes, glass-morphism utilities, skeleton/scrollbar systems
  - `frontend-v2/app/components/cockpit/*` — the **Cockpit** dashboard recreated in `ui_kits/cockpit/`
  - `frontend-v2/app/components/catalyst/*` — the project uses the [Catalyst by Tailwind Labs](https://catalyst.tailwindui.com/) component pack (`button`, `badge`, `input`, `dropdown`, `dialog`, `navbar`, etc.). We do **not** redistribute Catalyst — we recreate the visual look in our own JSX.
  - `frontend-v2/app/components/ChatInput.jsx`, `MessageBubble.jsx` — chat surface
  - `frontend-v2/app/components/cockpit/mock-data.ts` — sample stock symbols, P&L values, watchlists (used verbatim in the UI kit so screens look real)
  - `frontend-v2/public/manifest.json`, `frontend-v2/public/icons/*` — installable-app branding (logo, theme color, shortcut targets)
  - `CLAUDE.md`, `README.md` — voice, copy patterns, feature surface

If you have access to the repo, browse those files directly for the most up-to-date source of truth. This design system snapshot was taken **2026-05-20**.

## What the product does (in one breath)

A conversational LLM agent (the "Orchestrator") that you talk to like a junior trader. It calls into a battery of CLI tools (`nf-quote`, `nf-analyze`, `nf-portfolio`, `nf-order`, `nf-options`, `nf-watchlist`, `nf-monitor`, …) via Upstox, then renders results either as **markdown chat replies** with embedded confirmation UI cards, or in a dense **Cockpit dashboard**. Every order placement is human-in-the-loop — the agent renders an `[Approve] [Reject]` confirmation card before any trade actually fires.

Two primary surfaces:

1. **Chat** (`/chat/:threadId`) — the main interface. A scrolling thread, markdown messages, a sticky composer at the bottom, a tool-call breadcrumb at the top of each assistant turn. Heroicons, glass-morphism topbar, zinc neutrals.
2. **Cockpit / Dashboard** (`/dashboard`) — a Bloomberg-terminal-flavored dense data view: a top strip of portfolio KPIs, a left-rail Watchlist + Market Pulse, a center column of Positions / Holdings / Trades / Mutual-Fund tables with sortable columns and inline sparkline charts.

## Brand identity, quickly

- **Mark**: a blue-violet gradient rounded-square containing a single white `↗` (`ArrowTrendingUpIcon` from Heroicons, stroke 1.5). The whole product is "an arrow going up and to the right".
- **Primary brand color**: `amber-500 (#f59e0b)` — used for the FAB "Ask AI", active watchlist tab, sparkle/info accents, "Steer" chevron, AI-action affordances.
- **Accent color**: `blue-600 (#2563eb)` — used for the logo gradient, links, info badges, focus rings.
- **Neutral**: Tailwind's `zinc` ramp, top to bottom — the entire UI chrome sits on zinc surfaces.
- **Trading semantics**: green for profit/buy, red for loss/sell — never reverse this, never use them for non-trading state.
- **Typeface**: **Inter Variable** (sans), **Monaco / JetBrains Mono** (mono for code blocks). Tabular numerals are on for every number in the UI.

---

## Index — files in this design system

| Path | What it is |
|---|---|
| `README.md` | This file — orientation, brand, content & visual fundamentals. |
| `SKILL.md` | Front-matter skill descriptor for Claude Code use. |
| `colors_and_type.css` | All CSS custom properties — colors, type scale, radii, shadows, spacing, motion. Import this into anything you build. |
| `fonts/README.md` | Webfonts (Inter, JetBrains Mono) are loaded from Google Fonts inside `colors_and_type.css`. No `.ttf`/`.woff2` files are vendored — see notes below. |
| `assets/logo-512.png`, `logo-192.png`, `logo-96.png`, `favicon.png` | The official PWA app icon — blue gradient + white trending-up arrow. |
| `assets/legacy-eb-logo*.webp` | Earlier "EspressoBot" mark, retained for reference. **Do not use** in new Nifty Strategist designs. |
| `preview/*.html` | Small specimen cards that populate the Design System tab — colors, type, spacing, components. |
| `ui_kits/cockpit/` | High-fidelity recreation of the trading Cockpit dashboard. Start at `ui_kits/cockpit/index.html`. |
| `ui_kits/chat/` | High-fidelity recreation of the conversational chat surface. Start at `ui_kits/chat/index.html`. |

## Quick start for a new design

1. Open one of the kits as a reference (`ui_kits/cockpit/index.html` or `ui_kits/chat/index.html`).
2. Copy the components you need into your file and adapt.
3. Import `colors_and_type.css` at the top of any new HTML you write.
4. Use the previews (`preview/*.html`) as cheat sheets for individual specimens — type, colors, badges, KPI cards, etc.

---

## CONTENT FUNDAMENTALS

### Voice — "your junior analyst, two coffees in"

The agent is positioned as a **competent trading companion**, not a tool. Marketing copy: "An intelligent trading companion that helps you analyze stocks, understand market opportunities, and execute trades with human-in-the-loop approval." The CLAUDE.md guidelines reinforce: "educational tone for non-technical users", "Maximum agent autonomy for analysis", "render_ui confirmation card only for actual transactions".

**Tone is informed, calm, second-person, and honest about risk.** It will tell you when something looks bad. It will quote actual numbers rather than wave hands. It avoids hype-words ("moonshot", "to the moon", "🚀") and emoji-driven excitement.

### Pronouns

- **You** for the trader. Always second-person.
- **I / my take** for the agent when it offers an opinion. Used sparingly and only when reasoning is shown.
- **We** is essentially never used; this is not a team product.

### Capitalisation, casing, punctuation

- **Sentence case** for titles, buttons, menu items: "New chat", "Daily scorecard", "Cancel rule". Never Title Case.
- **ALL-CAPS micro-eyebrows** with 0.15em tracking for section dividers in dense UI: `MARKET PULSE`, `WATCHLIST`, `PORTFOLIO`, `OVERALL`. 10–11px, font-weight 700, zinc-400/500.
- **Ticker symbols** are always uppercase, monospace-feel: `RELIANCE`, `TCS`, `BAJFINANCE`. Treat them like proper nouns.
- **Currency** is always Indian Rupees, formatted via `Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' })`. Whole-rupee precision for portfolio / KPI values; two-decimal precision for prices. `₹2,847.50` not `Rs 2847.5`.
- **P&L sign**: always show `+` for positive (it's a feature, not noise), never show `+` for zero. Example: `+₹675` / `-₹500` / `+1.69%` / `-1.40%`.
- **Em-dashes** for "support at 2,780 — last week's low". Hyphens for compound modifiers.

### Vibe & rhythm

Sample agent reply (from the source `README.md`):

> "RELIANCE is trading at ₹2,847.50, up 1.2% today. The RSI is at 58 (neutral), and it's above its 20-day moving average which suggests bullish momentum. The stock found support at ₹2,780 last week. Would you like me to do a deeper technical analysis?"

Sample order-confirmation reply:

> "I'll place an order to buy 10 shares of TCS at the current market price of ₹4,125.00. Total value: ₹41,250.
> ⚠️ This requires your approval. Confirm this trade?  [Approve] [Reject]"

Sample longer analytical reply (from `cockpit/mock-data.ts`):

> "INFY is at 1,755 — just 25 points (1.4%) above your stop loss at 1,730.
> **Technical picture:**
> - RSI: 38 (approaching oversold)
> - Below 20-day SMA (bearish)
> - Support at 1,730–1,740 zone
> **My take:** The stop loss is doing its job. Rather than panic-exit, let it play out…"

Patterns to lift:

- Lead with the **fact** ("INFY is at 1,755"), then the **interpretation** (oversold/bullish/bearish), then the **suggestion** ("consider tightening your stop").
- Use **markdown structure** in long replies: `### Sections`, `- bullet lists`, `**bold**` for the key data points, occasional bold-italic for "My take".
- Sprinkle a single `⚠️` only on confirmation prompts. **Otherwise no emoji in agent output.**
- Lists of 3 — "Your positions / Watchlist alerts / Today's focus".
- A `?` at the end is a strong signal the agent wants you to confirm before acting.

### Empty states, loading, errors

- Empty: terse, one sentence + a nudge. "No open positions / Start trading to see your positions here."
- Loading: skeletons (zinc shimmer). Never spinners on full panels — only on the global refresh button.
- Errors: red-50 background, red-600 text, single line, dismissible. Example string from `Dashboard.jsx`: "Failed to load funds — retry in 30s."
- The market-status pill has just two words: `LIVE` (green, pulsing dot) or `CLOSED` (red).

### Emoji

- **Never in agent prose.**
- **Never in UI chrome.** (No emoji buttons, no emoji-headed sections.)
- The one exception is `⚠️` on the trade-approval card, signalling that this requires HITL.
- All "icon needs" go to Heroicons + Lucide (see ICONOGRAPHY).

---

## VISUAL FOUNDATIONS

### Colors

The system has **one neutral (zinc)**, **two brand colors**, and **two trading semantics**.

| Role | Light | Dark | Where it's used |
|---|---|---|---|
| Canvas | `zinc-50` | `zinc-950` | Page background |
| Surface | `white` | `zinc-900` | Card body, panels |
| Muted bg | `zinc-100` | `zinc-800` | Inputs, chips, segmented controls |
| Text strong | `zinc-900` | `zinc-100` | Headlines, KPI values |
| Text default | `zinc-800` | `zinc-200` | Body |
| Text muted | `zinc-500` | `zinc-400` | Labels, captions |
| Text subtle | `zinc-400` | `zinc-500` | Eyebrows, disabled |
| Border | `zinc-200/70` | `zinc-800/70` | Card borders, dividers |
| **Brand (amber)** | `amber-500` | `amber-400` | Active watchlist tab, "Ask AI", FAB-chat, focus accents on trading actions |
| **Accent (blue)** | `blue-600` | `blue-400` | Logo gradient, links, focus rings, info badges |
| Secondary (purple) | `purple-600` | `purple-400` | AI reasoning / thinking displays |
| Profit | `green-600` | `green-400` | Up sparkline, positive P&L, BUY badge |
| Loss | `red-600` | `red-400` | Down sparkline, negative P&L, SELL badge |

Notes:

- **Amber is the trading-brand accent**, not the logo. The logo is blue gradient; amber lives in the UI.
- The product is **fully dark-mode capable** — every component must read in both modes. Dark mode is the more common deployment for traders.
- Tints use `/15`, `/20`, `/30` opacity suffixes (Catalyst convention) for badges: e.g. green badge = `bg-green-500/15 text-green-700 dark:bg-green-500/10 dark:text-green-400`.

### Typography

- **Inter Variable** for everything except code. Weights used: 400, 500, 600, 700. Letter-spacing tightens at h1/h2.
- **Tabular nums on every number.** Use `tabular-nums` in Tailwind, or `font-variant-numeric: tabular-nums lining-nums;` — non-tabular currency in tables is a bug.
- **Eyebrows** are the signature: `10–11px, font-weight 700, uppercase, tracking-[0.15em], color: zinc-400/500`. Used above every dense panel.
- Type scale follows Tailwind defaults: `text-xs (12)`, `text-sm (14)`, `text-base (16)`, `text-lg (18)`, `text-xl (20)`, `text-2xl (24)`, `text-3xl (30)`. The Cockpit goes denser — `text-[10px]`, `text-[11px]` for table rows.

### Spacing

- 4px grid. Card interior padding is typically `p-3` (12px) in dense panels, `p-4 md:p-6` (16/24) in marketing-style cards.
- Compact dashboards use `gap-2` (8px) for grid cells, `space-y-1` to `space-y-2` between list items.
- Section gaps in landing/settings views use `gap-6` to `gap-8` (24/32).
- Horizontal rhythm: most dense rows use `px-3 py-2` so a 16-row table fits on a laptop.

### Backgrounds / patterns / imagery

- **No imagery, no illustrations, no photography in the core product UI.** The product is data — it pretends to be a Bloomberg terminal.
- The login / marketing surfaces use **ambient gradient washes**: `gradient-ambient` (light) = `linear-gradient(45deg, #f3e8ff, #eff6ff, #f0f9ff)`. Soft, low-contrast, used as page background — never on cards.
- **Glass morphism is the signature surface treatment.** Topbar, sidebar, modal, and cards all use `bg-white/70 backdrop-blur-xl border border-zinc-200/50` (and dark equivalents). Three preset levels: `glass-light-subtle (70/md)`, `glass-light (85/xl)`, `glass-light-strong (90/2xl)`. Don't stack two glass surfaces — one layer per region.
- **No full-bleed images.** Even the empty states are text-only.
- **Sparklines** are the most decorative element — `recharts` `<AreaChart>` with a fading gradient under a 1.5px stroke. Green when up, red when down.

### Borders & dividers

- Cards: `border border-zinc-200/50 dark:border-zinc-800/50` with `rounded-lg` (12px) for the default, `rounded-xl` (16px) for elevated, `rounded-2xl` (24px) for hero.
- Dividers between panels: `border-zinc-200/60 dark:border-zinc-800/60` — note the `/60` opacity. Borders are always **slightly transparent**; they should not punch through glass surfaces.
- Inputs: 1px border, `border-zinc-200 hover:border-zinc-300` light / `border-white/10 hover:border-white/20` dark.

### Shadows

- Cards: `shadow-sm` by default, `shadow-md` on hover for interactive ones, `shadow-lg` on elevated.
- The FAB chat button uses an **amber-tinted shadow**: `shadow-lg shadow-amber-500/20`. Same trick for blue and red action buttons.
- Modals: `shadow-2xl` + glass-strong + a backdrop overlay (`bg-black/30`).
- Inner shadows are not used.

### Corner radii

The system uses six radii — pick by element:

| Token | Value | Use |
|---|---|---|
| `radius-xs` | 4px | tiny chips, switch knobs |
| `radius-sm` | 6px | badges, dense list rows |
| `radius-md` | 8px | buttons, segmented controls |
| `radius-lg` | 12px | **cards (default)**, inputs, dropdowns |
| `radius-xl` | 16px | elevated cards, modals |
| `radius-2xl` | 24px | hero panels, full-screen empty states |
| `radius-full` | — | avatars, pills, FAB |

### Hover, press, focus

- **Hover**: lighten / darken by ~5–10%, often by stepping zinc by one — `text-zinc-500 → hover:text-zinc-700` and `hover:bg-zinc-100 dark:hover:bg-zinc-800`. Interactive cards also get `hover:-translate-y-0.5` and `hover:shadow-md`.
- **Press / active**: `active:scale-95` for FABs, `active:scale-[0.99]` for cards. Solid buttons step their bg one shade darker.
- **Focus**: `focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2`. Never use a different focus color — focus is always blue.
- Disabled: `opacity-50`, `cursor-not-allowed`, no shadow.

### Animation

- All transitions are **150–200ms ease-out** by default. Global rule in `index.css` applies `cubic-bezier(0.4, 0, 0.2, 1)` 150ms to every property. Slow only for entrance animations (300ms).
- Keyframes in use: `slideInFromBottom`, `slideInFromRight`, `slideInFromLeft`, `fadeIn`, `scaleIn`, `shimmer` (skeletons), `breathe` (subtle 5% pulse), `gentleBounce`, `gradientShift` (ambient backgrounds, 6s).
- Skeletons shimmer for **2s linear**, with a `bg-gradient-to-r from-zinc-200 via-zinc-100 to-zinc-200` gradient.
- The market-status `LIVE` dot uses `animate-pulse` — that's the only constantly-animating element on the dashboard.
- **No bouncy easings**, no spring physics, no slop. The product wants to feel precise.

### Transparency & blur

- Used aggressively for chrome (topbar, sidebar) and modals. Background must be visible through the glass.
- Sticky table headers: `bg-zinc-50/95 dark:bg-zinc-900/95 backdrop-blur-sm`.
- Drawer overlay: `bg-black/30` (light) — no blur on the overlay.
- **Never blur card bodies.** Cards are crisp surfaces on top of (potentially blurred) chrome.

### Layout rules

- The Cockpit has three permanent zones: left rail (`280px`, collapsible to `40px`) + center (fluid) + right drawer (opens on demand, `340px`). On `< xl` viewports the left becomes a drawer triggered by a FAB.
- The chat surface uses a sidebar layout (Catalyst `sidebar-layout`): sidebar left (`240–280px`), main column max-`760px` centered, with the composer pinned to the bottom with glass-topbar styling.
- Dense table rows are `~36px tall`. Action affordances live on row-hover only (`opacity-0 group-hover:opacity-100`).
- Drawer panels enter from their edge (`translate-x-full → translate-x-0`) over 300ms.

### Numbers, badges, alerts

- **Badge colors map 1:1 to trading meaning**: green = BUY / profit, red = SELL / loss, amber = warning / risk, blue = info / status, zinc = neutral.
- **Status pills** are tiny — `text-[10px] font-semibold px-2 py-1 rounded-md`. Always uppercase content.
- A bell (`BellIcon`) sized `2.5px` indicates a price alert is set; a single sparkles (`SparklesIcon`) means "Ask AI".

---

## ICONOGRAPHY

This product uses **two icon sets in parallel**, by historical accident — Heroicons (older Catalyst-derived chrome) and Lucide (newer dashboard work). Both have a similar weight/look. **For new work, prefer Lucide** to match the dashboard direction.

### Sets in use

| Set | Where | Stroke | Size convention |
|---|---|---|---|
| **Heroicons v2 outline** (`@heroicons/react/24/outline`) | Navbar, settings, dropdowns, Catalyst-style chrome, the global navigation icon | 1.5px, 24-grid | `h-4 w-4` (16px) for compact, `h-5 w-5` (20px) for nav |
| **Lucide React** (`lucide-react`) | The Cockpit, watchlist actions, chat input toolbar, table sort indicators | 2px, 24-grid | `h-3 w-3` (12px) for dense rows, `h-3.5 w-3.5`–`h-4 w-4` for chrome |

**For prototypes in this system**, use the [Lucide CDN](https://unpkg.com/lucide-static) or `<lucide-icon>` web component — it matches the dominant dashboard look. For very compact data tables, drop to `12px`. For navbar/topbar, `16px`. For section heads, `20px`. Never larger than `24px` in chrome — bigger icons belong to empty states and onboarding only.

Iconography in the repo is **never embedded as inline SVGs hand-written by us** — every icon is imported from one of the two libraries. We mirror that here: pull icons from Lucide/Heroicons or copy from `assets/`.

### Specific icons that appear repeatedly

- `ArrowTrendingUpIcon` (Heroicons) — the brand mark itself; sits in the topbar in front of "Nifty Strategist" text.
- `TrendingUp / TrendingDown` (Lucide) — every P&L row, every index quote.
- `Sparkles` (Lucide) — "Ask AI" hover affordance on any data row.
- `Wallet`, `PiggyBank`, `Coins`, `Gauge` (Lucide) — the six portfolio KPI cards.
- `Bell` (Lucide) — price-alert set indicator.
- `RefreshCw` (Lucide) — the topbar refresh, spins while loading.
- `Search` (Lucide) — every filter/search input.
- `CircleDot` (Lucide) — the LIVE/CLOSED market-status pill (pulsing when LIVE).
- `Mic / MicOff`, `Paperclip`, `ImagePlus`, `Send`, `Square`, `Navigation` (Lucide) — chat input toolbar (voice input, attach, upload image, send, stop, steer).

### Emoji & unicode

- `₹` (U+20B9, INR sign) is the canonical currency mark, never `Rs.` or `INR `.
- `&` is fine in tickers (`M&M`, `BAJAJ-AUTO`).
- `⚠️` is reserved exclusively for the order-confirmation render_ui card.
- Otherwise no emoji.

### Logo files

`assets/logo-512.png`, `logo-192.png`, `logo-96.png` — the official rounded-square app icon. The mark inside is the Heroicons `ArrowTrendingUpIcon` in white, on a `135deg` blue gradient. The icon corners are `~22% radius` (PWA-maskable safe zone). On dark surfaces the icon stays the same — never invert.

`assets/favicon.png` — same mark, 32px.

`assets/legacy-eb-logo*.webp` — the previous "EspressoBot" mark. Brown coffee-bean glyph. **Do not use** in any Nifty Strategist surface; only kept for archeology and migration reference.

---

## Fonts — vendored locally

Inter Variable (sans, both styles) and JetBrains Mono (regular / medium / semibold) ship as `.woff2` files in `fonts/`. The `@font-face` declarations at the top of `colors_and_type.css` load them with `font-display: swap` and resolve URLs relative to the CSS file. If you copy `colors_and_type.css` elsewhere, copy `fonts/` next to it or rewrite the `src` URLs.

The source codebase loads the same families from Google Fonts at runtime. The mono there uses a Monaco / Menlo system stack; this skill picks JetBrains Mono explicitly because it composes more cleanly with Inter and renders consistently offline.

Fallback chain in `--font-sans` / `--font-mono` covers environments that can't load woff2 (system-ui for sans; Monaco / Menlo / Consolas for mono).

---

## How to use this system

When designing a new surface for Nifty Strategist:

1. **Import** `colors_and_type.css` at the top of your HTML.
2. **Lean on glass + zinc** for chrome (topbar, sidebar, drawer). Lean on solid `bg-white / dark:bg-zinc-900` for cards.
3. **Always use tabular numerals** for any number. Always use `Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' })` for money.
4. **Green/red for trading semantics only.** A green dot does not mean "active" in this product — it means profit.
5. **Eyebrow + dense list** is the dominant rhythm. Don't make things spacious unless you're on a settings or marketing page.
6. **Icons come from Lucide (preferred) or Heroicons.** No hand-rolled SVG, no emoji, no Material.
7. **Sentence case everywhere.** No Title Case.
8. **Approve/Reject anything destructive.** Render a confirmation card with `⚠️` and two buttons before any trade or any data-mutating action.

For deep recreations, see `ui_kits/cockpit/` (dashboard) and `ui_kits/chat/` (conversational thread).
