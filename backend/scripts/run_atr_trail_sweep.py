#!/usr/bin/env python3
"""Run the ATR-trail k-sweep over a universe and print the measured k-table.

Gap-fade (REVERSION) entries, ATR read AS-OF-ENTRY, trail-only exit swept over a
k grid, bucketed by a candle-derived regime proxy, constant-₹-risk sizing,
walk-forward split (last 1/3 of days held out).

    python scripts/run_atr_trail_sweep.py --days 45 [--universe SYM,SYM,...] [--json]

See backtesting/atr_trail_sweep.py + docs/plans/2026-06-22-atr-regime-trail-width.md.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import statistics
import sys

_backend = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _backend not in sys.path:
    sys.path.insert(0, _backend)

from backtesting.atr_trail_sweep import (  # noqa: E402
    DEFAULT_K_GRID, MIN_GAP_PCT, RISK_BUDGET, atr_at, gap_fade_entry, orb_entry,
    group_by_day, regime_proxy, simulate_trail,
)

# setup → (entry fn, noise-tolerance class label)
_SETUPS = {
    "gap_fade": ("REVERSION", lambda day, prev, min_gap: gap_fade_entry(day, prev, min_gap)),
    "orb": ("MOMENTUM", lambda day, prev, min_gap: orb_entry(day)),
}
from services.atr_trail import trail_pct_from_atr  # noqa: E402

# Liquid, gap-prone default universe (~40 Nifty names). Override with --universe.
DEFAULT_UNIVERSE = [
    "RELIANCE", "HDFCBANK", "ICICIBANK", "INFY", "TCS", "SBIN", "AXISBANK",
    "KOTAKBANK", "LT", "ITC", "HINDUNILVR", "BHARTIARTL", "BAJFINANCE", "MARUTI",
    "ASIANPAINT", "TITAN", "SUNPHARMA", "TATAMOTORS", "TATASTEEL", "WIPRO",
    "HCLTECH", "ULTRACEMCO", "NTPC", "POWERGRID", "ONGC", "COALINDIA", "ADANIENT",
    "ADANIPORTS", "JSWSTEEL", "HINDALCO", "GRASIM", "TECHM", "INDUSINDBK",
    "BAJAJFINSV", "DRREDDY", "CIPLA", "EICHERMOT", "BPCL", "DIVISLAB", "BRITANNIA",
]

NIFTY_ALIASES = ["NIFTY 50", "NIFTY", "Nifty 50", "NIFTY50"]


async def _fetch(client, symbol, days):
    try:
        return await client.get_historical_data(symbol, interval="15minute", days=days)
    except Exception as e:
        print(f"  ! fetch failed {symbol}: {e}", file=sys.stderr)
        return None


async def _fetch_market(client, days):
    for alias in NIFTY_ALIASES:
        c = await _fetch(client, alias, days)
        if c:
            print(f"  market regime source: {alias} ({len(c)} candles)", file=sys.stderr)
            return c
    return None


def _walk_forward_split(dates_sorted):
    """Return the split date (start of the last 1/3 of trading days)."""
    if len(dates_sorted) < 3:
        return None
    n_val = max(1, round(len(dates_sorted) / 3.0))
    return dates_sorted[len(dates_sorted) - n_val]


async def run(universe, days, k_grid, min_gap, setup="gap_fade"):
    from services.candidate_analysis import _market_data_client
    client = _market_data_client()
    setup_class, entry_fn = _SETUPS[setup]

    market = await _fetch_market(client, days + 20)
    if not market:
        print("ABORT: could not fetch NIFTY candles for the regime proxy.", file=sys.stderr)
        return None
    market_days = group_by_day(market)
    regimes = {d: regime_proxy(cs) for d, cs in market_days.items()}

    # trades: list of dicts {date, symbol, regime, k, pnl, reason}
    trades = []
    n_entries = 0
    fetch_days = days + 20  # warmup headroom for ATR

    # fetch in small batches to be gentle on the quote API
    for i in range(0, len(universe), 4):
        batch = universe[i:i + 4]
        series_list = await asyncio.gather(*[_fetch(client, s, fetch_days) for s in batch])
        for symbol, series in zip(batch, series_list):
            if not series:
                continue
            by_day = group_by_day(series)
            day_keys = list(by_day.keys())
            # cumulative offset of each day's first candle in the full series
            offset = 0
            offsets = {}
            for d in day_keys:
                offsets[d] = offset
                offset += len(by_day[d])
            prev_close = None
            for d in day_keys:
                day_candles = by_day[d]
                if prev_close is not None and d in regimes:
                    entry = entry_fn(day_candles, prev_close, min_gap)
                    if entry:
                        eidx, eprice, direction = entry
                        abs_idx = offsets[d] + eidx
                        atr = atr_at(series[:abs_idx + 1])
                        if atr:
                            n_entries += 1
                            regime = regimes[d]["regime"]
                            for k in k_grid:
                                tp = trail_pct_from_atr(atr, eprice, k)
                                sim = simulate_trail(day_candles, eidx, eprice, direction, tp)
                                sl_pts = eprice * tp / 100.0
                                qty = math.floor(RISK_BUDGET / sl_pts) if sl_pts > 0 else 0
                                trades.append({
                                    "date": d, "symbol": symbol, "regime": regime, "k": k,
                                    "pnl": round(qty * sim["pnl_per_share"], 2),
                                    "reason": sim["exit_reason"],
                                })
                prev_close = float(day_candles[-1].get("close") if isinstance(day_candles[-1], dict)
                                   else getattr(day_candles[-1], "close"))

    # aggregate per (regime, k), with walk-forward validation slice
    all_dates = sorted({t["date"] for t in trades})
    split = _walk_forward_split(all_dates)

    def agg(rows):
        pnls = [r["pnl"] for r in rows]
        if not pnls:
            return None
        n = len(pnls)
        wins = sum(1 for p in pnls if p > 0)
        mean = statistics.mean(pnls)
        sd = statistics.pstdev(pnls) if n > 1 else 0.0
        tstat = (mean / (sd / math.sqrt(n))) if sd > 0 else 0.0
        return {"n": n, "total": round(sum(pnls)), "mean": round(mean),
                "win_rate": round(wins / n, 2), "tstat": round(tstat, 2)}

    regimes_seen = sorted({t["regime"] for t in trades})
    table = {}
    for reg in regimes_seen:
        table[reg] = {}
        for k in k_grid:
            cell = [t for t in trades if t["regime"] == reg and t["k"] == k]
            val = [t for t in cell if split and t["date"] >= split]
            table[reg][k] = {"all": agg(cell), "validation": agg(val)}

    return {"n_entries": n_entries, "n_trades": len(trades), "split_date": split,
            "k_grid": k_grid, "regimes": regimes_seen, "table": table,
            "universe_size": len(universe), "days": days,
            "setup": setup, "setup_class": setup_class}


def _print_report(res):
    if not res:
        return
    print(f"\n{'='*72}")
    print(f"ATR-TRAIL k-SWEEP — {res.get('setup','gap_fade')} ({res.get('setup_class','')}) — "
          f"{res['universe_size']} names, {res['days']}d")
    print(f"{res['n_entries']} entries → {res['n_trades']} (entry×k) sims. "
          f"Walk-forward split: {res['split_date']} (last 1/3 = validation)")
    print(f"Constant risk ₹{RISK_BUDGET:,.0f}/trade. ₹ = total P&L; mean = ₹/trade.")
    print(f"{'='*72}")
    for reg in res["regimes"]:
        print(f"\n  REGIME: {reg.upper()}")
        print(f"  {'k':>4} │ {'n':>4} {'total₹':>9} {'mean₹':>7} {'win%':>5} {'tstat':>6} "
              f"│ {'val_n':>5} {'val_mean₹':>9} {'val_t':>6}")
        print(f"  {'-'*4}─┼─{'-'*35}─┼─{'-'*24}")
        best_k, best_val = None, None
        for k in res["k_grid"]:
            c = res["table"][reg][k]
            a, v = c["all"], c["validation"]
            if not a:
                continue
            vline = (f"{v['n']:>5} {v['mean']:>9} {v['tstat']:>6}" if v else f"{'—':>5} {'—':>9} {'—':>6}")
            print(f"  {k:>4} │ {a['n']:>4} {a['total']:>9} {a['mean']:>7} "
                  f"{a['win_rate']*100:>4.0f}% {a['tstat']:>6} │ {vline}")
            if v and (best_val is None or v["mean"] > best_val):
                best_val, best_k = v["mean"], k
        if best_k is not None:
            print(f"  → best validation ₹/trade at k={best_k} (₹{best_val}/trade)")


def main():
    p = argparse.ArgumentParser(description="ATR-trail k-sweep runner")
    p.add_argument("--universe", default=None, help="Comma-separated symbols (else default ~40)")
    p.add_argument("--days", type=int, default=45, help="Trading-day window (default 45)")
    p.add_argument("--k-grid", default=None, help="Comma-separated k values (else 1.5..4.0)")
    p.add_argument("--min-gap", type=float, default=MIN_GAP_PCT, help=f"Gap %% threshold (default {MIN_GAP_PCT})")
    p.add_argument("--setup", choices=["gap_fade", "orb"], default="gap_fade",
                   help="Entry setup to sweep (gap_fade=REVERSION, orb=MOMENTUM).")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    # --universe accepts a named universe (nifty50/nifty100/nifty500/niftytotal)
    # or a comma-separated symbol list. Default = the built-in ~40-name list.
    if not args.universe:
        universe = DEFAULT_UNIVERSE
    elif args.universe.lower().replace(" ", "").replace("_", "") in (
            "nifty50", "nifty100", "nifty500", "niftytotal", "niftytotalmarket"):
        from services.instruments_cache import get_universe
        universe = sorted(get_universe(args.universe))
        print(f"universe '{args.universe}': {len(universe)} symbols", file=sys.stderr)
    else:
        universe = [s.strip().upper() for s in args.universe.split(",")]
    k_grid = ([float(x) for x in args.k_grid.split(",")] if args.k_grid else DEFAULT_K_GRID)

    res = asyncio.run(run(universe, args.days, k_grid, args.min_gap, args.setup))
    if args.json:
        print(json.dumps(res, indent=2, default=str))
    else:
        _print_report(res)


if __name__ == "__main__":
    main()
