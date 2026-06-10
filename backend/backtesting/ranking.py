"""Statistically-rigorous ranking for backtest combos — the "best" definition.

A backtest sweep over a grid of (symbol × indicator × confirm × exit-variant ×
side) combos produces hundreds of result rows. Sorting them by raw profit-factor
or net P&L is a *multiple-comparisons trap*: with enough combos, some win by luck
alone, and the loudest winners are usually fill-model or stop-anchoring artifacts
(see ``plausibility_warnings``). This module defines "best" in three defensible
layers so a deployment plan surfaces edges that have a chance of surviving live:

  Layer 1 — HARD GATES (``apply_gates``). Cheap disqualifiers run first: too few
            trades, plausibility red flags, single-trade dominance, an unsurvivable
            daily drawdown the live daemon would have force-squared-off, or a
            non-positive net. A combo that fails any gate is OUT regardless of how
            pretty its score is — gates kill PF=inf flukes before they're ranked.

  Layer 2 — SCORE (``tstat`` / ``day_consistency`` / ``combo_score``). The primary
            key is the t-statistic of the per-trade NET P&L series — mean/std×√n —
            which rewards a stable edge over a couple of lucky outliers. Day
            consistency (fraction of profitable trading days, median day P&L) is
            reported ALONGSIDE, never collapsed into one opaque number, so a human
            can see *why* a combo scored where it did.

  Layer 3 — WALK-FORWARD (``split_trades`` / ``validate_combo`` / ``confidence_label``).
            The grid is selected on the TRAIN slice; confirmation requires the
            held-out VALIDATE slice to be net-positive AND keep the same sign of
            mean P&L. This is the only honest defence against in-sample
            best-in-hindsight optimism — the figure quoted to the trader is the
            out-of-sample one.

Plus a grid-level ``plateau_flags`` that warns when a winner is a lone spike on a
parameter axis (its neighbours are net-negative) — a robust edge sits on a plateau,
not a spike.

PURE module: no I/O, no network, stdlib ``statistics``/``math`` only. Every
function operates on per-trade NET P&L — which is exactly what ``Trade.pnl`` holds
on a ``ScalpBacktestResult.trades`` list (``_apply_costs`` mutates ``trade.pnl`` in
place to subtract charges, and slippage is already baked into the fill prices). No
gross/net reconstruction is needed here.

profit_factor handling: ``compute_metrics`` serializes an infinite PF as the
string ``"inf"`` — every helper that touches it goes through ``_pf_to_float``.
"""
from __future__ import annotations

import math
import statistics
from datetime import date, datetime
from typing import Any, Iterable

from backtesting.metrics import plausibility_warnings
from backtesting.simulator import Trade


# ---------------------------------------------------------------------------
# profit_factor helper ("inf" is a valid serialized value from compute_metrics)
# ---------------------------------------------------------------------------

def _pf_to_float(pf: Any) -> float:
    """Coerce a profit_factor (number or the string "inf") to a sortable float."""
    if pf == "inf" or pf == float("inf"):
        return float("inf")
    try:
        return float(pf)
    except (TypeError, ValueError):
        return 0.0


# ---------------------------------------------------------------------------
# Small internals
# ---------------------------------------------------------------------------

def _pnls(trades: Iterable[Trade]) -> list[float]:
    """Per-trade NET P&L series (Trade.pnl is already net of charges+slippage)."""
    return [float(t.pnl) for t in trades]


def _trade_date(t: Trade) -> date:
    """The calendar date a trade was opened on (its entry_time date).

    entry_time may be an aware datetime (IST) or naive — ``.date()`` is correct
    either way for grouping, since we never compare dates across timezones here.
    """
    et = t.entry_time
    if isinstance(et, datetime):
        return et.date()
    # Defensive: accept a bare date too.
    return et  # type: ignore[return-value]


def _group_by_day(trades: Iterable[Trade]) -> dict[date, list[Trade]]:
    out: dict[date, list[Trade]] = {}
    for t in trades:
        out.setdefault(_trade_date(t), []).append(t)
    return out


# ---------------------------------------------------------------------------
# Layer 2a — t-statistic
# ---------------------------------------------------------------------------

def tstat(pnls: list[float]) -> float:
    """One-sample t-statistic of a per-trade P&L series against a zero mean.

    ``mean / std(ddof=1) × sqrt(n)`` — the standard signal-to-noise ratio for
    "is this mean reliably non-zero". Higher = a more reliable edge per trade;
    it down-weights series whose positive mean rides on one or two outliers
    (those inflate std). This is the PRIMARY ranking key.

    Returns 0.0 for n<2 (no dispersion estimate) or std==0 (degenerate — every
    trade identical, which is itself an artifact better caught by the gates).
    """
    n = len(pnls)
    if n < 2:
        return 0.0
    mean = statistics.fmean(pnls)
    std = statistics.stdev(pnls)  # ddof=1
    if std == 0:
        return 0.0
    return (mean / std) * math.sqrt(n)


# ---------------------------------------------------------------------------
# Layer 2b — day consistency
# ---------------------------------------------------------------------------

def day_consistency(trades: list[Trade]) -> dict:
    """Per-trading-day consistency of a combo's NET P&L.

    A combo that nets ₹X off one monster day and bleeds the rest is far more
    fragile than one that nets ₹X/3 across three positive days. We surface:

      profitable_day_fraction — share of distinct trading days that netted > 0
      median_day_pnl          — median of daily-summed net P&L (robust to one big day)
      n_days                  — distinct trading days present

    Reported alongside tstat, never folded into it.
    """
    if not trades:
        return {"profitable_day_fraction": 0.0, "median_day_pnl": 0.0, "n_days": 0}
    by_day = _group_by_day(trades)
    day_pnls = [sum(t.pnl for t in day_trades) for day_trades in by_day.values()]
    n_days = len(day_pnls)
    profitable_days = sum(1 for p in day_pnls if p > 0)
    return {
        "profitable_day_fraction": round(profitable_days / n_days, 4),
        "median_day_pnl": round(statistics.median(day_pnls), 2),
        "n_days": n_days,
    }


# ---------------------------------------------------------------------------
# Layer 2c — combined score (components kept separate, NOT collapsed)
# ---------------------------------------------------------------------------

def combo_score(trades: list[Trade]) -> dict:
    """Score one combo. Primary sort key = ``tstat``; day-consistency reported
    alongside so the ranking is interpretable, not an opaque number.

    Returns a dict with:
      tstat                   — primary ranking key (per-trade signal-to-noise)
      n_trades                — sample size behind the tstat
      net_pnl                 — total net P&L over the trades
      expectancy_per_trade    — mean per-trade net P&L
      profitable_day_fraction / median_day_pnl / n_days — from day_consistency
    """
    pnls = _pnls(trades)
    dc = day_consistency(trades)
    net = round(sum(pnls), 2)
    n = len(pnls)
    return {
        "tstat": round(tstat(pnls), 4),
        "n_trades": n,
        "net_pnl": net,
        "expectancy_per_trade": round(net / n, 2) if n else 0.0,
        "profitable_day_fraction": dc["profitable_day_fraction"],
        "median_day_pnl": dc["median_day_pnl"],
        "n_days": dc["n_days"],
    }


# ---------------------------------------------------------------------------
# Layer 1 — hard gates
# ---------------------------------------------------------------------------

def apply_gates(
    trades: list[Trade],
    metrics_net: dict,
    *,
    min_trades: int = 10,
    max_single_trade_share: float = 0.5,
    daily_loss_cap: float | None = None,
) -> list[str]:
    """Hard disqualifiers. Returns a list of failure reasons — EMPTY means the
    combo passes every gate. A non-empty list means it's out, with the reasons
    attached so a deployment plan can show *why* it was dropped.

    Gates (each independent):

    * ``min_trades`` — fewer trades than this → out. Doubles as the PF=inf-fluke
      killer: a 2-trade all-winner run can't clear a 10-trade floor.
    * plausibility — any string from ``plausibility_warnings`` → out (verbatim).
      These flag the fill-model / stop-anchoring artifacts (PF=inf, ≥90% WR,
      mechanical identical holds, etc.) that look like edge but aren't.
    * single-trade dominance — if the single best trade's pnl exceeds
      ``max_single_trade_share`` × gross profit (sum of winners), the "edge" is
      really one lucky print → out.
    * ``daily_loss_cap`` (if given) — if ANY single trading day's summed net P&L
      is worse than ``-daily_loss_cap``, the live daemon would have force-squared
      the book off at the cap; the backtest's deeper-hole-then-recovery curve is
      *unreachable* live, so the result is fictional → out.
    * net_pnl ≤ 0 — a losing or flat combo is never "best" → out.
    """
    reasons: list[str] = []

    n = len(trades)
    if n < min_trades:
        reasons.append(
            f"only {n} trades (< {min_trades} min) — sample too small; "
            "also kills PF=inf flukes"
        )

    # Plausibility red flags travel with the combo so a too-good signal can't
    # pass selection without its warning attached.
    for w in plausibility_warnings(trades, metrics_net):
        reasons.append(f"plausibility: {w}")

    # Single-trade dominance: best winner vs total gross profit.
    pnls = _pnls(trades)
    gross_profit = sum(p for p in pnls if p > 0)
    if pnls:
        best = max(pnls)
        if best > 0 and gross_profit > 0 and best > max_single_trade_share * gross_profit:
            share = best / gross_profit
            reasons.append(
                f"single-trade dominance: best trade is {round(share * 100)}% of "
                f"gross profit (> {round(max_single_trade_share * 100)}%) — edge "
                "rides on one print"
            )

    # Daily loss cap: a day the live force-squareoff would have truncated.
    if daily_loss_cap is not None:
        for d, day_trades in _group_by_day(trades).items():
            day_pnl = sum(t.pnl for t in day_trades)
            if day_pnl < -abs(daily_loss_cap):
                reasons.append(
                    f"daily loss cap breached on {d.isoformat()}: net "
                    f"₹{day_pnl:,.0f} worse than -₹{abs(daily_loss_cap):,.0f} — "
                    "live daemon would have force-squared off; curve unreachable"
                )
                break  # one breach is enough to disqualify

    # Non-positive net.
    net_pnl = metrics_net.get("net_pnl")
    if net_pnl is None:
        net_pnl = sum(pnls)
    if net_pnl <= 0:
        reasons.append(f"net P&L ₹{net_pnl:,.2f} ≤ 0 — not profitable")

    return reasons


# ---------------------------------------------------------------------------
# Gate-reason categorization (for sweep-level summaries)
# ---------------------------------------------------------------------------

# Map a verbose gate-failure reason (which embeds per-combo numbers — trade
# counts, rupee amounts, dates) to a stable category key, so a sweep can report
# "13 combos failed the net-P&L gate" instead of 13 unique strings. Prefixes
# match the exact strings ``apply_gates`` emits — keep in sync if those change.
_GATE_REASON_PREFIXES = [
    ("only ", "min_trades"),
    ("plausibility:", "plausibility"),
    ("single-trade dominance", "single_trade_dominance"),
    ("daily loss cap breached", "daily_loss_cap"),
    ("net P&L", "net_pnl<=0"),
]


def categorize_gate_reason(reason: str) -> str:
    """Collapse one ``apply_gates`` failure reason to its category key.

    Categories: ``min_trades``, ``plausibility``, ``single_trade_dominance``,
    ``daily_loss_cap``, ``net_pnl<=0`` — with ``other`` as a forward-compat
    fallback for reasons added later without a prefix entry here.
    """
    for prefix, category in _GATE_REASON_PREFIXES:
        if reason.startswith(prefix):
            return category
    return "other"


def gate_summary(reason_lists: Iterable[list[str]]) -> dict[str, int]:
    """Counter of gate-reason categories across many combos' gate_reasons.

    Takes an iterable of per-combo reason lists (one list per gated combo) and
    returns ``{category: count}`` sorted most-frequent-first (ties by name) —
    the per-symbol "why did everything gate out" digest. A combo failing two
    gates counts once in each category: the question this answers is "which
    gates are doing the killing", not "how many combos died".
    """
    counts: dict[str, int] = {}
    for reasons in reason_lists:
        for r in reasons:
            cat = categorize_gate_reason(r)
            counts[cat] = counts.get(cat, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))


# ---------------------------------------------------------------------------
# Layer 3 — walk-forward split + validation
# ---------------------------------------------------------------------------

def split_trades(
    trades: list[Trade], split_date: date
) -> tuple[list[Trade], list[Trade]]:
    """Partition trades by entry date into (train, validate).

    A trade opened *before* ``split_date`` goes to TRAIN; on or after → VALIDATE.
    Partitioning by date (not trade index) keeps whole trading days on one side,
    so an in-day sequence is never split across the boundary.
    """
    train: list[Trade] = []
    validate: list[Trade] = []
    for t in trades:
        if _trade_date(t) < split_date:
            train.append(t)
        else:
            validate.append(t)
    return train, validate


def _side_stats(trades: list[Trade]) -> dict:
    """net_pnl, n_trades, tstat, expectancy_per_day for one slice."""
    pnls = _pnls(trades)
    net = round(sum(pnls), 2)
    by_day = _group_by_day(trades)
    n_days = len(by_day)
    return {
        "net_pnl": net,
        "n_trades": len(pnls),
        "tstat": round(tstat(pnls), 4),
        "expectancy_per_day": round(net / n_days, 2) if n_days else 0.0,
        "n_days": n_days,
    }


def validate_combo(train_trades: list[Trade], validate_trades: list[Trade]) -> dict:
    """Walk-forward confirmation. The combo was SELECTED on ``train_trades``;
    we confirm it holds out-of-sample on ``validate_trades``.

    Confirmation requires BOTH:
      * validation net P&L > 0 (the held-out slice actually made money), AND
      * sign(mean validate P&L) == sign(mean train P&L) (the edge points the same
        way out of sample — a sign flip means we'd have traded it backwards).

    Returns ``{confirmed: bool, train: {...}, validation: {...}}`` where each side
    carries net_pnl, n_trades, tstat, expectancy_per_day, n_days.
    """
    train = _side_stats(train_trades)
    validation = _side_stats(validate_trades)

    train_pnls = _pnls(train_trades)
    val_pnls = _pnls(validate_trades)
    train_mean = statistics.fmean(train_pnls) if train_pnls else 0.0
    val_mean = statistics.fmean(val_pnls) if val_pnls else 0.0

    same_sign = (train_mean > 0 and val_mean > 0) or (train_mean < 0 and val_mean < 0)
    confirmed = bool(validation["net_pnl"] > 0 and same_sign)

    return {"confirmed": confirmed, "train": train, "validation": validation}


def confidence_label(validation_tstat: float, n_validate_trades: int) -> str:
    """Map out-of-sample evidence strength to a coarse confidence band.

    Thresholds (deliberately conservative — these are the numbers a trader sees):
      high   — validation tstat ≥ 2.0 AND ≥ 8 validation trades
               (a reliable per-trade edge on an adequate held-out sample)
      medium — validation tstat ≥ 1.0 (a directional edge, thinner evidence)
      low    — anything weaker (treat as anecdote)
    """
    if validation_tstat >= 2.0 and n_validate_trades >= 8:
        return "high"
    if validation_tstat >= 1.0:
        return "medium"
    return "low"


# ---------------------------------------------------------------------------
# Grid-level — plateau check (operates across rows, not one combo)
# ---------------------------------------------------------------------------

def plateau_flags(rows: list[dict], axis_keys: list[str]) -> None:
    """Annotate grid rows with a ``plateau_warning`` when a net-positive winner is
    a lone SPIKE on a parameter axis rather than sitting on a robust PLATEAU.

    A real edge degrades gracefully as you nudge a parameter: trail 0.8/1.0/1.2
    should all be roughly profitable if 1.0 is. If 1.0 nets +₹5,000 but its
    immediate neighbours on that axis (same everything else) are net-NEGATIVE,
    1.0 is an overfit spike — flag it.

    For each axis in ``axis_keys`` we group rows by every OTHER axis (the "rest"
    key). Within a group, rows differ only in that one axis; a row is a spike if
    it's net-positive but BOTH its axis-neighbours (the rows with the adjacent
    axis values present in the group) are net-negative. ``rows`` is mutated in
    place; nothing is returned.

    Each row must carry the axis values and a ``net_pnl`` (validation net is the
    honest choice when available; the caller decides which net it stores).
    """
    for axis in axis_keys:
        # Group rows that share every axis EXCEPT this one.
        groups: dict[tuple, list[dict]] = {}
        for row in rows:
            if axis not in row:
                continue
            rest = tuple(
                (k, row.get(k)) for k in axis_keys if k != axis
            )
            groups.setdefault(rest, []).append(row)

        for group in groups.values():
            if len(group) < 3:
                continue  # need a centre + two neighbours to call a spike
            # Sort by this axis's (numeric-where-possible) value.
            ordered = sorted(group, key=lambda r: _axis_sort_key(r.get(axis)))
            for idx in range(1, len(ordered) - 1):
                centre = ordered[idx]
                left = ordered[idx - 1]
                right = ordered[idx + 1]
                if (
                    centre.get("net_pnl", 0) > 0
                    and left.get("net_pnl", 0) < 0
                    and right.get("net_pnl", 0) < 0
                ):
                    centre["plateau_warning"] = (
                        f"spike on '{axis}'={centre.get(axis)}: net "
                        f"₹{centre.get('net_pnl', 0):,.0f} but neighbours "
                        f"{axis}={left.get(axis)} (₹{left.get('net_pnl', 0):,.0f}) and "
                        f"{axis}={right.get(axis)} (₹{right.get('net_pnl', 0):,.0f}) "
                        "are net-negative — likely overfit, not a robust plateau"
                    )


def _axis_sort_key(v: Any):
    """Sort axis values numerically when possible, else by string."""
    try:
        return (0, float(v))
    except (TypeError, ValueError):
        return (1, str(v))
