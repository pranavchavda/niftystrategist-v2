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
import json
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

# NSE ETFs — fetched from the NSE ETF JSON endpoint. The list isn't an "index"
# so niftyindices.com doesn't host it; this hits NSE directly (needs a real UA
# + Referer or it 401s). NSE rate-limits this endpoint sporadically, so we
# also ship a bundled seed file as a guaranteed fallback. A weekly scheduler
# job refreshes the live cache (NSE typically lists 3–8 new ETFs per month).
_NSE_ETF_URL = "https://www.nseindia.com/api/etf"
_NSE_ETF_CACHE = os.path.join(_CACHE_DIR, "nse_etfs.json")
_NSE_ETF_META = os.path.join(_CACHE_DIR, "nse_etfs.meta")
_NSE_ETF_SEED = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "seed", "nse_etfs.json"
)
NSE_ETF_SYMBOLS: set[str] = set()

# In-memory lookup tables (populated by ensure_loaded)
_symbol_to_instrument_key: dict[str, str] = {}
_symbol_to_name: dict[str, str] = {}
_index_alias_to_key: dict[str, str] = {}  # canonicalized alias → instrument_key
_index_key_to_name: dict[str, str] = {}  # instrument_key → display name
_index_key_to_tradingsymbol: dict[str, str] = {}  # instrument_key → tradingsymbol
_loaded = False
_nifty500_loaded = False
_etfs_loaded = False

# Common index aliases not directly in the CSV. Keys are canonicalized
# (uppercase, spaces/underscores/hyphens stripped). Values are the canonical
# tradingsymbol as it appears in the Upstox instruments CSV.
_INDEX_ALIASES: dict[str, str] = {
    "BANKNIFTY": "NIFTY BANK",
    "NIFTYBANK": "NIFTY BANK",
    "NIFTY": "NIFTY 50",
    "NIFTY50": "NIFTY 50",
    "FINNIFTY": "NIFTY FIN SERVICE",
    "NIFTYFIN": "NIFTY FIN SERVICE",
    "MIDCPNIFTY": "NIFTY MID SELECT",
    "NIFTYMIDCAPSELECT": "NIFTY MID SELECT",
    "NIFTYNEXT50": "NIFTY NEXT 50",
    "NIFTYNXT50": "NIFTY NEXT 50",
    "NNF": "NIFTY NEXT 50",
    "INDIAVIX": "INDIA VIX",
    "VIX": "INDIA VIX",
}

# Static BSE indices — not present in the NSE CSV we download. Values are
# (instrument_key, display_name). Registered directly during cache load.
_BSE_INDICES: dict[str, tuple[str, str]] = {
    "SENSEX": ("BSE_INDEX|SENSEX", "Sensex"),
    "BSESENSEX": ("BSE_INDEX|SENSEX", "Sensex"),
    "BANKEX": ("BSE_INDEX|BANKEX", "BSE Bankex"),
    "BSEBANKEX": ("BSE_INDEX|BANKEX", "BSE Bankex"),
    "SENSEX50": ("BSE_INDEX|SNSX50", "BSE Sensex 50"),
    "BSE100": ("BSE_INDEX|BSE100", "BSE 100"),
    "BSE200": ("BSE_INDEX|BSE200", "BSE 200"),
    "BSE500": ("BSE_INDEX|BSE500", "BSE 500"),
    "BSEMIDCAP": ("BSE_INDEX|MIDCAP", "BSE Midcap"),
    "BSESMLCAP": ("BSE_INDEX|SMLCAP", "BSE Smallcap"),
}


def _canon_index(s: str) -> str:
    """Canonicalize an index alias: uppercase, strip spaces/underscores/hyphens."""
    return "".join(s.upper().split()).replace("_", "").replace("-", "")


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
    global _index_alias_to_key, _index_key_to_name, _index_key_to_tradingsymbol

    if not os.path.exists(_CACHE_CSV):
        return False

    sym_to_key: dict[str, str] = {}
    sym_to_name: dict[str, str] = {}
    idx_alias_to_key: dict[str, str] = {}
    idx_key_to_name: dict[str, str] = {}
    idx_key_to_tsym: dict[str, str] = {}

    try:
        with open(_CACHE_CSV, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                exchange = row.get("exchange", "")
                inst_key = row.get("instrument_key", "")
                tsym = row.get("tradingsymbol", "")
                name = row.get("name", "")

                if exchange == "NSE_EQ":
                    symbol = tsym.upper()
                    if symbol and inst_key:
                        sym_to_key[symbol] = inst_key
                        if name:
                            sym_to_name[symbol] = name
                elif exchange == "NSE_INDEX" and inst_key:
                    idx_key_to_name[inst_key] = name or tsym
                    if tsym:
                        idx_key_to_tsym[inst_key] = tsym.upper()
                    # Register every canonicalized alias for this index
                    for raw in (tsym, name):
                        if not raw:
                            continue
                        alias = _canon_index(raw)
                        if alias:
                            idx_alias_to_key.setdefault(alias, inst_key)

        # Apply hand-curated aliases (map to the canonicalized tradingsymbol
        # we already registered above).
        for alias, canonical_tsym in _INDEX_ALIASES.items():
            target = idx_alias_to_key.get(_canon_index(canonical_tsym))
            if target:
                idx_alias_to_key.setdefault(alias, target)

        # Register BSE indices (not in the NSE CSV).
        for alias, (inst_key, display_name) in _BSE_INDICES.items():
            idx_alias_to_key.setdefault(alias, inst_key)
            idx_key_to_name.setdefault(inst_key, display_name)
            idx_key_to_tsym.setdefault(inst_key, alias)

        _symbol_to_instrument_key = sym_to_key
        _symbol_to_name = sym_to_name
        _index_alias_to_key = idx_alias_to_key
        _index_key_to_name = idx_key_to_name
        _index_key_to_tradingsymbol = idx_key_to_tsym
        _loaded = True
        logger.info(
            f"Instruments cache loaded: {len(sym_to_key)} equity, "
            f"{len(idx_key_to_name)} indices"
        )
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


def _etf_cache_is_fresh() -> bool:
    """Return True if NSE ETF cache exists and is less than _TTL_SECONDS old."""
    if not os.path.exists(_NSE_ETF_META):
        return False
    try:
        with open(_NSE_ETF_META) as f:
            ts = float(f.read().strip())
        return (time.time() - ts) < _TTL_SECONDS
    except (ValueError, OSError):
        return False


def _parse_etf_symbols(raw: str) -> set[str]:
    """Extract uppercased symbol set from an NSE ETF JSON payload."""
    data = json.loads(raw)
    return {
        (r.get("symbol") or "").strip().upper()
        for r in data.get("data", [])
        if r.get("symbol")
    }


def refresh_etf_cache() -> bool:
    """Force-download the NSE ETF list and overwrite the disk cache.

    Used by the weekly scheduler job. Returns True on success. Does not touch
    the in-memory NSE_ETF_SYMBOLS — call _load_etfs() afterwards (or restart)
    if you want the new symbols served immediately.
    """
    global _etfs_loaded
    os.makedirs(_CACHE_DIR, exist_ok=True)
    try:
        logger.info("Refreshing NSE ETF list (forced)")
        req = urllib.request.Request(
            _NSE_ETF_URL,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://www.nseindia.com/market-data/exchange-traded-funds-etf",
            },
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8")
        symbols = _parse_etf_symbols(raw)
        if not symbols:
            logger.warning("NSE ETF refresh returned no symbols; keeping old cache")
            return False
        with open(_NSE_ETF_CACHE, "w", encoding="utf-8") as f:
            f.write(raw)
        with open(_NSE_ETF_META, "w") as f:
            f.write(str(time.time()))
        # Bust the in-memory load so next ensure_loaded() picks up the new set.
        _etfs_loaded = False
        logger.info(f"NSE ETF refresh OK: {len(symbols)} symbols")
        return True
    except Exception as e:
        logger.warning(f"NSE ETF refresh failed: {e}")
        return False


def _load_etfs() -> bool:
    """Populate NSE_ETF_SYMBOLS from cache → live download → bundled seed.

    The NSE ETF endpoint requires a real browser User-Agent and a Referer
    header — without them it 401s. NSE also rate-limits sporadically, so we
    fall back to a bundled seed file (refreshed weekly via scheduler).
    """
    global NSE_ETF_SYMBOLS, _etfs_loaded

    if _etfs_loaded:
        return True

    # 1. Fresh disk cache (last successful download).
    if _etf_cache_is_fresh() and os.path.exists(_NSE_ETF_CACHE):
        try:
            with open(_NSE_ETF_CACHE, encoding="utf-8") as f:
                symbols = _parse_etf_symbols(f.read())
            if symbols:
                NSE_ETF_SYMBOLS = symbols
                _etfs_loaded = True
                logger.info(f"NSE ETFs loaded from cache: {len(symbols)} symbols")
                return True
        except Exception as e:
            logger.warning(f"Failed to parse NSE ETF cache: {e}")

    # 2. Live download from NSE.
    os.makedirs(_CACHE_DIR, exist_ok=True)
    try:
        logger.info("Downloading NSE ETF list")
        req = urllib.request.Request(
            _NSE_ETF_URL,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://www.nseindia.com/market-data/exchange-traded-funds-etf",
            },
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8")
        symbols = _parse_etf_symbols(raw)
        if symbols:
            with open(_NSE_ETF_CACHE, "w", encoding="utf-8") as f:
                f.write(raw)
            with open(_NSE_ETF_META, "w") as f:
                f.write(str(time.time()))
            NSE_ETF_SYMBOLS = symbols
            _etfs_loaded = True
            logger.info(f"NSE ETFs cached: {len(symbols)} symbols")
            return True
        logger.warning("NSE ETF JSON parsed but no symbols found")
    except Exception as e:
        logger.warning(f"Failed to download NSE ETF list: {e}")

    # 3. Bundled seed fallback.
    if os.path.exists(_NSE_ETF_SEED):
        try:
            with open(_NSE_ETF_SEED, encoding="utf-8") as f:
                symbols = _parse_etf_symbols(f.read())
            if symbols:
                NSE_ETF_SYMBOLS = symbols
                _etfs_loaded = True
                logger.warning(
                    f"NSE ETFs loaded from bundled seed (live + cache unavailable): {len(symbols)} symbols"
                )
                return True
        except Exception as e:
            logger.warning(f"Failed to parse bundled NSE ETF seed: {e}")

    _etfs_loaded = True  # Don't retry every call if everything failed.
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
    _load_etfs()


def get_instrument_key(symbol: str) -> str | None:
    """Return the Upstox instrument_key for a symbol, or None if unknown."""
    ensure_loaded()
    return _symbol_to_instrument_key.get(symbol.upper())


def get_company_name(symbol: str) -> str | None:
    """Return the company/instrument name for a symbol, or None."""
    ensure_loaded()
    return _symbol_to_name.get(symbol.upper())


def get_isin(symbol: str) -> str | None:
    """Return the ISIN for an NSE equity symbol, or None.

    Upstox NSE_EQ instrument_keys are formatted ``NSE_EQ|<ISIN>``, so we derive
    the ISIN by splitting. Indices/F&O don't have ISINs and return None.
    """
    key = get_instrument_key(symbol)
    if not key or not key.startswith("NSE_EQ|"):
        return None
    return key.split("|", 1)[1]


def is_nifty50(symbol: str) -> bool:
    """Return True if symbol is a Nifty 50 constituent."""
    return symbol.upper() in NIFTY_50_SYMBOLS


def is_nifty500(symbol: str) -> bool:
    """Return True if symbol is a Nifty 500 constituent."""
    ensure_loaded()
    return symbol.upper() in NIFTY_500_SYMBOLS


def is_etf(symbol: str) -> bool:
    """Return True if symbol is an NSE-listed ETF."""
    ensure_loaded()
    return symbol.upper() in NSE_ETF_SYMBOLS


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
    """Return True if symbol exists as an NSE equity OR index."""
    ensure_loaded()
    if symbol.upper() in _symbol_to_instrument_key:
        return True
    return _canon_index(symbol) in _index_alias_to_key


def equity_exists(symbol: str) -> bool:
    """Return True if symbol exists as an NSE equity (excludes indices)."""
    ensure_loaded()
    return symbol.upper() in _symbol_to_instrument_key


def index_exists(symbol: str) -> bool:
    """Return True if symbol resolves to an NSE index."""
    ensure_loaded()
    return _canon_index(symbol) in _index_alias_to_key


def get_index_key(symbol: str) -> str | None:
    """Return the Upstox instrument_key for an index, or None if unknown."""
    ensure_loaded()
    return _index_alias_to_key.get(_canon_index(symbol))


def get_index_name(symbol_or_key: str) -> str | None:
    """Return the display name for an index, given either an alias or the instrument_key."""
    ensure_loaded()
    if symbol_or_key in _index_key_to_name:
        return _index_key_to_name[symbol_or_key]
    key = get_index_key(symbol_or_key)
    return _index_key_to_name.get(key) if key else None


def list_indices() -> list[dict]:
    """Return sorted list of all known NSE indices as {symbol, name, instrument_key}."""
    ensure_loaded()
    results = []
    for inst_key, display_name in _index_key_to_name.items():
        results.append({
            "symbol": _index_key_to_tradingsymbol.get(inst_key, display_name.upper()),
            "name": display_name,
            "instrument_key": inst_key,
        })
    results.sort(key=lambda r: r["name"])
    return results


def search_indices(term: str, limit: int = 20) -> list[dict]:
    """Substring search across NSE indices (name + tradingsymbol)."""
    ensure_loaded()
    term_upper = term.upper()
    term_canon = _canon_index(term)
    results = []
    for inst_key, display_name in _index_key_to_name.items():
        tsym = _index_key_to_tradingsymbol.get(inst_key, "")
        if (
            term_upper in display_name.upper()
            or term_upper in tsym
            or term_canon and term_canon in _canon_index(display_name)
        ):
            results.append({
                "symbol": tsym or display_name.upper(),
                "name": display_name,
                "instrument_key": inst_key,
            })
    results.sort(key=lambda r: (
        0 if r["name"].upper() == term_upper else 1,
        0 if r["name"].upper().startswith(term_upper) else 1,
        r["name"],
    ))
    return results[:limit]


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
