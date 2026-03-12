"""Utility functions for F&O strategy templates.

Provides instrument resolution from the options cache and charges estimation.
"""
from __future__ import annotations

import csv
import os
from datetime import datetime
from typing import Any

_CACHE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    ".cache", "nse_instruments.csv",
)

_options_cache: dict[str, dict] = {}

# Standard lot sizes (updated periodically by NSE)
LOT_SIZES: dict[str, int] = {
    "NIFTY": 25,
    "BANKNIFTY": 15,
    "FINNIFTY": 25,
    "MIDCPNIFTY": 50,
    "SENSEX": 10,
}


def get_lot_size(underlying: str) -> int:
    """Return lot size for an underlying from cache, with hardcoded fallback."""
    underlying = underlying.upper()
    # Prefer cache (authoritative, updated daily)
    try:
        cache = _load_cache()
        for data in cache.values():
            if data["name"] == underlying:
                return data["lot_size"]
    except FileNotFoundError:
        pass
    # Fallback to hardcoded (may be stale)
    return LOT_SIZES.get(underlying, 1)


def _load_cache() -> dict[str, dict]:
    """Load F&O instruments from the shared NSE instruments CSV cache."""
    global _options_cache
    if _options_cache:
        return _options_cache

    if not os.path.exists(_CACHE_PATH):
        raise FileNotFoundError(
            f"Instruments cache not found at {_CACHE_PATH}. "
            "Run `nf-quote` first to download instruments."
        )

    options: dict[str, dict] = {}
    with open(_CACHE_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("instrument_type") in ("OPTIDX", "OPTSTK"):
                ts = row.get("tradingsymbol", "")
                options[ts] = {
                    "instrument_key": row.get("instrument_key"),
                    "tradingsymbol": ts,
                    "name": row.get("name"),
                    "expiry": row.get("expiry"),
                    "strike": float(row.get("strike") or 0),
                    "lot_size": int(row.get("lot_size") or 1),
                    "instrument_type": row.get("instrument_type"),
                    "option_type": row.get("option_type"),
                    "exchange": row.get("exchange"),
                }
    _options_cache = options
    return _options_cache


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
            data["name"] == underlying
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
