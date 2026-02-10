"""Shared utilities for Nifty Strategist CLI tools."""

import asyncio
import json
import os
import sys

# Add backend/ to sys.path so we can import services, models, etc.
_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from services.upstox_client import UpstoxClient  # noqa: E402

# Re-export symbol list for tools that need it
SYMBOLS = sorted(UpstoxClient.SYMBOL_TO_ISIN.keys())


def init_client() -> UpstoxClient:
    """Create an UpstoxClient using NF_ACCESS_TOKEN from environment.

    The orchestrator injects this env var when spawning CLI tool subprocesses.
    Falls back to UPSTOX_ACCESS_TOKEN for direct terminal usage.
    When NF_ACCESS_TOKEN is set (live user token), paper_trading is disabled.
    """
    live_token = os.environ.get("NF_ACCESS_TOKEN")
    token = live_token or os.environ.get("UPSTOX_ACCESS_TOKEN")
    user_id = int(os.environ.get("NF_USER_ID", "1"))
    return UpstoxClient(
        access_token=token,
        paper_trading=not live_token,
        user_id=user_id,
    )


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
