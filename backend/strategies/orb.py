"""Opening Range Breakout (ORB) strategy template.

Creates rules for:
1. Long entry: price breaks above the opening range high
2. Short entry: price breaks below the opening range low
3. Stop-loss for whichever entry fires
4. Target based on R:R ratio
5. Trailing stop after entry
6. Auto square-off at 15:15 IST
"""
from __future__ import annotations

from typing import Any

from strategies.sizing import compute_quantity, compute_target
from strategies.templates import RuleSpec, StrategyPlan, StrategyTemplate


class ORBTemplate(StrategyTemplate):
    name = "orb"
    description = (
        "Opening Range Breakout — enters on breakout of the first N-minute range. "
        "Creates entry, SL, target, trailing stop, and auto square-off rules."
    )
    required_params = ["capital"]
    optional_params = {
        "risk_percent": 2.0,
        "rr_ratio": 2.0,
        "range_minutes": 15,
        "product": "I",
        "trail_percent": 1.5,
        "squareoff_time": "15:15",
        "side": "both",       # "long", "short", or "both"
        # If provided, these override auto-detection (for pre-market planning)
        "range_high": None,
        "range_low": None,
    }

    def plan(self, symbol: str, params: dict[str, Any]) -> StrategyPlan:
        p = self.validate_params(params)
        capital = p["capital"]
        risk_pct = p["risk_percent"]
        rr = p["rr_ratio"]
        product = p["product"]
        trail_pct = p["trail_percent"]
        squareoff = p["squareoff_time"]
        side = p["side"]

        range_high = p.get("range_high")
        range_low = p.get("range_low")

        if not range_high or not range_low:
            raise ValueError(
                "ORB requires --range-high and --range-low (the opening range). "
                "Run after the first 15 minutes, or provide manually."
            )

        plan = StrategyPlan(
            template_name=self.name,
            symbol=symbol,
            summary=f"ORB {symbol}: range [{range_low}-{range_high}], capital ₹{capital}, R:R {rr}:1",
            params=p,
        )

        rules: list[RuleSpec] = []

        if side in ("long", "both"):
            sl_long = range_low
            qty_long = compute_quantity(capital, risk_pct, range_high, sl_long, product=product)
            target_long = compute_target(range_high, sl_long, rr)

            # Long entry
            rules.append(RuleSpec(
                name=f"{symbol} ORB Long Entry > {range_high}",
                trigger_type="price",
                trigger_config={"condition": "gte", "price": range_high, "reference": "ltp"},
                action_type="place_order",
                action_config={
                    "symbol": symbol, "transaction_type": "BUY",
                    "quantity": qty_long, "order_type": "MARKET", "product": product,
                },
                role="entry_long",
            ))
            # Long SL
            rules.append(RuleSpec(
                name=f"{symbol} ORB Long SL @ {sl_long}",
                trigger_type="price",
                trigger_config={"condition": "lte", "price": sl_long, "reference": "ltp"},
                action_type="place_order",
                action_config={
                    "symbol": symbol, "transaction_type": "SELL",
                    "quantity": qty_long, "order_type": "MARKET", "product": product,
                },
                role="sl_long",
                kills_roles=["target_long", "trailing_long", "squareoff"],
            ))
            # Long target
            rules.append(RuleSpec(
                name=f"{symbol} ORB Long Target @ {target_long}",
                trigger_type="price",
                trigger_config={"condition": "gte", "price": target_long, "reference": "ltp"},
                action_type="place_order",
                action_config={
                    "symbol": symbol, "transaction_type": "SELL",
                    "quantity": qty_long, "order_type": "MARKET", "product": product,
                },
                role="target_long",
                kills_roles=["sl_long", "trailing_long", "squareoff"],
            ))
            # Long trailing stop
            rules.append(RuleSpec(
                name=f"{symbol} ORB Long Trail {trail_pct}%",
                trigger_type="trailing_stop",
                trigger_config={
                    "trail_percent": trail_pct, "initial_price": range_high,
                    "highest_price": range_high, "direction": "long", "reference": "ltp",
                },
                action_type="place_order",
                action_config={
                    "symbol": symbol, "transaction_type": "SELL",
                    "quantity": qty_long, "order_type": "MARKET", "product": product,
                },
                role="trailing_long",
                kills_roles=["sl_long", "target_long", "squareoff"],
            ))

        if side in ("short", "both"):
            sl_short = range_high
            qty_short = compute_quantity(capital, risk_pct, range_low, sl_short, product=product)
            target_short = compute_target(range_low, sl_short, rr)

            # Short entry
            rules.append(RuleSpec(
                name=f"{symbol} ORB Short Entry < {range_low}",
                trigger_type="price",
                trigger_config={"condition": "lte", "price": range_low, "reference": "ltp"},
                action_type="place_order",
                action_config={
                    "symbol": symbol, "transaction_type": "SELL",
                    "quantity": qty_short, "order_type": "MARKET", "product": product,
                },
                role="entry_short",
            ))
            # Short SL
            rules.append(RuleSpec(
                name=f"{symbol} ORB Short SL @ {sl_short}",
                trigger_type="price",
                trigger_config={"condition": "gte", "price": sl_short, "reference": "ltp"},
                action_type="place_order",
                action_config={
                    "symbol": symbol, "transaction_type": "BUY",
                    "quantity": qty_short, "order_type": "MARKET", "product": product,
                },
                role="sl_short",
                kills_roles=["target_short", "trailing_short", "squareoff"],
            ))
            # Short target
            rules.append(RuleSpec(
                name=f"{symbol} ORB Short Target @ {target_short}",
                trigger_type="price",
                trigger_config={"condition": "lte", "price": target_short, "reference": "ltp"},
                action_type="place_order",
                action_config={
                    "symbol": symbol, "transaction_type": "BUY",
                    "quantity": qty_short, "order_type": "MARKET", "product": product,
                },
                role="target_short",
                kills_roles=["sl_short", "trailing_short", "squareoff"],
            ))
            # Short trailing stop
            rules.append(RuleSpec(
                name=f"{symbol} ORB Short Trail {trail_pct}%",
                trigger_type="trailing_stop",
                trigger_config={
                    "trail_percent": trail_pct, "initial_price": range_low,
                    "lowest_price": range_low, "direction": "short", "reference": "ltp",
                },
                action_type="place_order",
                action_config={
                    "symbol": symbol, "transaction_type": "BUY",
                    "quantity": qty_short, "order_type": "MARKET", "product": product,
                },
                role="trailing_short",
                kills_roles=["sl_short", "target_short", "squareoff"],
            ))

        # Auto square-off (covers both sides)
        # Use max qty between long and short
        max_qty = max(
            compute_quantity(capital, risk_pct, range_high, range_low, product=product) if side in ("long", "both") else 0,
            compute_quantity(capital, risk_pct, range_low, range_high, product=product) if side in ("short", "both") else 0,
        )
        rules.append(RuleSpec(
            name=f"{symbol} ORB Auto Square-Off @ {squareoff}",
            trigger_type="time",
            trigger_config={"at": squareoff, "on_days": ["mon", "tue", "wed", "thu", "fri"], "market_only": True},
            action_type="place_order",
            action_config={
                "symbol": symbol, "transaction_type": "SELL",
                "quantity": max_qty, "order_type": "MARKET", "product": product,
            },
            role="squareoff",
            kills_roles=["sl_long", "target_long", "trailing_long", "sl_short", "target_short", "trailing_short"],
        ))

        plan.rules = rules
        return plan
