"""Curated trading fixtures for the memory-model bake-off.

Two fixture sets:
- EXTRACTOR_FIXTURES: realistic conversations with ground-truth `expected_save`
  (durable facts the extractor SHOULD capture) and `expected_reject` (ephemeral
  / queryable / session noise it should NOT save). Graded by a human/Claude
  reading the side-by-side dump.
- JUDGE_FIXTURES: individually-labeled candidate facts (accept|reject) that the
  quality judge must classify. These deliberately PASS the regex pre-filter, so
  the decision tests the JUDGE MODEL's judgment, not the regex.

See docs/plans/2026-05-23-prefix-cache-memory-port.md (memory pipeline).
"""

from __future__ import annotations

# --- Extractor fixtures ----------------------------------------------------
# Each: id, conversation [{role, content}], expected_save [{gist, category}],
# expected_reject [gist]. `gist` is a human description for grading, not an
# exact-match string.

EXTRACTOR_FIXTURES = [
    {
        "id": "risk_and_avoid_with_price_trap",
        "conversation": [
            {"role": "user", "content": "I never trade penny stocks — got burned badly on a few in 2019 and swore them off."},
            {"role": "assistant", "content": "Understood, I'll keep recommendations to liquid large/mid-caps."},
            {"role": "user", "content": "Right. And keep my risk at 2% of capital per trade, always. What's NIFTY at right now?"},
            {"role": "assistant", "content": "NIFTY is at 24,850, up 0.4% on the day."},
        ],
        "expected_save": [
            {"gist": "avoids penny stocks (past losses in 2019)", "category": "avoid_list"},
            {"gist": "risk 2% of capital per trade", "category": "risk_tolerance"},
        ],
        "expected_reject": [
            "NIFTY is at 24,850 (live price, ephemeral)",
            "user asked what NIFTY is at (session query)",
        ],
    },
    {
        "id": "sector_pref_and_style",
        "conversation": [
            {"role": "user", "content": "I mostly swing trade — hold 2 to 5 days, rarely intraday. Focus on IT and banking names."},
            {"role": "assistant", "content": "Got it. Swing horizon, IT + banking focus."},
            {"role": "user", "content": "Yeah, and I avoid commodities entirely, never understood them."},
        ],
        "expected_save": [
            {"gist": "swing trader, holds 2-5 days", "category": "trading_style"},
            {"gist": "prefers IT and banking sectors", "category": "sector_preference"},
            {"gist": "avoids commodities", "category": "avoid_list"},
        ],
        "expected_reject": [],
    },
    {
        "id": "experience_and_comms",
        "conversation": [
            {"role": "user", "content": "I'm fairly new to this — please explain technical terms in plain language, I don't know much jargon yet."},
            {"role": "assistant", "content": "Absolutely, I'll keep it simple and define terms as we go."},
            {"role": "user", "content": "Thanks. Can you analyze RELIANCE for me today?"},
            {"role": "assistant", "content": "Sure. RELIANCE is showing an RSI of 58 and is above its 50-day EMA..."},
        ],
        "expected_save": [
            {"gist": "beginner experience level", "category": "experience_level"},
            {"gist": "wants plain-language explanations, minimal jargon", "category": "communication"},
        ],
        "expected_reject": [
            "user asked for RELIANCE analysis (session action)",
            "RELIANCE RSI is 58 (indicator, ephemeral)",
        ],
    },
    {
        "id": "schedule_and_sizing",
        "conversation": [
            {"role": "user", "content": "I only trade in the first hour after open — 9:15 to 10:15 — then I'm at my day job."},
            {"role": "assistant", "content": "Noted, first-hour trader."},
            {"role": "user", "content": "And cap any single position at 5% of my portfolio. Don't go above that."},
        ],
        "expected_save": [
            {"gist": "trades only first hour after open (9:15-10:15)", "category": "schedule"},
            {"gist": "max position size 5% of portfolio", "category": "position_sizing"},
        ],
        "expected_reject": [],
    },
    {
        "id": "pure_session_noise",
        "conversation": [
            {"role": "user", "content": "What's the option chain for BANKNIFTY this week?"},
            {"role": "assistant", "content": "Here's the BANKNIFTY weekly chain. ATM is 52000, the 52000 CE is at ₹210..."},
            {"role": "user", "content": "Ok place a buy order for 1 lot of the 52000 CE."},
            {"role": "assistant", "content": "[render_ui confirmation] Confirm: BUY 1 lot BANKNIFTY 52000 CE @ market?"},
            {"role": "user", "content": "yes"},
        ],
        "expected_save": [],
        "expected_reject": [
            "user wants to check the option chain (session task)",
            "BANKNIFTY 52000 CE at ₹210 (live premium)",
            "user placed a buy order on BANKNIFTY 52000 CE today (one-off action)",
        ],
    },
    {
        "id": "durable_buried_in_noise",
        "conversation": [
            {"role": "user", "content": "Margin left? And is the market open? Also remind me — I never hold F&O positions overnight, square everything off by 3pm."},
            {"role": "assistant", "content": "Available margin is ₹56,541 and yes, market is open. Noted on no overnight F&O."},
            {"role": "user", "content": "good. what's my P&L today?"},
            {"role": "assistant", "content": "You're up ₹3,200 today across 2 positions."},
        ],
        "expected_save": [
            {"gist": "never holds F&O overnight; squares off by 3pm", "category": "trading_style"},
        ],
        "expected_reject": [
            "available margin is ₹56,541 (queryable funds)",
            "market is open (queryable status)",
            "up ₹3,200 today (queryable P&L)",
        ],
    },
    {
        "id": "leverage_rule_and_indicator_pref",
        "conversation": [
            {"role": "user", "content": "Never recommend leverage above 2x for me. And for entries I like to see RSI below 30 before buying."},
            {"role": "assistant", "content": "Understood — max 2x leverage, and oversold (RSI<30) entries."},
        ],
        "expected_save": [
            {"gist": "never use leverage above 2x", "category": "risk_tolerance"},
            {"gist": "prefers buying when RSI below 30 (oversold entries)", "category": "trading_style"},
        ],
        "expected_reject": [],
    },
    {
        "id": "nothing_durable_smalltalk",
        "conversation": [
            {"role": "user", "content": "morning! thanks for the help yesterday, that was useful."},
            {"role": "assistant", "content": "Glad it helped! What would you like to look at today?"},
            {"role": "user", "content": "nothing yet, just saying hi"},
        ],
        "expected_save": [],
        "expected_reject": [
            "user said thanks / greeting (no durable info)",
        ],
    },
]


# --- Judge fixtures --------------------------------------------------------
# Individually-labeled facts. All chosen to PASS the regex pre-filter so the
# JUDGE MODEL's judgment is what's measured. label: "accept" (good, durable,
# weighted >=7 / INSERT) or "reject" (queryable/transient/session/generic).

JUDGE_FIXTURES = [
    # --- should ACCEPT (durable, behavioral, not queryable) ---
    {"fact": "User's risk tolerance is conservative — max 1% of capital per trade.", "category": "risk_tolerance", "label": "accept"},
    {"fact": "User prefers EMA crossover entries for equity intraday.", "category": "trading_style", "label": "accept"},
    {"fact": "User avoids the pharma sector entirely after past losses.", "category": "avoid_list", "label": "accept"},
    {"fact": "User wants trade rationale explained in plain language, not jargon.", "category": "communication", "label": "accept"},
    {"fact": "User is a swing trader who typically holds positions for two to five days.", "category": "trading_style", "label": "accept"},
    {"fact": "User never holds F&O positions overnight.", "category": "trading_style", "label": "accept"},
    {"fact": "User only trades during the first hour after market open.", "category": "schedule", "label": "accept"},
    # --- should REJECT (queryable / transient / session / generic) ---
    {"fact": "User currently holds 65 lots of the NIFTY 23750 call option.", "category": "position_sizing", "label": "reject"},
    {"fact": "Available margin is 56,541 rupees.", "category": "context", "label": "reject"},
    {"fact": "NIFTY is trading at 23,810 right now.", "category": "context", "label": "reject"},
    {"fact": "RSI on RELIANCE is 58 today.", "category": "context", "label": "reject"},
    {"fact": "User placed a buy order on TATACHEM this morning.", "category": "task", "label": "reject"},
    {"fact": "User wants to check today's option chain for BANKNIFTY.", "category": "task", "label": "reject"},
    {"fact": "Stocks can go up or down depending on market conditions.", "category": "fact", "label": "reject"},
    {"fact": "The user is currently up 3,200 rupees on the day.", "category": "context", "label": "reject"},
]
