#!/usr/bin/env python3
"""Build symbol-to-name/alias mapping for news headline → ticker matching.

Parses the Upstox instruments cache CSV and the hardcoded Nifty 500 universe
to produce a JSON mapping: symbol → {full_name, aliases, sector, nifty50}.
Also includes a MACRO pseudo-ticker for market-wide keywords.

Output: backend/data/training/ticker_mapping.json

Usage:
  python scripts/training/05_build_ticker_mapping.py
  python scripts/training/05_build_ticker_mapping.py --output data/training/ticker_mapping.json
"""

import argparse
import json
import logging
import os
import sys

_backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from dotenv import load_dotenv
load_dotenv(os.path.join(_backend_dir, ".env"))

import csv

from services.instruments_cache import NIFTY_50_SYMBOLS

# Paths to cached data (avoid ensure_loaded() which may try to download)
_CACHE_DIR = os.path.join(_backend_dir, ".cache")
_INSTRUMENTS_CSV = os.path.join(_CACHE_DIR, "nse_instruments.csv")
_NIFTY500_CSV = os.path.join(_CACHE_DIR, "nifty500_constituents.csv")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Common suffix expansions for truncated instrument names
SUFFIX_EXPANSIONS = {
    " LT": " Limited",
    " LTD": " Limited",
    " CORP": " Corporation",
    " IND": " Industries",
    " INDS": " Industries",
    " INFRA": " Infrastructure",
    " TECH": " Technologies",
    " PHARMA": " Pharmaceuticals",
    " FIN": " Finance",
    " FINSERV": " Financial Services",
    " FINSV": " Financial Services",
    " ENT": " Enterprises",
    " HLDNG": " Holdings",
    " HFL": " Housing Finance Limited",
}

# Hand-curated aliases for major stocks where the instrument name is insufficient.
# These are common names used in news headlines that differ from the trading symbol.
MANUAL_ALIASES: dict[str, list[str]] = {
    "RELIANCE": ["Reliance Industries", "RIL", "Mukesh Ambani", "Jio"],
    "TCS": ["Tata Consultancy Services", "Tata Consultancy"],
    "INFY": ["Infosys"],
    "HDFCBANK": ["HDFC Bank"],
    "ICICIBANK": ["ICICI Bank"],
    "SBIN": ["State Bank of India", "SBI"],
    "BHARTIARTL": ["Bharti Airtel", "Airtel"],
    "ITC": ["ITC Limited"],
    "KOTAKBANK": ["Kotak Mahindra Bank", "Kotak Bank"],
    "LT": ["Larsen & Toubro", "Larsen and Toubro", "L&T"],
    "HINDUNILVR": ["Hindustan Unilever", "HUL"],
    "AXISBANK": ["Axis Bank"],
    "BAJFINANCE": ["Bajaj Finance"],
    "BAJAJFINSV": ["Bajaj Finserv"],
    "BAJAJ-AUTO": ["Bajaj Auto"],
    "MARUTI": ["Maruti Suzuki"],
    "WIPRO": ["Wipro"],
    "TATAMOTORS": ["Tata Motors"],
    "TATASTEEL": ["Tata Steel"],
    "SUNPHARMA": ["Sun Pharma", "Sun Pharmaceutical"],
    "ONGC": ["Oil and Natural Gas Corporation", "Oil & Natural Gas"],
    "NTPC": ["NTPC Limited"],
    "ADANIENT": ["Adani Enterprises", "Gautam Adani"],
    "ADANIPORTS": ["Adani Ports", "Adani Ports and SEZ"],
    "ADANIGREEN": ["Adani Green Energy"],
    "ADANIPOWER": ["Adani Power"],
    "ASIANPAINT": ["Asian Paints"],
    "BPCL": ["Bharat Petroleum", "BPCL"],
    "BRITANNIA": ["Britannia Industries"],
    "CIPLA": ["Cipla"],
    "COALINDIA": ["Coal India"],
    "DIVISLAB": ["Divi's Laboratories", "Divis Lab"],
    "DRREDDY": ["Dr Reddy's Laboratories", "Dr Reddy"],
    "EICHERMOT": ["Eicher Motors", "Royal Enfield"],
    "GRASIM": ["Grasim Industries"],
    "HCLTECH": ["HCL Technologies", "HCL Tech"],
    "HDFCLIFE": ["HDFC Life"],
    "HEROMOTOCO": ["Hero MotoCorp", "Hero Honda"],
    "HINDALCO": ["Hindalco Industries"],
    "INDUSINDBK": ["IndusInd Bank"],
    "JSWSTEEL": ["JSW Steel"],
    "M&M": ["Mahindra & Mahindra", "Mahindra and Mahindra"],
    "NESTLEIND": ["Nestle India"],
    "POWERGRID": ["Power Grid Corporation", "Power Grid"],
    "SBILIFE": ["SBI Life Insurance", "SBI Life"],
    "TATACONSUM": ["Tata Consumer Products", "Tata Consumer"],
    "TECHM": ["Tech Mahindra"],
    "TITAN": ["Titan Company"],
    "ULTRACEMCO": ["UltraTech Cement"],
    "UPL": ["UPL Limited"],
    "DMART": ["Avenue Supermarts", "DMart", "D-Mart"],
    "HAL": ["Hindustan Aeronautics"],
    "MAZDOCK": ["Mazagon Dock", "Mazagon Dock Shipbuilders"],
    "NAUKRI": ["Info Edge", "Naukri.com"],
    "LICI": ["LIC", "Life Insurance Corporation"],
    "VEDL": ["Vedanta"],
    "DLF": ["DLF Limited"],
    "SIEMENS": ["Siemens India"],
    "BOSCHLTD": ["Bosch India", "Bosch"],
    "CHOLAFIN": ["Chola Finance", "Cholamandalam"],
    "TATAPOWER": ["Tata Power"],
    "PIDILITIND": ["Pidilite Industries", "Pidilite"],
    "HAVELLS": ["Havells India"],
    "GODREJCP": ["Godrej Consumer Products", "Godrej Consumer"],
    "BANKBARODA": ["Bank of Baroda", "BoB"],
    "PNB": ["Punjab National Bank"],
    "IOC": ["Indian Oil Corporation", "Indian Oil"],
    "GAIL": ["GAIL India", "Gas Authority of India"],
    "JINDALSTEL": ["Jindal Steel & Power", "Jindal Steel"],
    "MOTHERSON": ["Samvardhana Motherson", "Motherson Sumi"],
    "IRFC": ["Indian Railway Finance Corporation"],
    "PFC": ["Power Finance Corporation"],
    "RECLTD": ["REC Limited", "Rural Electrification"],
    "ZYDUSLIFE": ["Zydus Lifesciences", "Cadila Healthcare"],
    "TVSMOTOR": ["TVS Motor"],
    "VBL": ["Varun Beverages"],
    "HYUNDAI": ["Hyundai Motor India"],
}

# Macro keywords — these match market-wide headlines, not specific stocks
MACRO_KEYWORDS: dict[str, list[str]] = {
    "rbi": [
        "RBI", "Reserve Bank of India", "repo rate", "monetary policy",
        "rate cut", "rate hike", "MPC", "monetary policy committee",
        "reverse repo", "CRR", "SLR",
    ],
    "budget": [
        "Union Budget", "budget session", "fiscal deficit", "Sitharaman",
        "finance minister", "budget 2024", "budget 2025", "budget 2026",
    ],
    "inflation": [
        "inflation", "CPI", "WPI", "consumer price index",
        "wholesale price index", "food inflation", "retail inflation",
    ],
    "crude": [
        "crude oil", "Brent crude", "oil prices", "OPEC", "petroleum",
        "fuel price", "petrol price", "diesel price",
    ],
    "forex": [
        "rupee", "dollar", "USD/INR", "forex reserves", "INR",
        "exchange rate", "rupee depreciation", "rupee appreciation",
    ],
    "fii_dii": [
        "FII", "DII", "foreign institutional", "domestic institutional",
        "FPI", "foreign portfolio", "mutual fund inflows", "mutual fund outflows",
    ],
    "global": [
        "Fed", "Federal Reserve", "US market", "Wall Street", "Nasdaq",
        "Dow Jones", "S&P 500", "China", "recession", "global market",
        "trade war", "tariff",
    ],
    "market": [
        "Nifty", "Sensex", "BSE", "NSE", "stock market", "market crash",
        "market rally", "bull market", "bear market", "market cap",
        "IPO", "GDP", "GST",
    ],
}


def _expand_name(raw_name: str) -> str:
    """Expand truncated instrument name suffixes."""
    name = raw_name.strip()
    upper = name.upper()
    for suffix, expansion in SUFFIX_EXPANSIONS.items():
        if upper.endswith(suffix):
            # Replace the suffix portion only
            name = name[: len(name) - len(suffix)] + expansion
            break
    return name


def _generate_aliases(symbol: str, raw_name: str) -> list[str]:
    """Generate a list of searchable aliases for a stock symbol."""
    aliases = set()

    # The symbol itself
    aliases.add(symbol)

    # Raw name from instruments
    if raw_name:
        aliases.add(raw_name.strip())

    # Expanded name
    expanded = _expand_name(raw_name)
    if expanded != raw_name.strip():
        aliases.add(expanded)

    # Manual aliases
    if symbol in MANUAL_ALIASES:
        aliases.update(MANUAL_ALIASES[symbol])

    # Sort by length descending (longest first for regex matching)
    return sorted(aliases, key=len, reverse=True)


def _load_symbol_names() -> dict[str, str]:
    """Parse the instruments CSV directly to get symbol → name mapping."""
    if not os.path.exists(_INSTRUMENTS_CSV):
        logger.error(f"Instruments CSV not found at {_INSTRUMENTS_CSV}")
        logger.error("Run the backend once to populate the cache, or download manually.")
        sys.exit(1)

    sym_to_name: dict[str, str] = {}
    with open(_INSTRUMENTS_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("exchange") != "NSE_EQ":
                continue
            symbol = row.get("tradingsymbol", "").upper()
            name = row.get("name", "")
            if symbol and name:
                sym_to_name[symbol] = name

    logger.info(f"Loaded {len(sym_to_name)} symbol names from instruments CSV")
    return sym_to_name


def _load_nifty500() -> set[str]:
    """Load Nifty 500 constituents from cached CSV."""
    if os.path.exists(_NIFTY500_CSV):
        symbols = set()
        with open(_NIFTY500_CSV, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                sym = row.get("Symbol", "").strip().upper()
                if sym:
                    symbols.add(sym)
        if symbols:
            logger.info(f"Loaded {len(symbols)} Nifty 500 symbols from cache")
            return symbols

    # Fallback to Nifty 100 (hardcoded in instruments_cache.py)
    from services.instruments_cache import NIFTY_100_SYMBOLS
    logger.warning("Nifty 500 cache not found, falling back to Nifty 100")
    return NIFTY_100_SYMBOLS


def build_mapping(universe: str = "nifty500") -> dict:
    """Build the full ticker mapping."""
    sym_to_name = _load_symbol_names()

    if universe == "nifty50":
        symbols = NIFTY_50_SYMBOLS
    elif universe == "nifty100":
        from services.instruments_cache import NIFTY_100_SYMBOLS
        symbols = NIFTY_100_SYMBOLS
    else:
        symbols = _load_nifty500()

    logger.info(f"Building ticker mapping for {len(symbols)} symbols ({universe})")

    mapping = {}
    missing_name = 0

    for symbol in sorted(symbols):
        raw_name = sym_to_name.get(symbol, "")
        if not raw_name:
            missing_name += 1

        aliases = _generate_aliases(symbol, raw_name)
        mapping[symbol] = {
            "full_name": _expand_name(raw_name) if raw_name else symbol,
            "aliases": aliases,
            "nifty50": symbol in NIFTY_50_SYMBOLS,
        }

    # Add MACRO pseudo-ticker
    all_macro_keywords = []
    for keywords in MACRO_KEYWORDS.values():
        all_macro_keywords.extend(keywords)

    mapping["__MACRO__"] = {
        "full_name": "Market-wide macro keywords",
        "aliases": sorted(all_macro_keywords, key=len, reverse=True),
        "nifty50": False,
        "categories": MACRO_KEYWORDS,
    }

    if missing_name:
        logger.warning(f"{missing_name} symbols had no instrument name")

    logger.info(f"Built mapping for {len(mapping) - 1} stocks + MACRO pseudo-ticker")
    return mapping


def main():
    parser = argparse.ArgumentParser(
        description="Build ticker mapping for news headline matching",
        epilog="Example: python scripts/training/05_build_ticker_mapping.py",
    )
    parser.add_argument(
        "--output", "-o",
        default=os.path.join(_backend_dir, "data", "training", "ticker_mapping.json"),
        help="Output JSON path (default: data/training/ticker_mapping.json)",
    )
    parser.add_argument(
        "--universe",
        default="nifty500",
        choices=["nifty50", "nifty100", "nifty500"],
        help="Stock universe (default: nifty500)",
    )
    args = parser.parse_args()

    mapping = build_mapping(args.universe)

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(mapping, f, indent=2, ensure_ascii=False)

    logger.info(f"Saved ticker mapping to {args.output}")
    logger.info(f"  Stocks: {len(mapping) - 1}")
    logger.info(f"  Macro keywords: {sum(len(v) for v in MACRO_KEYWORDS.values())}")

    # Quick stats
    total_aliases = sum(len(v["aliases"]) for k, v in mapping.items() if k != "__MACRO__")
    logger.info(f"  Total aliases: {total_aliases} (avg {total_aliases / (len(mapping) - 1):.1f} per stock)")


if __name__ == "__main__":
    main()
