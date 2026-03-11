"""Position sizing calculator for strategy templates."""
from __future__ import annotations

import math


def compute_quantity(
    capital: float,
    risk_percent: float,
    entry: float,
    sl: float,
    lot_size: int = 1,
) -> int:
    """Compute position size from capital, risk %, entry price, and stop-loss.

    Args:
        capital: Total capital available for this trade.
        risk_percent: Max percentage of capital to risk (e.g. 2.0 = 2%).
        entry: Expected entry price.
        sl: Stop-loss price.
        lot_size: Minimum lot size (1 for equity, varies for F&O).

    Returns:
        Quantity (always a multiple of lot_size, minimum lot_size).
    """
    if entry <= 0 or sl <= 0:
        return lot_size
    risk_per_share = abs(entry - sl)
    if risk_per_share == 0:
        return lot_size
    max_risk = capital * (risk_percent / 100)
    raw_qty = max_risk / risk_per_share
    # Round down to nearest lot_size
    qty = int(math.floor(raw_qty / lot_size)) * lot_size
    return max(qty, lot_size)


def compute_target(entry: float, sl: float, rr_ratio: float = 2.0) -> float:
    """Compute target price from entry, SL, and reward:risk ratio.

    Args:
        entry: Entry price.
        sl: Stop-loss price.
        rr_ratio: Reward-to-risk ratio (default 2:1).

    Returns:
        Target price.
    """
    risk = abs(entry - sl)
    if entry > sl:
        # Long: target above entry
        return round(entry + risk * rr_ratio, 2)
    else:
        # Short: target below entry
        return round(entry - risk * rr_ratio, 2)
