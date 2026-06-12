"""Apply the Opportunity Ledger prompt series (2026-06-12) for user 1.

Plan: docs/plans/2026-06-12-opportunity-ledger-prompts.md
Backups: backend/.cache/awakening_prompts_backup_2026-06-12.txt,
         backend/.cache/mandate_backup_2026-06-12_pre_ledger.json

One-shot, idempotent-ish (append steps check for a marker before appending).
Run: cd backend && source venv/bin/activate && python scripts/apply_opportunity_ledger_prompts.py
"""

import asyncio
import copy
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from database.session import get_db_context

LEDGER_MARKER = "OPPORTUNITY LEDGER"

MANDATE_LEDGER_BLOCK = """

OPPORTUNITY LEDGER (anti-passivity, 2026-06-12): Selectivity stays primary — but every pass must be auditable. Whenever any awakening evaluates a specific setup and declines it, log ONE line in the thread:
PASS: SYMBOL LONG|SHORT setup=<tag> tier=<hero|solid|spec> entry=<px> sl=<px> tgt=<px> reason=<code> [trigger=<px/condition if no_trigger_yet>]
Reason codes: no_trigger_yet (MUST name the price/condition that would make you enter; stage an nf-monitor entry rule when practical), rr_below_2, risk_rail (slots/defense/cutoff/max-executions), thesis_conflict (name the conflicting evidence), liquidity, other (1 line, concrete).
"Oversold", "extended", "past its peak", "too late" are NOT pass reasons — they convert to no_trigger_yet with a named re-entry level, or they ARE a thesis for the opposite direction. "Market was choppy/mixed/uncertain" is NOT a pass reason — every regime has playbook setups (TRENDING: ORB/momentum; MIXED: VWAP fade/MR + defined-risk F&O; RANGE_BOUND: condor/MR; macro: regime ETF).
PRE-APPROVED structures (yesterday's learnings or principal): default is EXECUTE as approved. Skipping requires a SPECIFIC invalidation vs the approval thesis, logged as a PASS line — "low confidence" is not an invalidation.
Post-Close replays every PASS line against actual price action: ₹ left on table vs ₹ saved. Both outcomes are good data. Zero valid setups found = legitimate zero; unlogged or excuse-coded passes = the failure mode."""

PULSE_TEXT = """Check open positions. Day P&L below -₹10,000 → DEFENSE MODE: no new entries, only cuts, trail-tightens, exits. Below -₹20,000 → HARD STOP: manage exits only. Above thresholds, this pulse does BOTH jobs:
(1) MANAGE: cut loser (loss >1% beyond trail); tighten trail on +2% profit (trail 2.5%); WINNER GUARD: any position with unrealized profit ≥₹1,500 that has given back >40% from its peak — act NOW (tighten to lock, partial exit, or full exit). Never watch an OCO ride a winner back to a loss (JBMA 2026-06-12). Verify all exits have SL+trail+target+sqoff.
(2) HUNT: if discretionary slots remain (scratchpad) and the mandate cutoff for the current regime hasn't passed, ask explicitly: is there a playbook setup for the CURRENT regime right now? (TRENDING: ORB/momentum-continuation; MIXED: VWAP fade/MR or defined-risk F&O structure; RANGE_BOUND: condor/MR.) A documented thesis + tag is sufficient to enter — OOS validation only sizes (Hero ₹10K / Solid ₹7K / Spec ₹4K), it never vetoes. Max 1 action per pulse. Every entry: tag (setup= + thesis + conviction) + immediate OCO SL+target. Evaluated a specific setup and declined? Log a PASS line per the mandate Opportunity Ledger. NO TRADE stays valid — but it must leave behind either "zero candidates evaluated" or PASS lines, never a vague excuse.
Record action taken."""

PEAK_TEXT = """Check all open positions for peak conditions. Tighten trail on any position showing +2% profit (trail 2.5% to lock). WINNER GUARD (all regimes): any position with unrealized profit ≥₹1,500 that has given back >40% from its peak, OR that hit +1% and reversed below +0.3% within 30 minutes — act NOW: tighten to lock, partial, or cut. Never watch an OCO ride a winner back to a loss (JBMA 2026-06-12). No new deployments."""

APPEND_154 = """ ANTI-GATE GUARD: rejecting a finalist for sample-size / PF / HTF-mismatch alone is a v1 violation — those facts SIZE the trade down (Solid ₹7K or Spec ₹4K), they never veto it. A finalist may only be fully rejected for: no trigger yet (name the level, stage it), R:R < 2, liquidity, a risk rail, or a concrete thesis conflict. Log every vetted-but-passed finalist as a PASS line per the mandate Opportunity Ledger."""

APPEND_155 = """ PRE-APPROVED STRUCTURE CHECK: if yesterday's learnings or the principal pre-approved an F&O structure for today's conditions, the default is EXECUTE it as approved. Skip ONLY with a specific invalidation vs the approval thesis — "low confidence" is not an invalidation. Either way log it: execution with tags, or a PASS line with the invalidation. Any other deployment you evaluate and decline also gets a PASS line per the mandate Opportunity Ledger."""

APPEND_130 = """ (d) OPPORTUNITY LEDGER REPLAY: collect every PASS line logged today plus any staged-but-unfilled entry triggers. For each, replay against actual candles (nf-quote history): would the stated entry have triggered, and would SL or target have hit first? Report ₹ left on table vs ₹ saved by passing, per setup tag, plus the day's headline number. Both directions are good data — if passes were right, the bar is well-placed; if they paid, that's the case for more initiative. Flag any pass that used a vague/excuse reason (not a valid code) — those are the failure mode. (e) SESSION TRADES: list any trade taken today by still-enabled scalp/signal sessions explicitly — never fold them silently into P&L; they are principal-sanctioned but must be visible. (f) Append the running opportunity-ledger tally (cumulative ₹ left vs saved) to the lessons saved for tomorrow. Rate the day on mandate-scope P&L AND participation quality: unlogged or excuse-coded passes downgrade the grade; clean PASS lines never do."""

APPEND_SENTENCE = """ Any specific setup evaluated and declined gets a PASS line per the mandate Opportunity Ledger — never a vague excuse."""

PULSE_IDS = [131, 132, 133, 134, 135, 136, 137, 138, 139]
APPEND_SENTENCE_IDS = [125, 126, 127, 128]


async def main():
    async with get_db_context() as s:
        # 1. Mandate custom_instructions append (deepcopy + reassign — JSON
        #    column only marks dirty on attribute reassignment).
        r = await s.execute(text("SELECT trading_mandate FROM users WHERE id=1"))
        mandate = copy.deepcopy(r.scalar())
        ci = mandate.get("custom_instructions", "")
        if LEDGER_MARKER in ci:
            print("mandate: ledger block already present, skipping")
        else:
            mandate["custom_instructions"] = ci + MANDATE_LEDGER_BLOCK
            await s.execute(
                text("UPDATE users SET trading_mandate = :m WHERE id = 1"),
                {"m": __import__("json").dumps(mandate)},
            )
            print(f"mandate: custom_instructions {len(ci)} -> {len(mandate['custom_instructions'])} chars")

        # 2. Pulse template replace.
        for pid in PULSE_IDS:
            await s.execute(
                text("UPDATE user_awakening_schedules SET prompt = :p, updated_at = now() WHERE id = :i AND user_id = 1"),
                {"p": PULSE_TEXT, "i": pid},
            )
        print(f"pulses replaced: {PULSE_IDS}")

        # 3. Peak Check replace.
        await s.execute(
            text("UPDATE user_awakening_schedules SET prompt = :p, updated_at = now() WHERE id = 123 AND user_id = 1"),
            {"p": PEAK_TEXT},
        )
        print("peak check #123 replaced")

        # 4. Appends (guarded by marker so re-runs don't duplicate).
        for pid, block in [(154, APPEND_154), (155, APPEND_155), (130, APPEND_130)]:
            r = await s.execute(
                text("SELECT prompt FROM user_awakening_schedules WHERE id = :i AND user_id = 1"),
                {"i": pid},
            )
            cur = r.scalar()
            if LEDGER_MARKER in cur or "ANTI-GATE GUARD" in cur:
                print(f"#{pid}: already appended, skipping")
                continue
            await s.execute(
                text("UPDATE user_awakening_schedules SET prompt = :p, updated_at = now() WHERE id = :i AND user_id = 1"),
                {"p": cur + block, "i": pid},
            )
            print(f"#{pid}: appended ({len(cur)} -> {len(cur) + len(block)} chars)")

        for pid in APPEND_SENTENCE_IDS:
            r = await s.execute(
                text("SELECT prompt FROM user_awakening_schedules WHERE id = :i AND user_id = 1"),
                {"i": pid},
            )
            cur = r.scalar()
            if LEDGER_MARKER in cur:
                print(f"#{pid}: already appended, skipping")
                continue
            await s.execute(
                text("UPDATE user_awakening_schedules SET prompt = :p, updated_at = now() WHERE id = :i AND user_id = 1"),
                {"p": cur + APPEND_SENTENCE, "i": pid},
            )
            print(f"#{pid}: sentence appended")

        # 5. Delete stale disabled #146 (v1 signal-session refill landmine).
        res = await s.execute(
            text("DELETE FROM user_awakening_schedules WHERE id = 146 AND user_id = 1 AND enabled = false"),
        )
        print(f"#146 deleted: {res.rowcount} row(s)")

        await s.commit()
        print("COMMITTED")


if __name__ == "__main__":
    asyncio.run(main())
