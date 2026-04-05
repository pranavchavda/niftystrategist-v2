#!/usr/bin/env python3
"""Bulk download NSE historical OHLCV data for TimesFM fine-tuning.

Downloads daily and/or intraday candle data for Nifty 500 stocks via
Upstox V3 API. Supports multiple intervals and handles chunking
automatically for intraday data (90-day max per request).

Output: Parquet file with columns [symbol, timestamp, open, high, low, close, volume, interval]
sorted by (symbol, timestamp). Ready for ML training pipelines.

Usage:
  # Daily data (10 years, single API call per stock)
  python scripts/collect_training_data.py

  # 30-minute intraday (from Jan 2022, chunked automatically)
  python scripts/collect_training_data.py --interval 30min

  # Both daily + intraday in one run
  python scripts/collect_training_data.py --interval daily+30min

  # Smaller universe, custom output
  python scripts/collect_training_data.py --universe nifty50 --interval 30min --output data/custom.parquet

  # Resume interrupted download
  python scripts/collect_training_data.py --interval 30min --resume
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from dotenv import load_dotenv
load_dotenv(os.path.join(_backend_dir, ".env"))

import numpy as np

try:
    import pandas as pd
except ImportError:
    print("pandas required: pip install pandas pyarrow", file=sys.stderr)
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Upstox V3 rate limits: 50 req/s, 500/min, 2000/30min
REQUEST_DELAY = 0.5  # seconds between requests
BURST_PAUSE = 30     # seconds pause every BURST_SIZE requests
BURST_SIZE = 100     # requests before pausing

# Interval configs: (unit, interval_value, max_days_per_request, max_years_back)
INTERVAL_CONFIG = {
    "daily":  ("days",    1,  3650, 10),   # 10 years per request
    "30min":  ("minutes", 30, 90,   4),    # 90 days per request, data from Jan 2022
    "15min":  ("minutes", 15, 30,   4),    # 30 days per request, data from Jan 2022
    "5min":   ("minutes", 5,  30,   4),    # 30 days per request
    "1hour":  ("hours",   1,  90,   4),    # 90 days per request
}


def _get_api(access_token: str):
    """Create Upstox V3 history API client."""
    import upstox_client
    config = upstox_client.Configuration()
    config.access_token = access_token
    api_client = upstox_client.ApiClient(config)
    return upstox_client.HistoryV3Api(api_client)


async def fetch_candles_chunked(
    history_api,
    instrument_key: str,
    unit: str,
    interval: int,
    from_date: str,
    to_date: str,
    max_chunk_days: int,
) -> list[list]:
    """Fetch candles with automatic chunking for API limits.

    For daily data, a single request covers up to 10 years.
    For intraday, chunks into max_chunk_days windows.
    """
    all_candles = []
    chunk_from = datetime.strptime(from_date, "%Y-%m-%d")
    chunk_to = datetime.strptime(to_date, "%Y-%m-%d")
    request_count = 0

    while chunk_from < chunk_to:
        chunk_end = min(chunk_from + timedelta(days=max_chunk_days), chunk_to)

        response = history_api.get_historical_candle_data1(
            instrument_key=instrument_key,
            unit=unit,
            interval=interval,
            to_date=chunk_end.strftime("%Y-%m-%d"),
            from_date=chunk_from.strftime("%Y-%m-%d"),
        )

        if response.data and response.data.candles:
            all_candles.extend(response.data.candles)

        chunk_from = chunk_end + timedelta(days=1)
        request_count += 1

        # Rate limit between chunks
        if request_count > 1:
            await asyncio.sleep(REQUEST_DELAY)

    return all_candles, request_count


async def collect_symbol(
    symbol: str,
    instrument_key: str,
    interval_name: str,
    access_token: str,
) -> tuple[pd.DataFrame | None, int]:
    """Collect historical data for a single symbol at a given interval.

    Returns (dataframe, api_call_count).
    """
    unit, interval_val, max_chunk, max_years = INTERVAL_CONFIG[interval_name]

    to_date = datetime.now().strftime("%Y-%m-%d")
    from_date = (datetime.now() - timedelta(days=max_years * 365)).strftime("%Y-%m-%d")

    history_api = _get_api(access_token)

    try:
        candles, call_count = await fetch_candles_chunked(
            history_api, instrument_key, unit, interval_val,
            from_date, to_date, max_chunk,
        )
    except Exception as e:
        logger.warning(f"  {symbol} [{interval_name}]: API error: {e}")
        return None, 1

    if not candles:
        logger.warning(f"  {symbol} [{interval_name}]: No data returned")
        return None, call_count

    rows = []
    for c in candles:
        ts = c[0] if isinstance(c[0], str) else c[0].isoformat()
        rows.append({
            "symbol": symbol,
            "timestamp": ts,
            "open": float(c[1]),
            "high": float(c[2]),
            "low": float(c[3]),
            "close": float(c[4]),
            "volume": int(c[5]),
            "interval": interval_name,
        })

    df = pd.DataFrame(rows)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.sort_values("timestamp").reset_index(drop=True)
    return df, call_count


async def main():
    parser = argparse.ArgumentParser(
        description="Bulk download NSE OHLCV data for ML training",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Intervals:
  daily       10 years of daily candles (1 API call per stock)
  30min       ~4 years of 30-min candles (from Jan 2022, ~16 calls per stock)
  15min       ~4 years of 15-min candles (from Jan 2022, ~48 calls per stock)
  1hour       ~4 years of hourly candles (from Jan 2022, ~16 calls per stock)
  daily+30min Both daily and 30-min in one run
""",
    )
    parser.add_argument(
        "--universe", default="nifty500",
        choices=["nifty50", "nifty100", "nifty500"],
        help="Stock universe (default: nifty500)",
    )
    parser.add_argument(
        "--interval", default="daily",
        help="Candle interval: daily, 30min, 15min, 1hour, or combined like daily+30min",
    )
    parser.add_argument(
        "--output", default=None,
        help="Output parquet file path (default: auto-generated from params)",
    )
    parser.add_argument(
        "--resume", action="store_true",
        help="Resume interrupted download (skips already-collected symbols)",
    )
    parser.add_argument(
        "--no-index", action="store_true",
        help="Skip index data (Nifty 50, Bank Nifty, etc.)",
    )
    args = parser.parse_args()

    # Parse intervals
    intervals = [i.strip() for i in args.interval.split("+")]
    for iv in intervals:
        if iv not in INTERVAL_CONFIG:
            logger.error(f"Unknown interval: {iv}. Choose from: {', '.join(INTERVAL_CONFIG.keys())}")
            sys.exit(1)

    # Setup output path
    data_dir = Path(_backend_dir) / "data"
    data_dir.mkdir(exist_ok=True)

    interval_tag = "_".join(intervals)
    output_path = args.output or str(data_dir / f"nse_{args.universe}_{interval_tag}.parquet")
    progress_path = str(Path(output_path).with_suffix(".progress.json"))

    # Get Upstox token
    access_token = os.environ.get("NF_ACCESS_TOKEN") or os.environ.get("UPSTOX_ACCESS_TOKEN")
    if not access_token:
        logger.error("No Upstox access token. Set NF_ACCESS_TOKEN or UPSTOX_ACCESS_TOKEN.")
        sys.exit(1)

    # Load symbol universe
    from services.instruments_cache import ensure_loaded, get_universe, get_instrument_key

    ensure_loaded()
    symbols = sorted(get_universe(args.universe))
    logger.info(f"Universe: {args.universe} ({len(symbols)} symbols)")
    logger.info(f"Intervals: {', '.join(intervals)}")

    # Index instrument keys
    index_keys = {
        "NIFTY_50": "NSE_INDEX|Nifty 50",
        "NIFTY_BANK": "NSE_INDEX|Nifty Bank",
        "NIFTY_IT": "NSE_INDEX|Nifty IT",
        "NIFTY_NEXT_50": "NSE_INDEX|Nifty Next 50",
    }

    # Resume support
    # Progress key = "SYMBOL:interval" to track per-interval completion
    completed_keys: set[str] = set()
    existing_dfs: list[pd.DataFrame] = []

    if args.resume and os.path.exists(progress_path):
        with open(progress_path) as f:
            completed_keys = set(json.load(f))
        logger.info(f"Resuming: {len(completed_keys)} symbol-intervals already collected")
        if os.path.exists(output_path):
            existing_dfs.append(pd.read_parquet(output_path))

    # Build work list: (symbol, instrument_key, interval)
    work_items = []
    all_symbols = list(symbols)
    if not args.no_index:
        all_symbols.extend(index_keys.keys())

    for interval_name in intervals:
        for symbol in all_symbols:
            key = f"{symbol}:{interval_name}"
            if key in completed_keys:
                continue

            if symbol in index_keys:
                inst_key = index_keys[symbol]
            else:
                inst_key = get_instrument_key(symbol)
                if not inst_key:
                    continue
            work_items.append((symbol, inst_key, interval_name))

    total = len(work_items)
    all_dfs: list[pd.DataFrame] = list(existing_dfs)
    success = 0
    failed = 0
    total_api_calls = 0

    logger.info(f"Work items: {total} symbol-intervals to download")
    logger.info(f"Output: {output_path}")
    t_start = time.time()

    for i, (symbol, inst_key, interval_name) in enumerate(work_items):
        # Burst rate limiting
        if total_api_calls > 0 and total_api_calls % BURST_SIZE == 0:
            logger.info(f"  Rate limit pause ({BURST_PAUSE}s after {total_api_calls} API calls)...")
            await asyncio.sleep(BURST_PAUSE)

        logger.info(f"  [{i+1}/{total}] {symbol} [{interval_name}]...")
        df, call_count = await collect_symbol(symbol, inst_key, interval_name, access_token)
        total_api_calls += call_count

        if df is not None and len(df) > 0:
            all_dfs.append(df)
            completed_keys.add(f"{symbol}:{interval_name}")
            success += 1

            date_min = df["timestamp"].min().strftime("%Y-%m-%d")
            date_max = df["timestamp"].max().strftime("%Y-%m-%d")
            logger.info(f"  [{i+1}/{total}] {symbol} [{interval_name}]: {len(df):,} candles ({date_min} to {date_max})")
        else:
            failed += 1

        # Save progress periodically
        if success % 50 == 0 and success > 0:
            _save_progress(all_dfs, output_path, completed_keys, progress_path)

        await asyncio.sleep(REQUEST_DELAY)

    # Final save
    elapsed = time.time() - t_start

    if all_dfs:
        _save_progress(all_dfs, output_path, completed_keys, progress_path)

        combined = pd.read_parquet(output_path)
        n_symbols = combined["symbol"].nunique()
        n_rows = len(combined)

        logger.info("")
        logger.info("=" * 60)
        logger.info("COLLECTION COMPLETE")
        logger.info(f"  Symbols: {n_symbols} ({success} new, {failed} failed)")
        logger.info(f"  Total candles: {n_rows:,}")
        logger.info(f"  API calls: {total_api_calls:,}")

        for iv in intervals:
            iv_df = combined[combined["interval"] == iv]
            if len(iv_df) > 0:
                logger.info(f"  [{iv}] {iv_df['symbol'].nunique()} symbols, {len(iv_df):,} candles "
                           f"({iv_df['timestamp'].min().strftime('%Y-%m-%d')} to "
                           f"{iv_df['timestamp'].max().strftime('%Y-%m-%d')})")

        logger.info(f"  File size: {os.path.getsize(output_path) / 1024 / 1024:.1f} MB")
        logger.info(f"  Time: {elapsed:.0f}s ({elapsed/60:.1f} min)")
        logger.info(f"  Output: {output_path}")
        logger.info("=" * 60)

        # Data quality
        for iv in intervals:
            iv_df = combined[combined["interval"] == iv]
            if len(iv_df) > 0:
                cps = iv_df.groupby("symbol").size()
                thin = (cps < 500).sum()
                logger.info(f"\n  [{iv}] per symbol: min={cps.min():,}, median={cps.median():,.0f}, max={cps.max():,}")
                if thin > 0:
                    logger.warning(f"  [{iv}] {thin} symbols with <500 candles")

        # Clean up progress file
        if os.path.exists(progress_path):
            os.remove(progress_path)
    else:
        logger.error("No data collected!")


def _save_progress(
    dfs: list[pd.DataFrame],
    output_path: str,
    completed: set[str],
    progress_path: str,
):
    """Save intermediate results and progress tracker."""
    combined = pd.concat(dfs, ignore_index=True)
    combined = combined.sort_values(["symbol", "interval", "timestamp"]).reset_index(drop=True)
    combined = combined.drop_duplicates(subset=["symbol", "interval", "timestamp"], keep="last")
    combined.to_parquet(output_path, index=False)

    with open(progress_path, "w") as f:
        json.dump(sorted(completed), f)

    logger.info(f"  Progress saved: {len(completed)} items, {len(combined):,} candles")


if __name__ == "__main__":
    asyncio.run(main())
