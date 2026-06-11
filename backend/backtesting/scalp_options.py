"""Scalp-style options backtest — bar-replay mirror of the live ScalpSessionManager
options_scalp state machine.

The live engine (`monitor/scalp_session.py`) drives an underlying tick stream
through a primary indicator, BUYs an ATM CE on a bullish flip and an ATM PE
on a bearish flip, then manages SL/target/trail/squareoff in premium space
on the held option leg. This module reproduces that flow against historical
candles so a config can be evaluated before going live.

Key differences from the live engine
------------------------------------

* **Bar replay, not tick replay**. SL/target/trail are evaluated on each
  option candle's H/L. When SL and target both sit inside one bar's range
  the engine falls back to a conservative SL-first rule and increments
  ``intra_bar_ambiguity`` so callers can judge how often the estimator was
  load-bearing.
* **Two-pass design.** Pass 1 (`plan_atm_legs`) walks the underlying signal
  and records every (date, ATM strike, CE/PE) combination it would BUY.
  The API layer then fetches those leg candles from Upstox in parallel.
  Pass 2 (this module's main loop) replays underlying signal + premium
  candles in lockstep, with O(1) timestamp lookup into per-leg candle
  indexes. Without the two-pass split we'd either pre-fetch the whole
  option chain (huge) or do sequential per-flip fetches inside the bar
  loop (slow + non-async-safe).
* **Long-premium only.** Bullish flip → BUY ATM CE, bearish flip → BUY
  ATM PE. Both are long-premium positions; SL/target/trail mechanics
  are identical between sides at the leg level.
* **Fill model.** Flip detected at bar T close → entry at the option's
  bar T+1 close. Mirrors live behaviour where the order is placed on
  flip but premium isn't observed until the next subscribed tick window.
* **Charges.** Round-trip BUY+SELL via ``strategies.fno_utils.estimate_leg_charges``
  applied to each completed trade.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time as dtime, timezone
from typing import Any

from backtesting.metrics import compute_metrics
from backtesting.scalp_equity import (
    _INTERVAL_TO_TIMEFRAME,
    _candles_to_frame,
    _confirm_agrees_at,
    _interval_offset,
    _parse_candle_ts,
    _parse_squareoff,
)
from backtesting.simulator import Trade
from monitor.indicator_series import compute_indicator_series
from monitor.scalp_models import ScalpSessionConfig, SessionMode
from strategies.fno_utils import (
    estimate_leg_charges,
    get_lot_size,
    list_strikes,
    resolve_option_instrument,
)


@dataclass
class LegFetchPlan:
    """One leg-fetch the planner says the replay will need.

    Stable hashable identity so callers can dedupe before fetching.
    """
    date: str                # YYYY-MM-DD
    strike: float
    option_type: str         # "CE" | "PE"
    instrument_key: str
    tradingsymbol: str = ""
    lot_size: int = 0        # resolved per-contract lot (varies by expiry for stocks)
    expiry: str = ""         # ISO expiry the leg resolved against (rolling-aware)


@dataclass
class RollingExpiryData:
    """Pre-fetched contract metadata for rolling front-weekly resolution.

    expiries: sorted ISO dates covering the window (and the current front
    weekly if the window extends to today).
    contracts_by_expiry: expiry -> list of contract dicts, each with at least
    strike_price (float), instrument_type ("CE"/"PE"), instrument_key (str),
    trading_symbol (str), lot_size (int).
    """
    expiries: list[str]
    contracts_by_expiry: dict[str, list[dict]]


def front_expiry_for_date(d: str, expiries: list[str]) -> str | None:
    """Smallest expiry >= d (the weekly that is front-of-book on date ``d``).

    Tiny duplicated helper kept local so the backtest engine stays free of a
    ``services/`` import. ``expiries`` need not be pre-sorted.
    """
    candidates = [e for e in expiries if e >= d]
    if not candidates:
        return None
    return min(candidates)


def _atm_strike(strikes: list[float], underlying_price: float) -> float:
    """ATM strike = the listed strike nearest the underlying price.

    Shared by both passes and both expiry modes so the strike selection rule
    is byte-identical everywhere (a pass-1/pass-2 divergence would orphan
    every planned leg into ``missing_leg_blocks``).
    """
    return min(strikes, key=lambda s: abs(s - underlying_price))


def _rolling_resolve(
    rolling: RollingExpiryData,
    option_type: str,
    bar_date_iso: str,
    underlying_price: float,
) -> dict | None:
    """Resolve a single flip against the rolling front-weekly contract set.

    Returns a contract dict (strike_price/instrument_type/instrument_key/
    trading_symbol/lot_size) for the ATM strike on the contract that was
    front-of-book on ``bar_date_iso``, or ``None`` when no expiry covers the
    date or the front contract lists no strikes of this option_type.

    Both passes call this so the per-flip resolution is identical; a divergence
    would mean pass-1 plans legs pass-2 never looks up (missing_leg_blocks).
    """
    expiry = front_expiry_for_date(bar_date_iso, rolling.expiries)
    if expiry is None:
        return None
    contracts = [
        c for c in rolling.contracts_by_expiry.get(expiry, [])
        if c.get("instrument_type") == option_type
    ]
    if not contracts:
        return None
    strikes = sorted(float(c["strike_price"]) for c in contracts)
    atm = _atm_strike(strikes, underlying_price)
    for c in contracts:
        if float(c["strike_price"]) == atm:
            return {**c, "_expiry": expiry, "_strike": atm}
    return None


@dataclass
class ScalpOptionsBacktestResult:
    """Outcome of one options scalp replay."""
    underlying: str
    expiry: str
    interval: str
    days: int
    config: dict

    candle_count: int            # underlying candles replayed
    session_days: int            # distinct trading days touched

    trades: list[Trade]
    metrics: dict                # gross
    metrics_net: dict            # net of charges + slippage
    charges_total: float
    slippage_total: float

    # Diagnostics — same shape as scalp_equity result + a few extras for legs
    intra_bar_ambiguity: int
    primary_flips: int
    confirm_blocks: int
    cooldown_blocks: int
    max_trades_blocks: int
    squareoff_exits: int
    missing_leg_blocks: int      # flips where no option candles were available
    no_strike_blocks: int        # flips where the F&O cache returned no strikes
    post_cutoff_blocks: int = 0  # flips rejected for being at/after squareoff cutoff
    entry_side_blocks: int = 0   # flips rejected by entry_side (CE/PE-only) gate
    expiries_used: list[str] = field(default_factory=list)  # distinct expiries traded, sorted


@dataclass
class _OptionPositionState:
    """Live position tracking for the options-scalp replay.

    Always long-premium (we BUY CE or PE). Tracks the held leg's
    instrument_key + tradingsymbol so each round-trip can be tagged with
    the correct contract symbol. Mirrors ``ScalpSessionRuntime`` semantics
    relevant to the bar loop.
    """
    option_type: str | None = None    # "CE" | "PE" | None
    strike: float | None = None
    instrument_key: str | None = None
    tradingsymbol: str | None = None
    entry_price: float = 0.0
    entry_time: datetime | None = None
    quantity: int = 0
    trail_armed: bool = False
    highest_premium: float = 0.0

    @property
    def is_flat(self) -> bool:
        return self.option_type is None


# ──────────────────────────────────────────────────────────────────────
# Pass 1 — plan the leg fetches the bar loop will need
# ──────────────────────────────────────────────────────────────────────

def plan_atm_legs(
    underlying_candles: list[dict],
    config: ScalpSessionConfig,
    interval: str,
    warmup_bars: int = 0,
    rolling: RollingExpiryData | None = None,
) -> list[LegFetchPlan]:
    """Scan the underlying primary signal once, return every (date, ATM, type)
    leg the replay will need to BUY.

    Confirm gate is applied (legs blocked by confirm aren't fetched). Cooldown
    and max_trades are NOT applied here — they're cheap, deterministic, and
    keeping them out of the planner avoids replicating the bar-loop's full
    state machine. Over-fetching a few legs is preferable to a stale plan.

    When ``rolling`` is supplied, each flip resolves against the weekly
    contract that was front-of-book on that bar's date (via the pre-fetched
    ``RollingExpiryData``) instead of the single fixed ``config.expiry``. The
    fixed-expiry path is unchanged.
    """
    if config.session_mode != SessionMode.OPTIONS_SCALP.value:
        raise ValueError(
            f"plan_atm_legs only supports options_scalp; got {config.session_mode!r}"
        )
    if rolling is None and not config.expiry:
        raise ValueError("config.expiry is required for options_scalp planning")

    expected_tf = _INTERVAL_TO_TIMEFRAME.get(interval)
    if expected_tf is None:
        raise ValueError(f"unsupported interval: {interval}")
    if config.indicator_timeframe and config.indicator_timeframe != expected_tf:
        raise ValueError(
            f"indicator_timeframe {config.indicator_timeframe!r} does not match "
            f"interval {interval!r} (expected {expected_tf!r})."
        )

    normalised = _candles_to_frame(underlying_candles)
    normalised.sort(key=lambda c: _parse_candle_ts(c["timestamp"]))
    if not normalised:
        return []

    primary_series = compute_indicator_series(
        config.primary_indicator, normalised, config.primary_params or {}
    )
    confirm_series: list[float | None] | None = None
    if config.confirm_indicator:
        confirm_series = compute_indicator_series(
            config.confirm_indicator, normalised, config.confirm_params or {}
        )

    plans: list[LegFetchPlan] = []
    seen: set[tuple[str, float, str]] = set()
    prev_primary: float | None = None
    entry_side = (config.entry_side or "both").lower()

    # Cache strike lists per (date, type) — list_strikes is cheap but no
    # reason to redo it per flip.
    strikes_cache: dict[str, list[float]] = {}

    for i, bar in enumerate(normalised):
        primary_val = primary_series[i]
        if prev_primary is None or primary_val is None:
            if primary_val is not None:
                prev_primary = primary_val
            continue

        bullish = prev_primary <= 0 and primary_val > 0
        bearish = prev_primary >= 0 and primary_val < 0
        prev_primary = primary_val
        if not (bullish or bearish):
            continue
        # Warm-up region: indicators are still converging and the replay won't
        # trade here, so don't plan (or fetch) legs for these flips.
        if i < warmup_bars:
            continue

        direction_sign = 1 if bullish else -1
        option_type = "CE" if bullish else "PE"

        # Entry-side gate — don't plan (or fetch) legs the run loop will skip.
        # "long" → CE-only (bullish flips), "short" → PE-only (bearish flips).
        if (bullish and entry_side == "short") or (bearish and entry_side == "long"):
            continue

        # Confirm gate
        conf_val = confirm_series[i] if confirm_series is not None else None
        agrees, _ = _confirm_agrees_at(config, conf_val, direction_sign)
        if not agrees:
            continue

        # Resolve ATM at this bar's underlying close (same anchor live uses).
        underlying_price = float(bar["close"])
        ts = _parse_candle_ts(bar["timestamp"])
        day = ts.date().isoformat()

        if rolling is not None:
            # Rolling front-weekly: resolve against the contract front-of-book
            # on this date. instrument_key/tradingsymbol/lot_size come straight
            # off the matched contract dict (NOT resolve_option_instrument).
            contract = _rolling_resolve(rolling, option_type, day, underlying_price)
            if contract is None:
                continue
            atm = contract["_strike"]
            ident = (day, atm, option_type)
            if ident in seen:
                continue
            seen.add(ident)
            plans.append(LegFetchPlan(
                date=day,
                strike=atm,
                option_type=option_type,
                instrument_key=contract["instrument_key"],
                tradingsymbol=contract.get("trading_symbol", ""),
                lot_size=int(contract.get("lot_size") or 0),
                expiry=contract["_expiry"],
            ))
            continue

        # Fixed-expiry path (unchanged).
        cache_key = option_type
        strikes = strikes_cache.get(cache_key)
        if strikes is None:
            try:
                strikes = list_strikes(config.underlying, config.expiry, option_type)
            except Exception:
                strikes = []
            strikes_cache[cache_key] = strikes
        if not strikes:
            continue

        atm = _atm_strike(strikes, underlying_price)
        ident = (day, atm, option_type)
        if ident in seen:
            continue
        seen.add(ident)

        try:
            inst = resolve_option_instrument(
                config.underlying, config.expiry, atm, option_type,
            )
        except Exception:
            continue

        plans.append(LegFetchPlan(
            date=day,
            strike=atm,
            option_type=option_type,
            instrument_key=inst["instrument_key"],
            tradingsymbol=inst.get("tradingsymbol", ""),
            lot_size=int(inst.get("lot_size") or 0),
            expiry=config.expiry,
        ))

    return plans


# ──────────────────────────────────────────────────────────────────────
# Pass 2 — full bar replay with leg candles in hand
# ──────────────────────────────────────────────────────────────────────

def run_scalp_options_backtest(
    underlying_candles: list[dict],
    leg_candles_by_key: dict[str, list[dict]],
    config: ScalpSessionConfig,
    *,
    interval: str,
    slippage_bps: float = 0.0,
    progress_cb=None,
    cancel_check=None,
    warmup_bars: int = 0,
    rolling: RollingExpiryData | None = None,
) -> ScalpOptionsBacktestResult:
    """Bar-replay the options scalp state machine.

    Args:
        underlying_candles: OHLCV candles for the underlying index/symbol.
            Order is not required — sorted ascending internally.
        leg_candles_by_key: pre-fetched OHLCV by ``instrument_key``. The
            planner (``plan_atm_legs``) tells the API which legs to fetch.
            Missing legs cause ``missing_leg_blocks`` to increment instead
            of raising.
        config: ``ScalpSessionConfig`` with ``session_mode=options_scalp``.
        interval: Upstox interval string — must match
            ``config.indicator_timeframe`` per v1 contract (no resampling).
        slippage_bps: per-leg slippage in basis points applied to fill price.
        progress_cb / cancel_check: same contract as scalp_equity.
    """
    if config.session_mode != SessionMode.OPTIONS_SCALP.value:
        raise ValueError(
            f"run_scalp_options_backtest requires options_scalp; got {config.session_mode!r}"
        )
    if rolling is None and not config.expiry:
        raise ValueError("config.expiry is required for options_scalp backtest")
    if not config.lots or config.lots <= 0:
        raise ValueError("config.lots must be > 0 for options_scalp backtest")

    expected_tf = _INTERVAL_TO_TIMEFRAME.get(interval)
    if expected_tf is None:
        raise ValueError(f"unsupported interval: {interval}")
    if config.indicator_timeframe and config.indicator_timeframe != expected_tf:
        raise ValueError(
            f"indicator_timeframe {config.indicator_timeframe!r} does not match "
            f"interval {interval!r} (expected {expected_tf!r})."
        )

    normalised = _candles_to_frame(underlying_candles)
    normalised.sort(key=lambda c: _parse_candle_ts(c["timestamp"]))
    if not normalised:
        return _empty_result(config, interval)

    # Lot-aware sizing — option legs trade in multiples of lot_size. Pass the
    # expiry: stock (OPTSTK) lots can differ across expiries, and the whole
    # replay is anchored to config.expiry (the same contract plan_atm_legs
    # resolved), so this matches the legs being replayed. In rolling mode the
    # config.expiry is the "rolling" sentinel (not a real date), so the lookup
    # is best-effort and serves only as a per-trade fallback when a resolved
    # contract lacks lot_size; the per-trade lot comes off the contract.
    fallback_expiry = None if rolling is not None else config.expiry
    try:
        lot_size = get_lot_size(config.underlying, fallback_expiry)
    except Exception:
        lot_size = get_lot_size(config.underlying)
    quantity = int(config.lots) * lot_size

    # Build per-leg timestamp index for O(1) lookup. The replay aligns
    # underlying and option bars by timestamp; mismatches drop to
    # missing_leg_blocks rather than fail loudly.
    leg_ts_index: dict[str, dict[datetime, dict]] = {}
    for ik, candles in leg_candles_by_key.items():
        idx: dict[datetime, dict] = {}
        for c in _candles_to_frame(candles):
            t = _parse_candle_ts(c["timestamp"])
            idx[t] = c
        leg_ts_index[ik] = idx

    squareoff_cutoff = _parse_squareoff(config.squareoff_time)
    # Bar duration — used to evaluate the squareoff/entry cutoff against each
    # bar's CLOSE (the bar live at the cutoff) rather than its open, so a 15:09
    # cutoff trips on the bar containing 15:09 instead of the next one.
    disp_off = _interval_offset(interval)
    entry_side = (config.entry_side or "both").lower()

    # Precompute primary + confirm series on the underlying. Same trick as
    # scalp_equity: O(n) once instead of O(n²) per-bar.
    primary_series = compute_indicator_series(
        config.primary_indicator, normalised, config.primary_params or {}
    )
    confirm_series: list[float | None] | None = None
    if config.confirm_indicator:
        confirm_series = compute_indicator_series(
            config.confirm_indicator, normalised, config.confirm_params or {}
        )

    # Cache of (date, type) → strike list for ATM resolution at flip. Keys
    # carry the expiry too so rolling mode (front weekly changes across the
    # window) doesn't collide a strike list from one expiry onto another.
    strikes_cache: dict[tuple[str, str, str], list[float]] = {}
    inst_resolve_cache: dict[tuple[str, float, str], dict] = {}
    expiries_used: set[str] = set()

    pos = _OptionPositionState()
    trades: list[Trade] = []
    prev_primary: float | None = None
    current_day = None
    trade_count = 0
    last_exit_time: datetime | None = None
    prev_ts: datetime | None = None                # last processed bar ts (prior-day squareoff)

    intra_bar_ambiguity = 0
    primary_flips = 0
    confirm_blocks = 0
    cooldown_blocks = 0
    max_trades_blocks = 0
    squareoff_exits = 0
    missing_leg_blocks = 0
    no_strike_blocks = 0
    post_cutoff_blocks = 0
    entry_side_blocks = 0
    slippage_total = 0.0
    charges_total = 0.0

    session_days: set = set()

    # Warm-up buffer: drop the leading `warmup_bars` history candles from the
    # replay (trades/diagnostics cover only the requested window) but seed
    # prev_primary from the last warm-up bar so the first in-window flip is
    # detected against a converged value. Only the UNDERLYING is sliced — leg
    # candles are keyed by timestamp and only consumed when a position is held
    # (entries are in-window), so leg_ts_index is unaffected.
    if warmup_bars > 0 and normalised:
        warmup_bars = min(warmup_bars, len(normalised))
        if warmup_bars >= 1:
            prev_primary = primary_series[warmup_bars - 1]
        normalised = normalised[warmup_bars:]
        primary_series = primary_series[warmup_bars:]
        if confirm_series is not None:
            confirm_series = confirm_series[warmup_bars:]
        if not normalised:
            return _empty_result(config, interval)

    slip_frac = slippage_bps / 10_000.0
    total_bars = len(normalised)
    _PROGRESS_BATCH = 200

    for i, bar in enumerate(normalised):
        if cancel_check is not None and i % _PROGRESS_BATCH == 0:
            try:
                if cancel_check():
                    break
            except Exception:
                pass
        if progress_cb is not None and i % _PROGRESS_BATCH == 0:
            try:
                progress_cb(i, total_bars)
            except Exception:
                pass

        ts = _parse_candle_ts(bar["timestamp"])
        bar_date = ts.date()
        session_days.add(bar_date)

        # Day boundary — squareoff any open leg. With the past-cutoff entry
        # guard below this is rare (day ended before cutoff), but as a safety
        # net we close at the PRIOR day's last leg bar (close) and stamp the
        # prior day's ts — never carry overnight or show a next-day timestamp.
        # Reset trade_count + cooldown anchor.
        if current_day is not None and bar_date != current_day and not pos.is_flat:
            prior_opt_bar = (
                leg_ts_index.get(pos.instrument_key, {}).get(prev_ts)
                if prev_ts is not None else None
            )
            exit_price = prior_opt_bar["close"] if prior_opt_bar else pos.entry_price
            tr = _close_options(
                pos, exit_price, prev_ts or ts, "squareoff", slip_frac,
            )
            if tr:
                _apply_options_costs(tr)
                trades.append(tr)
                charges_total += getattr(tr, "_charges_total", 0.0)
            squareoff_exits += 1
            last_exit_time = prev_ts or ts
        if current_day != bar_date:
            trade_count = 0
            last_exit_time = None
        current_day = bar_date

        # Time-based squareoff guard within the day. Mirrors scalp_session
        # check_time_squareoff but driven by bar timestamps.
        bar_tod = ts.timetz().replace(tzinfo=None)
        bar_close_tod = (ts + disp_off).time() if disp_off else bar_tod
        prev_ts = ts  # track for the prior-day boundary close (before continues)
        if not pos.is_flat and bar_close_tod > squareoff_cutoff:
            opt_bar = leg_ts_index.get(pos.instrument_key, {}).get(ts)
            # Exit at this bar's close — the premium at the cutoff boundary.
            exit_price = opt_bar["close"] if opt_bar else pos.entry_price
            tr = _close_options(
                pos, exit_price, ts, "squareoff", slip_frac,
            )
            if tr:
                _apply_options_costs(tr)
                trades.append(tr)
                charges_total += getattr(tr, "_charges_total", 0.0)
            squareoff_exits += 1
            last_exit_time = ts
            # Past squareoff — no re-entry for the rest of the day.
            continue

        # Indicator evaluation
        primary_val = primary_series[i]
        if prev_primary is not None and primary_val is not None:
            bullish_flip = prev_primary <= 0 and primary_val > 0
            bearish_flip = prev_primary >= 0 and primary_val < 0
            if bullish_flip or bearish_flip:
                primary_flips += 1
        else:
            bullish_flip = bearish_flip = False

        # Premium-side checks (SL / target / trail) on the held leg's bar.
        if not pos.is_flat:
            opt_bar = leg_ts_index.get(pos.instrument_key, {}).get(ts)
            if opt_bar is not None:
                exit_info = _check_premium_exits(pos, opt_bar, config)
                if exit_info:
                    exit_reason, exit_price, ambiguous = exit_info
                    if ambiguous:
                        intra_bar_ambiguity += 1
                    tr = _close_options(
                        pos, exit_price, ts, exit_reason, slip_frac,
                    )
                    if tr:
                        _apply_options_costs(tr)
                        trades.append(tr)
                        charges_total += getattr(tr, "_charges_total", 0.0)
                    last_exit_time = ts
                    trade_count += 1

            # Reversal exit on opposite primary flip — uses option close
            # at this bar (mirrors the live engine using last_premium_ltp,
            # closest equivalent in bar space).
            if not pos.is_flat:
                bullish_state = pos.option_type == "CE"
                bearish_state = pos.option_type == "PE"
                if (bullish_state and bearish_flip) or (bearish_state and bullish_flip):
                    rev_opt_bar = leg_ts_index.get(pos.instrument_key, {}).get(ts)
                    rev_exit_price = (
                        rev_opt_bar["close"] if rev_opt_bar else pos.entry_price
                    )
                    tr = _close_options(
                        pos, rev_exit_price, ts, "entry_opposite",
                        slip_frac,
                    )
                    if tr:
                        _apply_options_costs(tr)
                        trades.append(tr)
                        charges_total += getattr(tr, "_charges_total", 0.0)
                    last_exit_time = ts
                    trade_count += 1

        # Entry on fresh flip — only when flat after the exit checks above.
        if pos.is_flat and (bullish_flip or bearish_flip):
            direction_sign = 1 if bullish_flip else -1
            option_type = "CE" if bullish_flip else "PE"

            # Entry-side gate (mirrors ScalpSessionManager): "long" takes only
            # bullish flips (BUY CE), "short" only bearish (BUY PE).
            if (bullish_flip and entry_side == "short") or (
                bearish_flip and entry_side == "long"
            ):
                entry_side_blocks += 1
                prev_primary = primary_val
                continue

            # Past-cutoff entry guard — mirrors the live session and the equity
            # backtest. Options scalps are always intraday; a flip on the bar
            # live at the cutoff (or later) would otherwise open a leg that gets
            # squared off on that same bar, carrying it across the cutoff.
            if bar_close_tod > squareoff_cutoff:
                post_cutoff_blocks += 1
                prev_primary = primary_val
                continue

            # Cooldown
            if last_exit_time is not None:
                elapsed = (ts - last_exit_time).total_seconds()
                if elapsed < (config.cooldown_seconds or 0):
                    cooldown_blocks += 1
                    prev_primary = primary_val
                    continue

            # Max trades guard
            if config.max_trades and trade_count >= config.max_trades:
                max_trades_blocks += 1
                prev_primary = primary_val
                continue

            # Confirm gate
            conf_val = confirm_series[i] if confirm_series is not None else None
            agrees, _ = _confirm_agrees_at(config, conf_val, direction_sign)
            if not agrees:
                confirm_blocks += 1
                prev_primary = primary_val
                continue

            # ATM resolution at this bar's underlying close. Pass-2 MUST mirror
            # pass-1 exactly (same per-flip expiry + ATM + contract) or the leg
            # candles fetched off pass-1 plans won't match these lookups and
            # every flip would fall to missing_leg_blocks.
            underlying_price = float(bar["close"])
            bar_date_iso = bar_date.isoformat()
            entry_lot_size = lot_size  # fixed-mode default; overridden in rolling

            if rolling is not None:
                contract = _rolling_resolve(
                    rolling, option_type, bar_date_iso, underlying_price,
                )
                if contract is None:
                    no_strike_blocks += 1
                    prev_primary = primary_val
                    continue
                atm = contract["_strike"]
                entry_expiry = contract["_expiry"]
                instrument_key = contract["instrument_key"]
                tradingsymbol = contract.get("trading_symbol", "")
                contract_lot = int(contract.get("lot_size") or 0)
                if contract_lot > 0:
                    entry_lot_size = contract_lot
            else:
                cache_key = (bar_date_iso, option_type, config.expiry)
                strikes = strikes_cache.get(cache_key)
                if strikes is None:
                    try:
                        strikes = list_strikes(
                            config.underlying, config.expiry, option_type,
                        )
                    except Exception:
                        strikes = []
                    strikes_cache[cache_key] = strikes
                if not strikes:
                    no_strike_blocks += 1
                    prev_primary = primary_val
                    continue

                atm = _atm_strike(strikes, underlying_price)
                entry_expiry = config.expiry
                inst_key = (config.expiry, atm, option_type)
                inst = inst_resolve_cache.get(inst_key)
                if inst is None:
                    try:
                        inst = resolve_option_instrument(
                            config.underlying, config.expiry, atm, option_type,
                        )
                        inst_resolve_cache[inst_key] = inst
                    except Exception:
                        no_strike_blocks += 1
                        prev_primary = primary_val
                        continue

                instrument_key = inst["instrument_key"]
                tradingsymbol = inst.get("tradingsymbol", "")

            # Fill: option close at next underlying bar's timestamp.
            if i + 1 >= total_bars:
                missing_leg_blocks += 1
                prev_primary = primary_val
                continue
            next_ts = _parse_candle_ts(normalised[i + 1]["timestamp"])
            # Guard: don't carry an entry across day boundary.
            if next_ts.date() != bar_date:
                missing_leg_blocks += 1
                prev_primary = primary_val
                continue
            # Past-cutoff FILL guard. Options fill at the next bar, so a flip
            # just before the cutoff (decision bar < cutoff, passes the guard
            # above) would fill AT/after the cutoff and be squared off on that
            # same bar — the degenerate enter→immediate-squareoff the live
            # session forbids. Block when the fill bar is the one live at the
            # cutoff (or later) — evaluated against its close, consistent with
            # the held-leg squareoff above.
            fill_close_tod = (
                (next_ts + disp_off).time() if disp_off
                else next_ts.timetz().replace(tzinfo=None)
            )
            if fill_close_tod > squareoff_cutoff:
                post_cutoff_blocks += 1
                prev_primary = primary_val
                continue
            fill_bar = leg_ts_index.get(instrument_key, {}).get(next_ts)
            if fill_bar is None:
                missing_leg_blocks += 1
                prev_primary = primary_val
                continue

            # Per-trade lot: rolling mode takes lot_size off the resolved
            # contract (index lots can change across expiries); fixed mode and
            # the rolling fallback use the single get_lot_size() above.
            trade_quantity = int(config.lots) * entry_lot_size

            raw_entry = float(fill_bar["close"])
            entry_price = raw_entry * (1 + slip_frac)
            slippage_total += abs(raw_entry - entry_price) * trade_quantity

            pos.option_type = option_type
            pos.strike = atm
            pos.instrument_key = instrument_key
            pos.tradingsymbol = tradingsymbol
            pos.entry_price = entry_price
            pos.entry_time = next_ts
            pos.quantity = trade_quantity
            pos.trail_armed = False
            pos.highest_premium = entry_price
            expiries_used.add(entry_expiry)

        prev_primary = primary_val if primary_val is not None else prev_primary

    if progress_cb is not None:
        try:
            progress_cb(total_bars, total_bars)
        except Exception:
            pass

    # Close any still-open leg on the last bar for accounting completeness.
    if not pos.is_flat:
        last_bar = normalised[-1]
        last_ts = _parse_candle_ts(last_bar["timestamp"])
        opt_bar = leg_ts_index.get(pos.instrument_key, {}).get(last_ts)
        exit_price = opt_bar["close"] if opt_bar else pos.entry_price
        tr = _close_options(pos, exit_price, last_ts, "end_of_data", slip_frac)
        if tr:
            _apply_options_costs(tr)
            trades.append(tr)
            charges_total += getattr(tr, "_charges_total", 0.0)

    # Metrics — gross from pre-cost pnl, net from current pnl on the trade.
    gross_trades = [_reconstruct_gross_options(t) for t in trades]
    notional = (
        config.lots * lot_size * (trades[0].entry_price if trades else 0)
    ) or 1
    metrics_gross = compute_metrics(gross_trades, initial_capital=notional)
    metrics_net = compute_metrics(trades, initial_capital=notional)

    return ScalpOptionsBacktestResult(
        underlying=config.underlying,
        expiry=config.expiry,
        interval=interval,
        days=len(session_days),
        config=config.model_dump(),
        candle_count=len(normalised),
        session_days=len(session_days),
        trades=trades,
        metrics=metrics_gross,
        metrics_net=metrics_net,
        charges_total=round(charges_total, 2),
        slippage_total=round(slippage_total, 2),
        intra_bar_ambiguity=intra_bar_ambiguity,
        primary_flips=primary_flips,
        confirm_blocks=confirm_blocks,
        cooldown_blocks=cooldown_blocks,
        max_trades_blocks=max_trades_blocks,
        squareoff_exits=squareoff_exits,
        missing_leg_blocks=missing_leg_blocks,
        no_strike_blocks=no_strike_blocks,
        post_cutoff_blocks=post_cutoff_blocks,
        entry_side_blocks=entry_side_blocks,
        expiries_used=sorted(expiries_used),
    )


# ──────────────────────────────────────────────────────────────────────
# Premium exit check — long-only, mirrors scalp_session._process_premium_tick
# ──────────────────────────────────────────────────────────────────────

def _check_premium_exits(
    pos: _OptionPositionState,
    opt_bar: dict,
    cfg: ScalpSessionConfig,
) -> tuple[str, float, bool] | None:
    """Decide whether this option bar fires SL / target / trail.

    Long-only — both CE and PE are bought (long premium). Mirrors the
    scalp_equity ``_check_exits`` long branch but on the option bar's H/L.
    """
    high = float(opt_bar["high"])
    low = float(opt_bar["low"])

    sl_level = (pos.entry_price - cfg.sl_points) if cfg.sl_points else None
    tgt_level = (pos.entry_price + cfg.target_points) if cfg.target_points else None

    sl_hit = sl_level is not None and low <= sl_level
    tgt_hit = tgt_level is not None and high >= tgt_level
    ambiguous = sl_hit and tgt_hit

    if sl_hit:
        return ("exit_sl", sl_level, ambiguous)

    armed_before_bar = pos.trail_armed
    trail_configured = cfg.trail_points is not None or cfg.trail_percent is not None

    if armed_before_bar:
        trail_level = _options_trail_level(pos, cfg)
        if trail_level is not None and low <= trail_level:
            return ("exit_trail", trail_level, False)
        if high > pos.highest_premium:
            pos.highest_premium = high

    if tgt_hit:
        return ("exit_target", tgt_level, ambiguous)

    if trail_configured and not pos.trail_armed:
        arm_threshold = cfg.trail_arm_points or 0
        if high >= pos.entry_price + arm_threshold:
            pos.trail_armed = True
            if high > pos.highest_premium:
                pos.highest_premium = high

    return None


def _options_trail_level(
    pos: _OptionPositionState, cfg: ScalpSessionConfig
) -> float | None:
    if cfg.trail_points is not None:
        return pos.highest_premium - cfg.trail_points
    if cfg.trail_percent is not None:
        return pos.highest_premium * (1 - cfg.trail_percent / 100)
    return None


# ──────────────────────────────────────────────────────────────────────
# Trade book-keeping — bypass TradeSimulator so each leg gets its own
# tradingsymbol; the simulator pins symbol at construction.
# ──────────────────────────────────────────────────────────────────────

def _close_options(
    pos: _OptionPositionState,
    raw_price: float,
    ts: datetime,
    reason: str,
    slip_frac: float,
) -> Trade | None:
    """Close the held leg with slippage + reset state. Returns the Trade row
    so the caller can apply costs and append to the trade list.
    """
    if pos.is_flat or pos.entry_time is None:
        return None
    exit_price = raw_price * (1 - slip_frac)  # long taker sells down
    pnl = (exit_price - pos.entry_price) * pos.quantity
    pnl_pct = (
        (pnl / (pos.entry_price * pos.quantity)) * 100 if pos.entry_price else 0.0
    )
    holding_mins = max(int((ts - pos.entry_time).total_seconds() / 60), 0)
    label = pos.tradingsymbol or (
        f"{pos.option_type or '?'} {pos.strike or '?'}"
    )
    trade = Trade(
        symbol=label,
        side="long",
        entry_price=pos.entry_price,
        entry_time=pos.entry_time,
        exit_price=exit_price,
        exit_time=ts,
        quantity=pos.quantity,
        pnl=round(pnl, 2),
        pnl_pct=round(pnl_pct, 2),
        exit_reason=reason,
        holding_minutes=holding_mins,
    )
    # Reset state
    pos.option_type = None
    pos.strike = None
    pos.instrument_key = None
    pos.tradingsymbol = None
    pos.entry_price = 0.0
    pos.entry_time = None
    pos.quantity = 0
    pos.trail_armed = False
    pos.highest_premium = 0.0
    return trade


def _apply_options_costs(trade: Trade) -> None:
    """Deduct round-trip BUY+SELL F&O charges from the trade in place.

    Stashes gross pnl + charges total as private attrs so the metrics
    reconstruction step can recover the gross figure.
    """
    entry_charges = estimate_leg_charges(
        trade.entry_price, trade.quantity, "BUY"
    )
    exit_charges = estimate_leg_charges(
        trade.exit_price, trade.quantity, "SELL"
    )
    total = round(entry_charges["total"] + exit_charges["total"], 2)
    trade._gross_pnl = trade.pnl  # type: ignore[attr-defined]
    trade._charges_total = total  # type: ignore[attr-defined]
    trade.pnl = round(trade.pnl - total, 2)
    if trade.entry_price and trade.quantity:
        trade.pnl_pct = round(
            (trade.pnl / (trade.entry_price * trade.quantity)) * 100, 2
        )


def _reconstruct_gross_options(trade: Trade) -> Trade:
    gross = Trade(
        symbol=trade.symbol,
        side=trade.side,
        entry_price=trade.entry_price,
        entry_time=trade.entry_time,
        exit_price=trade.exit_price,
        exit_time=trade.exit_time,
        quantity=trade.quantity,
        pnl=getattr(trade, "_gross_pnl", trade.pnl),
        pnl_pct=0.0,
        exit_reason=trade.exit_reason,
        holding_minutes=trade.holding_minutes,
    )
    if gross.entry_price and gross.quantity:
        gross.pnl_pct = round(
            (gross.pnl / (gross.entry_price * gross.quantity)) * 100, 2
        )
    return gross


def _empty_result(
    config: ScalpSessionConfig, interval: str
) -> ScalpOptionsBacktestResult:
    empty = compute_metrics([], initial_capital=1)
    return ScalpOptionsBacktestResult(
        underlying=config.underlying,
        expiry=config.expiry,
        interval=interval,
        days=0,
        config=config.model_dump(),
        candle_count=0,
        session_days=0,
        trades=[],
        metrics=empty,
        metrics_net=empty,
        charges_total=0.0,
        slippage_total=0.0,
        intra_bar_ambiguity=0,
        primary_flips=0,
        confirm_blocks=0,
        cooldown_blocks=0,
        max_trades_blocks=0,
        squareoff_exits=0,
        missing_leg_blocks=0,
        no_strike_blocks=0,
    )
