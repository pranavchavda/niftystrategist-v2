#!/usr/bin/env python3
"""Collect daily macroeconomic indicators and save to parquet.

Gathers USD/INR exchange rate, crude oil (Brent), RBI repo rate, and
Nifty 50 / Nifty Bank index levels. Computes percentage changes and
forward-fills to cover weekends/holidays. Output is a single parquet
file with one row per calendar day, suitable for joining to stock-level
training snapshots.

Output: backend/data/training/macro_daily.parquet

Usage:
  python scripts/training/04_collect_macro.py
  python scripts/training/04_collect_macro.py --output data/training/macro_daily.parquet
"""

import argparse
import logging
import os
import sys
from datetime import date, timedelta

import pandas as pd
import requests

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

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

START_DATE = date(2016, 1, 1)

NIFTY500_PARQUET = os.path.join(_backend_dir, "data", "nse_nifty500_10y.parquet")
BRENT_CRUDE_CSV = os.path.join(_backend_dir, "data", "raw", "brent_crude.csv")

FRANKFURTER_URL = "https://api.frankfurter.dev/v1/{start}..{end}?from=USD&to=INR"

RBI_REPO_RATE_CHANGES = [
    ("2016-04-05", 6.50), ("2016-10-04", 6.25), ("2017-08-02", 6.00),
    ("2018-06-06", 6.25), ("2018-08-01", 6.50), ("2019-02-07", 6.25),
    ("2019-04-04", 6.00), ("2019-06-06", 5.75), ("2019-08-07", 5.40),
    ("2019-10-04", 5.15), ("2020-03-27", 4.40), ("2020-05-22", 4.00),
    ("2022-05-04", 4.40), ("2022-06-08", 4.90), ("2022-08-05", 5.40),
    ("2022-09-30", 5.90), ("2022-12-07", 6.25), ("2023-02-08", 6.50),
    ("2025-02-07", 6.25), ("2025-04-09", 6.00), ("2025-06-06", 5.75),
]

# Symbols in the nse_nifty500_10y.parquet file
NIFTY50_SYMBOL = "NIFTY_50"
NIFTYBANK_SYMBOL = "NIFTY_BANK"


# ---------------------------------------------------------------------------
# Data collection functions
# ---------------------------------------------------------------------------

def fetch_usd_inr(start: date, end: date) -> pd.DataFrame:
    """Fetch USD/INR from Frankfurter API in yearly chunks."""
    logger.info("Fetching USD/INR exchange rate from Frankfurter API...")
    all_records: list[dict] = []
    chunk_start = start

    while chunk_start <= end:
        chunk_end = min(date(chunk_start.year, 12, 31), end)
        url = FRANKFURTER_URL.format(start=chunk_start.isoformat(), end=chunk_end.isoformat())
        logger.info(f"  {chunk_start} .. {chunk_end}")

        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        rates = data.get("rates", {})
        for dt_str, rate_dict in rates.items():
            inr_value = rate_dict.get("INR")
            if inr_value is not None:
                all_records.append({"date": pd.Timestamp(dt_str), "usd_inr": float(inr_value)})

        chunk_start = date(chunk_start.year + 1, 1, 1)

    if not all_records:
        logger.warning("No USD/INR data fetched")
        return pd.DataFrame(columns=["date", "usd_inr"])

    df = pd.DataFrame(all_records).sort_values("date").reset_index(drop=True)
    logger.info(f"  Got {len(df)} USD/INR data points ({df['date'].min().date()} to {df['date'].max().date()})")
    return df


def load_brent_crude() -> pd.DataFrame:
    """Load Brent crude prices from a pre-downloaded CSV.

    Expected columns: some date column and some price column.
    Tries common column name patterns.
    """
    if not os.path.exists(BRENT_CRUDE_CSV):
        logger.warning(f"Brent crude CSV not found at {BRENT_CRUDE_CSV} -- skipping")
        return pd.DataFrame(columns=["date", "crude_brent_usd"])

    logger.info(f"Loading Brent crude from {BRENT_CRUDE_CSV}")
    df = pd.read_csv(BRENT_CRUDE_CSV)
    logger.info(f"  Columns found: {list(df.columns)}")

    # Identify date column
    date_col = None
    for candidate in ["Date", "date", "DATE", "Day"]:
        if candidate in df.columns:
            date_col = candidate
            break
    if date_col is None:
        # Take first column as date
        date_col = df.columns[0]
        logger.info(f"  Using first column '{date_col}' as date")

    # Identify price column
    price_col = None
    for candidate in ["Price", "price", "PRICE", "Close", "close", "Value", "value"]:
        if candidate in df.columns:
            price_col = candidate
            break
    if price_col is None:
        # Take the second column (or last numeric column) as price
        numeric_cols = df.select_dtypes(include="number").columns
        if len(numeric_cols) > 0:
            price_col = numeric_cols[0]
        else:
            # Last column as fallback
            price_col = df.columns[-1]
        logger.info(f"  Using column '{price_col}' as price")

    result = pd.DataFrame({
        "date": pd.to_datetime(df[date_col], dayfirst=False, format="mixed"),
        "crude_brent_usd": pd.to_numeric(df[price_col], errors="coerce"),
    })
    result = result.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    logger.info(f"  Got {len(result)} crude data points ({result['date'].min().date()} to {result['date'].max().date()})")
    return result


def build_repo_rate(start: date, end: date) -> pd.DataFrame:
    """Build daily RBI repo rate series from change dates, forward-filled."""
    logger.info("Building RBI repo rate series...")

    # Create a series of change points
    records = []
    for dt_str, rate in RBI_REPO_RATE_CHANGES:
        records.append({"date": pd.Timestamp(dt_str), "rbi_repo_rate": rate})

    changes_df = pd.DataFrame(records)

    # Full daily index
    date_range = pd.date_range(start=start, end=end, freq="D")
    daily = pd.DataFrame({"date": date_range})

    # Merge and forward-fill
    daily = daily.merge(changes_df, on="date", how="left")

    # For dates before the first change, use the first known rate
    # (the rate effective at the start of our window)
    first_change_date = changes_df["date"].min()
    # Find the rate applicable before our start date
    pre_start_rates = changes_df[changes_df["date"] <= pd.Timestamp(start)]
    if len(pre_start_rates) > 0:
        initial_rate = pre_start_rates.iloc[-1]["rbi_repo_rate"]
    else:
        # Use the first rate from the list with earliest date before our range
        # Find the most recent rate change on or before start
        all_before = [(pd.Timestamp(d), r) for d, r in RBI_REPO_RATE_CHANGES if pd.Timestamp(d) <= pd.Timestamp(start)]
        if all_before:
            initial_rate = all_before[-1][1]
        else:
            # Start date is before any rate change -- use first known rate
            initial_rate = RBI_REPO_RATE_CHANGES[0][1]
            logger.info(f"  Start date is before first rate change; using {initial_rate}%")

    # Set the first day to the initial rate so ffill propagates correctly
    daily.loc[daily.index[0], "rbi_repo_rate"] = initial_rate
    daily["rbi_repo_rate"] = daily["rbi_repo_rate"].ffill()

    # Mark days where the rate changed
    daily["repo_rate_changed"] = daily["date"].isin(changes_df["date"])

    logger.info(f"  Built {len(daily)} daily repo rate values, {daily['repo_rate_changed'].sum()} change dates")
    return daily


def load_index_levels() -> pd.DataFrame:
    """Extract Nifty 50 and Nifty Bank close prices from the Nifty 500 parquet."""
    if not os.path.exists(NIFTY500_PARQUET):
        logger.warning(f"Nifty 500 parquet not found at {NIFTY500_PARQUET} -- skipping index levels")
        return pd.DataFrame(columns=["date", "nifty50_close", "niftybank_close"])

    logger.info(f"Loading index levels from {NIFTY500_PARQUET}")
    df = pd.read_parquet(NIFTY500_PARQUET)

    # Extract Nifty 50
    nifty50 = df[df["symbol"] == NIFTY50_SYMBOL][["date", "close"]].copy()
    nifty50 = nifty50.rename(columns={"close": "nifty50_close"})
    logger.info(f"  Nifty 50: {len(nifty50)} rows")

    # Extract Nifty Bank
    niftybank = df[df["symbol"] == NIFTYBANK_SYMBOL][["date", "close"]].copy()
    niftybank = niftybank.rename(columns={"close": "niftybank_close"})
    logger.info(f"  Nifty Bank: {len(niftybank)} rows")

    if nifty50.empty and niftybank.empty:
        available = df["symbol"].unique()
        index_like = [s for s in available if "nifty" in s.lower()]
        logger.warning(f"  No index data found. Index-like symbols: {index_like}")
        return pd.DataFrame(columns=["date", "nifty50_close", "niftybank_close"])

    # Merge on date
    if not nifty50.empty and not niftybank.empty:
        result = nifty50.merge(niftybank, on="date", how="outer")
    elif not nifty50.empty:
        result = nifty50.copy()
        result["niftybank_close"] = pd.NA
    else:
        result = niftybank.copy()
        result["nifty50_close"] = pd.NA

    result = result.sort_values("date").reset_index(drop=True)
    logger.info(f"  Combined index data: {len(result)} rows")
    return result


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------

def add_pct_changes(df: pd.DataFrame, col: str, prefix: str, periods: list[int]) -> pd.DataFrame:
    """Add N-day percentage change columns for a given series."""
    for n in periods:
        col_name = f"{prefix}_change_{n}d" if "return" not in prefix else f"{prefix}_{n}d"
        df[col_name] = df[col].pct_change(periods=n, fill_method=None) * 100.0
    return df


def assemble_macro(
    usd_inr: pd.DataFrame,
    crude: pd.DataFrame,
    repo: pd.DataFrame,
    indices: pd.DataFrame,
    start: date,
    end: date,
) -> pd.DataFrame:
    """Merge all series into a single daily DataFrame."""
    logger.info("Assembling macro DataFrame...")

    # Full daily date range
    date_range = pd.date_range(start=start, end=end, freq="D")
    master = pd.DataFrame({"date": date_range})

    # Merge USD/INR
    if not usd_inr.empty:
        master = master.merge(usd_inr, on="date", how="left")
    else:
        master["usd_inr"] = pd.NA

    # Merge crude
    if not crude.empty:
        master = master.merge(crude, on="date", how="left")
    else:
        master["crude_brent_usd"] = pd.NA

    # Merge repo rate (already full daily range, but re-merge for safety)
    if not repo.empty:
        master = master.merge(repo[["date", "rbi_repo_rate", "repo_rate_changed"]], on="date", how="left")
    else:
        master["rbi_repo_rate"] = pd.NA
        master["repo_rate_changed"] = False

    # Merge index levels
    if not indices.empty:
        master = master.merge(indices, on="date", how="left")
    else:
        master["nifty50_close"] = pd.NA
        master["niftybank_close"] = pd.NA

    # Forward-fill all series (weekends/holidays get the last known value)
    fill_cols = ["usd_inr", "crude_brent_usd", "rbi_repo_rate", "nifty50_close", "niftybank_close"]
    for col in fill_cols:
        if col in master.columns:
            master[col] = master[col].ffill()

    # Ensure repo_rate_changed doesn't get ffilled (it's a boolean event marker)
    if "repo_rate_changed" in master.columns:
        master["repo_rate_changed"] = master["repo_rate_changed"].fillna(False).astype(bool)

    # Compute percentage changes (on forward-filled data)
    if "usd_inr" in master.columns:
        master = add_pct_changes(master, "usd_inr", "usd_inr", [1, 5])

    if "crude_brent_usd" in master.columns:
        master = add_pct_changes(master, "crude_brent_usd", "crude", [1, 5])

    if "nifty50_close" in master.columns:
        master = add_pct_changes(master, "nifty50_close", "nifty50_return", [1, 5, 20])

    # Convert date to date type (not datetime)
    master["date"] = master["date"].dt.date

    # Reorder columns
    col_order = [
        "date",
        "usd_inr", "usd_inr_change_1d", "usd_inr_change_5d",
        "crude_brent_usd", "crude_change_1d", "crude_change_5d",
        "rbi_repo_rate", "repo_rate_changed",
        "nifty50_close", "nifty50_return_1d", "nifty50_return_5d", "nifty50_return_20d",
        "niftybank_close",
    ]
    # Only include columns that exist
    col_order = [c for c in col_order if c in master.columns]
    master = master[col_order]

    logger.info(f"  Assembled {len(master)} rows, {len(master.columns)} columns")
    return master


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Collect daily macroeconomic indicators for training data",
        epilog="Example: python scripts/training/04_collect_macro.py",
    )
    parser.add_argument(
        "--output", "-o",
        default=os.path.join(_backend_dir, "data", "training", "macro_daily.parquet"),
        help="Output parquet path (default: data/training/macro_daily.parquet)",
    )
    args = parser.parse_args()

    end_date = date.today()

    # 1. Fetch USD/INR
    usd_inr = fetch_usd_inr(START_DATE, end_date)

    # 2. Load Brent crude
    crude = load_brent_crude()

    # 3. Build repo rate
    repo = build_repo_rate(START_DATE, end_date)

    # 4. Load index levels
    indices = load_index_levels()

    # 5. Assemble
    macro = assemble_macro(usd_inr, crude, repo, indices, START_DATE, end_date)

    # 6. Save
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    macro.to_parquet(args.output, index=False)
    logger.info(f"Saved to {args.output}")

    # 7. Summary stats
    logger.info("=" * 60)
    logger.info("SUMMARY")
    logger.info("=" * 60)
    logger.info(f"  Date range: {macro['date'].min()} to {macro['date'].max()}")
    logger.info(f"  Total rows: {len(macro)}")
    logger.info(f"  Columns: {list(macro.columns)}")
    logger.info("")
    logger.info("  Null percentages:")
    for col in macro.columns:
        if col == "date":
            continue
        null_pct = macro[col].isna().sum() / len(macro) * 100
        logger.info(f"    {col:30s} {null_pct:6.2f}%")


if __name__ == "__main__":
    main()
