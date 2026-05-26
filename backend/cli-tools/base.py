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
    except Exception as e:
        # A lookup failure (DB unreachable, WARP down, decrypt error) is NOT
        # the same as "user has no token" — surface it to stderr so a transient
        # infra issue isn't silently reported to the user as an expired token.
        print(f"⚠️  Upstox token lookup failed for user {user_id}: {e}",
              file=sys.stderr)
        return None


# DB user id of the app owner (Pranav). The owner's .env tokens
# (NF_ACCESS_TOKEN / UPSTOX_ACCESS_TOKEN) belong to this account, so they
# may only be used when the owner is the requesting user — never as a
# silent fallback for another user.
OWNER_USER_ID = int(os.environ.get("NF_OWNER_USER_ID", "1"))


def init_client() -> UpstoxClient:
    """Create an UpstoxClient scoped to the requesting user's Upstox token.

    Resolution:
      1. Resolve the requesting user from ``NF_USER_ID``.
         - Valid positive int  -> that user.
         - Missing/invalid in an agent subprocess (``NF_AGENT_SUBPROCESS=1``)
           -> FAIL CLOSED. We refuse rather than default to the owner, because
           defaulting silently executed one user's request against another
           user's broker account (incident 2026-05-26, thread_1779776921833).
         - Missing/invalid in direct terminal use -> the owner.
      2. Use that user's live DB token (decrypt + expiry check).
      3. If no DB token: the OWNER may fall back to the ``.env`` token; any
         other user FAILS CLOSED (never borrow the owner's token).

    Note: cli-tools always ``load_dotenv()``, so the owner's NF_ACCESS_TOKEN /
    UPSTOX_ACCESS_TOKEN are present in every subprocess's env regardless of
    what the spawner injected — which is exactly why the fail-closed guard
    lives here and not in the env-injection sites.

    Use this for user-scoped reads/writes (portfolio, positions, orders,
    funds, trades, profile). For public market data (quotes, historical,
    chains, greeks, market status), prefer init_market_data_client() — it
    routes through the longer-lived analytics token when available.
    """
    nf_user_raw = os.environ.get("NF_USER_ID")
    is_agent = os.environ.get("NF_AGENT_SUBPROCESS") == "1"

    if nf_user_raw and nf_user_raw.isdigit() and int(nf_user_raw) > 0:
        user_id = int(nf_user_raw)
    elif is_agent:
        print_error(
            "UPSTOX_USER_UNIDENTIFIED: Could not determine which user this "
            "operation belongs to, so it was refused to avoid touching the "
            "wrong Upstox account. Tell the user their Upstox session could "
            "not be identified and ask them to reconnect Upstox in "
            "Settings → Trading Settings, then try again."
        )
    else:
        # Direct terminal/owner usage (no agent subprocess marker present).
        user_id = OWNER_USER_ID

    db_token = _resolve_db_token_sync(user_id) if user_id > 0 else None
    if db_token:
        return UpstoxClient(
            access_token=db_token,
            paper_trading=False,
            user_id=user_id,
        )

    # No live DB token for this user.
    if user_id != OWNER_USER_ID:
        print_error(
            f"UPSTOX_TOKEN_MISSING: No usable Upstox token for user {user_id} "
            "(missing, expired, or a temporary lookup error — see any warning "
            "above). Refusing to fall back to another account. Tell the user "
            "their Upstox connection isn't available right now and ask them to "
            "reconnect Upstox in Settings → Trading Settings; if they just "
            "connected, retrying shortly may resolve it."
        )

    # Owner only: the .env tokens belong to the owner, so they may serve as a
    # fallback (e.g. local dev without DB/WARP, or terminal usage).
    env_live_token = os.environ.get("NF_ACCESS_TOKEN")
    token = env_live_token or os.environ.get("UPSTOX_ACCESS_TOKEN")
    return UpstoxClient(
        access_token=token,
        paper_trading=not bool(token),
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
