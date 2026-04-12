#!/usr/bin/env python3
"""Compute full technical indicator time series for all stocks.

Loads daily OHLCV data from the Nifty 500 10-year parquet, computes ~86 TA
indicators per symbol via the `ta` library, adds derived features (returns,
SMAs, volume ratios, 52-week highs/lows, gaps), and saves the result as a
single parquet file for downstream training pipeline consumption.

Output: backend/data/training/ta_indicators.parquet

Usage:
  python scripts/training/01_compute_ta_indicators.py
  python scripts/training/01_compute_ta_indicators.py --input data/custom.parquet
  python scripts/training/01_compute_ta_indicators.py --output data/training/my_ta.parquet
"""

import argparse
import logging
import os
import sys
import time

import numpy as np
import pandas as pd
import ta

_backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from dotenv import load_dotenv
load_dotenv(os.path.join(_backend_dir, ".env"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Minimum trading days required for a symbol to be included.
# 50-period indicators need at least ~50 rows; 60 gives a small buffer.
MIN_TRADING_DAYS = 60


def compute_derived_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add derived features that are not part of the standard ta library output.

    Expects df sorted by date for a single symbol, with columns:
    open, high, low, close, volume (plus any ta columns already added).
    """
    close = df["close"]
    volume = df["volume"]

    # Previous close
    df["prev_close"] = close.shift(1)

    # Returns over various horizons
    df["return_1d"] = close / close.shift(1) - 1
    df["return_5d"] = close / close.shift(5) - 1
    df["return_20d"] = close / close.shift(20) - 1

    # Price vs simple moving averages
    sma20 = close.rolling(20).mean()
    sma50 = close.rolling(50).mean()
    df["price_vs_sma20_pct"] = (close - sma20) / sma20
    df["price_vs_sma50_pct"] = (close - sma50) / sma50

    # Volume ratio vs 20-day average
    vol_ma20 = volume.rolling(20).mean()
    df["volume_ratio_20d"] = volume / vol_ma20

    # Gap percentage (open vs previous close)
    df["gap_pct"] = (df["open"] - df["prev_close"]) / df["prev_close"]

    # 52-week (252 trading days) high and low
    df["high_52w"] = close.rolling(252, min_periods=1).max()
    df["low_52w"] = close.rolling(252, min_periods=1).min()
    df["pct_from_52w_high"] = (close - df["high_52w"]) / df["high_52w"]
    df["pct_from_52w_low"] = (close - df["low_52w"]) / df["low_52w"]

    return df


def process_symbol(sym_df: pd.DataFrame) -> pd.DataFrame:
    """Compute all TA indicators + derived features for a single symbol.

    Args:
        sym_df: DataFrame for one symbol, sorted by date.

    Returns:
        DataFrame with all original columns + ~86 ta columns + derived features.
    """
    # ta.add_all_ta_features modifies the df in-place and returns it.
    # Use fillna=True to fill NaN warm-up values with sensible defaults
    # (e.g., 0 for oscillators, forward-fill for trends).
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", pd.errors.PerformanceWarning)
        sym_df = ta.add_all_ta_features(
            sym_df,
            open="open",
            high="high",
            low="low",
            close="close",
            volume="volume",
            fillna=True,
        )

    # Defragment after ta inserts ~86 columns one at a time
    sym_df = sym_df.copy()

    # Add our derived features on top
    sym_df = compute_derived_features(sym_df)

    return sym_df


def main():
    parser = argparse.ArgumentParser(
        description="Compute TA indicators for all stocks in the OHLCV parquet",
        epilog="Example: python scripts/training/01_compute_ta_indicators.py",
    )
    parser.add_argument(
        "--input", "-i",
        default=os.path.join(_backend_dir, "data", "nse_nifty500_10y.parquet"),
        help="Input OHLCV parquet path (default: data/nse_nifty500_10y.parquet)",
    )
    parser.add_argument(
        "--output", "-o",
        default=os.path.join(_backend_dir, "data", "training", "ta_indicators.parquet"),
        help="Output parquet path (default: data/training/ta_indicators.parquet)",
    )
    args = parser.parse_args()

    # ------------------------------------------------------------------
    # 1. Load OHLCV data
    # ------------------------------------------------------------------
    logger.info(f"Loading OHLCV data from {args.input}")
    df = pd.read_parquet(args.input)
    logger.info(f"Loaded {len(df):,} rows, {df['symbol'].nunique()} symbols")

    # Filter for daily interval only if column exists
    if "interval" in df.columns:
        df = df[df["interval"] == "daily"].copy()
        logger.info(f"Filtered to daily: {len(df):,} rows")

    # Ensure date column is datetime (the parquet already has datetime64)
    if "date" not in df.columns and "timestamp" in df.columns:
        # Convert UTC timestamps to IST dates if needed
        df["date"] = pd.to_datetime(df["timestamp"]).dt.tz_localize("UTC").dt.tz_convert("Asia/Kolkata").dt.date
        df["date"] = pd.to_datetime(df["date"])

    # Sort by symbol and date for consistent processing
    df = df.sort_values(["symbol", "date"]).reset_index(drop=True)

    date_min = df["date"].min()
    date_max = df["date"].max()
    logger.info(f"Date range: {date_min.date()} to {date_max.date()}")

    # ------------------------------------------------------------------
    # 2. Process each symbol
    # ------------------------------------------------------------------
    symbols = df["symbol"].unique()
    total_symbols = len(symbols)
    logger.info(f"Processing {total_symbols} symbols...")

    results = []
    skipped = 0
    t_start = time.time()

    for idx, symbol in enumerate(symbols, 1):
        sym_df = df[df["symbol"] == symbol].copy()

        # Skip thin symbols
        if len(sym_df) < MIN_TRADING_DAYS:
            skipped += 1
            continue

        # Ensure sorted by date
        sym_df = sym_df.sort_values("date").reset_index(drop=True)

        # Compute indicators
        sym_df = process_symbol(sym_df)
        results.append(sym_df)

        # Log progress every 50 symbols
        if idx % 50 == 0 or idx == total_symbols:
            elapsed = time.time() - t_start
            rate = idx / elapsed if elapsed > 0 else 0
            logger.info(
                f"  [{idx}/{total_symbols}] processed {symbol} "
                f"({elapsed:.1f}s elapsed, {rate:.1f} sym/s)"
            )

    if not results:
        logger.error("No symbols had enough data. Aborting.")
        sys.exit(1)

    # ------------------------------------------------------------------
    # 3. Concatenate and save
    # ------------------------------------------------------------------
    logger.info("Concatenating results...")
    out_df = pd.concat(results, ignore_index=True)

    # Ensure output directory exists
    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    logger.info(f"Saving to {args.output}")
    out_df.to_parquet(args.output, index=False)

    # ------------------------------------------------------------------
    # 4. Summary
    # ------------------------------------------------------------------
    elapsed_total = time.time() - t_start
    logger.info("=" * 60)
    logger.info("DONE")
    logger.info(f"  Total rows:        {len(out_df):,}")
    logger.info(f"  Symbols processed: {total_symbols - skipped}")
    logger.info(f"  Symbols skipped:   {skipped} (< {MIN_TRADING_DAYS} trading days)")
    logger.info(f"  Date range:        {out_df['date'].min().date()} to {out_df['date'].max().date()}")
    logger.info(f"  Columns:           {len(out_df.columns)}")
    logger.info(f"  Elapsed:           {elapsed_total:.1f}s")
    logger.info(f"  Output:            {args.output}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
