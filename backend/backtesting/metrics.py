"""Compute backtest performance metrics from a list of completed trades."""
from __future__ import annotations

import math
from backtesting.simulator import Trade

# Exit reasons that are time-driven rather than signal-driven (shared by both
# the rule-based engine and the scalp state machine).
_TIME_EXIT_REASONS = {"squareoff", "end_of_data"}


def plausibility_warnings(trades: list[Trade], metrics: dict) -> list[str]:
    """Heuristic red flags for backtest results that look too good — or too
    mechanical — to be real.

    Returned strings are emitted verbatim next to the metrics (human and
    JSON output) so artifact-driven results can't be quoted as edge without
    the warning travelling with them. Origin: the 2026-06-09 mean-reversion
    day-open SL bug reported 100% WR / PF=inf with a straight face and the
    EOD reflection pivoted strategy allocation on it.
    """
    warnings: list[str] = []
    total = metrics.get("total_trades", 0)
    if not total:
        return warnings

    if metrics.get("profit_factor") in ("inf", float("inf")):
        warnings.append(
            "PF=inf: zero gross loss across all trades — almost always a "
            "simulation artifact (misplaced stop, phantom fill), not an "
            "edge. Inspect individual exit prices before trusting."
        )

    if total < 10:
        warnings.append(
            f"n={total} trades: sample too small to establish an edge — "
            "treat as anecdote, not statistics."
        )

    if total >= 5 and metrics.get("win_rate", 0) >= 90:
        warnings.append(
            f"win_rate={metrics['win_rate']}%: ≥90% win rates in backtests "
            "have historically been fill-model or stop-anchoring artifacts. "
            "Verify losing trades are actually possible before acting."
        )

    time_exits = sum(1 for t in trades if t.exit_reason in _TIME_EXIT_REASONS)
    if total >= 4 and time_exits / total > 0.5:
        pct = round(100 * time_exits / total)
        warnings.append(
            f"{pct}% of exits are time-based (squareoff/end_of_data), not "
            "signal exits — P&L may be directional drift capture in this "
            "window, not repeatable strategy edge."
        )

    zero_dur = sum(1 for t in trades if t.holding_minutes == 0)
    if zero_dur:
        warnings.append(
            f"{zero_dur} zero-duration trade(s) (entry and exit on the same "
            "bar) — possible same-bar fill artifact; inspect those trades."
        )

    winners = [t for t in trades if t.pnl > 0]
    if len(winners) >= 5:
        holds = {t.holding_minutes for t in winners}
        if len(holds) == 1:
            warnings.append(
                f"every winner exits after exactly {holds.pop()} min — "
                "mechanical exit pattern; check whether a stop/target sits "
                "on the wrong side of the entry fill."
            )

    return warnings


def compute_metrics(trades: list[Trade], initial_capital: float) -> dict:
    """Compute backtest performance metrics.

    Args:
        trades: List of completed Trade objects.
        initial_capital: Starting capital for return calculation.

    Returns:
        Dict of performance metrics.
    """
    if not trades:
        return {
            "total_trades": 0,
            "winners": 0,
            "losers": 0,
            "win_rate": 0.0,
            "avg_winner": 0.0,
            "avg_loser": 0.0,
            "profit_factor": 0.0,
            "max_drawdown_pct": 0.0,
            "net_pnl": 0.0,
            "return_pct": 0.0,
            "sharpe_ratio": 0.0,
            "max_consecutive_losses": 0,
            "avg_holding_minutes": 0.0,
            "best_trade": 0.0,
            "worst_trade": 0.0,
            "expectancy": 0.0,
        }

    winners = [t for t in trades if t.pnl > 0]
    losers = [t for t in trades if t.pnl < 0]
    # Break-even trades (pnl == 0) are neither — counting them as losers gave
    # them 0 gross loss and pushed profit_factor to inf on otherwise all-win runs.
    total = len(trades)

    win_rate = (len(winners) / total) * 100 if total else 0.0
    avg_winner = sum(t.pnl for t in winners) / len(winners) if winners else 0.0
    avg_loser = sum(t.pnl for t in losers) / len(losers) if losers else 0.0

    gross_profit = sum(t.pnl for t in winners)
    gross_loss = abs(sum(t.pnl for t in losers))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf") if gross_profit > 0 else 0.0

    net_pnl = sum(t.pnl for t in trades)
    return_pct = (net_pnl / initial_capital) * 100 if initial_capital else 0.0

    # Max drawdown (peak-to-trough on equity curve)
    equity = initial_capital
    peak = equity
    max_dd = 0.0
    for t in trades:
        equity += t.pnl
        if equity > peak:
            peak = equity
        dd = (peak - equity) / peak if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd

    # Sharpe ratio (annualized, assume 252 trading days)
    pnl_list = [t.pnl for t in trades]
    if len(pnl_list) >= 2:
        mean_pnl = sum(pnl_list) / len(pnl_list)
        variance = sum((p - mean_pnl) ** 2 for p in pnl_list) / (len(pnl_list) - 1)
        std_pnl = math.sqrt(variance) if variance > 0 else 0.0
        sharpe = (mean_pnl / std_pnl) * math.sqrt(252) if std_pnl > 0 else 0.0
    else:
        sharpe = 0.0

    # Max consecutive losses
    max_consec = 0
    current_consec = 0
    for t in trades:
        if t.pnl < 0:
            current_consec += 1
            max_consec = max(max_consec, current_consec)
        else:
            current_consec = 0

    avg_holding = sum(t.holding_minutes for t in trades) / total if total else 0.0
    best = max(t.pnl for t in trades)
    worst = min(t.pnl for t in trades)

    # Expectancy: (win_rate% * avg_winner) - ((100-win_rate)% * |avg_loser|)
    wr = win_rate / 100
    expectancy = (wr * avg_winner) - ((1 - wr) * abs(avg_loser))

    return {
        "total_trades": total,
        "winners": len(winners),
        "losers": len(losers),
        "win_rate": round(win_rate, 1),
        "avg_winner": round(avg_winner, 2),
        "avg_loser": round(avg_loser, 2),
        "profit_factor": round(profit_factor, 2) if profit_factor != float("inf") else "inf",
        "max_drawdown_pct": round(max_dd * 100, 1),
        "net_pnl": round(net_pnl, 2),
        "return_pct": round(return_pct, 1),
        "sharpe_ratio": round(sharpe, 2),
        "max_consecutive_losses": max_consec,
        "avg_holding_minutes": round(avg_holding, 1),
        "best_trade": round(best, 2),
        "worst_trade": round(worst, 2),
        "expectancy": round(expectancy, 2),
    }
