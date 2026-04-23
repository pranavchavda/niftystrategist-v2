# Scalp-Style Equity Backtest — Design

**Date:** 2026-04-23
**Status:** Design — not yet implemented
**Author:** Pranav + Claude

## Motivation

The live scalp session engine (`monitor/scalp_session.py`) runs a position-aware state machine: wait for a primary indicator flip, optionally confirm with a secondary indicator, enter long/short, exit on SL/target/trail/squareoff, then re-arm. Users currently have no way to evaluate a scalp configuration before putting real capital behind it.

A backtest with **the same indicator stack, same config shape, and same exit semantics** as the live scalper answers one question directly: *"would this config have made money over the last N days?"*

**Why equity first:**
- No contract expiration — any lookback window works.
- Upstox historical candle data goes back months on daily and ~30 days on intraday minute intervals.
- All five trend indicators the user called out (UT Bot, HalfTrend, SSL Hybrid, EMA Crossover, Supertrend) plus confirm candidates (QQE MOD, Linear Regression, Renko, Bollinger, RSI, MACD, VWAP) already exist in `monitor/indicator_engine.py`.
- The live scalper already supports `OPTIONS_SCALP` and equity session modes, so reusing its config type means the backtest is comparing apples to apples.

**Why options come later:**
- Upstox expires option instrument_keys within days of expiry (verified 2026-04-22 — past-expiry tokens return 400).
- Upstox Plus includes `ExpiredInstrumentApi.get_expired_historical_candle_data` + `get_expired_option_contracts`. Design for options backtests will layer on top of the equity engine later, using this endpoint.

## Scope

### In scope
- New backtest engine that mirrors `ScalpSessionManager` semantics in a bar-replay loop.
- Config uses the existing `ScalpSessionConfig` shape (so a user can point a live session at a backtest and get a fair preview).
- **Intraday mode**: flatten at `squareoff_time`, re-arm next session.
- **Swing mode**: hold positions across sessions; exit only on opposite flip / SL / target / trail.
- Trade log + metrics (reuse `backtesting/metrics.py`).
- CLI, REST, and UI surfaces.

### Out of scope (for v1)
- Options (separate follow-up, once expired-candle API is wired).
- Multi-leg / spread strategies.
- Live paper-trading parallel to backtest.
- Walk-forward optimization or parameter sweeps (could be a v2 on top of the engine).

## Current-state inventory

| Component | Path | Status |
|---|---|---|
| Trend indicators (UT Bot, HalfTrend, SSL Hybrid, Supertrend, EMA Cross) | `monitor/indicator_engine.py` | ✅ exist, production-tested by live scalper |
| Confirm indicators (QQE MOD, LR, Renko, BB, RSI, MACD, VWAP) | `monitor/indicator_engine.py` | ✅ exist |
| `ScalpSessionConfig` — config schema | `monitor/scalp_models.py:39` | ✅ exists, reusable |
| `TradeSimulator` — position + trade accounting | `backtesting/simulator.py:34` | ✅ usable as-is |
| `compute_metrics` — win rate, drawdown, Sharpe, etc. | `backtesting/metrics.py` | ✅ reusable |
| Equity historical data fetch | `services/upstox_client.py:373` — `get_historical_data()` | ✅ reusable |
| Rule-based backtest engine | `backtesting/engine.py` | ⚠️ wrong paradigm — evaluates `RuleSpec` chains; scalp uses state machine |
| REST API `/api/backtest` | `api/backtest.py` | ⚠️ only handles template rules |
| Frontend backtest UI | `frontend-v2/app/routes/backtest.tsx` | ⚠️ template-driven |

**Key decision: do not try to reuse `backtesting/engine.py`.** It drives template rules. A scalp session is a state machine (IDLE → HOLDING_LONG/SHORT → IDLE), not a rule set. Forcing a state machine through the rule engine would re-implement state handling in rule conditions — clearer to build a dedicated scalp-replay module.

## Architecture

New module: `backend/backtesting/scalp_equity.py`.

```
backend/backtesting/
├── engine.py           (existing — template rule runner, untouched)
├── fno_engine.py       (existing — multi-leg F&O runner, untouched)
├── simulator.py        (existing — Trade, TradeSimulator — reused)
├── metrics.py          (existing — reused)
└── scalp_equity.py     (NEW — scalp-style state-machine replay)
```

New entry-points:
- CLI: `backend/cli-tools/nf-backtest-scalp` (follows existing CLI conventions).
- REST: `POST /api/backtest/scalp` in `api/backtest.py` (new route, reuses module).
- UI: new tab in `frontend-v2/app/routes/backtest.tsx` — "Scalp Replay".

## Config schema

Reuse `ScalpSessionConfig` verbatim via a thin request wrapper. This keeps the backtest-↔-live contract tight: any backtested config can be saved as a live session with one click.

```python
class ScalpBacktestRequest(BaseModel):
    config: ScalpSessionConfig         # entire live config, identity fields ignored
    symbol: str                         # equity symbol — e.g., "RELIANCE", "NIFTY"
    days: int = 30                      # lookback window
    interval: str = "5minute"           # must be in INTERVAL_MAP
    session_mode: Literal["intraday", "swing"] = "intraday"
    initial_capital: float | None = None  # optional for metrics; defaults to position notional
```

Fields that don't apply to equity (e.g. `expiry`, `lots`) are ignored. `quantity` drives equity sizing. `underlying` maps to `symbol` for backtest purposes. A validator rejects configs with an `indicator_timeframe` coarser than the requested `interval` (we can't upsample from 15m bars to 5m indicators).

## Engine flow

```
load candles (Upstox get_historical_data)
  ↓
for each bar in order:
  ├── if intraday and crossed into new session: reset simulator to flat,
  │   reset trade_count, clear cooldown
  ├── if squareoff_time hit and position open: close with "squareoff"
  ├── compute primary indicator on window [0..i]
  ├── compute confirm indicator (if configured) on window [0..i]
  ├── detect primary flip: sign change vs previous bar's primary value
  │
  ├── if HOLDING: check exit conditions using THIS bar's O/H/L/C
  │   ├── SL hit inside H/L range  → close @ SL price, reason="sl"
  │   ├── Trail arm: if favourable_move >= trail_arm_points, arm trail
  │   ├── Trail hit (if armed): close @ trail stop, reason="trailing"
  │   ├── Target hit: close @ target price, reason="target"
  │   └── Opposite primary flip: close @ close, reason="entry_opposite"
  │       (re-entry in opposite direction is queued for next bar)
  │
  ├── if IDLE: check entry
  │   ├── only if trade_count < max_trades
  │   ├── only if now - last_exit_time >= cooldown_seconds
  │   ├── only on fresh primary flip this bar
  │   ├── only if confirm agrees (if set) — sign of confirm value
  │   └── open @ this bar's close, mark entry bar
  │
  └── snapshot indicator values as "previous" for next iteration
```

### Intra-bar fill assumption (IMPORTANT)

When a bar's high/low range contains **both** the SL level and the target level, we cannot know from OHLC alone which fired first. Live scalp uses tick data and has no such ambiguity; bar replay does.

**Rule for v1: SL fires first** when both levels sit inside a bar's H/L. This is the conservative/industry-standard assumption. The result object will include an `intra_bar_ambiguity_count` field so users can see how often this estimator mattered.

A future v2 could re-fetch 1-minute candles for every bar-with-ambiguity to resolve the order precisely (Upstox allows 1m for 30 days — enough for most scalp windows).

### Trailing stop mechanics

Trail activation uses `trail_arm_points` (favourable move from entry before trail engages) and `trail_points` (distance the trail trails the highest favourable price). Percentage trails (`trail_percent`) are resolved into points at arm time. All three fields mirror live-scalper semantics exactly — copy the arm/update logic from `monitor/scalp_session.py` rather than re-derive it.

### Session boundaries (intraday mode)

- A "session" is a calendar trading day, IST.
- At the first bar of a new session: clear any open position (shouldn't exist, but defensive), reset `trade_count`, clear cooldown, clear primary/prev indicator caches.
- At the first bar **at or after** `squareoff_time` (e.g., 15:15 IST): if a position is open, close it with reason="squareoff" at that bar's open price.

### Swing mode

- No session reset; `trade_count` accumulates across the full backtest window.
- No squareoff; exits are SL, target, trail, opposite-flip only.
- `cooldown_seconds` still applies.

## Data fetch

Use existing `UpstoxClient.get_historical_data(symbol, interval, days)`. Respects Upstox's chunking limits (25 days for 1–15m, 80 days for 30m). For swing backtests on `day` interval, we can request years of history.

One new helper needed: `normalize_candles_to_dicts()` — `get_historical_data()` returns `list[OHLCVData]` (Pydantic), but `compute_indicator()` expects `list[dict]`. Add a one-liner adapter.

## Output

```python
@dataclass
class ScalpBacktestResult:
    symbol: str
    session_mode: str
    interval: str
    days: int
    config: dict              # echo of input config for reproducibility
    candle_count: int
    bars_in_session: int

    trades: list[Trade]       # from simulator, with exit_reason
    metrics: dict             # from compute_metrics: win_rate, pnl, drawdown, sharpe, avg_hold

    # Backtest-specific diagnostics
    intra_bar_ambiguity_count: int      # bars where SL+target both in H/L
    primary_flips: int                   # how many times signal flipped
    confirm_blocks: int                  # how many flips were rejected by confirm
    squareoff_exits: int                 # intraday mode only
    max_consecutive_losses: int
```

## Surfaces

### CLI — `nf-backtest-scalp`

```
nf-backtest-scalp --symbol RELIANCE --days 30 --interval 5minute \
    --primary utbot --primary-period 10 --primary-sensitivity 1.0 \
    --confirm qqe_mod --confirm-rsi-period 6 --confirm-smoothing 5 \
    --sl 2.0 --target 4.0 --trail-arm 1.5 --trail 0.8 \
    --quantity 10 --max-trades 20 --cooldown 60 \
    --session-mode intraday --squareoff 15:15 --json
```

Matches `nf-scalp`'s flag conventions so the mental model transfers. `--json` emits the full result; default text output prints a human-readable summary.

### REST — `POST /api/backtest/scalp`

Body = `ScalpBacktestRequest`. Uses `get_current_user` + `get_user_upstox_token` — same pattern as `api/backtest.py` existing endpoints. Returns JSON-serialized `ScalpBacktestResult`.

### UI — new Backtest tab

Add a "Scalp Replay" tab to `frontend-v2/app/routes/backtest.tsx`:
- Form mirrors the Scalp Session creation form (same field names, same defaults).
- "Run" button calls the API, shows progress indicator.
- Results: equity curve chart, trade table (entry/exit/reason/P&L), metrics card, diagnostic badges.
- "Save as Live Session" button: pre-fills the scalp-session creation form with the same config (the whole point of reusing `ScalpSessionConfig`).

## Testing

**Unit tests** (`backend/tests/backtesting/test_scalp_equity.py`):
1. Synthetic candles with known UT Bot flip → entry fires on correct bar.
2. Synthetic candles with SL inside bar H/L → SL exit at correct price.
3. Bar with both SL + target in H/L → SL fires first (conservative rule), ambiguity counter increments.
4. Trail arm then trail hit → exit at trail level, not at target.
5. Intraday squareoff: open position at 15:14, first bar >= 15:15 closes it.
6. Swing mode: position held across days, no squareoff, closes only on flip/SL/target/trail.
7. Confirm rejection: primary flips but confirm disagrees → no entry.
8. Max trades hit: further flips in the session are ignored.
9. Cooldown: exit at bar N, flip at bar N+1 with cooldown=60s — entry deferred.

**Integration test** (marked slow, requires Upstox token): fetch 7 days of RELIANCE 5m, run default UT Bot config, assert result schema shape and plausible trade count.

## Open questions — resolved

1. **Brokerage model — DECIDED:** compute charges per round-trip, report P&L both gross and net, mirroring `cockpit._estimate_charges()`.

2. **Slippage model — DECIDED:** optional `--slippage-bps` flag, default 0 for v1.

3. **Indicator timeframe ≠ fetch interval — DECIDED:** v1 requires `interval == indicator_timeframe`. Reject mismatches with a clear error. Resampling is a v2 feature.

4. **Intra-bar ambiguity disclosure — DECIDED:** show "⚠️ N of M trades had bar-resolution ambiguity, results are approximate" in the UI when the ratio exceeds 20%.

## Implementation phases

**Phase 1 — Engine core (1 session of work):**
- `backtesting/scalp_equity.py` with state machine + intra-bar fill logic.
- Unit tests (1–9 above).
- Test harness runnable via `pytest`.

**Phase 2 — Surfaces:**
- CLI `nf-backtest-scalp`.
- REST endpoint `/api/backtest/scalp`.
- Integration test.

**Phase 3 — UI:**
- New tab in `backtest.tsx`.
- Equity curve + trade table + metrics card.
- "Save as Live Session" button wired to scalp-session creation.

**Phase 4 (defer) — Polish:**
- Charges/slippage modeling.
- Resampling support (`indicator_timeframe` ≠ `interval`).
- 1-minute ambiguity resolution.

**Phase 5 (defer) — Options backtest:**
- Separate module `backtesting/scalp_options.py` using `ExpiredInstrumentApi`.
- Resolves past-expiry ATM strikes from `get_expired_option_contracts`.
- Fetches candles via `get_expired_historical_candle_data`.

## Risks

- **Bar-based approximation is lossy for short SL/target distances.** If SL is 0.5 points and a 5m bar spans 3 points, almost every trade is ambiguous. The diagnostic banner mitigates this, but a user might still draw bad conclusions. Countermeasure: document prominently; consider auto-suggesting a smaller interval when ambiguity ratio is high.
- **Config drift between live and backtest.** If `ScalpSessionConfig` gains a field used by the live engine but not the backtest, silent divergence. Countermeasure: keep both engines calling the same `compute_indicator()` helper; add a regression test that runs a small live session replay against its recorded ticks and compares to backtest output on the same bars.
- **Expensive indicator recomputation.** Recomputing UT Bot from scratch on every bar is O(N²) over the backtest. For 30 days × 75 bars/day = 2,250 bars, that's ~5M indicator evaluations — manageable but not free. Countermeasure: profile after Phase 1; if slow, add incremental update support to indicators that can stream (UT Bot, Supertrend).

## Success criteria

- A user can paste a live scalp config into the backtest UI, hit Run, and see trade-by-trade P&L for the last 30 days in under 10 seconds.
- The "Save as Live Session" button takes a backtested config live with zero manual re-entry.
- Metrics match what the user would see on a production session over the same window (within 5%, accounting for bar vs tick).
