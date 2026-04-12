#!/usr/bin/env python3
"""Parse Economic Times headlines and match to NSE stock tickers.

Reads the Kaggle "Economic Times Headlines India 2022-2025" CSVs,
matches each headline to stock symbols using regex pattern matching
from ticker_mapping.json, and classifies macro-level headlines.

Input:  backend/data/raw/et_headlines/*.csv  (user downloads from Kaggle)
Depends: backend/data/training/ticker_mapping.json (from 05_build_ticker_mapping.py)
Output: backend/data/training/news_headlines.parquet

Usage:
  python scripts/training/02_collect_news_headlines.py
  python scripts/training/02_collect_news_headlines.py --input data/raw/et_headlines/ --output data/training/news_headlines.parquet
"""

import argparse
import json
import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path

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


def _load_ticker_mapping(path: str) -> dict:
    """Load ticker mapping JSON."""
    with open(path) as f:
        return json.load(f)


def _build_stock_patterns(mapping: dict) -> list[tuple[str, re.Pattern]]:
    """Build compiled regex patterns for each stock symbol.

    Returns list of (symbol, compiled_pattern) sorted by alias length
    descending (longest patterns first to avoid partial matches).
    """
    patterns = []
    for symbol, info in mapping.items():
        if symbol == "__MACRO__":
            continue
        aliases = info.get("aliases", [symbol])
        if not aliases:
            continue
        # Build alternation pattern with word boundaries
        # Sort aliases by length descending within each symbol
        sorted_aliases = sorted(aliases, key=len, reverse=True)
        escaped = [re.escape(a) for a in sorted_aliases]
        pattern_str = r"\b(?:" + "|".join(escaped) + r")\b"
        try:
            compiled = re.compile(pattern_str, re.IGNORECASE)
            patterns.append((symbol, compiled))
        except re.error as e:
            logger.warning(f"Bad regex for {symbol}: {e}")
    return patterns


def _build_macro_patterns(mapping: dict) -> dict[str, re.Pattern]:
    """Build compiled regex patterns for macro categories."""
    macro_info = mapping.get("__MACRO__", {})
    categories = macro_info.get("categories", {})
    patterns = {}
    for category, keywords in categories.items():
        sorted_kw = sorted(keywords, key=len, reverse=True)
        escaped = [re.escape(k) for k in sorted_kw]
        pattern_str = r"\b(?:" + "|".join(escaped) + r")\b"
        patterns[category] = re.compile(pattern_str, re.IGNORECASE)
    return patterns


def _parse_et_csvs(input_dir: str) -> pd.DataFrame:
    """Parse all ET headline CSVs from the input directory.

    Expected CSV columns: Archive, Date (dd-mm-yyyy), Headline, Headline link
    """
    csv_files = sorted(Path(input_dir).glob("*.csv"))
    if not csv_files:
        logger.error(f"No CSV files found in {input_dir}")
        logger.error("Download from: kaggle.com/datasets/abhiaero/economic-times-headlines-india-2022-to-2025")
        sys.exit(1)

    logger.info(f"Found {len(csv_files)} CSV files in {input_dir}")
    dfs = []
    for csv_file in csv_files:
        try:
            df = pd.read_csv(csv_file, encoding="utf-8")
            logger.info(f"  {csv_file.name}: {len(df)} rows")
            dfs.append(df)
        except Exception as e:
            logger.warning(f"  Failed to read {csv_file.name}: {e}")

    if not dfs:
        logger.error("No CSV files could be parsed")
        sys.exit(1)

    combined = pd.concat(dfs, ignore_index=True)

    # Normalize column names
    col_map = {}
    for col in combined.columns:
        lower = col.strip().lower()
        if "date" in lower:
            col_map[col] = "date_raw"
        elif "headline" in lower and "link" in lower:
            col_map[col] = "headline_link"
        elif "headline" in lower:
            col_map[col] = "headline"
        elif "archive" in lower:
            col_map[col] = "archive"
    combined = combined.rename(columns=col_map)

    if "headline" not in combined.columns or "date_raw" not in combined.columns:
        logger.error(f"Expected 'Headline' and 'Date' columns, got: {list(combined.columns)}")
        sys.exit(1)

    # Parse dates - try multiple formats
    def parse_date(d):
        if pd.isna(d):
            return None
        d = str(d).strip()
        for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d-%b-%Y"):
            try:
                return datetime.strptime(d, fmt).date()
            except ValueError:
                continue
        return None

    combined["date"] = combined["date_raw"].apply(parse_date)
    null_dates = combined["date"].isna().sum()
    if null_dates:
        logger.warning(f"  {null_dates} rows had unparseable dates, dropping them")
        combined = combined.dropna(subset=["date"])

    # Drop rows with empty headlines
    combined = combined.dropna(subset=["headline"])
    combined = combined[combined["headline"].str.strip().str.len() > 0]

    # Drop duplicates
    before = len(combined)
    combined = combined.drop_duplicates(subset=["date", "headline"], keep="first")
    dupes = before - len(combined)
    if dupes:
        logger.info(f"  Dropped {dupes} duplicate headlines")

    logger.info(f"Total headlines after parsing: {len(combined)}")
    return combined


def _match_headlines(
    df: pd.DataFrame,
    stock_patterns: list[tuple[str, re.Pattern]],
    macro_patterns: dict[str, re.Pattern],
) -> pd.DataFrame:
    """Match each headline to stock symbols and macro categories."""
    matched_symbols_list = []
    is_macro_list = []
    macro_category_list = []

    total = len(df)
    stock_match_count = 0
    macro_match_count = 0
    neither_count = 0

    for i, headline in enumerate(df["headline"]):
        if i > 0 and i % 50000 == 0:
            logger.info(f"  Processed {i}/{total} headlines...")

        headline_str = str(headline)

        # Match stock symbols
        matched_symbols = []
        for symbol, pattern in stock_patterns:
            if pattern.search(headline_str):
                matched_symbols.append(symbol)

        # Match macro categories
        matched_macros = []
        for category, pattern in macro_patterns.items():
            if pattern.search(headline_str):
                matched_macros.append(category)

        if matched_symbols:
            stock_match_count += 1
        if matched_macros:
            macro_match_count += 1
        if not matched_symbols and not matched_macros:
            neither_count += 1

        matched_symbols_list.append(matched_symbols)
        is_macro_list.append(bool(matched_macros))
        macro_category_list.append("|".join(matched_macros) if matched_macros else None)

    df = df.copy()
    df["matched_symbols"] = matched_symbols_list
    df["is_macro"] = is_macro_list
    df["macro_category"] = macro_category_list
    df["symbol_count"] = df["matched_symbols"].apply(len)

    logger.info(f"Matching results:")
    logger.info(f"  Headlines with stock match: {stock_match_count} ({stock_match_count/total*100:.1f}%)")
    logger.info(f"  Headlines with macro match: {macro_match_count} ({macro_match_count/total*100:.1f}%)")
    logger.info(f"  Headlines with neither: {neither_count} ({neither_count/total*100:.1f}%)")

    return df


def main():
    parser = argparse.ArgumentParser(
        description="Parse ET headlines and match to NSE stock tickers",
        epilog="Requires: ticker_mapping.json from 05_build_ticker_mapping.py",
    )
    parser.add_argument(
        "--input", "-i",
        default=os.path.join(_backend_dir, "data", "raw", "et_headlines"),
        help="Directory with ET headline CSVs (default: data/raw/et_headlines/)",
    )
    parser.add_argument(
        "--mapping",
        default=os.path.join(_backend_dir, "data", "training", "ticker_mapping.json"),
        help="Ticker mapping JSON (default: data/training/ticker_mapping.json)",
    )
    parser.add_argument(
        "--output", "-o",
        default=os.path.join(_backend_dir, "data", "training", "news_headlines.parquet"),
        help="Output parquet path (default: data/training/news_headlines.parquet)",
    )
    parser.add_argument(
        "--keep-unmatched",
        action="store_true",
        help="Keep headlines that match neither stocks nor macro (default: drop them)",
    )
    args = parser.parse_args()

    # Load ticker mapping
    if not os.path.exists(args.mapping):
        logger.error(f"Ticker mapping not found at {args.mapping}")
        logger.error("Run 05_build_ticker_mapping.py first")
        sys.exit(1)

    logger.info("Loading ticker mapping...")
    mapping = _load_ticker_mapping(args.mapping)
    stock_patterns = _build_stock_patterns(mapping)
    macro_patterns = _build_macro_patterns(mapping)
    logger.info(f"  {len(stock_patterns)} stock patterns, {len(macro_patterns)} macro categories")

    # Parse CSVs
    logger.info("Parsing ET headline CSVs...")
    df = _parse_et_csvs(args.input)

    # Match headlines
    logger.info("Matching headlines to tickers...")
    df = _match_headlines(df, stock_patterns, macro_patterns)

    # Filter: drop headlines with no match unless --keep-unmatched
    if not args.keep_unmatched:
        before = len(df)
        df = df[(df["symbol_count"] > 0) | (df["is_macro"])]
        dropped = before - len(df)
        logger.info(f"Dropped {dropped} unmatched headlines ({dropped/before*100:.1f}%)")

    # Prepare output columns
    # Convert matched_symbols list to JSON string for parquet compatibility
    df["matched_symbols"] = df["matched_symbols"].apply(json.dumps)

    output_cols = ["date", "headline", "headline_link", "matched_symbols", "is_macro", "macro_category"]
    available_cols = [c for c in output_cols if c in df.columns]
    df_out = df[available_cols].sort_values("date").reset_index(drop=True)

    # Save
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    df_out.to_parquet(args.output, index=False)

    # Summary
    logger.info(f"\nSaved to {args.output}")
    logger.info(f"  Total headlines: {len(df_out)}")
    logger.info(f"  Date range: {df_out['date'].min()} to {df_out['date'].max()}")
    logger.info(f"  Stock-matched: {(df_out['matched_symbols'] != '[]').sum()}")
    logger.info(f"  Macro-only: {((df_out['matched_symbols'] == '[]') & df_out['is_macro']).sum()}")

    # Top matched symbols
    all_symbols = []
    for syms_json in df_out["matched_symbols"]:
        all_symbols.extend(json.loads(syms_json))
    if all_symbols:
        from collections import Counter
        top = Counter(all_symbols).most_common(20)
        logger.info(f"  Top 20 matched symbols:")
        for sym, count in top:
            logger.info(f"    {sym}: {count}")


if __name__ == "__main__":
    main()
