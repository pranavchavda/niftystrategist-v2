#!/usr/bin/env python3
"""Assemble point-in-time training snapshots from all intermediate data sources.

Joins TA indicators, news headlines, earnings announcements, and macro data
into a single parquet with one row per (symbol, date). Each row contains
only information that was knowable at 9:15 AM IST on that trading day,
plus outcome labels computed from future prices.

Inputs (in backend/data/training/):
  - ta_indicators.parquet       (from 01_compute_ta_indicators.py)
  - news_headlines.parquet      (from 02_collect_news_headlines.py)
  - earnings_announcements.parquet (from 03_collect_earnings.py)
  - macro_daily.parquet         (from 04_collect_macro.py)

Output: backend/data/training/snapshots_v1.parquet

Usage:
  python scripts/training/06_assemble_snapshots.py
  python scripts/training/06_assemble_snapshots.py --stats
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import date, timedelta

import numpy as np
import pandas as pd

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

# Paths
TRAINING_DIR = os.path.join(_backend_dir, "data", "training")
TA_PATH = os.path.join(TRAINING_DIR, "ta_indicators.parquet")
NEWS_PATH = os.path.join(TRAINING_DIR, "news_headlines.parquet")
EARNINGS_PATH = os.path.join(TRAINING_DIR, "earnings_announcements.parquet")
MACRO_PATH = os.path.join(TRAINING_DIR, "macro_daily.parquet")

# News headline lookback window (calendar days before T)
NEWS_LOOKBACK_DAYS = 3

# Earnings season months (Jan/Feb, Apr/May, Jul/Aug, Oct/Nov)
EARNINGS_SEASON_MONTHS = {1, 2, 4, 5, 7, 8, 10, 11}


def load_ta() -> pd.DataFrame:
    """Load TA indicators parquet."""
    logger.info(f"Loading TA indicators from {TA_PATH}")
    df = pd.read_parquet(TA_PATH)
    # Ensure date is a date object for joining
    if hasattr(df["date"].dtype, "tz"):
        df["date"] = df["date"].dt.tz_localize(None)
    df["date"] = pd.to_datetime(df["date"]).dt.date
    logger.info(f"  {len(df):,} rows, {df['symbol'].nunique()} symbols")
    return df


def load_news() -> pd.DataFrame | None:
    """Load news headlines parquet. Returns None if not available."""
    if not os.path.exists(NEWS_PATH):
        logger.warning(f"News headlines not found at {NEWS_PATH} — skipping news features")
        return None
    logger.info(f"Loading news headlines from {NEWS_PATH}")
    df = pd.read_parquet(NEWS_PATH)
    df["date"] = pd.to_datetime(df["date"]).dt.date
    logger.info(f"  {len(df):,} headlines, {df['date'].min()} to {df['date'].max()}")
    return df


def load_earnings() -> pd.DataFrame | None:
    """Load earnings announcements parquet. Returns None if not available."""
    if not os.path.exists(EARNINGS_PATH):
        logger.warning(f"Earnings data not found at {EARNINGS_PATH} — skipping earnings features")
        return None
    logger.info(f"Loading earnings from {EARNINGS_PATH}")
    df = pd.read_parquet(EARNINGS_PATH)
    df["announcement_date"] = pd.to_datetime(df["announcement_date"]).dt.date
    logger.info(f"  {len(df):,} announcements, {df['symbol'].nunique()} symbols")
    return df


def load_macro() -> pd.DataFrame | None:
    """Load macro daily parquet. Returns None if not available."""
    if not os.path.exists(MACRO_PATH):
        logger.warning(f"Macro data not found at {MACRO_PATH} — skipping macro features")
        return None
    logger.info(f"Loading macro data from {MACRO_PATH}")
    df = pd.read_parquet(MACRO_PATH)
    # Ensure date is a date object
    if not isinstance(df["date"].iloc[0], date):
        df["date"] = pd.to_datetime(df["date"]).dt.date
    logger.info(f"  {len(df):,} rows, {df['date'].min()} to {df['date'].max()}")
    return df


def build_news_features(spine: pd.DataFrame, news_df: pd.DataFrame) -> pd.DataFrame:
    """For each (symbol, date) in spine, aggregate headlines from the past N days.

    Point-in-time rule: For trading day T, we include headlines from
    T-NEWS_LOOKBACK_DAYS to T-1 (calendar days). Day T headlines are
    excluded since we can't know the full day's news at 9:15 AM.

    Returns DataFrame with columns: symbol, date, news_stock_headlines,
    news_macro_headlines, news_headline_count.
    """
    logger.info("Building news features...")
    t_start = time.time()

    # Parse matched_symbols JSON strings
    news_df = news_df.copy()
    news_df["symbols_list"] = news_df["matched_symbols"].apply(
        lambda x: json.loads(x) if isinstance(x, str) else x
    )

    # Separate stock-specific and macro headlines
    stock_news = news_df[news_df["symbols_list"].apply(len) > 0].copy()
    macro_news = news_df[news_df["is_macro"] == True].copy()  # noqa: E712

    # Build date-indexed lookups for fast range queries
    # For stock news: expand to one row per (symbol, date, headline)
    stock_expanded = []
    for _, row in stock_news.iterrows():
        for sym in row["symbols_list"]:
            stock_expanded.append({
                "symbol": sym,
                "news_date": row["date"],
                "headline": row["headline"],
            })
    stock_exp_df = pd.DataFrame(stock_expanded) if stock_expanded else pd.DataFrame(
        columns=["symbol", "news_date", "headline"]
    )

    macro_headlines_by_date = {}
    for _, row in macro_news.iterrows():
        d = row["date"]
        if d not in macro_headlines_by_date:
            macro_headlines_by_date[d] = []
        macro_headlines_by_date[d].append(row["headline"])

    # For each (symbol, date) in spine, collect headlines
    results = []
    unique_pairs = spine[["symbol", "date"]].drop_duplicates()

    for i, (symbol, trade_date) in enumerate(zip(unique_pairs["symbol"], unique_pairs["date"])):
        if i > 0 and i % 200000 == 0:
            logger.info(f"  News features: {i:,}/{len(unique_pairs):,} pairs...")

        # Date window: T-N to T-1 (calendar days)
        window_start = trade_date - timedelta(days=NEWS_LOOKBACK_DAYS)
        window_end = trade_date - timedelta(days=1)

        # Stock-specific headlines
        stock_hl = []
        if len(stock_exp_df) > 0:
            mask = (
                (stock_exp_df["symbol"] == symbol)
                & (stock_exp_df["news_date"] >= window_start)
                & (stock_exp_df["news_date"] <= window_end)
            )
            stock_hl = stock_exp_df.loc[mask, "headline"].tolist()

        # Macro headlines
        macro_hl = []
        for d in pd.date_range(window_start, window_end):
            d_date = d.date()
            if d_date in macro_headlines_by_date:
                macro_hl.extend(macro_headlines_by_date[d_date])

        results.append({
            "symbol": symbol,
            "date": trade_date,
            "news_stock_headlines": "|".join(stock_hl) if stock_hl else "",
            "news_macro_headlines": "|".join(macro_hl) if macro_hl else "",
            "news_headline_count": len(stock_hl) + len(macro_hl),
        })

    elapsed = time.time() - t_start
    logger.info(f"  News features built in {elapsed:.1f}s")

    return pd.DataFrame(results)


def build_earnings_features(spine: pd.DataFrame, earnings_df: pd.DataFrame) -> pd.DataFrame:
    """For each (symbol, date) compute earnings-related features.

    Features:
    - days_since_earnings: business days since most recent announcement before T
    - is_earnings_week: True if earnings announced within past 5 trading days
    - earnings_announced_yesterday: True if announced on T-1
    - in_earnings_season: True if month is in EARNINGS_SEASON_MONTHS
    """
    logger.info("Building earnings features...")
    t_start = time.time()

    # Group announcements by symbol, sorted by date
    earnings_by_symbol = {}
    for sym, grp in earnings_df.groupby("symbol"):
        earnings_by_symbol[sym] = sorted(grp["announcement_date"].unique())

    results = []
    unique_pairs = spine[["symbol", "date"]].drop_duplicates()

    for i, (symbol, trade_date) in enumerate(zip(unique_pairs["symbol"], unique_pairs["date"])):
        if i > 0 and i % 200000 == 0:
            logger.info(f"  Earnings features: {i:,}/{len(unique_pairs):,} pairs...")

        ann_dates = earnings_by_symbol.get(symbol, [])

        # Find most recent announcement before trade_date
        days_since = None
        earnings_yesterday = False

        # Binary search for efficiency
        import bisect
        idx = bisect.bisect_left(ann_dates, trade_date)
        if idx > 0:
            last_ann = ann_dates[idx - 1]
            delta = (trade_date - last_ann).days
            # Approximate business days (weekdays only)
            days_since = sum(
                1 for d in range(delta)
                if (trade_date - timedelta(days=d + 1)).weekday() < 5
            ) if delta <= 30 else delta  # Exact for recent, approximate for old
            earnings_yesterday = (last_ann == trade_date - timedelta(days=1))

        results.append({
            "symbol": symbol,
            "date": trade_date,
            "days_since_earnings": days_since,
            "is_earnings_week": days_since is not None and days_since <= 5,
            "earnings_announced_yesterday": earnings_yesterday,
            "in_earnings_season": trade_date.month in EARNINGS_SEASON_MONTHS,
        })

    elapsed = time.time() - t_start
    logger.info(f"  Earnings features built in {elapsed:.1f}s")

    return pd.DataFrame(results)


def add_outcome_labels(df: pd.DataFrame) -> pd.DataFrame:
    """Add target labels using future price data.

    For each (symbol, date=T):
    - target_return_1d: (close_T - open_T) / open_T  (intraday return)
    - target_return_5d: (close_T+4 - open_T) / open_T (5-day return from open)
    - target_direction_1d: "up" or "down"
    - target_direction_5d: "up" or "down"

    Note: These use the CURRENT day's prices (close) and FUTURE prices (T+4 close),
    which are NOT features — they are training labels only.
    """
    logger.info("Computing outcome labels...")

    # Use _orig_open and _orig_close (unshifted) for outcome labels.
    # These are the ACTUAL prices for day T, not the shifted T-1 features.
    # _orig_open = open price of day T (knowable at 9:15 AM)
    # _orig_close = close price of day T (future — training label only)

    df = df.sort_values(["symbol", "date"]).reset_index(drop=True)

    df["target_return_1d"] = np.nan
    df["target_return_5d"] = np.nan

    for symbol, grp in df.groupby("symbol"):
        idx = grp.index
        opens = grp["_orig_open"].values
        closes = grp["_orig_close"].values

        # 1-day return: (close_T - open_T) / open_T
        with np.errstate(divide="ignore", invalid="ignore"):
            intraday = (closes - opens) / opens
        df.loc[idx, "target_return_1d"] = intraday

        # 5-day return: (close_{T+4} - open_T) / open_T
        if len(closes) > 4:
            future_close = np.empty(len(closes))
            future_close[:] = np.nan
            future_close[:-4] = closes[4:]
            with np.errstate(divide="ignore", invalid="ignore"):
                five_day = (future_close - opens) / opens
            df.loc[idx, "target_return_5d"] = five_day

    # Direction labels
    df["target_direction_1d"] = np.where(df["target_return_1d"] > 0, "up", "down")
    df["target_direction_5d"] = np.where(df["target_return_5d"] > 0, "up", "down")

    # Set direction to NaN where return is NaN
    df.loc[df["target_return_1d"].isna(), "target_direction_1d"] = None
    df.loc[df["target_return_5d"].isna(), "target_direction_5d"] = None

    logger.info(f"  1d targets: {df['target_return_1d'].notna().sum():,} non-null")
    logger.info(f"  5d targets: {df['target_return_5d'].notna().sum():,} non-null")

    return df


def main():
    parser = argparse.ArgumentParser(
        description="Assemble point-in-time training snapshots",
        epilog="Requires: ta_indicators.parquet + optionally news, earnings, macro parquets",
    )
    parser.add_argument(
        "--output", "-o",
        default=os.path.join(TRAINING_DIR, "snapshots_v1.parquet"),
        help="Output parquet path",
    )
    parser.add_argument(
        "--stats", action="store_true",
        help="Print detailed stats after assembly",
    )
    parser.add_argument(
        "--no-news", action="store_true",
        help="Skip news features even if available",
    )
    parser.add_argument(
        "--no-earnings", action="store_true",
        help="Skip earnings features even if available",
    )
    args = parser.parse_args()

    t_total = time.time()

    # ----------------------------------------------------------------
    # 1. Load TA indicators (required — this is the spine)
    # ----------------------------------------------------------------
    if not os.path.exists(TA_PATH):
        logger.error(f"TA indicators not found at {TA_PATH}")
        logger.error("Run 01_compute_ta_indicators.py first")
        sys.exit(1)

    ta_df = load_ta()

    # The spine: for each (symbol, date) we build a snapshot.
    # Point-in-time: row T in ta_df contains indicators computed from data
    # through T's close. For the snapshot at date T, we want indicators
    # through T-1. So we shift indicator columns by 1.
    #
    # IMPORTANT: We keep the ORIGINAL OHLCV for outcome label computation
    # (open_T, close_T, close_T+4) — these are NOT features, just labels.
    # The shifted versions become the features (what was knowable at 9:15 AM).
    logger.info("Applying point-in-time shift (T-1 indicators for date T)...")
    ta_df = ta_df.sort_values(["symbol", "date"]).reset_index(drop=True)

    # Save original OHLCV for outcome labels before shifting
    ta_df["_orig_open"] = ta_df["open"]
    ta_df["_orig_close"] = ta_df["close"]

    # Columns NOT to shift:
    # - symbol, date: identity
    # - _orig_open, _orig_close: for outcome labels
    non_shift_cols = {"symbol", "date", "_orig_open", "_orig_close"}
    shift_cols = [c for c in ta_df.columns if c not in non_shift_cols]

    shifted_parts = []
    for symbol, grp in ta_df.groupby("symbol"):
        grp = grp.copy()
        grp[shift_cols] = grp[shift_cols].shift(1)
        shifted_parts.append(grp)

    spine = pd.concat(shifted_parts, ignore_index=True)

    # After shift: open/close/high/low/volume are now T-1's values (features).
    # _orig_open/_orig_close are T's actual values (for labels).
    # First row per symbol will have NaN features — keep for now, filter later.
    logger.info(f"  Spine: {len(spine):,} rows after shift")

    # ----------------------------------------------------------------
    # 2. Join macro data
    # ----------------------------------------------------------------
    macro_df = load_macro()
    if macro_df is not None:
        # Convert spine dates to same type for merge
        spine_dates = pd.DataFrame({"date": spine["date"].unique()})
        macro_merged = spine_dates.merge(
            macro_df, on="date", how="left"
        )
        # Forward-fill any gaps in macro
        macro_merged = macro_merged.sort_values("date")
        fill_cols = [c for c in macro_merged.columns if c != "date"]
        macro_merged[fill_cols] = macro_merged[fill_cols].ffill()

        spine = spine.merge(macro_merged, on="date", how="left")
        logger.info(f"  After macro join: {len(spine):,} rows, {len(spine.columns)} cols")

    # ----------------------------------------------------------------
    # 3. Join news headlines
    # ----------------------------------------------------------------
    if not args.no_news:
        news_df = load_news()
        if news_df is not None:
            news_features = build_news_features(spine, news_df)
            spine = spine.merge(news_features, on=["symbol", "date"], how="left")
            # Fill missing news with empty strings / 0
            for col in ["news_stock_headlines", "news_macro_headlines"]:
                if col in spine.columns:
                    spine[col] = spine[col].fillna("")
            if "news_headline_count" in spine.columns:
                spine["news_headline_count"] = spine["news_headline_count"].fillna(0).astype(int)
            logger.info(f"  After news join: {len(spine):,} rows, {len(spine.columns)} cols")

    # ----------------------------------------------------------------
    # 4. Join earnings features
    # ----------------------------------------------------------------
    if not args.no_earnings:
        earnings_df = load_earnings()
        if earnings_df is not None:
            earnings_features = build_earnings_features(spine, earnings_df)
            spine = spine.merge(earnings_features, on=["symbol", "date"], how="left")
            # Fill missing earnings features
            if "days_since_earnings" in spine.columns:
                spine["days_since_earnings"] = spine["days_since_earnings"].fillna(-1).astype(int)
            for col in ["is_earnings_week", "earnings_announced_yesterday"]:
                if col in spine.columns:
                    spine[col] = spine[col].fillna(False).astype(bool)
            if "in_earnings_season" in spine.columns:
                spine["in_earnings_season"] = spine["in_earnings_season"].fillna(False).astype(bool)
            logger.info(f"  After earnings join: {len(spine):,} rows, {len(spine.columns)} cols")

    # ----------------------------------------------------------------
    # 5. Add outcome labels
    # ----------------------------------------------------------------
    spine = add_outcome_labels(spine)

    # ----------------------------------------------------------------
    # 6. Quality filters
    # ----------------------------------------------------------------
    logger.info("Applying quality filters...")
    before = len(spine)

    # Drop rows with zero volume (no trading activity)
    if "volume" in spine.columns:
        spine = spine[spine["volume"] > 0]
        logger.info(f"  After volume > 0 filter: {len(spine):,} rows (dropped {before - len(spine):,})")

    # Drop rows with null 1d target (last row per symbol has no close, first row after shift has no T-1)
    before = len(spine)
    spine = spine[spine["target_return_1d"].notna()]
    logger.info(f"  After null target filter: {len(spine):,} rows (dropped {before - len(spine):,})")

    # Drop rows where > 50% of TA indicators are NaN (warm-up period)
    ta_cols = [c for c in spine.columns if c.startswith(("momentum_", "trend_", "volatility_", "volume_", "others_"))]
    if ta_cols:
        before = len(spine)
        nan_pct = spine[ta_cols].isna().mean(axis=1)
        spine = spine[nan_pct <= 0.5]
        logger.info(f"  After TA NaN filter (<=50%): {len(spine):,} rows (dropped {before - len(spine):,})")

    spine = spine.reset_index(drop=True)

    # Drop helper columns used for outcome label computation
    drop_cols = [c for c in spine.columns if c.startswith("_orig_")]
    if drop_cols:
        spine = spine.drop(columns=drop_cols)

    # ----------------------------------------------------------------
    # 7. Save
    # ----------------------------------------------------------------
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    logger.info(f"Saving to {args.output}...")
    spine.to_parquet(args.output, index=False)

    # ----------------------------------------------------------------
    # 8. Summary
    # ----------------------------------------------------------------
    elapsed = time.time() - t_total
    logger.info("=" * 60)
    logger.info("ASSEMBLY COMPLETE")
    logger.info("=" * 60)
    logger.info(f"  Total rows:     {len(spine):,}")
    logger.info(f"  Symbols:        {spine['symbol'].nunique()}")
    logger.info(f"  Date range:     {spine['date'].min()} to {spine['date'].max()}")
    logger.info(f"  Columns:        {len(spine.columns)}")
    logger.info(f"  File size:      {os.path.getsize(args.output) / 1e6:.1f} MB")
    logger.info(f"  Elapsed:        {elapsed:.1f}s")

    if args.stats:
        logger.info("")
        logger.info("DETAILED STATS:")
        logger.info(f"  Target direction_1d distribution:")
        if "target_direction_1d" in spine.columns:
            dist = spine["target_direction_1d"].value_counts()
            for k, v in dist.items():
                logger.info(f"    {k}: {v:,} ({v/len(spine)*100:.1f}%)")

        logger.info(f"  News coverage:")
        if "news_headline_count" in spine.columns:
            has_news = (spine["news_headline_count"] > 0).sum()
            logger.info(f"    Rows with news: {has_news:,} ({has_news/len(spine)*100:.1f}%)")
        else:
            logger.info(f"    No news data available")

        logger.info(f"  Earnings coverage:")
        if "days_since_earnings" in spine.columns:
            has_earnings = (spine["days_since_earnings"] >= 0).sum()
            logger.info(f"    Rows with earnings data: {has_earnings:,} ({has_earnings/len(spine)*100:.1f}%)")
        else:
            logger.info(f"    No earnings data available")

        logger.info(f"  Null percentages by column group:")
        col_groups = {
            "price": ["open", "close", "high", "low", "volume", "prev_close"],
            "returns": ["return_1d", "return_5d", "return_20d"],
            "ta_momentum": [c for c in spine.columns if c.startswith("momentum_")],
            "ta_trend": [c for c in spine.columns if c.startswith("trend_")],
            "ta_volatility": [c for c in spine.columns if c.startswith("volatility_")],
            "macro": [c for c in spine.columns if c.startswith(("usd_", "crude_", "rbi_", "nifty"))],
            "targets": ["target_return_1d", "target_return_5d"],
        }
        for group_name, cols in col_groups.items():
            existing = [c for c in cols if c in spine.columns]
            if existing:
                null_pct = spine[existing].isna().mean().mean() * 100
                logger.info(f"    {group_name:20s}: {null_pct:.2f}% null (avg across {len(existing)} cols)")


if __name__ == "__main__":
    main()
