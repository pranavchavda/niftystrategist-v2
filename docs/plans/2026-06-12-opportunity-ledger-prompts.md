# Opportunity Ledger — Awakening Prompt Series v2.1 (2026-06-12)

**Problem (from Jun 11–12 audit):** NS picks good trades but never self-initiates — ~20
autonomous entry decision points across two days, zero entries taken without coaxing.
Three causes: (1) OOS validation still applied as an entry *gate* despite mandate v2
demoting it to sizing; (2) pulses framed as position-management checklists, entry mindset
shuts off after 09:20; (3) scorecard rewards restraint, never measures missed
participation. Plus the JBMA lesson: lazy OCO-only management let +₹2k revert to −₹2.2k.

**Fix:** an Opportunity Ledger. Selectivity stays primary — we punish *passivity*
(passing on identified setups with vague excuses), never *selectivity* (genuinely finding
nothing). Every evaluated-and-declined setup becomes a structured, falsifiable PASS line;
Post-Close replays them against actual candles and reports ₹ left on table vs ₹ saved —
good data in both directions. Excuse-shaped passes ("oversold", "past its peak", "market
was choppy") are structurally disallowed: they must convert to a named re-entry trigger
or a counter-direction thesis. Tracked **every day** — the playbook has setups for every
regime, so passivity is never regime-excused (Pranav, 2026-06-12).

Canonical protocol lives once in the mandate `custom_instructions`; prompts reference it.

---

## 1. Mandate `custom_instructions` — APPEND this block

> Apply via `nf-mandate edit` (cmd_edit uses deepcopy — safe). No restart needed.

```
OPPORTUNITY LEDGER (anti-passivity, 2026-06-12): Selectivity stays primary — but every
pass must be auditable. Whenever any awakening evaluates a specific setup and declines
it, log ONE line in the thread:
PASS: SYMBOL LONG|SHORT setup=<tag> tier=<hero|solid|spec> entry=<px> sl=<px> tgt=<px>
reason=<code> [trigger=<px/condition if no_trigger_yet>]
Reason codes: no_trigger_yet (MUST name the price/condition that would make you enter;
stage an nf-monitor entry rule when practical), rr_below_2, risk_rail
(slots/defense/cutoff/max-executions), thesis_conflict (name the conflicting evidence),
liquidity, other (1 line, concrete).
"Oversold", "extended", "past its peak", "too late" are NOT pass reasons — they convert
to no_trigger_yet with a named re-entry level, or they ARE a thesis for the opposite
direction. "Market was choppy/mixed/uncertain" is NOT a pass reason — every regime has
playbook setups (TRENDING: ORB/momentum; MIXED: VWAP fade/MR + defined-risk F&O;
RANGE_BOUND: condor/MR; macro: regime ETF).
PRE-APPROVED structures (yesterday's learnings or principal): default is EXECUTE as
approved. Skipping requires a SPECIFIC invalidation vs the approval thesis, logged as a
PASS line — "low confidence" is not an invalidation.
Post-Close replays every PASS line against actual price action: ₹ left on table vs
₹ saved. Both outcomes are good data. Zero valid setups found = legitimate zero;
unlogged or excuse-coded passes = the failure mode.
```

---

## 2. Pulse template — #131, #132, #133, #134, #135, #136, #137, #138, #139

**Before (623 chars, all nine identical):** manage-only framing — cut/tighten/pivot,
verify exits, record action.

**After (replace all nine; pulses time-late in the day still honor the regime cutoff
via the mandate cutoff_time dict, which is injected in the thread):**

```
Check open positions. Day P&L below -₹10,000 → DEFENSE MODE: no new entries, only cuts,
trail-tightens, exits. Below -₹20,000 → HARD STOP: manage exits only. Above thresholds,
this pulse does BOTH jobs:
(1) MANAGE: cut loser (loss >1% beyond trail); tighten trail on +2% profit (trail 2.5%);
WINNER GUARD: any position with unrealized profit ≥₹1,500 that has given back >40% from
its peak — act NOW (tighten to lock, partial exit, or full exit). Never watch an OCO ride
a winner back to a loss (JBMA 2026-06-12). Verify all exits have SL+trail+target+sqoff.
(2) HUNT: if discretionary slots remain (scratchpad) and the mandate cutoff for the
current regime hasn't passed, ask explicitly: is there a playbook setup for the CURRENT
regime right now? (TRENDING: ORB/momentum-continuation; MIXED: VWAP fade/MR or
defined-risk F&O structure; RANGE_BOUND: condor/MR.) A documented thesis + tag is
sufficient to enter — OOS validation only sizes (Hero ₹10K / Solid ₹7K / Spec ₹4K), it
never vetoes. Max 1 action per pulse. Every entry: tag (setup= + thesis + conviction) +
immediate OCO SL+target. Evaluated a specific setup and declined? Log a PASS line per
the mandate Opportunity Ledger. NO TRADE stays valid — but it must leave behind either
"zero candidates evaluated" or PASS lines, never a vague excuse.
Record action taken.
```

---

## 3. #154 — Morning Signal Deploy (09:20)

**Change:** APPEND to the existing prompt:

```
ANTI-GATE GUARD: rejecting a finalist for sample-size / PF / HTF-mismatch alone is a v1
violation — those facts SIZE the trade down (Solid ₹7K or Spec ₹4K), they never veto it.
A finalist may only be fully rejected for: no trigger yet (name the level, stage it),
R:R < 2, liquidity, a risk rail, or a concrete thesis conflict. Log every vetted-but-
passed finalist as a PASS line per the mandate Opportunity Ledger.
```

---

## 4. #155 — Regime Gate (10:00)

**Change:** APPEND:

```
PRE-APPROVED STRUCTURE CHECK: if yesterday's learnings or the principal pre-approved an
F&O structure for today's conditions, the default is EXECUTE it as approved. Skip ONLY
with a specific invalidation vs the approval thesis — "low confidence" is not an
invalidation. Either way log it: execution with tags, or a PASS line with the
invalidation. Any other deployment you evaluate and decline also gets a PASS line.
```

---

## 5. #123 — Peak Check (10:20)

**Before:** peak-reversal rule scoped to "mixed regime", +1%/+0.3% thresholds.

**After (replace — generalize to the winner guard so it matches the pulses):**

```
Check all open positions for peak conditions. Tighten trail on any position showing +2%
profit (trail 2.5% to lock). WINNER GUARD (all regimes): any position with unrealized
profit ≥₹1,500 that has given back >40% from its peak, OR that hit +1% and reversed
below +0.3% within 30 minutes — act NOW: tighten to lock, partial, or cut. Never watch
an OCO ride a winner back to a loss (JBMA 2026-06-12). No new deployments.
```

---

## 6. #125 Mid-Morning, #126 Lunch Protection, #127 Afternoon Comeback, #128 Pre-Close

**Change:** APPEND one sentence to each:

```
Any specific setup evaluated and declined gets a PASS line per the mandate Opportunity
Ledger — never a vague excuse.
```

(#127 already carries the sizing-not-gate language; #128's regime cutoff stays the
boundary for the pulses' HUNT step.)

---

## 7. #130 — Post-Close Review (15:45)

**Change:** APPEND:

```
(d) OPPORTUNITY LEDGER REPLAY: collect every PASS line logged today plus any staged-but-
unfilled entry triggers. For each, replay against actual candles (nf-quote history):
would the stated entry have triggered, and would SL or target have hit first? Report
₹ left on table vs ₹ saved by passing, per setup tag, plus the day's headline number.
Both directions are good data — if passes were right, the bar is well-placed; if they
paid, that's the case for more initiative. Flag any pass that used a vague/excuse reason
(not a valid code) — those are the failure mode. (e) SESSION TRADES: list any trade taken
today by still-enabled scalp/signal sessions explicitly — never fold them silently into
P&L; they are principal-sanctioned but must be visible. (f) Append the running
opportunity-ledger tally (cumulative ₹ left vs saved) to the lessons saved for tomorrow.
Rate the day on mandate-scope P&L AND participation quality: unlogged or excuse-coded
passes downgrade the grade; clean PASS lines never do.
```

---

## 8. Housekeeping

- **#146 "Final Deployment" (disabled):** stale v1 text ("fill remaining signal session
  slots (up to 12)", defense ₹15K). DELETE the row — if ever re-enabled by accident it
  would inject retired-scalp behavior.
- **Apply procedure:** UPDATE `user_awakening_schedules.prompt` for user_id=1 rows
  (#123, #125–139 minus #146, #154, #155, #130); `nf-mandate edit` for the ledger block.
  Prompt text is read fresh at fire time — no restart needed (cron-time changes would
  need one; none here).
- **Effect date:** next trading day (Mon Jun 15) from the 09:20 scan onward.
