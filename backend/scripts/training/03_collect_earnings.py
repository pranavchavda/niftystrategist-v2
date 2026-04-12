#!/usr/bin/env python3
"""Collect earnings announcement dates from NSE corporate announcements API.

Fetches corporate announcements for NSE equities, filtered for financial
result disclosures. Used to determine earnings timing for each stock
(point-in-time: was an earnings result knowable on a given date?).

Source: https://www.nseindia.com/api/corporate-announcements
Output: backend/data/training/earnings_announcements.parquet

Usage:
  python scripts/training/03_collect_earnings.py
  python scripts/training/03_collect_earnings.py --from-date 2020-01-01 --to-date 2026-04-01
  python scripts/training/03_collect_earnings.py --resume
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

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

# NSE API config
NSE_BASE_URL = "https://www.nseindia.com"
NSE_API_URL = f"{NSE_BASE_URL}/api/corporate-announcements"
REQUEST_DELAY = 2.0  # seconds between requests
MAX_RETRIES = 3
RETRY_BACKOFF = 5  # seconds

# Announcement types that indicate earnings/financial results
EARNINGS_DESCRIPTIONS = {
    "Financial Result Updates",
    "Financial Results",
    "Integrated Filing- Financial",
    "Outcome of Board Meeting",
    "Board Meeting Outcome for Financial Results",
    "Board Meeting Intimation for Financial Results",
}

# NSE requires realistic browser headers + session cookies
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.nseindia.com/companies-listing/corporate-filings-announcements",
}


def _create_session() -> requests.Session:
    """Create a session with NSE cookies."""
    session = requests.Session()
    session.headers.update(HEADERS)
    # Hit the main page first to get cookies
    try:
        resp = session.get(NSE_BASE_URL, timeout=10)
        resp.raise_for_status()
        logger.info("NSE session established")
    except Exception as e:
        logger.warning(f"Failed to establish NSE session: {e}")
    return session


def _refresh_session(session: requests.Session) -> requests.Session:
    """Refresh session cookies by hitting the main page."""
    try:
        resp = session.get(NSE_BASE_URL, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        logger.warning(f"Session refresh failed: {e}")
        session = _create_session()
    return session


def _fetch_announcements(
    session: requests.Session,
    from_date: str,
    to_date: str,
) -> list[dict]:
    """Fetch corporate announcements for a date range.

    Args:
        from_date: DD-MM-YYYY format (NSE API format)
        to_date: DD-MM-YYYY format
    """
    params = {
        "index": "equities",
        "from_date": from_date,
        "to_date": to_date,
    }

    for attempt in range(MAX_RETRIES):
        try:
            resp = session.get(NSE_API_URL, params=params, timeout=15)

            if resp.status_code == 403:
                logger.warning(f"403 Forbidden — refreshing session (attempt {attempt + 1})")
                session = _refresh_session(session)
                time.sleep(RETRY_BACKOFF * (attempt + 1))
                continue

            if resp.status_code == 429:
                wait = RETRY_BACKOFF * (attempt + 2)
                logger.warning(f"429 Rate limited — waiting {wait}s")
                time.sleep(wait)
                continue

            resp.raise_for_status()
            data = resp.json()

            # NSE returns either a list or a dict with data key
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                return data.get("data", data.get("announcements", []))
            return []

        except requests.exceptions.JSONDecodeError:
            logger.warning(f"Non-JSON response for {from_date}..{to_date} (attempt {attempt + 1})")
            if attempt < MAX_RETRIES - 1:
                session = _refresh_session(session)
                time.sleep(RETRY_BACKOFF)
        except requests.exceptions.RequestException as e:
            logger.warning(f"Request failed: {e} (attempt {attempt + 1})")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_BACKOFF * (attempt + 1))

    logger.error(f"Failed to fetch {from_date}..{to_date} after {MAX_RETRIES} attempts")
    return []


def _parse_announcement(ann: dict) -> dict | None:
    """Parse a single announcement into a standardized record.

    Returns None if the announcement is not an earnings-related filing.
    """
    desc = ann.get("desc", "")

    # Check if this is an earnings-related announcement
    is_earnings = False
    for earnings_desc in EARNINGS_DESCRIPTIONS:
        if earnings_desc.lower() in desc.lower():
            is_earnings = True
            break

    # Also check for "financial result" substring
    if not is_earnings and "financial result" in desc.lower():
        is_earnings = True

    if not is_earnings:
        return None

    symbol = ann.get("symbol", "").strip().upper()
    if not symbol:
        return None

    # Parse announcement date
    an_dt = ann.get("an_dt", "")
    announcement_date = None
    announcement_time = None
    if an_dt:
        for fmt in ("%d-%b-%Y %H:%M:%S", "%d-%m-%Y %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
            try:
                dt = datetime.strptime(an_dt.strip(), fmt)
                announcement_date = dt.date()
                announcement_time = dt.strftime("%H:%M")
                break
            except ValueError:
                continue

    if not announcement_date:
        # Try date-only formats
        for fmt in ("%d-%b-%Y", "%d-%m-%Y", "%Y-%m-%d"):
            try:
                announcement_date = datetime.strptime(an_dt.strip(), fmt).date()
                break
            except ValueError:
                continue

    if not announcement_date:
        return None

    # Extract summary text
    attchmnt = ann.get("attchmntText", "") or ""
    summary = attchmnt[:500].strip() if attchmnt else ""

    # Try to extract quarter ended date
    quarter_ended = None
    import re
    patterns = [
        r"(?:period|quarter|half.year|year)\s+ended?\s+(?:on\s+)?(\w+\s+\d{1,2},?\s+\d{4})",
        r"(\d{1,2}(?:st|nd|rd|th)?\s+\w+\s+\d{4})",
        r"(\w+\s+\d{4})\s+(?:quarter|results)",
    ]
    for pat in patterns:
        match = re.search(pat, summary, re.IGNORECASE)
        if match:
            quarter_ended = match.group(1).strip()
            break

    return {
        "symbol": symbol,
        "announcement_date": announcement_date,
        "announcement_time": announcement_time,
        "desc_type": desc,
        "quarter_ended": quarter_ended,
        "summary_text": summary,
    }


def _generate_monthly_ranges(from_date: datetime, to_date: datetime) -> list[tuple[str, str]]:
    """Generate (from_date, to_date) pairs in DD-MM-YYYY format, one per month."""
    ranges = []
    current = from_date.replace(day=1)
    while current <= to_date:
        month_start = current
        # Last day of current month
        if current.month == 12:
            month_end = current.replace(year=current.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            month_end = current.replace(month=current.month + 1, day=1) - timedelta(days=1)

        # Clamp to requested range
        start = max(month_start, from_date)
        end = min(month_end, to_date)

        ranges.append((
            start.strftime("%d-%m-%Y"),
            end.strftime("%d-%m-%Y"),
        ))

        # Move to next month
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)

    return ranges


def _load_progress(progress_path: str) -> set[str]:
    """Load completed month keys from progress file."""
    if os.path.exists(progress_path):
        with open(progress_path) as f:
            return set(json.load(f))
    return set()


def _save_progress(completed: set[str], progress_path: str):
    """Save completed month keys."""
    with open(progress_path, "w") as f:
        json.dump(sorted(completed), f)


def main():
    parser = argparse.ArgumentParser(
        description="Collect earnings announcements from NSE corporate filings",
        epilog="Example: python scripts/training/03_collect_earnings.py --resume",
    )
    parser.add_argument(
        "--from-date",
        default="2018-01-01",
        help="Start date YYYY-MM-DD (default: 2018-01-01)",
    )
    parser.add_argument(
        "--to-date",
        default=datetime.now().strftime("%Y-%m-%d"),
        help="End date YYYY-MM-DD (default: today)",
    )
    parser.add_argument(
        "--output", "-o",
        default=os.path.join(_backend_dir, "data", "training", "earnings_announcements.parquet"),
        help="Output parquet path",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip already-fetched months (uses progress file)",
    )
    args = parser.parse_args()

    from_dt = datetime.strptime(args.from_date, "%Y-%m-%d")
    to_dt = datetime.strptime(args.to_date, "%Y-%m-%d")

    progress_path = args.output + ".progress.json"
    completed = _load_progress(progress_path) if args.resume else set()

    monthly_ranges = _generate_monthly_ranges(from_dt, to_dt)
    logger.info(f"Fetching earnings announcements: {args.from_date} to {args.to_date}")
    logger.info(f"  {len(monthly_ranges)} months to process")
    if completed:
        logger.info(f"  Resuming: {len(completed)} months already done")

    session = _create_session()
    all_records = []
    total_api_calls = 0
    failed_months = []

    for i, (start, end) in enumerate(monthly_ranges):
        month_key = f"{start}..{end}"
        if month_key in completed:
            continue

        if i > 0 and i % 10 == 0:
            logger.info(f"Progress: {i}/{len(monthly_ranges)} months, {len(all_records)} earnings records")

        # Refresh session every 20 requests
        if total_api_calls > 0 and total_api_calls % 20 == 0:
            session = _refresh_session(session)

        time.sleep(REQUEST_DELAY)
        announcements = _fetch_announcements(session, start, end)
        total_api_calls += 1

        if announcements is None:
            failed_months.append(month_key)
            continue

        month_records = 0
        for ann in announcements:
            record = _parse_announcement(ann)
            if record:
                all_records.append(record)
                month_records += 1

        completed.add(month_key)

        # Save progress every 10 months
        if len(completed) % 10 == 0:
            _save_progress(completed, progress_path)

        if month_records > 0:
            logger.debug(f"  {month_key}: {month_records} earnings announcements")

    # Save progress
    _save_progress(completed, progress_path)

    if not all_records:
        logger.warning("No earnings records collected!")
        return

    # Build DataFrame
    df = pd.DataFrame(all_records)
    df = df.drop_duplicates(subset=["symbol", "announcement_date", "desc_type"], keep="first")
    df = df.sort_values(["symbol", "announcement_date"]).reset_index(drop=True)

    # Save
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    df.to_parquet(args.output, index=False)

    # Summary
    logger.info(f"\nSaved to {args.output}")
    logger.info(f"  Total records: {len(df)}")
    logger.info(f"  Unique symbols: {df['symbol'].nunique()}")
    logger.info(f"  Date range: {df['announcement_date'].min()} to {df['announcement_date'].max()}")
    logger.info(f"  API calls: {total_api_calls}")
    if failed_months:
        logger.warning(f"  Failed months: {len(failed_months)}")
        for m in failed_months[:5]:
            logger.warning(f"    {m}")

    # Top symbols by announcement count
    top = df["symbol"].value_counts().head(10)
    logger.info(f"  Top 10 symbols by announcement count:")
    for sym, count in top.items():
        logger.info(f"    {sym}: {count}")


if __name__ == "__main__":
    main()
