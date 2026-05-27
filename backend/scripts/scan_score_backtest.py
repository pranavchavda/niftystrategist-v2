#!/usr/bin/env python3
"""Backtest nf-morning-scan's CURRENT scoring at multiple times of day.

Premise to test: the score is morning-biased (gap is worth 2 fixed points that
never decay), but Hero Scanner runs all day. Does the score's predictive power
degrade in the afternoon, and which components carry the afternoon signal?

Method (no lookahead): for each symbol and each complete trading day in the
fetched window, at each eval time T ∈ {09:30, 11:30, 13:30, 14:30} reconstruct
the exact inputs the live scan would have had at T (gap, rel-strength, RSI,
session VWAP, RVOL-T, volume expansion) from candles up to T, compute the real
phase1+phase2 score using the scan's own functions, then measure the forward
intraday return over the next `--horizon` minutes in the candidate's momentum
direction. Reports Spearman correlation of score (and each component) with
forward return, per eval time.

Usage:
  python scripts/scan_score_backtest.py --max-symbols 8 --test-days 4 --json
  python scripts/scan_score_backtest.py --universe nifty50 --horizon 90
"""
import argparse
import importlib.util
import json
import os
import sys
from datetime import datetime, time as dtime, timedelta

_backend = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _backend not in sys.path:
    sys.path.insert(0, _backend)

import pandas as pd

from base import init_market_data_client, run_async  # noqa: E402  (cli-tools on path below)


def _load_scan_module():
    """Import the hyphenated nf-morning-scan CLI as a module for its scoring fns."""
    cli = os.path.join(_backend, "cli-tools")
    if cli not in sys.path:
        sys.path.insert(0, cli)
    path = os.path.join(cli, "nf-morning-scan")
    from importlib.machinery import SourceFileLoader
    loader = SourceFileLoader("nf_morning_scan", path)
    spec = importlib.util.spec_from_loader("nf_morning_scan", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


EVAL_TIMES = [dtime(9, 30), dtime(11, 30), dtime(13, 30), dtime(14, 30)]


def _to_dt(ts):
    return pd.to_datetime(ts)


def fetch_series(client, symbol, days, instrument_key=None):
    candles = run_async(client.get_historical_data(
        symbol, interval="15minute", days=days, instrument_key=instrument_key))
    for c in candles:
        c._dt = _to_dt(c.timestamp)              # tz-aware IST (for .date()/.time())
        c._naive = c._dt.tz_localize(None)       # naive IST wall-clock (for arithmetic)
    candles.sort(key=lambda c: c._dt)
    return candles


def build_index_closes(index_candles):
    """date -> (prev_close, {time: close}) for the Nifty index."""
    by_date = {}
    for c in index_candles:
        by_date.setdefault(c._dt.date(), []).append(c)
    dates = sorted(by_date)
    out = {}
    for i, d in enumerate(dates):
        prev_close = by_date[dates[i - 1]][-1].close if i > 0 else None
        bars = sorted(((c._naive, c.close) for c in by_date[d]), key=lambda x: x[0])
        out[d] = {"prev_close": prev_close, "bars": bars}
    return out, dates


def _index_close_before(index_info, d, moment):
    """Last index close that closed strictly before `moment` (closed-bar convention)."""
    if d not in index_info:
        return None
    last = None
    for naive, close in index_info[d]["bars"]:
        if naive < moment:
            last = close
    return last


def index_pct_at(index_info, d, eval_dt):
    """Nifty % change from prev close to the last closed index bar before eval_dt."""
    if d not in index_info or not index_info[d]["prev_close"]:
        return 0.0
    prev_close = index_info[d]["prev_close"]
    last = _index_close_before(index_info, d, eval_dt)
    return (last - prev_close) / prev_close * 100 if last else 0.0


def _index_fwd_ret(index_info, d, eval_dt, fwd_dt):
    """Nifty % return over [eval_dt, fwd_dt] (for market-neutralizing the stock return)."""
    p0 = _index_close_before(index_info, d, eval_dt)
    p1 = _index_close_before(index_info, d, fwd_dt)
    if not p0 or not p1:
        return 0.0
    return (p1 - p0) / p0 * 100


def evaluate_symbol(scan, symbol, candles, index_info, horizon_min, test_days):
    """Yield one record per (day, eval_time)."""
    by_date = {}
    for c in candles:
        by_date.setdefault(c._dt.date(), []).append(c)
    dates = sorted(by_date)
    # leave the earliest days as warmup for RSI/RVOL baselines
    target_days = dates[-test_days:] if test_days < len(dates) else dates[1:]

    records = []
    for d in target_days:
        day_candles = by_date[d]
        if len(day_candles) < 6:
            continue
        prev_dates = [x for x in dates if x < d]
        if not prev_dates:
            continue
        prev_close = by_date[prev_dates[-1]][-1].close
        today_open = day_candles[0].open

        # (c) intraday-momentum feature: first 30-min return (Gao et al 2018).
        # = (price at 09:45 − open) / open. Known only after 09:45.
        first30_dt = datetime.combine(d, dtime(9, 45))
        f30_bars = [c for c in day_candles if c._naive < first30_dt]
        first30_ret = ((f30_bars[-1].close - today_open) / today_open * 100
                       if f30_bars and today_open else None)

        for T in EVAL_TIMES:
            # No lookahead: only bars that have CLOSED strictly before T. For the
            # 15-min grid this means the last bar is the one ending exactly at T
            # (e.g. T=09:30 → last bar is 09:15, covering 09:15-09:30). The bar
            # timestamped T itself covers T..T+15 and must be excluded.
            eval_dt = datetime.combine(d, T)
            today_T = [c for c in day_candles if c._naive < eval_dt]
            if len(today_T) < 1:
                continue
            up_to_T = [c for c in candles if c._naive < eval_dt]
            ltp = today_T[-1].close
            if prev_close <= 0:
                continue
            stock_pct = (ltp - prev_close) / prev_close * 100
            if stock_pct == 0:
                continue
            nifty_pct = index_pct_at(index_info, d, eval_dt)

            gap = scan.compute_gap({"open": today_open, "close": prev_close})
            rel = scan.compute_relative_strength(stock_pct, nifty_pct)
            p1 = scan.phase1_score(gap, rel, stock_pct)

            rsi = scan.compute_rsi(up_to_T)
            vwap = scan.compute_vwap(today_T)
            rvol = scan.compute_rvol_t(today_T, up_to_T)
            volx = scan.compute_volume_expansion(today_T, up_to_T)
            p2 = scan.phase2_score(rsi, vwap, ltp, rvol, volx)

            # forward return: price h minutes after the eval moment, same closed-bar
            # convention (last bar that closed before eval_dt + horizon).
            fwd_dt = eval_dt + timedelta(minutes=horizon_min)
            fwd = [c for c in day_candles if c._naive < fwd_dt]
            fwd_close = fwd[-1].close if fwd else day_candles[-1].close
            raw_ret = (fwd_close - ltp) / ltp * 100
            # (a) market-neutralize: stock forward return minus Nifty's over the same window.
            nifty_fwd = _index_fwd_ret(index_info, d, eval_dt, fwd_dt)
            alpha_fwd = raw_ret - nifty_fwd

            records.append({
                "symbol": symbol, "date": str(d), "eval_time": T.strftime("%H:%M"),
                "score": p1 + p2, "p1": p1, "p2": p2,
                "gap_abs": abs(gap), "rel_strength": abs(rel),
                "rsi": rsi if rsi is not None else float("nan"),
                "above_vwap": 1 if (vwap and ltp > vwap) else 0,
                "rvol": (rvol if rvol is not None else volx) or float("nan"),
                # first30 is only KNOWN once the 09:45 bar has closed — null it for
                # earlier evals to avoid lookahead (e.g. the 09:30 eval).
                "first30": (first30_ret if (first30_ret is not None and eval_dt >= first30_dt)
                            else float("nan")),
                "alpha_fwd": alpha_fwd,       # market-neutralized forward return (the target)
                "raw_fwd": raw_ret,
            })
    return records


TARGET = "alpha_fwd"  # market-neutralized forward return


def _rankcorr(a, b):
    """Spearman = Pearson on ranks (sidesteps the scipy dep pandas' spearman pulls in)."""
    if len(a) < 8 or a.nunique() < 2 or b.nunique() < 2:
        return None
    rho = a.rank().corr(b.rank())
    return None if pd.isna(rho) else float(rho)


def _ic_by_cross_section(df, col, min_names=10):
    """(b) Information Coefficient done right: rank-corr of `col` vs TARGET WITHIN each
    (date, eval_time) cross-section, then average across cross-sections. Returns mean IC,
    its t-stat (mean / se), and # of cross-sections. Also the mean top-minus-bottom
    quintile spread of TARGET sorted by `col`."""
    ics, spreads = [], []
    for _, g in df.groupby(["date", "eval_time"]):
        sub = g[[col, TARGET]].dropna()
        if len(sub) < min_names:
            continue
        ic = _rankcorr(sub[col], sub[TARGET])
        if ic is not None:
            ics.append(ic)
        # quintile spread
        try:
            q = pd.qcut(sub[col].rank(method="first"), 5, labels=False)
            top = sub[TARGET][q == 4].mean()
            bot = sub[TARGET][q == 0].mean()
            if pd.notna(top) and pd.notna(bot):
                spreads.append(top - bot)
        except (ValueError, IndexError):
            pass
    if not ics:
        return {"mean_ic": None, "ic_t": None, "n_cs": 0, "q_spread": None}
    s = pd.Series(ics)
    se = s.std(ddof=1) / (len(s) ** 0.5) if len(s) > 1 else float("nan")
    return {
        "mean_ic": round(float(s.mean()), 4),
        "ic_t": round(float(s.mean() / se), 2) if se and not pd.isna(se) and se > 0 else None,
        "n_cs": len(s),
        "q_spread": round(float(pd.Series(spreads).mean()), 4) if spreads else None,
    }


def summarize(records):
    df = pd.DataFrame(records)
    out = {"total_samples": len(df), "target": TARGET, "by_time": {}}
    if df.empty:
        return out, df
    comps = ["score", "first30", "gap_abs", "rel_strength", "rsi", "above_vwap", "rvol"]
    for T in sorted(df["eval_time"].unique()):
        sub = df[df["eval_time"] == T]
        out["by_time"][T] = {
            "n": len(sub),
            "mean_alpha": round(float(sub[TARGET].mean()), 4),
            "ic": {col: _ic_by_cross_section(sub, col) for col in comps},
        }
    return out, df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--universe", default="nifty50")
    ap.add_argument("--max-symbols", type=int, default=12)
    ap.add_argument("--fetch-days", type=int, default=25, help="candle history window")
    ap.add_argument("--test-days", type=int, default=10, help="recent days to evaluate")
    ap.add_argument("--horizon", type=int, default=90, help="forward return horizon (min)")
    ap.add_argument("--shuffle", action="store_true", help="random sample of the universe (seed 42) instead of alphabetical head")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    scan = _load_scan_module()
    from services.instruments_cache import ensure_loaded, get_universe
    from services.upstox_client import UpstoxClient
    ensure_loaded()

    universe = sorted(get_universe(args.universe))
    if args.shuffle:
        import random
        random.seed(42)
        universe = random.sample(universe, min(len(universe), args.max_symbols))
    symbols = universe[: args.max_symbols]
    client = init_market_data_client()

    index_candles = fetch_series(
        client, "NIFTY 50", args.fetch_days,
        instrument_key=UpstoxClient.INDEX_KEYS["NIFTY 50"])
    index_info, _ = build_index_closes(index_candles)

    all_records = []
    for i, sym in enumerate(symbols, 1):
        try:
            candles = fetch_series(client, sym, args.fetch_days)
            recs = evaluate_symbol(scan, sym, candles, index_info, args.horizon, args.test_days)
            all_records.extend(recs)
            print(f"  [{i}/{len(symbols)}] {sym}: {len(recs)} samples", file=sys.stderr)
        except Exception as e:
            print(f"  [{i}/{len(symbols)}] {sym}: SKIP ({e})", file=sys.stderr)

    summary, df = summarize(all_records)

    if args.json:
        print(json.dumps(summary, indent=2))
        return

    print(f"\n=== Information Coefficient vs market-neutralized forward {args.horizon}min alpha — "
          f"{summary['total_samples']} samples, {len(symbols)} symbols ===")
    print("IC = rank-corr WITHIN each (date,time) cross-section, averaged. t = IC mean/SE.")
    print("Rule of thumb: |mean IC| ~0.02-0.05 with |t|>~2 is a real, tradeable signal.\n")
    cols = ["score", "first30", "gap_abs", "rel_strength", "rsi", "above_vwap", "rvol"]
    for T, s in summary["by_time"].items():
        print(f"  --- {T} (n={s['n']}, mean alpha {s['mean_alpha']}%) ---")
        print(f"      {'feature':<13} {'meanIC':>8} {'t':>6} {'q-spread':>9} {'#cs':>4}")
        for c in cols:
            ic = s["ic"][c]
            print(f"      {c:<13} {str(ic['mean_ic']):>8} {str(ic['ic_t']):>6} "
                  f"{str(ic['q_spread']):>9} {ic['n_cs']:>4}")
    print("\n'score' = current composite. 'first30' = Gao intraday-momentum feature "
          "(NaN at 09:30). q-spread = top-minus-bottom quintile mean alpha (%).")


if __name__ == "__main__":
    main()
