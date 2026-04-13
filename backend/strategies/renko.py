"""Renko reversal strategy template.

Enters on Renko brick color change (trend reversal) with SL, trailing stop,
and time-based square-off. Traditional Renko with configurable brick size.

- Long entry: Renko turns green (up) after red bricks
- Short entry: Renko turns red (down) after green bricks
- Exit: opposite Renko reversal, SL, trailing stop, or square-off
"""
from __future__ import annotations

from typing import Any

from strategies.sizing import compute_quantity
from strategies.templates import RuleSpec, StrategyPlan, StrategyTemplate


class RenkoTemplate(StrategyTemplate):
    name = "renko"
    description = (
        "Renko reversal — enters when Renko chart changes direction. "
        "Traditional brick size, exits on reverse signal, SL, or trailing stop."
    )
    required_params = ["capital"]
    optional_params = {
        "brick_size": 15.0,
        "direction": "both",  # "long", "short", or "both"
        "sl_bricks": 2,  # SL = brick_size * sl_bricks below/above entry
        "risk_percent": 2.0,
        "trail_percent": 1.5,
        "product": "I",
        "squareoff_time": "15:15",
    }

    def plan(self, symbol: str, params: dict[str, Any]) -> StrategyPlan:
        p = self.validate_params(params)
        capital = p["capital"]
        brick_size = p["brick_size"]
        direction = p["direction"]
        sl_bricks = p["sl_bricks"]
        risk_pct = p["risk_percent"]
        trail_pct = p["trail_percent"]
        product = p["product"]
        squareoff = p["squareoff_time"]

        plan = StrategyPlan(
            template_name=self.name,
            symbol=symbol,
            summary=(
                f"Renko Reversal {symbol}: brick=₹{brick_size}, "
                f"SL={sl_bricks} bricks, direction={direction}"
            ),
            params=p,
        )

        # Estimate SL distance for position sizing
        sl_distance = brick_size * sl_bricks
        # Use a reasonable entry price estimate (will be refined at runtime)
        estimated_entry = 1000  # placeholder, actual qty computed by engine
        qty = compute_quantity(capital, risk_pct, estimated_entry, estimated_entry - sl_distance, product=product)
        qty = max(qty, 1)

        if direction in ("long", "both"):
            plan.rules.extend(self._long_rules(symbol, brick_size, sl_bricks, qty, trail_pct, product, squareoff))

        if direction in ("short", "both"):
            plan.rules.extend(self._short_rules(symbol, brick_size, sl_bricks, qty, trail_pct, product, squareoff))

        return plan

    def _long_rules(self, symbol, brick_size, sl_bricks, qty, trail_pct, product, squareoff):
        # Long-side rules. Each side owns its own squareoff so direction=short
        # also gets a time-based safety net (previously only the long side
        # emitted one). Exits start disabled and self-disable so re-entry
        # re-activates them.
        return [
            RuleSpec(
                name=f"{symbol} Renko Long Entry (brick ₹{brick_size})",
                trigger_type="renko",
                trigger_config={
                    "brick_size": brick_size,
                    "condition": "reversal_up",
                },
                action_type="place_order",
                action_config={
                    "symbol": symbol, "transaction_type": "BUY",
                    "quantity": qty, "order_type": "MARKET", "product": product,
                },
                role="entry_long",
                max_fires=None,
                activates_roles=["sl_long", "trailing_long", "squareoff_long"],
            ),
            RuleSpec(
                name=f"{symbol} Renko Long Exit (reversal down)",
                trigger_type="renko",
                trigger_config={
                    "brick_size": brick_size,
                    "condition": "reversal_down",
                },
                action_type="place_order",
                action_config={
                    "symbol": symbol, "transaction_type": "SELL",
                    "quantity": qty, "order_type": "MARKET", "product": product,
                },
                role="sl_long",
                enabled=False,
                kills_roles=["sl_long", "trailing_long", "squareoff_long"],
                max_fires=None,
            ),
            RuleSpec(
                name=f"{symbol} Renko Long Trail {trail_pct}%",
                trigger_type="trailing_stop",
                trigger_config={
                    "trail_percent": trail_pct, "initial_price": 0,
                    "highest_price": 0, "direction": "long", "reference": "ltp",
                },
                action_type="place_order",
                action_config={
                    "symbol": symbol, "transaction_type": "SELL",
                    "quantity": qty, "order_type": "MARKET", "product": product,
                },
                role="trailing_long",
                enabled=False,
                kills_roles=["sl_long", "trailing_long", "squareoff_long"],
            ),
            RuleSpec(
                name=f"{symbol} Renko Long Square-Off @ {squareoff}",
                trigger_type="time",
                trigger_config={"at": squareoff, "on_days": ["mon", "tue", "wed", "thu", "fri"], "market_only": True},
                action_type="place_order",
                action_config={
                    "symbol": symbol, "transaction_type": "SELL",
                    "quantity": qty, "order_type": "MARKET", "product": product,
                },
                role="squareoff_long",
                enabled=False,
                kills_roles=["sl_long", "trailing_long"],
            ),
        ]

    def _short_rules(self, symbol, brick_size, sl_bricks, qty, trail_pct, product, squareoff):
        # Short-side rules with their own squareoff (previously missing —
        # direction="short" had no time-based auto close).
        return [
            RuleSpec(
                name=f"{symbol} Renko Short Entry (brick ₹{brick_size})",
                trigger_type="renko",
                trigger_config={
                    "brick_size": brick_size,
                    "condition": "reversal_down",
                },
                action_type="place_order",
                action_config={
                    "symbol": symbol, "transaction_type": "SELL",
                    "quantity": qty, "order_type": "MARKET", "product": product,
                },
                role="entry_short",
                max_fires=None,
                activates_roles=["sl_short", "trailing_short", "squareoff_short"],
            ),
            RuleSpec(
                name=f"{symbol} Renko Short Exit (reversal up)",
                trigger_type="renko",
                trigger_config={
                    "brick_size": brick_size,
                    "condition": "reversal_up",
                },
                action_type="place_order",
                action_config={
                    "symbol": symbol, "transaction_type": "BUY",
                    "quantity": qty, "order_type": "MARKET", "product": product,
                },
                role="sl_short",
                enabled=False,
                kills_roles=["sl_short", "trailing_short", "squareoff_short"],
                max_fires=None,
            ),
            RuleSpec(
                name=f"{symbol} Renko Short Trail {trail_pct}%",
                trigger_type="trailing_stop",
                trigger_config={
                    "trail_percent": trail_pct, "initial_price": 0,
                    "lowest_price": float("inf"), "direction": "short", "reference": "ltp",
                },
                action_type="place_order",
                action_config={
                    "symbol": symbol, "transaction_type": "BUY",
                    "quantity": qty, "order_type": "MARKET", "product": product,
                },
                role="trailing_short",
                enabled=False,
                kills_roles=["sl_short", "trailing_short", "squareoff_short"],
            ),
            RuleSpec(
                name=f"{symbol} Renko Short Square-Off @ {squareoff}",
                trigger_type="time",
                trigger_config={"at": squareoff, "on_days": ["mon", "tue", "wed", "thu", "fri"], "market_only": True},
                action_type="place_order",
                action_config={
                    "symbol": symbol, "transaction_type": "BUY",
                    "quantity": qty, "order_type": "MARKET", "product": product,
                },
                role="squareoff_short",
                enabled=False,
                kills_roles=["sl_short", "trailing_short"],
            ),
        ]
