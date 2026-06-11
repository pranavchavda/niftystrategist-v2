"""Thin async client for Upstox's expired-instruments API (Plus-plan feature).

Provides rolling-expiry historical options data for backtests: past expiry
dates, the option contracts that existed for a given expiry, and historical
candles for an expired contract. All three are heavily disk-cached because the
underlying data is largely immutable once an expiry is in the past.

Design constraints (see CLAUDE.md gotchas):
  - httpx async ONLY. The sync Upstox SDK froze the event loop once via urllib3
    Retry-After sleeps; never use it here.
  - Rate-limit protection: a module-level semaphore bounds concurrent HTTP
    calls, and 429 responses are retried with Retry-After / exponential backoff.
  - Disk cache under backend/.cache/expired_instruments/. Expired-contract data
    (contracts for past expiries, candles) is immutable → cached permanently.
    The expiries list grows over time → 1-day TTL.

No DB access, no token resolution: the caller passes a valid token string.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://api.upstox.com/v2/expired-instruments"

# Index underlyings → Upstox instrument_key. Stocks are resolved via the
# equity instruments cache (see underlying_instrument_key()).
UNDERLYING_INDEX_KEYS: dict[str, str] = {
    "NIFTY": "NSE_INDEX|Nifty 50",
    "BANKNIFTY": "NSE_INDEX|Nifty Bank",
    "FINNIFTY": "NSE_INDEX|Nifty Fin Service",
    "SENSEX": "BSE_INDEX|SENSEX",
    "BANKEX": "BSE_INDEX|BANKEX",
}

# Cache directory. Module-level so tests can repoint it at tmp_path. Env var
# NF_EXPIRED_INSTRUMENTS_CACHE_DIR overrides the default at import time.
CACHE_DIR: Path = Path(
    os.environ.get(
        "NF_EXPIRED_INSTRUMENTS_CACHE_DIR",
        str(Path(__file__).resolve().parent.parent / ".cache" / "expired_instruments"),
    )
)

# Bound concurrent HTTP calls to avoid tripping Upstox rate limits.
_SEMAPHORE = asyncio.Semaphore(6)

_TIMEOUT = 30.0
_MAX_RETRIES = 3
_BACKOFF_SCHEDULE = (1.0, 2.0, 4.0)  # seconds, used when no Retry-After header


# --------------------------------------------------------------------------- #
# Disk cache helpers (sync — files are tiny; guarded against corruption)
# --------------------------------------------------------------------------- #
def _safe_filename(*parts: str) -> str:
    """Build a filesystem-safe cache filename from arbitrary key parts."""
    raw = "__".join(parts)
    for bad in ("|", ":", "/", "\\", " ", "%7C", "%7c"):
        raw = raw.replace(bad, "_")
    return raw + ".json"


def _cache_path(filename: str) -> Path:
    return CACHE_DIR / filename


def _cache_read(filename: str) -> object | None:
    """Read a cached JSON payload, or None on miss/corruption."""
    path = _cache_path(filename)
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError, ValueError) as exc:
        logger.warning("expired_instruments: corrupt cache %s (%s); refetching", path, exc)
        return None


def _cache_write(filename: str, payload: object) -> None:
    """Write a JSON payload to the cache; failures are non-fatal."""
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path = _cache_path(filename)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh)
        os.replace(tmp, path)
    except OSError as exc:
        logger.warning("expired_instruments: failed to write cache %s (%s)", filename, exc)


def _is_fresh(filename: str, ttl_seconds: float) -> bool:
    """True if the cache file exists and is younger than ttl_seconds."""
    path = _cache_path(filename)
    try:
        return path.exists() and (time.time() - path.stat().st_mtime) < ttl_seconds
    except OSError:
        return False


# --------------------------------------------------------------------------- #
# HTTP core
# --------------------------------------------------------------------------- #
async def _get(token: str, url: str, params: dict | None = None) -> dict:
    """GET a URL with Bearer auth, semaphore-bounded, with 429 retry handling.

    Returns the parsed JSON body. Raises httpx.HTTPStatusError on non-429
    error responses, or RuntimeError if 429 retries are exhausted.
    """
    headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
    async with _SEMAPHORE:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            for attempt in range(_MAX_RETRIES + 1):
                resp = await client.get(url, params=params, headers=headers)
                if resp.status_code == 429:
                    if attempt >= _MAX_RETRIES:
                        logger.error("expired_instruments: 429 retries exhausted for %s", url)
                        resp.raise_for_status()
                    retry_after = resp.headers.get("Retry-After")
                    if retry_after is not None:
                        try:
                            delay = float(retry_after)
                        except ValueError:
                            delay = _BACKOFF_SCHEDULE[min(attempt, len(_BACKOFF_SCHEDULE) - 1)]
                    else:
                        delay = _BACKOFF_SCHEDULE[min(attempt, len(_BACKOFF_SCHEDULE) - 1)]
                    logger.warning(
                        "expired_instruments: 429 on %s; sleeping %.1fs (attempt %d/%d)",
                        url, delay, attempt + 1, _MAX_RETRIES,
                    )
                    await asyncio.sleep(delay)
                    continue
                resp.raise_for_status()
                return resp.json()
    # Unreachable: loop either returns or raises.
    raise RuntimeError(f"expired_instruments: exhausted retries for {url}")


# --------------------------------------------------------------------------- #
# Public: key resolution + pure helpers
# --------------------------------------------------------------------------- #
def underlying_instrument_key(underlying: str) -> str:
    """Return the Upstox instrument_key for an underlying.

    Indices come from UNDERLYING_INDEX_KEYS. Anything else is treated as an
    equity symbol and resolved via the instruments cache. Raises ValueError if
    it cannot be resolved.
    """
    if not underlying:
        raise ValueError("underlying must be a non-empty string")
    upper = underlying.strip().upper()
    if upper in UNDERLYING_INDEX_KEYS:
        return UNDERLYING_INDEX_KEYS[upper]

    # Equity fallback via the existing instruments cache.
    try:
        from services.instruments_cache import get_instrument_key
    except Exception as exc:  # pragma: no cover - import guard
        raise ValueError(
            f"cannot resolve underlying {underlying!r}: instruments cache unavailable ({exc})"
        )
    key = get_instrument_key(upper)
    if not key:
        raise ValueError(f"cannot resolve instrument key for underlying {underlying!r}")
    return key


def front_expiry_for_date(d: str, expiries: list[str]) -> str | None:
    """Return the smallest expiry >= d (ISO date strings), or None if none.

    Pure function, no IO. ISO date strings sort lexicographically.
    """
    candidates = [e for e in expiries if e >= d]
    if not candidates:
        return None
    return min(candidates)


def _today_iso() -> str:
    # Indirection so tests can reason about "future" expiries deterministically.
    from datetime import date

    return date.today().isoformat()


# --------------------------------------------------------------------------- #
# Public: API wrappers with caching
# --------------------------------------------------------------------------- #
async def get_expiries(token: str, underlying: str) -> list[str]:
    """Return sorted ISO past-expiry dates for an underlying.

    Disk-cached with a 1-day TTL (new past-expiries accumulate over time).
    """
    instrument_key = underlying_instrument_key(underlying)
    filename = _safe_filename("expiries", instrument_key)

    if _is_fresh(filename, ttl_seconds=86400):
        cached = _cache_read(filename)
        if isinstance(cached, list):
            return cached

    body = await _get(
        token,
        f"{BASE_URL}/expiries",
        params={"instrument_key": instrument_key},
    )
    expiries = sorted(body.get("data") or [])
    _cache_write(filename, expiries)
    return expiries


async def get_expired_contracts(token: str, underlying: str, expiry: str) -> list[dict]:
    """Return raw contract dicts for an underlying + expiry.

    Cached PERMANENTLY once the expiry is in the past (immutable data). For an
    expiry that is today or in the future, the result is fetched fresh and not
    cached (contracts may still change).
    """
    instrument_key = underlying_instrument_key(underlying)
    is_past = expiry < _today_iso()
    filename = _safe_filename("contracts", instrument_key, expiry)

    if is_past:
        cached = _cache_read(filename)
        if isinstance(cached, list):
            return cached

    body = await _get(
        token,
        f"{BASE_URL}/option/contract",
        params={"instrument_key": instrument_key, "expiry_date": expiry},
    )
    contracts = body.get("data") or []

    if is_past:
        _cache_write(filename, contracts)
    return contracts


async def fetch_expired_candles(
    token: str,
    expired_instrument_key: str,
    interval: str,
    from_date: str,
    to_date: str,
) -> list[dict]:
    """Return ASCENDING candle dicts for an expired contract.

    Upstox returns candles newest-first; we reverse them so callers can replay
    chronologically. Each candle dict has keys: timestamp, open, high, low,
    close, volume, oi.

    Cached PERMANENTLY (expired-contract candles never change). The cache key
    includes the instrument key, interval, and the full date range.
    """
    filename = _safe_filename(
        "candles", expired_instrument_key, interval, from_date, to_date
    )
    cached = _cache_read(filename)
    if isinstance(cached, list):
        return cached

    # Pipe chars in the instrument key must be URL-encoded; quote with no safe
    # chars so '|' and ':' are escaped, then embed in the path.
    encoded_key = quote(expired_instrument_key, safe="")
    url = (
        f"{BASE_URL}/historical-candle/"
        f"{encoded_key}/{interval}/{to_date}/{from_date}"
    )
    body = await _get(token, url)
    raw = ((body.get("data") or {}).get("candles")) or []

    # Upstox returns newest-first → reverse to ascending (chronological).
    candles: list[dict] = []
    for row in reversed(raw):
        # Row shape: [ts, open, high, low, close, volume, oi]
        candles.append(
            {
                "timestamp": row[0],
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "volume": float(row[5]) if len(row) > 5 and row[5] is not None else 0.0,
                "oi": float(row[6]) if len(row) > 6 and row[6] is not None else 0.0,
            }
        )

    _cache_write(filename, candles)
    return candles
