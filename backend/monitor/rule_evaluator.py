"""Pure-function rule evaluators for the trade monitor.

No I/O, no DB, no network — takes a rule + context data and returns
whether the trigger condition fires (True) or not (False).
"""
from __future__ import annotations

from datetime import datetime

from monitor.models import MonitorRule, OrderStatusTrigger, PriceTrigger, TimeTrigger


# ── Day-name mapping (ISO weekday: Monday=0 … Sunday=6) ─────────────

_DAY_INDEX: dict[str, int] = {
    "mon": 0,
    "tue": 1,
    "wed": 2,
    "thu": 3,
    "fri": 4,
    "sat": 5,
    "sun": 6,
}


# ── Price triggers ───────────────────────────────────────────────────

def evaluate_price_trigger(
    rule: MonitorRule,
    market_data: dict,
    prev_price: float | None = None,
) -> bool:
    """Evaluate a price trigger against current (and optionally previous) market data.

    Args:
        rule: MonitorRule with trigger_type="price".
        market_data: Dict with price fields (e.g. ``{"ltp": 123.4, "bid": 122.0}``).
        prev_price: The previous tick's price for the same reference field.
                    Required for ``crosses_above`` / ``crosses_below`` conditions.

    Returns:
        True if the trigger condition is met, False otherwise.
    """
    cfg = PriceTrigger(**rule.trigger_config)

    current = market_data.get(cfg.reference)
    if current is None:
        return False

    if cfg.condition == "lte":
        return current <= cfg.price

    if cfg.condition == "gte":
        return current >= cfg.price

    if cfg.condition == "crosses_above":
        if prev_price is None:
            return False
        return prev_price < cfg.price and current >= cfg.price

    if cfg.condition == "crosses_below":
        if prev_price is None:
            return False
        return prev_price > cfg.price and current <= cfg.price

    return False


# ── Time triggers ────────────────────────────────────────────────────

def evaluate_time_trigger(
    rule: MonitorRule,
    now: datetime,
    tolerance_seconds: int = 60,
) -> bool:
    """Evaluate a time trigger against the current datetime.

    Args:
        rule: MonitorRule with trigger_type="time".
        now: Current datetime (naive, assumed IST).
        tolerance_seconds: How many seconds after the target time the
                           trigger still fires.  ``0 <= delta < tolerance``.

    Returns:
        True if the trigger condition is met, False otherwise.
    """
    cfg = TimeTrigger(**rule.trigger_config)

    # Weekend guard
    if cfg.market_only and now.weekday() >= 5:
        return False

    # Day-of-week check
    current_day_idx = now.weekday()
    allowed_indices = {_DAY_INDEX[d] for d in cfg.on_days}
    if current_day_idx not in allowed_indices:
        return False

    # Time-of-day check
    hour, minute = (int(p) for p in cfg.at.split(":"))
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    delta = (now - target).total_seconds()

    return 0 <= delta < tolerance_seconds


# ── Order-status triggers ────────────────────────────────────────────

def evaluate_order_status_trigger(
    rule: MonitorRule,
    order_event: dict,
) -> bool:
    """Evaluate an order-status trigger against an order event.

    Args:
        rule: MonitorRule with trigger_type="order_status".
        order_event: Dict with at least ``order_id`` and ``status`` keys.

    Returns:
        True if the event's order_id and status match the trigger config.
    """
    cfg = OrderStatusTrigger(**rule.trigger_config)

    event_order_id = order_event.get("order_id")
    event_status = order_event.get("status")

    return event_order_id == cfg.order_id and event_status == cfg.status
