"""Position sizing calculator for strategy templates."""
from __future__ import annotations

import math


# Upstox intraday leverage multipliers (approximate).
# With product I, you only need ~20% margin (5x leverage).
MARGIN_FACTORS = {
    "I": 0.20,   # Intraday: ~5x leverage
    "D": 1.00,   # Delivery: full price
}


def compute_quantity(
    capital: float,
    risk_percent: float,
    entry: float,
    sl: float,
    lot_size: int = 1,
    product: str = "I",
) -> int:
    """Compute position size from capital, risk %, entry price, and stop-loss.

    Uses two constraints and takes the smaller:
    1. Risk-based: max_risk / risk_per_share
    2. Capital-based: capital / (entry * margin_factor)

    Args:
        capital: Total capital available for this trade.
        risk_percent: Max percentage of capital to risk (e.g. 2.0 = 2%).
        entry: Expected entry price.
        sl: Stop-loss price.
        lot_size: Minimum lot size (1 for equity, varies for F&O).
        product: "I" for intraday (5x leverage) or "D" for delivery (no leverage).

    Returns:
        Quantity (always a multiple of lot_size, minimum lot_size).
    """
    if entry <= 0 or sl <= 0:
        return lot_size
    risk_per_share = abs(entry - sl)
    if risk_per_share == 0:
        return lot_size

    # Constraint 1: risk-based sizing
    max_risk = capital * (risk_percent / 100)
    risk_qty = max_risk / risk_per_share

    # Constraint 2: capital/margin-based affordability
    margin_factor = MARGIN_FACTORS.get(product, 1.0)
    margin_per_share = entry * margin_factor
    afford_qty = capital / margin_per_share if margin_per_share > 0 else risk_qty

    # Take the smaller of the two
    raw_qty = min(risk_qty, afford_qty)

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
