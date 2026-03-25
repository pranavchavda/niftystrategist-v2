"""NSE instruments cache — download once daily, lookup any NSE symbol.

Downloads the public Upstox instruments CSV (~2 MB gzipped) and caches
to disk at ``backend/.cache/nse_instruments.csv``.  Provides fast
symbol → instrument_key / company_name lookups for *any* NSE equity.

Usage::

    from services.instruments_cache import ensure_loaded, get_instrument_key, is_nifty50

    ensure_loaded()
    key = get_instrument_key("GOLDBEES")  # "NSE_EQ|INE..."
"""

import csv
import gzip
import io
import logging
import os
import time
import urllib.request

logger = logging.getLogger(__name__)

_INSTRUMENTS_URL = "https://assets.upstox.com/market-quote/instruments/exchange/NSE.csv.gz"
_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".cache")
_CACHE_CSV = os.path.join(_CACHE_DIR, "nse_instruments.csv")
_CACHE_META = os.path.join(_CACHE_DIR, "nse_instruments.meta")
_TTL_SECONDS = 24 * 60 * 60  # 24 hours

# Nifty 50 constituents (same symbols as UpstoxClient.SYMBOL_TO_ISIN keys)
NIFTY_50_SYMBOLS: set[str] = {
    "RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK", "SBIN",
    "BHARTIARTL", "ITC", "KOTAKBANK", "LT", "HINDUNILVR", "AXISBANK",
    "BAJFINANCE", "MARUTI", "WIPRO", "TATAMOTORS", "TATASTEEL",
    "SUNPHARMA", "ONGC", "NTPC", "ADANIENT", "ADANIPORTS", "ASIANPAINT",
    "BAJAJ-AUTO", "BAJAJFINSV", "BPCL", "BRITANNIA", "CIPLA", "COALINDIA",
    "DIVISLAB", "DRREDDY", "EICHERMOT", "GRASIM", "HCLTECH", "HDFC",
    "HDFCLIFE", "HEROMOTOCO", "HINDALCO", "INDUSINDBK", "JSWSTEEL",
    "M&M", "NESTLEIND", "POWERGRID", "SBILIFE", "SHREECEM",
    "TATACONSUM", "TECHM", "TITAN", "ULTRACEMCO", "UPL",
}

# Nifty Next 50 constituents (51st-100th by market cap, reviewed semi-annually)
NIFTY_NEXT_50_SYMBOLS: set[str] = {
    "ABB", "ADANIENSOL", "ADANIGREEN", "ADANIPOWER", "AMBUJACEM",
    "BAJAJHFL", "BAJAJHLDNG", "BANKBARODA", "BOSCHLTD", "CANBK",
    "CGPOWER", "CHOLAFIN", "DLF", "DMART", "ENRIN",
    "GAIL", "GODREJCP", "HAL", "HAVELLS", "HINDZINC",
    "HYUNDAI", "ICICIGI", "INDHOTEL", "IOC", "IRFC",
    "JINDALSTEL", "JSWENERGY", "LICI", "LODHA", "LTM",
    "MAZDOCK", "MOTHERSON", "NAUKRI", "PFC", "PIDILITIND",
    "PNB", "RECLTD", "SIEMENS", "SOLARINDS", "TATAPOWER",
    "TORNTPHARM", "TVSMOTOR", "UNITDSPR", "VBL", "VEDL",
    "ZYDUSLIFE",
}

# Combined Nifty 100 = Nifty 50 + Nifty Next 50
NIFTY_100_SYMBOLS: set[str] = NIFTY_50_SYMBOLS | NIFTY_NEXT_50_SYMBOLS

# Nifty 500 — fetched dynamically from NSE (populated by _load_nifty500)
_NIFTY_500_URL = "https://www.niftyindices.com/IndexConstituent/ind_nifty500list.csv"
_NIFTY_500_CACHE = os.path.join(_CACHE_DIR, "nifty500_constituents.csv")
_NIFTY_500_META = os.path.join(_CACHE_DIR, "nifty500_constituents.meta")
NIFTY_500_SYMBOLS: set[str] = set()

# In-memory lookup tables (populated by ensure_loaded)
_symbol_to_instrument_key: dict[str, str] = {}
_symbol_to_name: dict[str, str] = {}
_loaded = False
_nifty500_loaded = False


def _cache_is_fresh() -> bool:
    """Return True if disk cache exists and is less than _TTL_SECONDS old."""
    if not os.path.exists(_CACHE_META):
        return False
    try:
        with open(_CACHE_META) as f:
            ts = float(f.read().strip())
        return (time.time() - ts) < _TTL_SECONDS
    except (ValueError, OSError):
        return False


def _download() -> bool:
    """Download the instruments CSV and save to disk cache. Returns True on success."""
    os.makedirs(_CACHE_DIR, exist_ok=True)
    try:
        logger.info(f"Downloading NSE instruments from {_INSTRUMENTS_URL}")
        req = urllib.request.Request(
            _INSTRUMENTS_URL,
            headers={"User-Agent": "NiftyStrategist/1.0"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()

        csv_bytes = gzip.decompress(raw)
        with open(_CACHE_CSV, "wb") as f:
            f.write(csv_bytes)
        with open(_CACHE_META, "w") as f:
            f.write(str(time.time()))

        logger.info(f"Instruments cache saved ({len(csv_bytes)} bytes)")
        return True
    except Exception as e:
        logger.warning(f"Failed to download instruments CSV: {e}")
        return False


def _load_from_disk() -> bool:
    """Parse the cached CSV into in-memory dicts. Returns True if successful."""
    global _symbol_to_instrument_key, _symbol_to_name, _loaded

    if not os.path.exists(_CACHE_CSV):
        return False

    sym_to_key: dict[str, str] = {}
    sym_to_name: dict[str, str] = {}

    try:
        with open(_CACHE_CSV, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                itype = row.get("instrument_type", "")
                exchange = row.get("exchange", "")
                # Keep EQUITY rows from NSE only
                if exchange != "NSE_EQ":
                    continue
                if itype not in ("EQUITY", "ETF", ""):
                    # Some rows have empty instrument_type; include them
                    # as long as exchange is NSE_EQ
                    pass

                symbol = row.get("tradingsymbol", "").upper()
                inst_key = row.get("instrument_key", "")
                name = row.get("name", "")

                if symbol and inst_key:
                    sym_to_key[symbol] = inst_key
                    if name:
                        sym_to_name[symbol] = name

        _symbol_to_instrument_key = sym_to_key
        _symbol_to_name = sym_to_name
        _loaded = True
        logger.info(f"Instruments cache loaded: {len(sym_to_key)} symbols")
        return True
    except Exception as e:
        logger.warning(f"Failed to parse instruments cache: {e}")
        return False


def _nifty500_cache_is_fresh() -> bool:
    """Return True if Nifty 500 cache exists and is less than _TTL_SECONDS old."""
    if not os.path.exists(_NIFTY_500_META):
        return False
    try:
        with open(_NIFTY_500_META) as f:
            ts = float(f.read().strip())
        return (time.time() - ts) < _TTL_SECONDS
    except (ValueError, OSError):
        return False


def _load_nifty500() -> bool:
    """Download Nifty 500 constituents from NSE and cache to disk."""
    global NIFTY_500_SYMBOLS, _nifty500_loaded

    if _nifty500_loaded:
        return True

    # Try loading from fresh cache first
    if _nifty500_cache_is_fresh() and os.path.exists(_NIFTY_500_CACHE):
        try:
            with open(_NIFTY_500_CACHE, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                symbols = {row["Symbol"].strip().upper() for row in reader if row.get("Symbol")}
            if symbols:
                NIFTY_500_SYMBOLS = symbols
                _nifty500_loaded = True
                logger.info(f"Nifty 500 loaded from cache: {len(symbols)} symbols")
                return True
        except Exception as e:
            logger.warning(f"Failed to parse Nifty 500 cache: {e}")

    # Download fresh
    os.makedirs(_CACHE_DIR, exist_ok=True)
    try:
        logger.info("Downloading Nifty 500 constituents from NSE")
        req = urllib.request.Request(
            _NIFTY_500_URL,
            headers={"User-Agent": "Mozilla/5.0 (NiftyStrategist/1.0)"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read().decode("utf-8")

        with open(_NIFTY_500_CACHE, "w", encoding="utf-8") as f:
            f.write(data)
        with open(_NIFTY_500_META, "w") as f:
            f.write(str(time.time()))

        reader = csv.DictReader(io.StringIO(data))
        symbols = {row["Symbol"].strip().upper() for row in reader if row.get("Symbol")}
        if symbols:
            NIFTY_500_SYMBOLS = symbols
            _nifty500_loaded = True
            logger.info(f"Nifty 500 constituents cached: {len(symbols)} symbols")
            return True
        else:
            logger.warning("Nifty 500 CSV parsed but no symbols found")
            return False
    except Exception as e:
        logger.warning(f"Failed to download Nifty 500 constituents: {e}")
        # Fallback: use Nifty 100 if download fails
        if not NIFTY_500_SYMBOLS:
            NIFTY_500_SYMBOLS = NIFTY_100_SYMBOLS.copy()
            logger.warning(f"Falling back to Nifty 100 ({len(NIFTY_500_SYMBOLS)} symbols)")
        _nifty500_loaded = True
        return False


def ensure_loaded() -> None:
    """Download instruments CSV if stale/missing, then load into memory.

    Safe to call multiple times — no-ops if already loaded and fresh.
    """
    global _loaded

    if _loaded:
        return

    if not _cache_is_fresh():
        ok = _download()
        if not ok and not os.path.exists(_CACHE_CSV):
            # No cache at all — Nifty 50 hardcoded dict still works
            logger.warning("No instruments cache available; only Nifty 50 symbols will work")
            _loaded = True  # Don't retry every call
            return

    _load_from_disk()
    _load_nifty500()


def get_instrument_key(symbol: str) -> str | None:
    """Return the Upstox instrument_key for a symbol, or None if unknown."""
    ensure_loaded()
    return _symbol_to_instrument_key.get(symbol.upper())


def get_company_name(symbol: str) -> str | None:
    """Return the company/instrument name for a symbol, or None."""
    ensure_loaded()
    return _symbol_to_name.get(symbol.upper())


def is_nifty50(symbol: str) -> bool:
    """Return True if symbol is a Nifty 50 constituent."""
    return symbol.upper() in NIFTY_50_SYMBOLS


def is_nifty500(symbol: str) -> bool:
    """Return True if symbol is a Nifty 500 constituent."""
    ensure_loaded()
    return symbol.upper() in NIFTY_500_SYMBOLS


def get_universe(name: str = "nifty500") -> set[str]:
    """Return the symbol set for a named universe.

    Supported: nifty50, nifty100, nifty500.
    """
    ensure_loaded()
    match name.lower().replace(" ", "").replace("_", "").replace("-", ""):
        case "nifty50":
            return NIFTY_50_SYMBOLS
        case "nifty100":
            return NIFTY_100_SYMBOLS
        case "nifty500":
            return NIFTY_500_SYMBOLS
        case _:
            raise ValueError(f"Unknown universe: {name}. Use nifty50, nifty100, or nifty500.")


def symbol_exists(symbol: str) -> bool:
    """Return True if symbol exists in the NSE instruments cache."""
    ensure_loaded()
    return symbol.upper() in _symbol_to_instrument_key


def get_all_symbols() -> list[str]:
    """Return sorted list of all known NSE symbols."""
    ensure_loaded()
    return sorted(_symbol_to_instrument_key.keys())


def search_symbols(term: str, limit: int = 20) -> list[dict]:
    """Search symbols and company names by substring match.

    Returns list of dicts with keys: symbol, name, nifty50.
    Collects all matches first, then sorts by relevance and truncates.
    """
    ensure_loaded()
    term_upper = term.upper()
    results = []

    for sym, name in _symbol_to_name.items():
        if term_upper in sym or term_upper in name.upper():
            results.append({
                "symbol": sym,
                "name": name,
                "nifty50": sym in NIFTY_50_SYMBOLS,
            })

    # Sort: exact match → symbol starts with term → Nifty 50 → alphabetical
    results.sort(key=lambda r: (
        0 if r["symbol"] == term_upper else 1,
        0 if r["symbol"].startswith(term_upper) else 1,
        0 if r["nifty50"] else 1,
        r["symbol"],
    ))
    return results[:limit]


def symbol_count() -> int:
    """Return total number of known NSE symbols."""
    ensure_loaded()
    return len(_symbol_to_instrument_key) or len(NIFTY_50_SYMBOLS)
