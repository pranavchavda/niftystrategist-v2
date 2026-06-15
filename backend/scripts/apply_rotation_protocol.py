"""Apply the Rotation Protocol / slots-not-quota fix (2026-06-15) for user 1.

Problem (Jun 15 review): the mandate said "0-3 trades/day" (a daily quota) and a
hard "Max 6 executions/day" rail. 3 trades == 6 executions, so "3 slots" silently
became "3 and done" — NS sat on a dead ANTHEM long all day and passed ACUTAAS (and
other live setups) coding reason=risk_rail=slots, when it should have cut the laggard
and rotated.

Fix (Pranav's call): 3 slots = CONCURRENCY, not a daily quota. Turnover guard is
justification (calculation + conviction + intuition), not a count — backstop only.
Cut-and-switch encouraged when a held position is dead/adverse and a better setup is live.

Backups: backend/.cache/mandate_backup_2026-06-15_pre_rotation.json,
         backend/.cache/awakening_prompts_backup_2026-06-15.txt
Idempotent: marker-guarded (ROTATION PROTOCOL / LAGGARD GUARD).
Run: cd backend && source venv/bin/activate && python scripts/apply_rotation_protocol.py
"""

import asyncio
import copy
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from database.session import get_db_context

CACHE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".cache")

ROTATION_MARKER = "ROTATION PROTOCOL"
LAGGARD_MARKER = "LAGGARD GUARD"

# --- mandate custom_instructions edits (exact-substring replace on live value) ---
MANDATE_EDITS = [
    (
        "• 0-3 trades/day, either direction.",
        "• Up to 3 CONCURRENT positions (slots) at a time, either direction — a CONCURRENCY limit, NOT a daily quota; a slot frees the moment a position closes and may be reused (see ROTATION PROTOCOL).",
    ),
    (
        "• Max 6 executions/day total — frequency is the enemy; it killed ₹105k in charges in 6 weeks.",
        "• Turnover guard: UNJUSTIFIED churn is the enemy — it killed ₹105k in charges in 6 weeks. The guard is JUSTIFICATION, not a count: every slot recycle must clear the ROTATION PROTOCOL bar. A high backstop (~10 executions/day) is a runaway-churn circuit-breaker only, never a quality gate — a genuinely justified rotation is rare and earns back its own charges.",
    ),
    (
        "risk_rail (slots/defense/cutoff/max-executions)",
        "risk_rail (defense/cutoff; slots ONLY valid if all 3 are working positions — a slot held by a laggard is NOT a valid slots-pass, see ROTATION PROTOCOL)",
    ),
    (
        "may CUT, TIGHTEN TRAIL, or PIVOT (max 1 action/pulse).",
        "may CUT, TIGHTEN TRAIL, or PIVOT (max 1 action/pulse; a cut-and-switch ROTATION counts as ONE action).",
    ),
]

# Inserted before the STRATEGIC F&O block.
ROTATION_BLOCK = """ROTATION PROTOCOL (cut-and-switch, 2026-06-15): The 3 slots are CONCURRENCY, not a daily quota — recycle them. Cut a held position and rotate the slot into a fresh setup when BOTH hold: (a) the held position is stalled (no progress toward its thesis given the time elapsed) or turning adverse / thesis-broken, AND (b) a higher- or equal-conviction setup is live in the scan. The justification may rest on calculation (R:R, regime fit, tape), conviction (thesis strength / tier), AND intuition — state which carried it. Log a ROTATE line: ROTATE: cut SYM (dead|adverse|thesis-broken) -> enter SYM2 setup=<tag> tier=<hero|solid|spec> thesis=<1 line>. A laggard occupying a slot while a better trade goes untaken is ITSELF a cost — "3/3 slots full" is NEVER a pass reason when one of those slots holds a laggard you should be cutting. Genuinely justified rotations are rare and pay for their own charges; unjustified churn is the ₹105k enemy.

"""

# --- pulse #131-139 edits ---
PULSE_IDS = [131, 132, 133, 134, 135, 136, 137, 138, 139]
PULSE_EDITS = [
    (
        "Never watch an OCO ride a winner back to a loss (JBMA 2026-06-12). Verify all exits",
        "Never watch an OCO ride a winner back to a loss (JBMA 2026-06-12). LAGGARD GUARD: flag any position stalled vs its thesis or turning adverse — it is a rotation candidate (see HUNT), not a protected tenant of its slot. Verify all exits",
    ),
    (
        "(2) HUNT: if discretionary slots remain (scratchpad) and the mandate cutoff for the current regime hasn't passed, ask explicitly: is there a playbook setup for the CURRENT regime right now?",
        "(2) HUNT: ask explicitly EVERY pulse (until the regime cutoff passes): is there a playbook setup for the CURRENT regime right now? If a discretionary slot is free (scratchpad), take it. If all 3 slots are full but one holds a LAGGARD (stalled vs its thesis or turning adverse) and the new setup is higher- or equal-conviction, ROTATE per the mandate ROTATION PROTOCOL — cut the laggard, enter the new setup, log a ROTATE line. \"3/3 slots\" is NOT a pass reason when one slot holds a laggard.",
    ),
    (
        "Max 1 action per pulse.",
        "Max 1 action per pulse (a cut-and-switch ROTATION counts as one action).",
    ),
]

# --- #130 Post-Close ledger-replay edit ---
POSTCLOSE_EDIT = (
    "Flag any pass that used a vague/excuse reason (not a valid code) — those are the failure mode.",
    "Flag any pass that used a vague/excuse reason (not a valid code) — those are the failure mode. Also flag any PASS coded risk_rail=slots where a held position was a LAGGARD that should have been rotated out: a missed rotation is the same failure class as an excuse pass.",
)


async def main():
    os.makedirs(CACHE, exist_ok=True)
    async with get_db_context() as s:
        # ---- backups ----
        r = await s.execute(text("SELECT trading_mandate FROM users WHERE id=1"))
        mandate = copy.deepcopy(r.scalar())
        with open(os.path.join(CACHE, "mandate_backup_2026-06-15_pre_rotation.json"), "w") as f:
            json.dump(mandate, f, ensure_ascii=False, indent=2)
        rs = await s.execute(text("SELECT id, prompt FROM user_awakening_schedules WHERE user_id=1 ORDER BY id"))
        allp = rs.fetchall()
        with open(os.path.join(CACHE, "awakening_prompts_backup_2026-06-15.txt"), "w") as f:
            for row in allp:
                f.write(f"===== #{row._mapping['id']} =====\n{row._mapping['prompt']}\n\n")
        print(f"backups written ({len(allp)} prompts)")

        # ---- 1. mandate ----
        ci = mandate.get("custom_instructions", "")
        if ROTATION_MARKER in ci:
            print("mandate: ROTATION PROTOCOL already present, skipping mandate edits")
        else:
            for old, new in MANDATE_EDITS:
                if old not in ci:
                    raise SystemExit(f"MANDATE substring NOT FOUND: {old[:60]!r}")
                ci = ci.replace(old, new, 1)
            # insert rotation block before STRATEGIC F&O
            anchor = "STRATEGIC F&O (defined-risk ONLY):"
            if anchor not in ci:
                raise SystemExit("MANDATE anchor 'STRATEGIC F&O' not found")
            ci = ci.replace(anchor, ROTATION_BLOCK + anchor, 1)
            mandate["custom_instructions"] = ci
            await s.execute(
                text("UPDATE users SET trading_mandate = :m WHERE id = 1"),
                {"m": json.dumps(mandate)},
            )
            print(f"mandate: custom_instructions updated -> {len(ci)} chars")

        # ---- 2. pulses ----
        for pid in PULSE_IDS:
            r = await s.execute(
                text("SELECT prompt FROM user_awakening_schedules WHERE id=:i AND user_id=1"),
                {"i": pid},
            )
            cur = r.scalar()
            if cur is None:
                print(f"#{pid}: not found, skipping")
                continue
            if LAGGARD_MARKER in cur:
                print(f"#{pid}: already has LAGGARD GUARD, skipping")
                continue
            new = cur
            for old, rep in PULSE_EDITS:
                if old not in new:
                    raise SystemExit(f"#{pid} substring NOT FOUND: {old[:50]!r}")
                new = new.replace(old, rep, 1)
            await s.execute(
                text("UPDATE user_awakening_schedules SET prompt=:p, updated_at=now() WHERE id=:i AND user_id=1"),
                {"p": new, "i": pid},
            )
            print(f"#{pid}: rotation edits applied ({len(cur)} -> {len(new)} chars)")

        # ---- 3. #130 post-close ----
        r = await s.execute(text("SELECT prompt FROM user_awakening_schedules WHERE id=130 AND user_id=1"))
        cur = r.scalar()
        if cur and "missed rotation" in cur:
            print("#130: already has missed-rotation flag, skipping")
        elif cur:
            old, rep = POSTCLOSE_EDIT
            if old not in cur:
                raise SystemExit("#130 substring NOT FOUND")
            await s.execute(
                text("UPDATE user_awakening_schedules SET prompt=:p, updated_at=now() WHERE id=130 AND user_id=1"),
                {"p": cur.replace(old, rep, 1)},
            )
            print("#130: missed-rotation flag appended")

        await s.commit()
        print("COMMITTED")


if __name__ == "__main__":
    asyncio.run(main())
