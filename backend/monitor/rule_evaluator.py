"""Pure-function rule evaluators for the trade monitor.

No I/O, no DB, no network — takes a rule + context data and returns
whether the trigger condition fires (True) or not (False).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from monitor.models import (
    CancelRuleAction,
    CompoundTrigger,
    IndicatorTrigger,
    MonitorRule,
    OrderStatusTrigger,
    PriceTrigger,
    TimeTrigger,
    TrailingStopTrigger,
)


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


# ── Trailing stop triggers ──────────────────────────────────────────

def evaluate_trailing_stop_trigger(
    rule: MonitorRule,
    market_data: dict,
) -> tuple[bool, dict | None]:
    """Evaluate a trailing stop-loss trigger.

    Returns (fired, trigger_config_update).
    - fired=True when price drops to or below the trailing stop level.
    - trigger_config_update is non-None when highest_price needs updating.
    """
    cfg = TrailingStopTrigger(**rule.trigger_config)

    current = market_data.get(cfg.reference)
    if current is None:
        return False, None

    stop_price = cfg.highest_price * (1 - cfg.trail_percent / 100)

    # Check if price has dropped to/below the stop level
    if current <= stop_price:
        return True, None

    # Check if we have a new high
    if current > cfg.highest_price:
        updated = rule.trigger_config.copy()
        updated["highest_price"] = current
        return False, updated

    return False, None


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


# ── Indicator triggers ───────────────────────────────────────────────

def evaluate_indicator_trigger(
    rule: MonitorRule,
    indicator_values: dict,
    prev_indicator_values: dict | None = None,
) -> bool:
    """Evaluate an indicator trigger against pre-computed indicator values.

    The daemon pre-computes indicator values (RSI, MACD, etc.) and passes
    them in via ``indicator_values``.  This function just compares the
    current value against the configured threshold.

    Args:
        rule: MonitorRule with trigger_type="indicator".
        indicator_values: Dict keyed by ``{indicator}_{timeframe}``,
                          e.g. ``{"rsi_5m": 28.5, "macd_15m": -0.3}``.
        prev_indicator_values: Previous tick's indicator values.
                               Required for ``crosses_above`` / ``crosses_below``.

    Returns:
        True if the trigger condition is met, False otherwise.
    """
    cfg = IndicatorTrigger(**rule.trigger_config)

    key = f"{cfg.indicator}_{cfg.timeframe}"
    current = indicator_values.get(key)
    if current is None:
        return False

    if cfg.condition == "lte":
        return current <= cfg.value

    if cfg.condition == "gte":
        return current >= cfg.value

    if cfg.condition == "crosses_above":
        if prev_indicator_values is None:
            return False
        prev = prev_indicator_values.get(key)
        if prev is None:
            return False
        return prev < cfg.value and current >= cfg.value

    if cfg.condition == "crosses_below":
        if prev_indicator_values is None:
            return False
        prev = prev_indicator_values.get(key)
        if prev is None:
            return False
        return prev > cfg.value and current <= cfg.value

    return False


# ── Compound triggers ────────────────────────────────────────────────

def evaluate_compound_trigger(rule: MonitorRule, ctx: dict) -> bool:
    """Evaluate a compound trigger (AND/OR over a list of sub-conditions).

    Args:
        rule: MonitorRule with trigger_type="compound".
        ctx: Dict with keys ``market_data``, ``now``, ``order_event``.

    Returns:
        True if the compound condition is satisfied, False otherwise.
    """
    cfg = CompoundTrigger(**rule.trigger_config)

    results: list[bool] = []
    for condition in cfg.conditions:
        cond_type = condition["type"]

        # Build a minimal temporary rule so we can reuse existing evaluators
        temp_config = {k: v for k, v in condition.items() if k != "type"}
        temp_rule = MonitorRule(
            id=rule.id,
            user_id=rule.user_id,
            name=rule.name,
            trigger_type=cond_type,
            trigger_config=temp_config,
            action_type=rule.action_type,
            action_config=rule.action_config,
            instrument_token=rule.instrument_token,
        )

        if cond_type == "price":
            results.append(evaluate_price_trigger(temp_rule, ctx.get("market_data") or {}))
        elif cond_type == "time":
            now = ctx.get("now")
            if now is None:
                results.append(False)
            else:
                results.append(evaluate_time_trigger(temp_rule, now))
        elif cond_type == "order_status":
            results.append(evaluate_order_status_trigger(temp_rule, ctx.get("order_event") or {}))
        elif cond_type == "indicator":
            results.append(evaluate_indicator_trigger(
                temp_rule,
                ctx.get("indicator_values") or {},
                prev_indicator_values=ctx.get("prev_indicator_values"),
            ))
        else:
            results.append(False)

    if cfg.operator == "and":
        return all(results)
    else:  # "or"
        return any(results)


# ── Top-level entry point ────────────────────────────────────────────

@dataclass
class EvalContext:
    """Context passed to rule evaluation."""
    market_data: dict = field(default_factory=dict)
    prev_prices: dict = field(default_factory=dict)  # {instrument_token: prev_ltp}
    order_event: dict = field(default_factory=dict)
    now: datetime = field(default_factory=datetime.utcnow)
    indicator_values: dict = field(default_factory=dict)  # {"rsi_5m": 28.5, "macd_5m": -0.3, ...}
    prev_indicator_values: dict = field(default_factory=dict)  # previous tick's indicator values


@dataclass
class RuleResult:
    """Result of evaluating a single rule."""
    rule_id: int
    fired: bool = False
    skipped: bool = False
    action_type: str | None = None
    action_config: dict = field(default_factory=dict)
    rules_to_cancel: list[int] = field(default_factory=list)
    trigger_config_update: dict | None = None


def evaluate_rule(rule: MonitorRule, ctx: EvalContext) -> RuleResult:
    """Evaluate a single rule against the given context.

    This is the top-level entry point for the rule engine.

    Args:
        rule: The rule to evaluate.
        ctx: Evaluation context with market data, timestamps, etc.

    Returns:
        RuleResult indicating whether the rule fired, was skipped, and
        what actions (if any) should be executed.
    """
    result = RuleResult(rule_id=rule.id)

    # 1. Check if the rule should be evaluated at all
    if not rule.should_evaluate:
        result.skipped = True
        return result

    # 2. Dispatch to the appropriate trigger evaluator
    fired = False
    if rule.trigger_type == "price":
        prev_price = ctx.prev_prices.get(rule.instrument_token)
        fired = evaluate_price_trigger(rule, ctx.market_data, prev_price=prev_price)
    elif rule.trigger_type == "time":
        fired = evaluate_time_trigger(rule, ctx.now)
    elif rule.trigger_type == "order_status":
        fired = evaluate_order_status_trigger(rule, ctx.order_event)
    elif rule.trigger_type == "indicator":
        fired = evaluate_indicator_trigger(
            rule,
            ctx.indicator_values,
            prev_indicator_values=ctx.prev_indicator_values or None,
        )
    elif rule.trigger_type == "compound":
        compound_ctx = {
            "market_data": ctx.market_data,
            "now": ctx.now,
            "order_event": ctx.order_event,
            "indicator_values": ctx.indicator_values,
            "prev_indicator_values": ctx.prev_indicator_values or None,
        }
        fired = evaluate_compound_trigger(rule, compound_ctx)
    elif rule.trigger_type == "trailing_stop":
        fired, config_update = evaluate_trailing_stop_trigger(rule, ctx.market_data)
        result.trigger_config_update = config_update

    result.fired = fired

    # 3. If fired, populate action details
    if fired:
        result.action_type = rule.action_type
        result.action_config = rule.action_config

        if rule.action_type == "cancel_rule":
            cancel = CancelRuleAction(**rule.action_config)
            result.rules_to_cancel = [cancel.rule_id]

    return result
