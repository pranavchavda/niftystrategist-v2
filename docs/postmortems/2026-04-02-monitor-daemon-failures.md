# 2026-04-02 Monitor Daemon Post-Mortem

## Context
5 ORB strategies deployed pre-market (GRSE LONG, ACUTAAS SHORT, HINDPETRO SHORT, GRAVITA SHORT, POLICYBZR SHORT) with 45 monitor rules (903-948). P&L peaked at +3,007 around 10:47 AM, ended at -2,265. Target was +5K-7.5K.

## TL;DR

**The daemon worked perfectly.** 19 rules fired, all successful, all kill chains executed correctly. The cascading failures were caused by the orchestrator agent misdiagnosing the daemon as broken, then switching to manual mode and making increasingly poor decisions.

## Investigation Findings

### Finding 1: Daemon fired all rules correctly (19/19 success)

Full fire log (all UTC, add 5:30 for IST):

| Time (UTC) | Rule | Name | Result |
|------------|------|------|--------|
| 03:45:01 | 905 | GRSE ORB Long Entry > 2229.0 | SELL order placed |
| 03:45:01 | 915 | ACUTAAS ORB Short Entry < 2573.0 | SELL order placed |
| 03:45:01 | 917 | HINDPETRO ORB Short Entry < 338.1 | SELL order placed |
| 03:45:02 | 944 | POLICYBZR ORB Short Entry < 1429.5 | SELL order placed |
| 03:45:03 | 935 | GRAVITA ORB Short Entry < 1297.2 | SELL order placed |
| 03:45:16 | 921 | ACUTAAS ORB Short Target @ 2449.4 | BUY cover placed (15s after entry!) |
| 03:45:25 | 901 | IDEA OCO Stop-Loss @ 8.5 | SELL order placed |
| 03:45:48 | 913 | GRSE ORB Long Trail 1.5% | SELL exit placed (48s after entry!) |
| 05:51:24 | 949 | ASTRAL OCO Stop-Loss @ 1485.1 | BUY cover placed |
| 05:56:22 | 947 | POLICYBZR ORB Short Trail 1.5% | BUY cover placed |
| 06:55:29 | 952 | HINDPETRO OCO Target @ 314.3 | BUY cover placed |
| 07:48:02 | 959 | GRSE ORB Short Entry < 2215.0 (batch 2) | SELL order placed |
| 07:54:55 | 960 | GRSE ORB Short SL @ 2230.0 | BUY cover placed (7m after entry) |
| 07:59:33 | **966** | **COFORGE VWAP Bounce Target @ 1177.01** | **SELL 278 placed (10s after rule creation!)** |
| 08:00:27 | 927 | HINDPETRO ORB Short Trail 1.5% | BUY cover placed |
| 08:03:36 | 954 | HINDPETRO Trailing SL 0.5% | BUY cover placed |
| 08:20:26 | 968 | TATACHEM VWAP Bounce Entry @ ~652.61 | BUY order placed |
| 09:45:09 | 939 | GRAVITA ORB Auto Square-Off @ 15:15 | BUY cover placed |
| 09:45:09 | 971 | TATACHEM VWAP Bounce Square-Off @ 15:15 | SELL exit placed |

**Entries fired within 3 seconds of market open. Kill chains (OCO, also_cancel_rules) all executed correctly. Zero errors in daemon logs.**

### Finding 2: Agent misdiagnosed "daemon not firing" — critical cascade

At AW2 (03:52 UTC / 9:22 AM IST), the agent reported: *"All rules have fire_count = 0. Daemon NOT FIRING. Manual mode."*

**This was wrong.** By 03:52 UTC, 8 rules had already fired (03:45:01–03:45:48). What happened:

1. Agent ran `nf-monitor list --active` which only shows `enabled=True` rules
2. All 8 fired rules had `max_fires=1` and were **auto-disabled** after firing
3. The remaining active rules were **exit rules** (SL, trail, target) just enabled by entry fires — naturally `fire_count=0`
4. Agent saw "all active rules have fire_count=0" and concluded the daemon was broken

**The daemon had already resolved 2 complete strategies** (ACUTAAS: entry + target in 15s; GRSE: entry + trail in 48s). The agent's misdiagnosis caused it to switch to manual mode, leading to every subsequent error.

**Fix needed:** `nf-monitor list` should show recently-fired rules by default (or have a `--recent-fires` flag). The agent also needs instructions to check `nf-monitor logs` for recent fires, not just active rule fire_counts.

### Finding 3: COFORGE — agent bought 54 shares, daemon sold 278 (qty mismatch)

Upstox order book for COFORGE on April 2:

| Time (IST) | Side | Qty | Avg Price | Order ID | Source |
|-----------|------|-----|-----------|----------|--------|
| 13:26:37 | BUY | 54 | 1202.0 | ...391719 | Agent (nf-order) |
| 13:29:33 | SELL | 278 | 1202.5 | ...399291 | Daemon rule 966 |
| 14:34:38 | BUY | 224 | 1233.5 | ...552518 | Cover the short |
| 14:35:37 | BUY | 50 | 1231.3 | ...554956 | User scalp |
| 15:24:51 | SELL | 50 | 1207.51 | ...690152 | User scalp exit |

**The sequence:**
1. 07:56:37 UTC — Agent buys 54 COFORGE @ 1202.0
2. 07:59:23 UTC — Agent creates exit rules 965-967 with **qty=278** (hallucinated position size, 5x actual)
3. 07:59:33 UTC — Rule 966 fires (target `gte 1177.01` already met, LTP=1202.7) → SELL 278 @ MARKET
4. Net position: 54 long - 278 sold = **-224 SHORT** (accidental)
5. Price runs to 1233.5 → SHORT bleeds ~6,944
6. 08:34:38 UTC — Cover BUY 224 @ 1233.5

**Two bugs compounded:**
- **Bug A:** Agent created rules with qty=278 when actual position was 54 shares (hallucinated position size)
- **Bug B:** Target price 1177.01 was already below LTP 1202.7 at rule creation → instant fire on first tick

The daemon executed correctly. It was given a SELL 278 rule with a condition that was already true, and it fired within 10 seconds. The -224 short was created by the qty mismatch, not by multiple fires or orphaned rules.

### Finding 4: Agent hallucinated rule numbers

In message 4730 (08:54 UTC), the agent attributed the COFORGE mess to "OCO rules 979-980." **These rules do not exist in the database.** The highest rule ID is 971. The actual COFORGE rules are 965-967.

### Finding 5: ACUTAAS target was met on gap-open

Rule 921 (ACUTAAS Short Target @ 2449.4, condition `lte`) fired 15 seconds after entry. The stock gap-opened to 2281.0 — already well below the target of 2449.4. The short entry filled AND the target triggered on essentially the same tick. Not a bug, but a strategy gap: targets should account for gap-open scenarios.

## Root Causes (Revised)

### 1. Agent misdiagnosing daemon → manual mode cascade (PRIMARY)
The agent's incorrect conclusion that the daemon wasn't working led to every other failure: manual positioning without rules (ASTRAL), dual management of positions (COFORGE), premature exits, time confusion. **The daemon was fine; the agent was the problem.**

### 2. COFORGE: qty mismatch (54 actual vs 278 in rules) + already-met target
Agent bought 54 shares, created rules for 278. Target (1177.01) was below LTP (1202.7) → fired in 10 seconds. SELL 278 on a 54-share LONG created a -224 SHORT. Realized loss ~6,944 on the phantom short.

### 3. ASTRAL deployed without monitor rules
AW4 entered ASTRAL SHORT manually, no SL/exit rules. Started bleeding immediately.

### 4. Agent time confusion → premature exits
At 2:18 PM (AW7/AW8), agent placed exit orders as if near close. User corrected at 2:30 PM.

### 5. Agent hallucinated rule states and rule numbers
Referenced non-existent rules 979-980. Misreported fire_counts. Made decisions based on hallucinated state.

### 6. Bloated awakening messages (bug)
Messages id=4717 (34K chars) and id=4721 (70K chars) replayed entire prior conversation history.

## Action Items

### High Priority — Prevent Agent Misdiagnosis
- [ ] **Inject active monitor rules into system prompt** — user's idea from end of thread. Agent always sees full rule state including recently-fired rules. Prevents blindness to both orphaned rules and daemon activity.
- [ ] **`nf-monitor list` should show recently-fired rules** — add a "Recently Fired" section or `--include-fired` flag showing rules that fired in the last hour, even if disabled. Currently fired+disabled rules are invisible with `--active`.
- [ ] **Add `nf-monitor status` command** — shows daemon health, last tick time, today's fire count, active subscriptions. Agent can quickly verify daemon is alive without misreading rule states.

### Medium Priority — Prevent Position/Rule Mismatch
- [ ] **Pre-fire position validation** — before executing a place_order action, check actual position size. If rule says SELL 278 COFORGE but there are only 54 shares long, cap the qty or abort. This single check would have prevented the entire COFORGE disaster.
- [ ] **Rule creation validation** — warn if a price trigger condition is already met at creation time (e.g., target 1177 when LTP is 1202). Could be a `--force` flag override. Would have caught the instant-fire.
- [ ] **Guard against no-rules deployments** — agent should never enter a position without corresponding exit rules in the same operation.

### Lower Priority — Quality of Life
- [ ] **Fix awakening message bloat** — `_write_followup_to_thread()` concatenating history into response
- [ ] **Agent time awareness** — ensure awakenings have accurate IST time, don't confuse 2:30 PM with close
- [ ] **Gap-open target handling** — ORB strategy should set targets that account for gap-open scenarios (e.g., don't set short target above gap-open price)

## Appendix: DB Evidence

- **Rules 903-971**: 70 rules total. No rules beyond 971 exist (agent's "979-980" were hallucinated).
- **monitor_logs**: 19 entries for April 2. All `action_result.success = true`.
- **COFORGE rule 966**: created 07:59:23, fired 07:59:33, LTP=1202.7, target=1177.01 (condition gte already met).
- **Pre-market fires**: Daemon correctly detected rule conditions during pre-open auction (03:30-03:44 UTC) but blocked order placement with `"FIRED but market CLOSED"` guard. Orders placed at 03:45 (9:15 AM IST market open). fire_count NOT consumed during pre-market blocks.
