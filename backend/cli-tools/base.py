"""Shared utilities for Nifty Strategist CLI tools."""

import asyncio
import json
import os
import sys

# Add backend/ to sys.path so we can import services, models, etc.
_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

# Load .env so CLI tools can access API keys when run directly from terminal
from dotenv import load_dotenv  # noqa: E402
load_dotenv(os.path.join(_backend_dir, ".env"))

from services.upstox_client import UpstoxClient  # noqa: E402
from services.instruments_cache import (  # noqa: E402
    ensure_loaded as _ensure_instruments,
    symbol_exists as _symbol_exists,
    get_company_name as _get_company_name,
    search_symbols,
    symbol_count,
    NIFTY_50_SYMBOLS,
)

# Re-export symbol list for backward compat (Nifty 50 only)
SYMBOLS = sorted(UpstoxClient.SYMBOL_TO_ISIN.keys())


def _resolve_db_token_sync(user_id: int):
    """Sync best-effort lookup for the user's current Upstox token.

    Returns the decrypted token if present and unexpired; None otherwise.
    CLI tools call this in preference to ``NF_ACCESS_TOKEN`` because the
    env var is a snapshot taken by the orchestrator at chat-handler start
    time — any TOTP refresh after that point leaves the snapshot stale.
    Upstox invalidates prior tokens whenever a new TOTP login succeeds, so
    using a stale snapshot guarantees a 401 → unnecessary force-refresh.
    """
    try:
        from datetime import datetime as _dt
        from sqlalchemy import select as _select

        from database.session import get_db_session
        from database.models import User as _DBUser
        from utils.encryption import decrypt_token as _decrypt

        from database.session import engine as _engine

        async def _query():
            try:
                async with get_db_session() as session:
                    result = await session.execute(
                        _select(_DBUser).where(_DBUser.id == user_id)
                    )
                    db_user = result.scalar_one_or_none()
                    if not db_user or not db_user.upstox_access_token:
                        return None
                    if (db_user.upstox_token_expiry
                            and db_user.upstox_token_expiry < _dt.utcnow()):
                        return None
                    return _decrypt(db_user.upstox_access_token)
            finally:
                # Dispose the engine pool while the loop is still alive, so
                # asyncpg connections don't get torn down against a closed
                # loop by ``asyncio.run`` (cosmetic RuntimeWarning otherwise).
                await _engine.dispose()

        return asyncio.run(_query())
    except Exception:
        return None


def init_client() -> UpstoxClient:
    """Create an UpstoxClient using the freshest Upstox token available.

    Resolution order:
      1. Live DB token for ``NF_USER_ID`` (decrypt + expiry check).
      2. ``NF_ACCESS_TOKEN`` (orchestrator-injected snapshot).
      3. ``UPSTOX_ACCESS_TOKEN`` (direct terminal usage).

    The DB lookup is preferred because the env snapshot can be invalidated
    by any other process refreshing the token mid-session.  Falls back to
    env when the DB lookup fails (e.g. local dev without WARP).

    Use this for user-scoped reads/writes (portfolio, positions, orders,
    funds, trades, profile). For public market data (quotes, historical,
    chains, greeks, market status), prefer init_market_data_client() — it
    routes through the longer-lived analytics token when available.
    """
    nf_user_raw = os.environ.get("NF_USER_ID", "1")
    user_id = int(nf_user_raw) if nf_user_raw and nf_user_raw.isdigit() else 1

    db_token = _resolve_db_token_sync(user_id) if user_id > 0 else None
    env_live_token = os.environ.get("NF_ACCESS_TOKEN")
    token = db_token or env_live_token or os.environ.get("UPSTOX_ACCESS_TOKEN")

    # Live mode whenever we have a per-user token (either source).
    live_mode = bool(db_token or env_live_token)

    return UpstoxClient(
        access_token=token,
        paper_trading=not live_mode,
        user_id=user_id,
    )


def init_market_data_client() -> UpstoxClient:
    """Create an UpstoxClient suitable for non-user-specific market reads.

    Prefers UPSTOX_ANALYTICS_TOKEN — exchange-wide, doesn't expire daily —
    over per-user tokens, eliminating UDAPI100050 401s when a user's token
    is stale. Falls back to NF_ACCESS_TOKEN / UPSTOX_ACCESS_TOKEN when the
    analytics env var isn't set.

    Use for: quotes, historical OHLC, option chain, greeks, market status,
    holiday/timing API. Do NOT use for: portfolio, positions, orders, funds.
    """
    analytics = os.environ.get("UPSTOX_ANALYTICS_TOKEN", "").strip()
    if analytics:
        return UpstoxClient(
            access_token=analytics,
            paper_trading=False,
            user_id=int(os.environ.get("NF_USER_ID", "1")),
        )
    return init_client()


def run_async(coro):
    """Run an async coroutine synchronously."""
    return asyncio.run(coro)


def print_json(data):
    """Print data as formatted JSON to stdout."""
    print(json.dumps(data, indent=2, default=str))


def print_success(msg: str):
    """Print a success message with checkmark prefix."""
    print(f"✅ {msg}")


def print_error(msg: str):
    """Print an error message and exit with code 1."""
    print(f"❌ {msg}", file=sys.stderr)
    sys.exit(1)


def validate_symbol(symbol: str) -> str:
    """Validate a stock symbol against the NSE instruments cache.

    Returns the uppercased symbol if valid.
    Exits with error if the symbol doesn't exist at all.
    """
    sym = symbol.upper()
    _ensure_instruments()

    if not _symbol_exists(sym):
        print_error(f"Unknown symbol: {sym}. Use nf-quote --search to find valid NSE symbols.")

    return sym


def format_inr(amount: float | int | None) -> str:
    """Format a number as Indian Rupees (₹1,23,456.78)."""
    if amount is None:
        return "N/A"
    negative = amount < 0
    amount = abs(amount)
    # Indian number formatting: last 3 digits, then groups of 2
    integer_part = int(amount)
    decimal_part = f"{amount - integer_part:.2f}"[1:]  # ".XX"
    s = str(integer_part)
    if len(s) <= 3:
        formatted = s
    else:
        # Last 3 digits
        formatted = s[-3:]
        remaining = s[:-3]
        # Groups of 2
        while remaining:
            formatted = remaining[-2:] + "," + formatted
            remaining = remaining[:-2]
    result = f"₹{formatted}{decimal_part}"
    return f"-{result}" if negative else result


def format_volume(vol: int | float | None) -> str:
    """Format volume with K/M/B suffix."""
    if vol is None:
        return "N/A"
    vol = float(vol)
    if vol >= 1_000_000_000:
        return f"{vol / 1_000_000_000:.1f}B"
    if vol >= 1_000_000:
        return f"{vol / 1_000_000:.1f}M"
    if vol >= 1_000:
        return f"{vol / 1_000:.1f}K"
    return str(int(vol))


def format_change(change_pct: float | None) -> str:
    """Format percentage change with arrow indicator."""
    if change_pct is None:
        return "N/A"
    arrow = "▲" if change_pct >= 0 else "▼"
    sign = "+" if change_pct >= 0 else ""
    return f"{arrow} {sign}{change_pct:.2f}%"
