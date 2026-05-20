---
name: nifty-strategist-design
description: Use this skill to generate well-branded interfaces and assets for Nifty Strategist (AI-powered trading assistant for Indian stock markets, NSE/BSE), either for production or throwaway prototypes/mocks. Contains essential design guidelines, colors, type, fonts, assets, and UI kit components for prototyping the trading-cockpit and chat surfaces.
user-invocable: true
---

Read the `README.md` file within this skill, and explore the other available files.

If creating visual artifacts (slides, mocks, throwaway prototypes, etc), copy assets out and create static HTML files for the user to view. Import `colors_and_type.css` at the top and use the CSS custom properties it exposes. Use the high-fidelity recreations under `ui_kits/cockpit/` and `ui_kits/chat/` as a starting point for new screens.

If working on production code, you can copy assets and read the rules here to become an expert in designing with this brand. The source codebase is at <https://github.com/pranavchavda/niftystrategist-v2> — its `frontend-v2/app/styles/design-tokens.ts` and `frontend-v2/app/index.css` remain the canonical token sources.

If the user invokes this skill without any other guidance, ask them what they want to build or design, ask some questions (especially: which surface — Cockpit dashboard, conversational chat, settings, or a new screen? light or dark mode? what data are they showing?), and act as an expert designer who outputs HTML artifacts _or_ production code, depending on the need.

Key things to remember while designing for this brand:

- **Tabular numerals** on every price, quantity, and P&L value. Use `Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' })` for money.
- **Green = profit/buy, Red = loss/sell.** Never reverse, never use these for non-trading state.
- **Amber-500** is the brand-accent (active states, "Ask AI" sparkle, FAB chat). **Blue-600** is the logo gradient + links + focus.
- **Zinc** is the only neutral — top to bottom of the surface.
- **Glass-morphism** (`bg-white/70 backdrop-blur-xl`) is the signature chrome treatment for topbar / sidebar / modal.
- **Eyebrow labels** (`10–11px, 700-weight, uppercase, tracking-[0.15em], zinc-400`) sit above every dense panel.
- **Sentence case** for every label, button, heading. No Title Case.
- **No emoji** in product copy or UI chrome. The one exception is `⚠️` on order-confirmation cards.
- **Icons** come from Lucide (preferred) or Heroicons outline (24-grid). Never hand-rolled SVG.
- **Currency** is always `₹` with `en-IN` grouping.
- **Tone** is calm, second-person, fact-then-interpretation-then-suggestion. The agent is a junior analyst, not a hype machine.
