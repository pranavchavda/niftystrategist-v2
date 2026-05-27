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
        c._dt = _to_dt(c.timestamp)
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
        out[d] = (prev_close, {c._dt.time(): c.close for c in by_date[d]})
    return out, dates


def index_pct_at(index_info, d, T):
    """Nifty % change from prev close to the last index close at/before T on day d."""
    if d not in index_info:
        return 0.0
    prev_close, times = index_info[d]
    if not prev_close:
        return 0.0
    last = None
    for t in sorted(times):
        if t <= T:
            last = times[t]
    if last is None:
        return 0.0
    return (last - prev_close) / prev_close * 100


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

        for T in EVAL_TIMES:
            today_T = [c for c in day_candles if c._dt.time() <= T]
            if len(today_T) < 2:
                continue
            up_to_T = [c for c in candles if c._dt <= today_T[-1]._dt]
            ltp = today_T[-1].close
            if prev_close <= 0:
                continue
            stock_pct = (ltp - prev_close) / prev_close * 100
            if stock_pct == 0:
                continue
            nifty_pct = index_pct_at(index_info, d, T)

            gap = scan.compute_gap({"open": today_open, "close": prev_close})
            rel = scan.compute_relative_strength(stock_pct, nifty_pct)
            p1 = scan.phase1_score(gap, rel, stock_pct)

            rsi = scan.compute_rsi(up_to_T)
            vwap = scan.compute_vwap(today_T)
            rvol = scan.compute_rvol_t(today_T, up_to_T)
            volx = scan.compute_volume_expansion(today_T, up_to_T)
            p2 = scan.phase2_score(rsi, vwap, ltp, rvol, volx)

            # forward return over the horizon, in the momentum direction
            target_dt = today_T[-1]._dt + timedelta(minutes=horizon_min)
            fwd = [c for c in day_candles if c._dt >= target_dt]
            fwd_close = fwd[0].close if fwd else day_candles[-1].close
            raw_ret = (fwd_close - ltp) / ltp * 100
            direction = 1 if stock_pct > 0 else -1
            fwd_ret = raw_ret * direction

            records.append({
                "symbol": symbol, "date": str(d), "eval_time": T.strftime("%H:%M"),
                "score": p1 + p2, "p1": p1, "p2": p2,
                "gap_abs": abs(gap), "rel_strength": abs(rel),
                "rsi": rsi if rsi is not None else float("nan"),
                "above_vwap": 1 if (vwap and ltp > vwap) else 0,
                "rvol": (rvol if rvol is not None else volx) or float("nan"),
                "fwd_ret": fwd_ret,
            })
    return records


def _spear(df, col):
    sub = df[[col, "fwd_ret"]].dropna()
    if len(sub) < 5 or sub[col].nunique() < 2:
        return None, len(sub)
    # Spearman = Pearson on ranks (avoids the scipy dependency pandas' spearman pulls in)
    rho = sub[col].rank().corr(sub["fwd_ret"].rank())
    return (None if pd.isna(rho) else round(float(rho), 3)), len(sub)


def summarize(records):
    df = pd.DataFrame(records)
    out = {"total_samples": len(df), "by_time": {}}
    if df.empty:
        return out, df
    comps = ["score", "p1", "p2", "gap_abs", "rel_strength", "rsi", "above_vwap", "rvol"]
    for T in sorted(df["eval_time"].unique()):
        sub = df[df["eval_time"] == T]
        corrs = {}
        for col in comps:
            rho, n = _spear(sub, col)
            corrs[col] = rho
        hi = sub[sub["score"] >= 7]["fwd_ret"]
        lo = sub[sub["score"] < 7]["fwd_ret"]
        out["by_time"][T] = {
            "n": len(sub),
            "mean_fwd_ret": round(float(sub["fwd_ret"].mean()), 3),
            "score_corr": corrs["score"],
            "component_corr": {k: corrs[k] for k in comps if k != "score"},
            "mean_fwd_ret_score_ge7": round(float(hi.mean()), 3) if len(hi) else None,
            "mean_fwd_ret_score_lt7": round(float(lo.mean()), 3) if len(lo) else None,
            "n_score_ge7": int(len(hi)),
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

    print(f"\n=== Scan score vs forward {args.horizon}min return — "
          f"{summary['total_samples']} samples, {len(symbols)} symbols ===\n")
    print(f"{'time':>6} {'n':>5} {'meanRet':>8} {'scoreρ':>7} {'ret≥7':>7} {'ret<7':>7}  component ρ (gap/rel/rsi/vwap/rvol)")
    for T, s in summary["by_time"].items():
        cc = s["component_corr"]
        comp = f"{cc['gap_abs']}/{cc['rel_strength']}/{cc['rsi']}/{cc['above_vwap']}/{cc['rvol']}"
        print(f"{T:>6} {s['n']:>5} {s['mean_fwd_ret']:>8} {str(s['score_corr']):>7} "
              f"{str(s['mean_fwd_ret_score_ge7']):>7} {str(s['mean_fwd_ret_score_lt7']):>7}  {comp}")
    print("\nρ = Spearman rank corr with forward return (higher = score predicts move better).")
    print("Watch whether scoreρ and gap-ρ fall from morning → afternoon (the premise).")


if __name__ == "__main__":
    main()
