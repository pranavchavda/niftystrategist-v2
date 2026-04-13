"""Breakout strategy template.

Simple level breakout with SL, target, and trailing stop.
"""
from __future__ import annotations

from typing import Any

from strategies.sizing import compute_quantity, compute_target
from strategies.templates import RuleSpec, StrategyPlan, StrategyTemplate


class BreakoutTemplate(StrategyTemplate):
    name = "breakout"
    description = (
        "Level breakout — enters when price crosses a key level. "
        "Creates entry, SL, target, and trailing stop rules."
    )
    required_params = ["capital", "entry", "sl"]
    optional_params = {
        "risk_percent": 2.0,
        "rr_ratio": 2.0,
        "product": "I",
        "trail_percent": 1.5,
        "squareoff_time": "15:15",
        "target": None,  # Auto-calculated from R:R if not provided
    }

    def plan(self, symbol: str, params: dict[str, Any]) -> StrategyPlan:
        p = self.validate_params(params)
        entry = p["entry"]
        sl = p["sl"]
        capital = p["capital"]
        risk_pct = p["risk_percent"]
        rr = p["rr_ratio"]
        product = p["product"]
        trail_pct = p["trail_percent"]
        squareoff = p["squareoff_time"]

        target = p.get("target") or compute_target(entry, sl, rr)
        qty = compute_quantity(capital, risk_pct, entry, sl, product=product)

        # Determine direction from entry vs SL
        is_long = entry > sl
        side_entry = "BUY" if is_long else "SELL"
        side_exit = "SELL" if is_long else "BUY"
        entry_cond = "gte" if is_long else "lte"
        sl_cond = "lte" if is_long else "gte"
        target_cond = "gte" if is_long else "lte"
        direction = "long" if is_long else "short"
        label = "Long" if is_long else "Short"

        plan = StrategyPlan(
            template_name=self.name,
            symbol=symbol,
            summary=f"Breakout {label} {symbol}: entry {entry}, SL {sl}, target {target}, qty {qty}",
            params=p,
        )

        # Exits start disabled and are activated only when the entry fires.
        # Prevents rogue positions if an exit level is hit before entry (e.g. SL
        # triggers a BUY on a short-side strategy that never entered the market).
        plan.rules = [
            RuleSpec(
                name=f"{symbol} Breakout {label} Entry @ {entry}",
                trigger_type="price",
                trigger_config={"condition": entry_cond, "price": entry, "reference": "ltp"},
                action_type="place_order",
                action_config={
                    "symbol": symbol, "transaction_type": side_entry,
                    "quantity": qty, "order_type": "MARKET", "product": product,
                },
                role="entry",
                activates_roles=["sl", "target", "trailing", "squareoff"],
            ),
            RuleSpec(
                name=f"{symbol} Breakout SL @ {sl}",
                trigger_type="price",
                trigger_config={"condition": sl_cond, "price": sl, "reference": "ltp"},
                action_type="place_order",
                action_config={
                    "symbol": symbol, "transaction_type": side_exit,
                    "quantity": qty, "order_type": "MARKET", "product": product,
                },
                role="sl",
                enabled=False,
                kills_roles=["target", "trailing", "squareoff"],
            ),
            RuleSpec(
                name=f"{symbol} Breakout Target @ {target}",
                trigger_type="price",
                trigger_config={"condition": target_cond, "price": target, "reference": "ltp"},
                action_type="place_order",
                action_config={
                    "symbol": symbol, "transaction_type": side_exit,
                    "quantity": qty, "order_type": "MARKET", "product": product,
                },
                role="target",
                enabled=False,
                kills_roles=["sl", "trailing", "squareoff"],
            ),
            RuleSpec(
                name=f"{symbol} Breakout Trail {trail_pct}%",
                trigger_type="trailing_stop",
                trigger_config={
                    "trail_percent": trail_pct, "initial_price": entry,
                    "highest_price" if is_long else "lowest_price": entry,
                    "direction": direction, "reference": "ltp",
                },
                action_type="place_order",
                action_config={
                    "symbol": symbol, "transaction_type": side_exit,
                    "quantity": qty, "order_type": "MARKET", "product": product,
                },
                role="trailing",
                enabled=False,
                kills_roles=["sl", "target", "squareoff"],
            ),
            RuleSpec(
                name=f"{symbol} Breakout Square-Off @ {squareoff}",
                trigger_type="time",
                trigger_config={"at": squareoff, "on_days": ["mon", "tue", "wed", "thu", "fri"], "market_only": True},
                action_type="place_order",
                action_config={
                    "symbol": symbol, "transaction_type": side_exit,
                    "quantity": qty, "order_type": "MARKET", "product": product,
                },
                role="squareoff",
                enabled=False,
                kills_roles=["sl", "target", "trailing"],
            ),
        ]

        return plan
