# ATR / Regime-Aware Trail Width

**Status:** Spec — framework locked (Pranav, 2026-06-22), not yet implemented.
**Origin:** SPLPETRO whipsaw, 2026-06-22 daily review. A fixed 2% trail fired at the
morning-flush bottom (−₹5,684); the stock's post-entry low was only −2.85% and it
closed −0.5%. A ≥3% stop would never have triggered. Root cause: a flat-% trail is
mis-sized for an instrument's volatility. See `memory/project_trail_only_stops.md`,
`memory/project_ns_agent_as_primary_user.md`.

## 1. Problem & locked decisions

Trail-only is settled as the base exit structure (no fixed target). The open problem
was **how wide** the from-entry trail should be. "Percent" is the wrong unit — 2% means
something different on a sleepy largecap vs. a name printing a 4% opening candle.

Locked framework (Pranav, 2026-06-22):
- **Unit = ATR multiple**, converted to a `trail_percent` for the existing rule engine.
- **No separate hard floor.** A correctly-sized trail is its own floor; "trail + floor"
  is collapsed to "trail-only, ATR-sized."
- **ATR base = intraday ATR-14** (the 15-min ATR we already compute), not daily ATR —
  an intraday trade must absorb intraday breath; daily ATR smooths away the gap/news
  range that actually does the whipsawing. (Leaning; the sweep in §9 confirms.)
- **Automatic by default, NS-overridable by exception with a logged reason.** NS stops
  *choosing* a width and starts *judging* a computed one. This is the only version that
  is backtestable (a fixed `k`-table is sweepable; per-pulse gut-feel is not).

## 2. The model

```
trail_pct = clamp( k × ATR14_15m / entry_price × 100 ,  FLOOR_PCT , CEIL_PCT )
sl_points = entry_price × trail_pct / 100
qty       = floor( risk_budget / sl_points )          # = nf-size's existing risk formula
```

Two properties matter:

- **Risk-invariance (the safety property).** Width and size are coupled through the
  second/third lines, so widening the trail (larger `k`) *reduces* share count and the
  rupee risk-per-trade stays pinned to the mandate budget. Buying whipsaw-immunity costs
  share count, never risk. This is already the "Sizing principle" in the trail-only memo;
  the gap is that live deploys hardcode a flat 2%.
- **Clean separation of inputs.** `ATR` = *instrument breath* (per-stock, captures how
  much this name moves). `regime` = *market-wide modifier* on `k` (captures whether the
  tape is chopping or trending). nf-regime is a NIFTY-level read, so it is correctly a
  modifier, not the base — the per-stock ATR already carries stock-specific volatility.

## 3. The `k` table (SEED VALUES — provisional, sweep-derived in §9)

`k` is set by **setup class × regime**, with a time-of-day nudge. Setups collapse into
three noise-tolerance classes rather than per-string values:

| Setup class | Member setups (from `nf-morning-scan detect_setup` + mandate tags) | Why |
|---|---|---|
| **REVERSION** | Gap fade, VWAP pullback/rejection, reversal | thesis *is* the snapback — must outlast the dip (this is SPLPETRO) → widest |
| **MOMENTUM** | ORB breakout/breakdown, momentum continuation, breakout | if it reverses, thesis is dead fast → tightest |
| **NEUTRAL** | relative strength/weakness leader, "watching", other | mid |

Seed `k` (ATR multiples):

| | TRENDING | MIXED | RANGE_BOUND |
|---|---|---|---|
| REVERSION | 2.0 | 2.5 | **3.0–3.5** |
| MOMENTUM  | 1.5 | 2.0 | 2.5 |
| NEUTRAL   | 1.75 | 2.25 | 2.75 |

- Clamp: `FLOOR_PCT ≈ 1.5%` (don't over-tighten a dead-quiet largecap),
  `CEIL_PCT ≈ 5–6%` (beyond this the thesis is probably wrong / share count too small).
- Time-of-day: first ~30 min, nudge `k` up (or read a stabilized ATR — see §7).
- SPLPETRO check: REVERSION (gap fade) × RANGE_BOUND → k≈3.0 → ~3% trail → never tagged
  → rides to −0.5%. The seed table reproduces the right call on the motivating case.

**These numbers are intuition, not measurement.** §9 replaces them with swept values.

## 4. Automatic-by-default contract

- **Deploy-time width is computed, not chosen.** At entry NS already knows symbol, setup,
  direction, and regime, and ATR is on the `deep:` line. So `k → trail_pct → qty` follow
  deterministically. The width **arrives precomputed** (same spirit as the Sunday scan
  deep-reads) — NS reads a suggestion and confirms.
- **Override is the exception, and it is logged.** NS may widen/tighten when it knows
  something the formula can't see (earnings tonight; a support level 0.3% below to snug
  under; a fast scalp). The override value **and its one-line reason** are recorded
  (nf-intent + the trigger_config provenance in §6), so overrides are auditable and the
  sweep can learn which ones paid off.
- **The ratchet stays NS-driven in v1** (per-pulse `update-trail`, which already preserves
  the high-water anchor). Tool-proposed tightening (e.g. once MFE > N×ATR) is **Phase 2**
  — v1 fixes the *initial* width, which is the SPLPETRO bug.

## 5. Tool design

Extend **`nf-size`** (it already owns the risk→qty math and binding-constraint logic) with
an ATR-trail mode, rather than a new tool — keep all sizing in one place.

```
nf-size SYMBOL --atr-trail --direction long|short --setup SETUP \
  [--regime trending|mixed|range_bound|auto] [--risk-pct 2 | --risk RS] \
  [--capital auto] [--entry auto|PRICE] [--k OVERRIDE] [--json]
```

Behavior:
1. Resolve `entry` (live LTP if `auto`) and `direction`.
2. Resolve `regime`: prefer the explicit `--regime` (NS already has it from the regime-gate
   pulse / the snapshot injects it — avoids recomputing nf-regime per deploy);
   `auto` falls back to invoking nf-regime.
3. Fetch `ATR14` via `TechnicalAnalysisService.calculate_indicators` on 15-min/10-day
   candles (the exact path `nf-analyze`/`candidate_analysis` use; mirror the ATR-sized
   Renko seeding in `trading_snapshot._tape_read`). Require ≥50 candles or abort with a
   clear error (don't size on thin data).
4. Map `setup → setup_class`, look up `k` (or use `--k` override), compute `trail_pct`
   with the clamp, then size via the existing risk formula.
5. Emit (extends nf-size's current JSON):
   ```json
   {
     "kind": "equity", "symbol": "...", "entry_price": 779.18, "direction": "long",
     "atr_14": 13.3, "atr_pct": 1.71, "regime": "range_bound", "setup_class": "REVERSION",
     "k": 3.0, "trail_percent": 3.1, "sl_points": 24.15,
     "recommended_qty": 207, "actual_risk_amount": 5000, "binding_constraint": "risk",
     "rationale": "REVERSION × range_bound → k=3.0; ATR 13.3 (1.71%) → 3.1% trail",
     "warnings": []
   }
   ```

`nf-monitor add-trailing` stays mechanical — NS passes the computed
`--trail-percent` (or its override). add-trailing additionally **records provenance**
(see §6). The `update-trail` ratchet path is unchanged.

## 6. Provenance storage (no migration)

`MonitorRule.trigger_config` is JSON, so no schema change is needed. On
`add-trailing`, store alongside the existing trail fields:

```json
"width_provenance": {
  "source": "atr_regime" | "manual_override",
  "atr_14": 13.3, "k": 3.0, "regime": "range_bound", "setup_class": "REVERSION",
  "override_reason": null | "earnings tonight, widened"
}
```

This makes every live trail self-describing for the backtest sweep and for post-hoc
review ("did the auto width or the override do better?"). Purely additive; the daemon
ignores unknown keys.

## 7. ATR seeding-time (open, v1 = simplest)

The opening 15-min bars inflate ATR-14 on gap days. ATR-14 self-dampens somewhat
(an opening spike is ~2 of 14 bars at 09:45), but a violent gap still skews it.
Options: (a) use ATR-14 as-is — simplest, self-dampening; (b) compute ATR over a window
excluding the first N opening bars; (c) blend prior-day ATR with intraday. **v1 = (a)**;
the sweep reveals whether opening-bar contamination materially hurts. Flagged, not decided.

## 8. Orchestrator prompt changes

The deploy protocol (`agents/orchestrator.py` ~lines 1898–1916) currently hardcodes
`--trail-percent 15` in the add-trailing examples. Change the discretionary-deploy step to:

> Compute the trail width with `nf-size --atr-trail --direction … --setup … --regime …`
> (regime from the latest regime gate). Deploy `add-trailing` with the returned
> `trail_percent` and `qty`. Override only with a stated reason (record it via nf-intent).

Also update the standalone add-trailing example lines (~1695, ~1910) to reference the
computed width rather than a literal 15%.

## 9. Backtest validation (replaces the seed `k`-table with measured values)

Use the existing matrix/sweep infra (`nf-backtest-matrix`, `backtesting/sweep.py`,
`memory/project_backtest_matrix.md`):

1. Backtest exit model = trail-only, trail sized as `k × ATR14 / entry`, swept over
   `k ∈ {1.5 … 3.5}` per `{setup_class × regime}` cell.
2. Rank cells on **walk-forward ₹/day after charges** (gates → t-stat → walk-forward, the
   existing ranking pipeline), not in-sample.
3. **Caveat (honest):** the rule engine's fill model is optimistic — no gap/slippage on
   the trail exit (`memory/project_harness_hardening_backlog.md`). Swept `k` will read
   slightly rosy; prefer the *relative* ranking across cells over absolute ₹, and bias
   `k` a touch wider than the optimum to absorb real slippage.
4. Output: the measured `k`-table that replaces §3's seeds.

## 10. Phasing

- **Phase 1 (this spec):** `nf-size --atr-trail` mode + provenance + prompt change +
  the `k`-sweep to set the table. Fixes the initial-width bug (SPLPETRO). Discretionary
  deploy path only.
- **Phase 2:** tool-proposed ratchet — recompute a tighter `k` as the trade matures
  (MFE > N×ATR or trend confirmation), surfaced as an `update-trail` suggestion per pulse.
- **Phase 3:** extend ATR-sizing to the hands-off session path (`nf-deploy-sessions` /
  `nf-scalp`), which currently fixes trail width at creation.

## 10a. BACKTEST VERDICT (2026-06-22) — formula is the floor, judgment is the edge

The k-sweep (gap-fade + ORB, Nifty-100 × 120d, ~8k entries; `backtesting/
atr_trail_sweep.py`, `scripts/run_atr_trail_sweep.py`) **overturned the §3 seed
table and reframed the feature**:

- **Entry-regime gate is first-order (~₹1,000/trade); trail width is
  second-order (~₹100/trade)** — ~10× smaller. Each setup has a structural
  anti-regime: fades bleed in TRENDING (tstat −2), ORB bleeds in RANGE_BOUND
  (tstat −3.9, the cleanest signal). The mandate already enforces this gate.
- **No durable *formulaic* width edge.** Per-cell signal is marginal and
  degrades out-of-sample (MIXED fade ₹1,700 in-sample → ₹254 OOS); ORB has no
  OOS-positive cell. A finely-tuned k-table would be fitting noise.
- **Tightness rarely wins.** Wider k (≈3) ≥ tight in nearly every viable cell
  (both fades and breakouts need room to survive the retest). The seed's
  "REVERSION wide / MOMENTUM tight" split is dropped. The SPLPETRO "wider"
  intuition holds only as "not blindly tight," not as a per-cell rule.
- **In TRENDING there is no formula answer at all** (ORB flips +in-sample →
  −OOS). Yet trending is where runners (COFORGE/CARTRADE) and the outsized P&L
  live → that P&L is discretionary, not formulaic.

**Conclusion (Pranav, 2026-06-22):** "NS's judgement in fine-tuning the trail
width — particularly in trending, but generally always — is the edge vs a
formula." So:
- The formula is the **FLOOR**: an ATR-grounded baseline + risk-invariant qty +
  the regime gate (prevents the blind-flat-2% SPLPETRO error). Keep it.
- NS's per-situation tuning is the **CEILING** and the alpha. The tool hands a
  baseline and gets out of the way.
- **Simplify**: collapse the per-cell k-table to ONE sane ATR baseline (k≈2.75,
  optional light regime nudge); drop the setup×regime width split; reposition
  `nf-size --atr-trail` output as "baseline to tune," not an authority.
- **Phase 2 (tool-proposed ratchet) is DEMOTED** — the ratchet judgment is the
  edge; automating it away would remove alpha. Keep the ratchet NS-driven.

Methodology to shore up before trusting any finer distinction: regime proxy vs
live nf-regime day-labels; interleaved/rolling walk-forward (not one contiguous
cut — it conflates OOS with a specific later market); realistic slippage.

## 11. Open decisions (for Pranav)

1. ATR base timeframe — confirm intraday ATR-14 (15-min) over daily (leaning intraday).
2. ATR seeding-time handling (§7) — v1 "as-is", or exclude opening bars from the start?
3. `FLOOR_PCT` / `CEIL_PCT` clamp values (1.5% / 5–6% seeds).
4. Tool shape — extend `nf-size` (recommended) vs. a dedicated `nf-trail`.
5. Whether overrides require a reason string (recommended: yes, for the audit trail).
