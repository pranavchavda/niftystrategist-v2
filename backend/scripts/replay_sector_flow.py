#!/usr/bin/env python3
"""Replay the two-layer intraday sector-flow sensor over historical tape —
validation-first, before any thresholds are wired or any awakening fires.

Layer 1 (market-aggregate): the whole-universe timeline = an intraday REGIME-ROLL
sensor (tape turning + accelerating mid-session). Layer 2 (sector-relative):
sector − market, stripping beta → persistent laggard/leader selection
(`rel_median` level) + real-time decoupling (`d_rel_median`).

Goal (Pranav, 2026-06-27/28): the 06-25 backtest showed the "IT sell-off" was
mostly a market roll-over (every sector red); the sector edge only survives net of
market. This replay confirms (a) the market layer flags the back-half roll, and
(b) the relative layer pegs IT as the persistent laggard from the open.

Usage (from backend/, venv active, WARP up, NF_USER_ID set):
  PYTHONPATH=.:cli-tools NF_USER_ID=1 python scripts/replay_sector_flow.py \
      --sectors it,bank,pharma --dates 2026-06-25 --universe nifty500
"""
import argparse
import asyncio
import os
import sys
from collections import defaultdict

_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (_BACKEND, os.path.join(_BACKEND, "cli-tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

from services import instruments_cache as ic  # noqa: E402
from services.sector_flow import (  # noqa: E402
    sector_timeline, relative_timeline, persistent_bias,
)
from base import init_market_data_client  # noqa: E402

MIN_SECTOR_NAMES = 8  # breadth needs names; below this a sector is too thin to read


def _shape_for_day(candles, day: str):
    day_c = sorted((c for c in candles if c.timestamp[:10] == day), key=lambda c: c.timestamp)
    if not day_c:
        return None
    closes = {c.timestamp[11:16]: c.close for c in day_c}
    return day_c[0].open, closes


async def _fetch_all(client, symbols, days):
    sem = asyncio.Semaphore(10)
    async def one(sym):
        async with sem:
            try:
                return sym, await client.get_historical_data(sym, interval="15minute", days=days)
            except Exception as e:
                print(f"   ! {sym}: {e}", file=sys.stderr)
                return sym, []
    return dict(await asyncio.gather(*[one(s) for s in symbols]))


def _build_day(symbols, results, day):
    """→ (times, per_open, per_closes) for a symbol set on one date."""
    per_open, per_closes, times = {}, {}, set()
    for sym in symbols:
        shaped = _shape_for_day(results.get(sym, []), day)
        if not shaped:
            continue
        per_open[sym], per_closes[sym] = shaped
        times |= set(per_closes[sym].keys())
    return sorted(times), per_open, per_closes


def _print_market(tl):
    print(f"\n══ MARKET (regime-roll layer) ══")
    print(f"   {'time':>5}  {'n':>3}  {'net':>6}  {'med%':>6}  {'Δmed':>6}  {'decis':>6}")
    for s in tl:
        dmed = "" if s.d_median is None else f"{s.d_median:+.2f}"
        dec = "" if s.decisiveness is None else f"{s.decisiveness:.3f}"
        mark = "  ⟵ roll" if (s.decisiveness or 0) >= 0.10 else ""
        print(f"   {s.as_of:>5}  {s.n:>3}  {s.net_breadth:+.2f}  {s.median_move:+.2f}  "
              f"{dmed:>6}  {dec:>6}{mark}")


def _print_relative(label, rel_tl, bias):
    print(f"\n── {label} (relative to market) — bias={bias['bias']} "
          f"avg_rel={bias['avg_rel_median']:+.2f} ──")
    print(f"   {'time':>5}  {'secMed':>7} {'mktMed':>7} {'rel':>6} {'Δrel':>6} {'decoup':>6} {'relDec':>6}")
    for s in rel_tl:
        drel = "" if s.d_rel_median is None else f"{s.d_rel_median:+.2f}"
        dec = "" if s.rel_decisiveness is None else f"{s.rel_decisiveness:.3f}"
        dcp = "" if s.decoupling is None else ("▲" if s.decoupling else "·")
        mark = "  ⟵ decoupling" if (s.rel_decisiveness or 0) >= 0.08 else ""
        print(f"   {s.as_of:>5}  {s.sector_median:>+7.2f} {s.market_median:>+7.2f} "
              f"{s.rel_median:>+6.2f} {drel:>6} {dcp:>6} {dec:>6}{mark}")


async def run(args):
    ic.ensure_loaded()
    client = init_market_data_client()
    dates = [d.strip() for d in args.dates.split(",") if d.strip()]
    terms = [t.strip() for t in args.sectors.split(",") if t.strip()]

    labels = []
    for term in terms:
        matched = ic.match_sectors(term)
        if not matched:
            print(f"No sector matched '{term}'. Available: {', '.join(ic.list_sectors())}", file=sys.stderr)
            continue
        labels.extend(sorted(matched))

    universe = sorted(ic.get_universe(args.universe))
    by_sector = defaultdict(list)
    for s in universe:
        sec = ic.get_sector(s)
        if sec:
            by_sector[sec].append(s)

    span = max(7, args.days)
    print(f"Fetching {len(universe)} {args.universe} names ({span}d window)…", file=sys.stderr)
    results = await _fetch_all(client, universe, span)

    for day in dates:
        print(f"\n\n############### {day} ###############")
        m_times, m_open, m_closes = _build_day(universe, results, day)
        if not m_open:
            print("  (no market data)")
            continue
        market_tl = sector_timeline("MARKET", m_times, m_closes, m_open,
                                    threshold=args.threshold, window=args.window)
        _print_market(market_tl)

        for label in labels:
            members = by_sector.get(label, [])
            if len(members) < MIN_SECTOR_NAMES:
                print(f"\n── {label}: only {len(members)} names (<{MIN_SECTOR_NAMES}), skipped ──")
                continue
            s_times, s_open, s_closes = _build_day(members, results, day)
            if not s_open:
                continue
            sector_tl = sector_timeline(label, s_times, s_closes, s_open,
                                        threshold=args.threshold, window=args.window)
            rel_tl = relative_timeline(sector_tl, market_tl, window=args.window)
            _print_relative(label, rel_tl, persistent_bias(rel_tl))


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--sectors", default="it", help="Comma-separated sector terms (e.g. 'it,bank,pharma').")
    p.add_argument("--dates", required=True, help="Comma-separated YYYY-MM-DD dates to replay.")
    p.add_argument("--universe", default="nifty500", help="nifty50|nifty100|nifty500|niftytotal.")
    p.add_argument("--threshold", type=float, default=0.3, help="Per-name move threshold %% (default 0.3).")
    p.add_argument("--window", type=int, default=2, help="Acceleration window in bars (default 2 = 30min).")
    p.add_argument("--days", type=int, default=7, help="Fetch window in days (default 7).")
    args = p.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
