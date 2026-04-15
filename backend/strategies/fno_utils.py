"""Utility functions for F&O strategy templates.

Provides instrument resolution from the options cache and charges estimation.
"""
from __future__ import annotations

import csv
import os
import re
from datetime import datetime
from typing import Any

_CACHE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    ".cache", "nse_instruments.csv",
)

_options_cache: dict[str, dict] = {}
# Maps short trading symbol prefix (e.g. "RELIANCE") → full company name
_symbol_to_name: dict[str, str] = {}

# Standard lot sizes (updated periodically by NSE)
LOT_SIZES: dict[str, int] = {
    "NIFTY": 25,
    "BANKNIFTY": 15,
    "FINNIFTY": 25,
    "MIDCPNIFTY": 50,
    "SENSEX": 10,
}


def _resolve_symbol(symbol: str) -> str:
    """Resolve a short symbol to the name used in the options cache.

    For OPTIDX, name is the short symbol (e.g. "NIFTY").
    For OPTSTK, name is the full company name (e.g. "RELIANCE INDUSTRIES LTD").
    """
    _load_cache()
    symbol = symbol.upper()
    for data in _options_cache.values():
        if data["name"] == symbol:
            return symbol
    return _symbol_to_name.get(symbol, symbol)


def get_lot_size(underlying: str) -> int:
    """Return lot size for an underlying from cache, with hardcoded fallback."""
    underlying = underlying.upper()
    # Prefer cache (authoritative, updated daily)
    try:
        cache = _load_cache()
        resolved = _resolve_symbol(underlying)
        for data in cache.values():
            if data["name"] == resolved:
                return data["lot_size"]
    except FileNotFoundError:
        pass
    # Fallback to hardcoded (may be stale)
    return LOT_SIZES.get(underlying, 1)


def _load_cache() -> dict[str, dict]:
    """Load F&O instruments from the shared NSE instruments CSV cache."""
    global _options_cache, _symbol_to_name
    if _options_cache:
        return _options_cache

    if not os.path.exists(_CACHE_PATH):
        raise FileNotFoundError(
            f"Instruments cache not found at {_CACHE_PATH}. "
            "Run `nf-quote` first to download instruments."
        )

    options: dict[str, dict] = {}
    sym_to_name: dict[str, str] = {}
    with open(_CACHE_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("instrument_type") in ("OPTIDX", "OPTSTK"):
                ts = row.get("tradingsymbol", "")
                name = row.get("name", "")
                options[ts] = {
                    "instrument_key": row.get("instrument_key"),
                    "tradingsymbol": ts,
                    "name": name,
                    "expiry": row.get("expiry"),
                    "strike": float(row.get("strike") or 0),
                    "lot_size": int(row.get("lot_size") or 1),
                    "instrument_type": row.get("instrument_type"),
                    "option_type": row.get("option_type"),
                    "exchange": row.get("exchange"),
                }
                if row.get("instrument_type") == "OPTSTK" and ts:
                    m = re.match(r'^([A-Z&-]+?)\d', ts)
                    if m and m.group(1) not in sym_to_name:
                        sym_to_name[m.group(1)] = name
    _options_cache = options
    _symbol_to_name = sym_to_name
    return _options_cache


def list_expiries(underlying: str) -> list[str]:
    """Return sorted unique expiry dates (YYYY-MM-DD) available for an underlying."""
    cache = _load_cache()
    resolved = _resolve_symbol(underlying.upper())
    expiries = {
        data.get("expiry")
        for data in cache.values()
        if data.get("name") == resolved and data.get("expiry")
    }
    return sorted(expiries)


def list_strikes(
    underlying: str,
    expiry: str,
    option_type: str | None = None,
) -> list[float]:
    """Return sorted unique strikes for an underlying + expiry (+ optional CE/PE)."""
    cache = _load_cache()
    resolved = _resolve_symbol(underlying.upper())

    expiry_normalized = expiry
    if "-" in expiry:
        try:
            dt = datetime.strptime(expiry, "%Y-%m-%d")
            expiry_normalized = dt.strftime("%d%b%y").upper()
        except ValueError:
            pass

    opt_type = option_type.upper() if option_type else None
    strikes: set[float] = set()
    for data in cache.values():
        if data.get("name") != resolved:
            continue
        if opt_type and data.get("option_type") != opt_type:
            continue
        cache_expiry = data.get("expiry", "") or ""
        if expiry not in cache_expiry and expiry_normalized not in cache_expiry:
            continue
        strike_val = data.get("strike")
        if strike_val:
            strikes.add(float(strike_val))
    return sorted(strikes)


def resolve_option_instrument(
    underlying: str,
    expiry: str,
    strike: float,
    option_type: str,
) -> dict[str, Any]:
    """Resolve an option contract to its instrument details.

    Args:
        underlying: e.g. "NIFTY", "BANKNIFTY"
        expiry: "YYYY-MM-DD" or "DDMMMYY" format
        strike: Strike price (e.g. 25000)
        option_type: "CE" or "PE"

    Returns:
        Dict with instrument_key, tradingsymbol, lot_size, etc.

    Raises:
        ValueError: If no matching instrument found.
    """
    cache = _load_cache()
    underlying = underlying.upper()
    resolved_name = _resolve_symbol(underlying)
    opt_type = option_type.upper()

    # Normalize expiry to DDMMMYY for matching
    expiry_normalized = expiry
    if "-" in expiry:
        dt = datetime.strptime(expiry, "%Y-%m-%d")
        expiry_normalized = dt.strftime("%d%b%y").upper()

    # Primary search: match by name, strike, option_type, and expiry
    matching = []
    for data in cache.values():
        if (
            data["name"] == resolved_name
            and data["strike"] == strike
            and data["option_type"] == opt_type
        ):
            cache_expiry = data.get("expiry", "")
            if expiry_normalized in cache_expiry or expiry in cache_expiry:
                matching.append(data)

    # Fallback: fuzzy match on tradingsymbol endings
    if not matching:
        for ts, data in cache.items():
            if (
                ts.startswith(underlying)
                and ts.endswith(f"{int(strike)}{opt_type}")
            ):
                cache_expiry = data.get("expiry", "")
                if expiry in cache_expiry or expiry_normalized[-4:] in ts:
                    matching.append(data)

    if not matching:
        raise ValueError(
            f"No instrument found for {underlying} {expiry} {strike} {opt_type}. "
            "Check that the instruments cache is up-to-date."
        )

    matching.sort(key=lambda x: x.get("expiry", ""))
    return matching[0]


def estimate_leg_charges(
    premium: float,
    quantity: int,
    side: str,
) -> dict[str, float]:
    """Estimate charges for one F&O leg.

    Args:
        premium: Option premium per unit
        quantity: Number of units (lots * lot_size)
        side: "BUY" or "SELL"

    Returns:
        Dict with brokerage, stt, txn_charges, gst, sebi, stamp, total.
    """
    turnover = premium * quantity
    brokerage = min(20.0, turnover * 0.0003)  # ₹20/order cap

    # STT: 0.0625% on sell-side only
    stt = turnover * 0.000625 if side.upper() == "SELL" else 0.0

    # Transaction charges: 0.053% (NSE F&O)
    txn = turnover * 0.00053

    # GST: 18% on (brokerage + txn charges)
    gst = (brokerage + txn) * 0.18

    # SEBI turnover fee: 0.0001%
    sebi = turnover * 0.000001

    # Stamp duty: 0.003% on buy-side only
    stamp = turnover * 0.00003 if side.upper() == "BUY" else 0.0

    total = brokerage + stt + txn + gst + sebi + stamp
    return {
        "brokerage": round(brokerage, 2),
        "stt": round(stt, 2),
        "txn_charges": round(txn, 2),
        "gst": round(gst, 2),
        "sebi": round(sebi, 2),
        "stamp": round(stamp, 2),
        "total": round(total, 2),
    }
