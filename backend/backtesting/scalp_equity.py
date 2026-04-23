"""Scalp-style equity backtest — bar-replay of the live ScalpSessionManager state machine.

Mirrors `monitor/scalp_session.py` semantics against historical candles so a user
can evaluate a scalp config before putting capital behind it. Same primary/
confirm indicator stack, same SL/target/trail/squareoff/cooldown/max_trades
guards, same flip-detection contract.

Key differences from the live engine:

* Bar replay, not tick replay. Intra-bar fills for SL/target/trail are
  approximated from each bar's O/H/L/C. When both an SL and a target level
  sit inside a single bar's high-low range, we cannot tell from OHLC alone
  which fired first — v1 applies a conservative **SL-first** rule and
  increments an ``intra_bar_ambiguity`` counter so callers can judge how
  often the estimator was load-bearing.

* Direction-aware SL/target/trail for SHORT positions. The live scalper's
  ``_process_premium_tick`` only handles long-direction exits today; here we
  mirror the arithmetic for shorts so the backtest stays mathematically
  correct. (Follow-up ticket: port this correctness back to the live engine.)

* No broker I/O — positions open/close in a ``TradeSimulator``, P&L is
  booked synchronously, charges + slippage are applied at close time.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time as dtime, timezone
from typing import Any, Literal

from backtesting.metrics import compute_metrics
from backtesting.simulator import Trade, TradeSimulator
from monitor.indicator_engine import compute_indicator
from monitor.scalp_models import ScalpSessionConfig, SessionMode


# Map candle interval name → indicator_timeframe token used by the live
# scalper. Used to enforce the v1 rule "interval must match indicator
# timeframe" — resampling is deferred to a later release.
_INTERVAL_TO_TIMEFRAME = {
    "1minute": "1m",
    "3minute": "3m",
    "5minute": "5m",
    "10minute": "10m",
    "15minute": "15m",
    "30minute": "30m",
    "day": "1d",
}


# Per-trade charges helper mirrors api/cockpit.py::_estimate_charges
# (Upstox Plus rate card, 2026-04). Kept local to avoid pulling in the
# cockpit API module.
def _estimate_round_trip_charges(
    entry_price: float, exit_price: float, quantity: int, is_intraday: bool
) -> dict[str, float]:
    buy_value = entry_price * quantity
    sell_value = exit_price * quantity
    turnover = buy_value + sell_value

    brokerage = 60.0 if is_intraday else 0.0  # 2 legs × ₹30 for Upstox Plus
    stt = sell_value * (0.00025 if is_intraday else 0.001)
    txn_charges = turnover * 0.0000345
    gst = (brokerage + txn_charges) * 0.18
    sebi = turnover * 0.000001
    stamp = buy_value * (0.00003 if is_intraday else 0.00015)
    total = brokerage + stt + txn_charges + gst + sebi + stamp
    return {
        "total": round(total, 2),
        "brokerage": round(brokerage, 2),
        "stt": round(stt, 2),
        "gst": round(gst, 2),
        "stamp_duty": round(stamp, 2),
        "other": round(txn_charges + sebi, 2),
    }


@dataclass
class ScalpBacktestResult:
    """Result of a single scalp equity backtest run."""

    symbol: str
    session_mode: str
    interval: str
    days: int
    config: dict

    candle_count: int
    session_days: int

    trades: list[Trade]
    metrics: dict                            # gross (compute_metrics output)
    metrics_net: dict                        # same shape, after charges + slippage
    charges_total: float                     # sum of per-trade round-trip charges
    slippage_total: float                    # sum of slippage costs

    # Backtest-specific diagnostics
    intra_bar_ambiguity: int                 # bars where SL+target both in H/L
    primary_flips: int                       # total flips seen (IDLE or not)
    confirm_blocks: int                      # flips rejected by confirm gate
    cooldown_blocks: int                     # flips rejected by cooldown
    max_trades_blocks: int                   # flips rejected by max_trades cap
    squareoff_exits: int                     # intraday mode only


@dataclass
class _PositionState:
    """Live position tracking mirroring ScalpSessionRuntime for a backtest bar loop."""

    side: str | None = None                  # "long" | "short" | None
    entry_price: float = 0.0
    entry_time: datetime | None = None
    trail_armed: bool = False
    highest_price: float = 0.0               # long: track highest; short unused
    lowest_price: float = float("inf")       # short: track lowest; long unused

    @property
    def is_long(self) -> bool:
        return self.side == "long"

    @property
    def is_short(self) -> bool:
        return self.side == "short"

    @property
    def is_flat(self) -> bool:
        return self.side is None


def _parse_candle_ts(ts: Any) -> datetime:
    """Normalize a candle timestamp (str or datetime) to aware UTC datetime."""
    if isinstance(ts, datetime):
        return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
    # Upstox returns "2026-04-15T09:15:00+05:30" — fromisoformat handles this.
    return datetime.fromisoformat(ts)


def _candles_to_frame(candles: list[dict]) -> list[dict]:
    """Ensure candles are dicts compatible with compute_indicator (needs
    timestamp/open/high/low/close/volume keys). Passes through if already OK."""
    normalized: list[dict] = []
    for c in candles:
        if isinstance(c, dict):
            normalized.append(c)
            continue
        # OHLCVData pydantic or bare tuple
        if hasattr(c, "timestamp"):
            normalized.append({
                "timestamp": c.timestamp,
                "open": c.open,
                "high": c.high,
                "low": c.low,
                "close": c.close,
                "volume": getattr(c, "volume", 0),
            })
        elif isinstance(c, (list, tuple)) and len(c) >= 6:
            normalized.append({
                "timestamp": c[0],
                "open": float(c[1]),
                "high": float(c[2]),
                "low": float(c[3]),
                "close": float(c[4]),
                "volume": int(c[5]),
            })
        else:
            raise ValueError(f"Unrecognised candle format: {type(c).__name__}")
    return normalized


def _bullish_direction_for_mode(mode: str) -> str | None:
    if mode == SessionMode.EQUITY_INTRADAY.value:
        return "long"
    if mode == SessionMode.EQUITY_SWING.value:
        return "long"
    return None


def _bearish_direction_for_mode(mode: str) -> str | None:
    # equity_swing is delivery-only; no shorting (SLBM not supported).
    if mode == SessionMode.EQUITY_INTRADAY.value:
        return "short"
    return None


def _confirm_agrees(
    cfg: ScalpSessionConfig, candles: list[dict], direction_sign: int
) -> tuple[bool, float | None]:
    """Mirror ScalpSessionManager._confirm_agrees. Returns (agrees, confirm_val).

    When no confirm is configured, returns (True, None). When configured but
    not ready (insufficient data), returns (False, None) — matches the live
    scalper's posture of skipping unconfirmed signals rather than firing.
    """
    if not cfg.confirm_indicator:
        return True, None
    val = compute_indicator(cfg.confirm_indicator, candles, cfg.confirm_params or {})
    if val is None:
        return False, None
    if direction_sign > 0 and val <= 0:
        return False, val
    if direction_sign < 0 and val >= 0:
        return False, val
    return True, val


def _parse_squareoff(ts_str: str) -> dtime:
    hour, minute = (int(p) for p in ts_str.split(":"))
    return dtime(hour=hour, minute=minute)


def run_scalp_equity_backtest(
    candles: list[dict],
    config: ScalpSessionConfig,
    *,
    symbol: str,
    interval: str,
    slippage_bps: float = 0.0,
) -> ScalpBacktestResult:
    """Run a scalp-style bar-replay backtest.

    Args:
        candles: list of candle dicts/tuples with OHLCV + timestamp. Order
            does not matter — will be sorted ascending by timestamp.
        config: a ScalpSessionConfig. Only session_mode in
            ``equity_intraday`` or ``equity_swing`` is supported; options
            modes raise ValueError.
        symbol: equity symbol for labelling trades. Typically the same as
            ``config.underlying``.
        interval: Upstox interval string (``1minute``..``day``). Must match
            ``config.indicator_timeframe`` per v1 contract.
        slippage_bps: optional slippage haircut applied to every fill in
            basis points (1 bp = 0.01%). Default 0.

    Returns:
        ScalpBacktestResult with trades + gross/net metrics + diagnostics.
    """
    # ── Validate inputs ────────────────────────────────────────────────
    mode = config.session_mode
    if mode not in (SessionMode.EQUITY_INTRADAY.value, SessionMode.EQUITY_SWING.value):
        raise ValueError(
            f"scalp equity backtest only supports equity_intraday and "
            f"equity_swing modes, got: {mode}"
        )
    if not config.quantity or config.quantity <= 0:
        raise ValueError("config.quantity must be > 0 for equity backtest")

    expected_tf = _INTERVAL_TO_TIMEFRAME.get(interval)
    if expected_tf is None:
        raise ValueError(f"unsupported interval: {interval}")
    if config.indicator_timeframe and config.indicator_timeframe != expected_tf:
        raise ValueError(
            f"indicator_timeframe {config.indicator_timeframe!r} does not match "
            f"interval {interval!r} (expected {expected_tf!r}). Resampling is "
            "not supported in v1 — fetch data at the indicator's native timeframe."
        )

    # ── Normalise candle data ──────────────────────────────────────────
    normalised = _candles_to_frame(candles)
    normalised.sort(key=lambda c: _parse_candle_ts(c["timestamp"]))
    if not normalised:
        return _empty_result(symbol, config, interval)

    is_intraday = mode == SessionMode.EQUITY_INTRADAY.value
    squareoff_cutoff = _parse_squareoff(config.squareoff_time) if is_intraday else None

    # ── Replay state ───────────────────────────────────────────────────
    sim = TradeSimulator(symbol)
    pos = _PositionState()
    quantity = int(config.quantity)

    prev_primary: float | None = None
    current_day: datetime.date | None = None
    trade_count: int = 0                           # resets at session boundary (intraday)
    last_exit_time: datetime | None = None

    intra_bar_ambiguity = 0
    primary_flips = 0
    confirm_blocks = 0
    cooldown_blocks = 0
    max_trades_blocks = 0
    squareoff_exits = 0
    slippage_total = 0.0

    session_days: set = set()

    # Slippage as multiplier on fill price (asymmetric by side applied at close time).
    slip_frac = slippage_bps / 10_000.0  # 1 bp = 0.0001

    for i, bar in enumerate(normalised):
        ts = _parse_candle_ts(bar["timestamp"])
        bar_date = ts.date()
        session_days.add(bar_date)

        # ── Session boundary (intraday only) ──────────────────────────
        if is_intraday and current_day is not None and bar_date != current_day:
            if not pos.is_flat:
                trade = _close(sim, pos, bar["open"], ts, "squareoff",
                               slip_frac, is_intraday)
                if trade:
                    _apply_costs(trade, is_intraday)
                squareoff_exits += 1
            trade_count = 0
            last_exit_time = None
        current_day = bar_date

        # ── Squareoff guard (intraday only) ───────────────────────────
        if is_intraday and squareoff_cutoff and not pos.is_flat:
            bar_tod = ts.timetz().replace(tzinfo=None)
            if bar_tod >= squareoff_cutoff:
                trade = _close(sim, pos, bar["open"], ts, "squareoff",
                               slip_frac, is_intraday)
                if trade:
                    _apply_costs(trade, is_intraday)
                squareoff_exits += 1
                last_exit_time = ts
                # Don't evaluate re-entry this bar — day is over.
                continue

        # ── Indicator evaluation ──────────────────────────────────────
        history = normalised[: i + 1]
        primary_val = compute_indicator(
            config.primary_indicator, history, config.primary_params or {}
        )

        if prev_primary is not None and primary_val is not None:
            bullish_flip = prev_primary <= 0 and primary_val > 0
            bearish_flip = prev_primary >= 0 and primary_val < 0
            if bullish_flip or bearish_flip:
                primary_flips += 1
        else:
            bullish_flip = bearish_flip = False

        # ── If HOLDING: check exits first ─────────────────────────────
        if not pos.is_flat:
            exit_info = _check_exits(pos, bar, config)
            if exit_info:
                exit_reason, exit_price, ambiguous = exit_info
                if ambiguous:
                    intra_bar_ambiguity += 1
                trade = _close(sim, pos, exit_price, ts, exit_reason,
                               slip_frac, is_intraday)
                if trade:
                    _apply_costs(trade, is_intraday)
                last_exit_time = ts
                # Count this flip-initiated exit toward trade_count so
                # max_trades limits effective round-trips per session.
                trade_count += 1
            else:
                # Reversal exit: adverse primary flip vs current side.
                if (pos.is_long and bearish_flip) or (pos.is_short and bullish_flip):
                    trade = _close(sim, pos, bar["close"], ts, "entry_opposite",
                                   slip_frac, is_intraday)
                    if trade:
                        _apply_costs(trade, is_intraday)
                    last_exit_time = ts
                    trade_count += 1

        # ── If IDLE: check entry on fresh flip + confirm + guards ─────
        if pos.is_flat and (bullish_flip or bearish_flip):
            direction_sign = 1 if bullish_flip else -1
            direction = (
                _bullish_direction_for_mode(mode) if bullish_flip
                else _bearish_direction_for_mode(mode)
            )
            if direction is None:
                # e.g. swing mode + bearish flip → no short allowed
                prev_primary = primary_val
                continue

            # Cooldown guard
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
            agrees, _ = _confirm_agrees(config, history, direction_sign)
            if not agrees:
                confirm_blocks += 1
                prev_primary = primary_val
                continue

            # Open at this bar's close with slippage. Slippage is paid by the
            # taker: long entry pays slippage upward, short entry pays downward.
            raw_entry = bar["close"]
            slip_adj = 1 + slip_frac if direction == "long" else 1 - slip_frac
            entry_price = raw_entry * slip_adj
            slippage_total += abs(raw_entry - entry_price) * quantity

            pos.side = direction
            pos.entry_price = entry_price
            pos.entry_time = ts
            pos.trail_armed = False
            pos.highest_price = entry_price
            pos.lowest_price = entry_price
            sim.open_position(direction, entry_price, ts, quantity)

        prev_primary = primary_val

    # Close any still-open position at the last bar for accounting completeness
    # (swing mode without an opposite flip, or an intraday session that ran out
    # of bars before squareoff cutoff).
    if not pos.is_flat:
        last_bar = normalised[-1]
        last_ts = _parse_candle_ts(last_bar["timestamp"])
        trade = _close(sim, pos, last_bar["close"], last_ts, "end_of_data",
                       slip_frac, is_intraday)
        if trade:
            _apply_costs(trade, is_intraday)

    # ── Metrics ────────────────────────────────────────────────────────
    trades = list(sim.trades)
    # Gross metrics: raw P&L (pre-cost) is already what Trade.pnl holds at
    # this point because _apply_costs stored the adjusted pnl on the trade
    # and we rescind it to derive gross below.
    gross_trades = [_reconstruct_gross(t) for t in trades]
    charges_total = round(sum(getattr(t, "_charges_total", 0.0) for t in trades), 2)
    slippage_total = round(slippage_total, 2)

    notional = config.quantity * (trades[0].entry_price if trades else 0) or 1
    metrics_gross = compute_metrics(gross_trades, initial_capital=notional)
    metrics_net = compute_metrics(trades, initial_capital=notional)

    return ScalpBacktestResult(
        symbol=symbol,
        session_mode=mode,
        interval=interval,
        days=len(session_days),
        config=config.model_dump(),
        candle_count=len(normalised),
        session_days=len(session_days),
        trades=trades,
        metrics=metrics_gross,
        metrics_net=metrics_net,
        charges_total=charges_total,
        slippage_total=slippage_total,
        intra_bar_ambiguity=intra_bar_ambiguity,
        primary_flips=primary_flips,
        confirm_blocks=confirm_blocks,
        cooldown_blocks=cooldown_blocks,
        max_trades_blocks=max_trades_blocks,
        squareoff_exits=squareoff_exits,
    )


# ──────────────────────────────────────────────────────────────────────
# Exit check — direction-aware
# ──────────────────────────────────────────────────────────────────────

def _check_exits(
    pos: _PositionState, bar: dict, cfg: ScalpSessionConfig
) -> tuple[str, float, bool] | None:
    """Check whether this bar triggers SL/target/trail for the current position.

    Returns (exit_reason, exit_price, ambiguous) if an exit fires, else None.
    ``ambiguous`` is True when both SL and target sit inside the bar's H/L
    range — v1 resolves that conservatively as SL-first.
    """
    high = float(bar["high"])
    low = float(bar["low"])

    # Trail ordering approximates tick behaviour from OHLC:
    #
    # 1. If the position armed on a PRIOR bar, use this bar's extreme to
    #    update highest/lowest first, then check the trail exit. This
    #    matches a live tick trail that rides up to the bar's high and
    #    only then exits on the pullback.
    #
    # 2. If the position arms on THIS bar, update state but don't check
    #    the trail exit on the same bar. Without this guard, a bar whose
    #    favourable extreme arms the trail and whose adverse extreme
    #    breaches the freshly-set level would exit immediately — even
    #    though in tick time the arm happens first, so no adverse tick
    #    can reach the trail level before it moves with price.

    trail_configured = cfg.trail_points is not None or cfg.trail_percent is not None

    if pos.is_long:
        sl_level = (pos.entry_price - cfg.sl_points) if cfg.sl_points else None
        tgt_level = (pos.entry_price + cfg.target_points) if cfg.target_points else None

        sl_hit = sl_level is not None and low <= sl_level
        tgt_hit = tgt_level is not None and high >= tgt_level
        ambiguous = sl_hit and tgt_hit

        if sl_hit:
            return ("sl", sl_level, ambiguous)

        armed_before_bar = pos.trail_armed

        # Conservative: check trail exit against the pre-update highest
        # (set on prior bars). This handles the unknown intra-bar order
        # — if the low came before this bar's high, the trail would have
        # used the prior highest anyway; if the high came first, the low
        # still breaches whatever level prior bars set. Either way, we
        # fire at the prior-bar trail level and don't mix in this bar's
        # high (which could make us exit too aggressively).
        if armed_before_bar:
            trail_level = _long_trail_level(pos, cfg)
            if trail_level is not None and low <= trail_level:
                return ("trailing", trail_level, False)
            if high > pos.highest_price:
                pos.highest_price = high

        if tgt_hit:
            return ("target", tgt_level, ambiguous)

        # First-time arm on this bar — update state, don't check exit.
        if trail_configured and not pos.trail_armed:
            arm_threshold = cfg.trail_arm_points or 0
            if high >= pos.entry_price + arm_threshold:
                pos.trail_armed = True
                if high > pos.highest_price:
                    pos.highest_price = high

    elif pos.is_short:
        sl_level = (pos.entry_price + cfg.sl_points) if cfg.sl_points else None
        tgt_level = (pos.entry_price - cfg.target_points) if cfg.target_points else None

        sl_hit = sl_level is not None and high >= sl_level
        tgt_hit = tgt_level is not None and low <= tgt_level
        ambiguous = sl_hit and tgt_hit

        if sl_hit:
            return ("sl", sl_level, ambiguous)

        armed_before_bar = pos.trail_armed

        if armed_before_bar:
            trail_level = _short_trail_level(pos, cfg)
            if trail_level is not None and high >= trail_level:
                return ("trailing", trail_level, False)
            if low < pos.lowest_price:
                pos.lowest_price = low

        if tgt_hit:
            return ("target", tgt_level, ambiguous)

        if trail_configured and not pos.trail_armed:
            arm_threshold = cfg.trail_arm_points or 0
            if low <= pos.entry_price - arm_threshold:
                pos.trail_armed = True
                if low < pos.lowest_price:
                    pos.lowest_price = low

    return None


def _long_trail_level(pos: _PositionState, cfg: ScalpSessionConfig) -> float | None:
    if cfg.trail_points is not None:
        return pos.highest_price - cfg.trail_points
    if cfg.trail_percent is not None:
        return pos.highest_price * (1 - cfg.trail_percent / 100)
    return None


def _short_trail_level(pos: _PositionState, cfg: ScalpSessionConfig) -> float | None:
    if cfg.trail_points is not None:
        return pos.lowest_price + cfg.trail_points
    if cfg.trail_percent is not None:
        return pos.lowest_price * (1 + cfg.trail_percent / 100)
    return None


# ──────────────────────────────────────────────────────────────────────
# Close helper — applies slippage on exit, delegates to simulator
# ──────────────────────────────────────────────────────────────────────

def _close(
    sim: TradeSimulator,
    pos: _PositionState,
    raw_price: float,
    ts: datetime,
    reason: str,
    slip_frac: float,
    is_intraday: bool,
) -> Trade | None:
    """Close the current position with slippage, reset _PositionState, return Trade."""
    # Slippage paid by taker: long sells down, short buys up.
    if pos.is_long:
        exit_price = raw_price * (1 - slip_frac)
    elif pos.is_short:
        exit_price = raw_price * (1 + slip_frac)
    else:
        return None
    trade = sim.close_position(exit_price, ts, reason)
    pos.side = None
    pos.entry_price = 0.0
    pos.entry_time = None
    pos.trail_armed = False
    pos.highest_price = 0.0
    pos.lowest_price = float("inf")
    return trade


def _apply_costs(trade: Trade, is_intraday: bool) -> None:
    """Deduct round-trip charges from the trade's pnl, in place.

    Stashes the gross pnl and charges total as private attributes on the
    dataclass so callers can reconstruct gross metrics after the fact.
    """
    charges = _estimate_round_trip_charges(
        trade.entry_price, trade.exit_price, trade.quantity, is_intraday
    )
    # Store gross so we can reconstruct later.
    trade._gross_pnl = trade.pnl  # type: ignore[attr-defined]
    trade._charges_total = charges["total"]  # type: ignore[attr-defined]
    trade.pnl = round(trade.pnl - charges["total"], 2)
    if trade.entry_price and trade.quantity:
        trade.pnl_pct = round(
            (trade.pnl / (trade.entry_price * trade.quantity)) * 100, 2
        )


def _reconstruct_gross(trade: Trade) -> Trade:
    """Return a shallow copy of ``trade`` with pnl reset to pre-cost value."""
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
    symbol: str, config: ScalpSessionConfig, interval: str
) -> ScalpBacktestResult:
    empty = compute_metrics([], initial_capital=1)
    return ScalpBacktestResult(
        symbol=symbol,
        session_mode=config.session_mode,
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
    )
