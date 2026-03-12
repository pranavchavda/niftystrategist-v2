"""F&O multi-leg backtest engine.

Purpose-built for options strategies (straddle, strangle, spreads, iron condor).
Each leg is tracked independently with its own candle stream and position state.
Charges are computed per-leg using F&O-specific rates.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from backtesting.engine import BacktestEngine
from backtesting.simulator import Trade
from strategies.fno_utils import estimate_leg_charges
from strategies.templates import RuleSpec

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class LegTrade:
    """A completed trade on a single option leg."""
    instrument_key: str
    label: str  # e.g. "NIFTY 25000 CE"
    side: str  # "BUY" or "SELL"
    quantity: int
    entry_price: float
    exit_price: float
    entry_time: datetime
    exit_time: datetime
    exit_reason: str
    gross_pnl: float
    charges: dict[str, float]
    net_pnl: float
    holding_minutes: int


@dataclass
class FnODayResult:
    """Result for one day of F&O backtesting."""
    date: str
    leg_trades: list[LegTrade]
    gross_pnl: float
    total_charges: float
    net_pnl: float


@dataclass
class FnOBacktestResult:
    """Aggregated F&O backtest result across multiple days."""
    strategy: str
    underlying: str
    days_traded: int
    day_results: list[FnODayResult]
    all_leg_trades: list[LegTrade]
    metrics: dict[str, Any]
    equity_curve: list[float]
    initial_capital: float
    total_charges: float


# ---------------------------------------------------------------------------
# Per-leg engine (wraps BacktestEngine for one instrument)
# ---------------------------------------------------------------------------

def _set_day_sl_prices(rules: list[RuleSpec], day_candles: list[dict]) -> None:
    """Set SL trigger prices from the day's first candle (entry premium proxy).

    For rules with price=0 and condition gte/lte, derive SL from entry premium.
    """
    if not day_candles:
        return
    entry_premium = day_candles[0]["open"]
    for r in rules:
        if r.trigger_type != "price":
            continue
        tc = r.trigger_config
        if tc.get("price", 0) == 0:
            note = tc.get("note", "")
            # Parse the multiplier from the note if available
            # e.g. "Set to entry_premium * 1.30 at deployment"
            import re
            m = re.search(r"entry_premium \* ([\d.]+)", note)
            if m:
                multiplier = float(m.group(1))
            else:
                multiplier = 1.30  # default 30% SL
            tc["price"] = round(entry_premium * multiplier, 2)


def _run_leg_backtest(
    candles: list[dict],
    rules: list[RuleSpec],
    instrument_key: str,
    label: str,
) -> list[LegTrade]:
    """Run backtest on a single option leg and return LegTrades with charges."""
    if not candles or not rules:
        return []

    engine = BacktestEngine(
        candles=candles,
        rules=rules,
        symbol=label,
        strategy_name="fno_leg",
        initial_capital=0,  # not used for leg-level
    )
    # Disable exit rules initially (wait for entry)
    for rs in engine._rules:
        if rs.is_exit:
            rs.enabled = False

    result = engine.run()
    leg_trades = []
    for t in result.trades:
        side = "SELL" if t.side == "short" else "BUY"
        exit_side = "BUY" if side == "SELL" else "SELL"

        entry_charges = estimate_leg_charges(t.entry_price, t.quantity, side)
        exit_charges = estimate_leg_charges(t.exit_price, t.quantity, exit_side)
        total_charges = {
            k: round(entry_charges[k] + exit_charges[k], 2)
            for k in entry_charges
        }

        leg_trades.append(LegTrade(
            instrument_key=instrument_key,
            label=label,
            side=side,
            quantity=t.quantity,
            entry_price=t.entry_price,
            exit_price=t.exit_price,
            entry_time=t.entry_time,
            exit_time=t.exit_time,
            exit_reason=t.exit_reason,
            gross_pnl=t.pnl,
            charges=total_charges,
            net_pnl=round(t.pnl - total_charges["total"], 2),
            holding_minutes=t.holding_minutes,
        ))
    return leg_trades


# ---------------------------------------------------------------------------
# Main F&O backtest function
# ---------------------------------------------------------------------------

def run_fno_backtest(
    leg_candles: dict[str, list[dict]],
    rules: list[RuleSpec],
    strategy_name: str,
    underlying: str,
    initial_capital: float,
) -> FnOBacktestResult:
    """Run multi-leg F&O backtest across multiple days.

    Args:
        leg_candles: {instrument_key: [candle_dicts]} for each option leg.
        rules: All RuleSpecs from the strategy template.
        strategy_name: e.g. "straddle", "iron-condor".
        underlying: e.g. "NIFTY", "BANKNIFTY".
        initial_capital: Starting capital for metrics.

    Returns:
        FnOBacktestResult with per-day breakdown and aggregate metrics.
    """
    # Group rules by their instrument_key
    rules_by_inst: dict[str, list[RuleSpec]] = defaultdict(list)
    label_by_inst: dict[str, str] = {}
    for r in rules:
        inst_key = r.action_config.get("instrument_token", "")
        if not inst_key:
            logger.warning(f"Rule '{r.name}' has no instrument_token, skipping")
            continue
        rules_by_inst[inst_key].append(r)
        # Build a human-readable label from the rule name
        if inst_key not in label_by_inst:
            label_by_inst[inst_key] = r.name.split(" ")[-1] if r.name else inst_key

    instruments = set(rules_by_inst.keys()) & set(leg_candles.keys())
    if not instruments:
        logger.error("No matching instruments between rules and candle data")
        return _empty_result(strategy_name, underlying, initial_capital)

    # Split candles by day for each instrument
    day_candles_by_inst: dict[str, dict[str, list[dict]]] = {}
    all_days: set[str] = set()
    for inst_key in instruments:
        by_day: dict[str, list[dict]] = defaultdict(list)
        for c in leg_candles[inst_key]:
            ts = BacktestEngine._parse_timestamp(c["timestamp"])
            day_key = ts.strftime("%Y-%m-%d")
            by_day[day_key].append(c)
            all_days.add(day_key)
        day_candles_by_inst[inst_key] = dict(by_day)

    # Run per-day
    day_results: list[FnODayResult] = []
    all_leg_trades: list[LegTrade] = []

    for day_key in sorted(all_days):
        day_legs: list[LegTrade] = []

        for inst_key in instruments:
            day_c = day_candles_by_inst.get(inst_key, {}).get(day_key, [])
            if len(day_c) < 2:
                continue

            # Deep-copy rules for this day so SL prices are independent
            import copy
            inst_rules = copy.deepcopy(rules_by_inst[inst_key])

            # Set per-day SL prices from the day's first candle
            _set_day_sl_prices(inst_rules, day_c)

            label = label_by_inst.get(inst_key, inst_key)
            trades = _run_leg_backtest(day_c, inst_rules, inst_key, label)
            day_legs.extend(trades)

        if day_legs:
            gross = sum(lt.gross_pnl for lt in day_legs)
            charges = sum(lt.charges["total"] for lt in day_legs)
            net = sum(lt.net_pnl for lt in day_legs)
            day_results.append(FnODayResult(
                date=day_key,
                leg_trades=day_legs,
                gross_pnl=round(gross, 2),
                total_charges=round(charges, 2),
                net_pnl=round(net, 2),
            ))
            all_leg_trades.extend(day_legs)

    # Compute aggregate metrics
    metrics = _compute_fno_metrics(day_results, initial_capital)

    # Equity curve (by day net P&L)
    equity_curve = [initial_capital]
    for dr in day_results:
        equity_curve.append(round(equity_curve[-1] + dr.net_pnl, 2))

    total_charges = sum(dr.total_charges for dr in day_results)

    return FnOBacktestResult(
        strategy=strategy_name,
        underlying=underlying,
        days_traded=len(day_results),
        day_results=day_results,
        all_leg_trades=all_leg_trades,
        metrics=metrics,
        equity_curve=equity_curve,
        initial_capital=initial_capital,
        total_charges=round(total_charges, 2),
    )


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def _compute_fno_metrics(
    day_results: list[FnODayResult], initial_capital: float
) -> dict[str, Any]:
    """Compute aggregate metrics across F&O backtest days."""
    if not day_results:
        return _zero_metrics()

    day_pnls = [d.net_pnl for d in day_results]
    total_days = len(day_results)
    winning_days = sum(1 for p in day_pnls if p > 0)
    losing_days = sum(1 for p in day_pnls if p <= 0)

    gross_profit = sum(p for p in day_pnls if p > 0)
    gross_loss = abs(sum(p for p in day_pnls if p <= 0))
    net_pnl = sum(day_pnls)
    return_pct = (net_pnl / initial_capital) * 100 if initial_capital else 0

    profit_factor = (
        gross_profit / gross_loss if gross_loss > 0
        else float("inf") if gross_profit > 0
        else 0.0
    )

    # Max drawdown
    equity = initial_capital
    peak = equity
    max_dd = 0.0
    for p in day_pnls:
        equity += p
        if equity > peak:
            peak = equity
        dd = (peak - equity) / peak if peak > 0 else 0
        max_dd = max(max_dd, dd)

    # Sharpe (annualized, 252 trading days)
    import math
    if len(day_pnls) >= 2:
        mean = sum(day_pnls) / len(day_pnls)
        var = sum((p - mean) ** 2 for p in day_pnls) / (len(day_pnls) - 1)
        std = math.sqrt(var) if var > 0 else 0
        sharpe = (mean / std) * math.sqrt(252) if std > 0 else 0
    else:
        sharpe = 0.0

    # Total legs traded
    total_legs = sum(len(d.leg_trades) for d in day_results)
    total_charges = sum(d.total_charges for d in day_results)

    avg_day_pnl = net_pnl / total_days if total_days else 0
    best_day = max(day_pnls)
    worst_day = min(day_pnls)

    return {
        "total_days": total_days,
        "winning_days": winning_days,
        "losing_days": losing_days,
        "win_rate": round((winning_days / total_days) * 100, 1),
        "net_pnl": round(net_pnl, 2),
        "gross_pnl": round(net_pnl + total_charges, 2),
        "total_charges": round(total_charges, 2),
        "return_pct": round(return_pct, 2),
        "profit_factor": round(profit_factor, 2) if profit_factor != float("inf") else "inf",
        "max_drawdown_pct": round(max_dd * 100, 2),
        "sharpe_ratio": round(sharpe, 2),
        "avg_day_pnl": round(avg_day_pnl, 2),
        "best_day": round(best_day, 2),
        "worst_day": round(worst_day, 2),
        "total_legs_traded": total_legs,
    }


def _zero_metrics() -> dict[str, Any]:
    return {
        "total_days": 0, "winning_days": 0, "losing_days": 0,
        "win_rate": 0.0, "net_pnl": 0.0, "gross_pnl": 0.0,
        "total_charges": 0.0, "return_pct": 0.0, "profit_factor": 0.0,
        "max_drawdown_pct": 0.0, "sharpe_ratio": 0.0,
        "avg_day_pnl": 0.0, "best_day": 0.0, "worst_day": 0.0,
        "total_legs_traded": 0,
    }


def _empty_result(
    strategy: str, underlying: str, capital: float
) -> FnOBacktestResult:
    return FnOBacktestResult(
        strategy=strategy, underlying=underlying,
        days_traded=0, day_results=[], all_leg_trades=[],
        metrics=_zero_metrics(), equity_curve=[capital],
        initial_capital=capital, total_charges=0.0,
    )
