"""Scalp strategy template.

Tight-range scalping with small SL, quick target, and trailing stop.
Allows multiple entries via max_fires.
"""
from __future__ import annotations

from typing import Any

from strategies.sizing import compute_quantity, compute_target
from strategies.templates import RuleSpec, StrategyPlan, StrategyTemplate


class ScalpTemplate(StrategyTemplate):
    name = "scalp"
    description = (
        "Scalp — tight range trading with small SL and quick target. "
        "Supports multiple entries via max-fires. Creates entry, SL, target, and trailing rules."
    )
    required_params = ["capital", "entry", "sl"]
    optional_params = {
        "risk_percent": 1.0,       # Tighter risk for scalps
        "rr_ratio": 1.5,           # Lower R:R (quick exits)
        "product": "I",
        "trail_percent": 0.5,      # Tight trail for scalps
        "max_entries": 3,           # Allow re-entries
        "target": None,
        "squareoff_time": "15:15",
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
        max_entries = p["max_entries"]
        squareoff = p["squareoff_time"]

        target = p.get("target") or compute_target(entry, sl, rr)
        qty = compute_quantity(capital, risk_pct, entry, sl, product=product)

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
            summary=f"Scalp {label} {symbol}: entry {entry}, SL {sl}, target {target}, max {max_entries} entries",
            params=p,
        )

        plan.rules = [
            # Entry (allows re-entries)
            RuleSpec(
                name=f"{symbol} Scalp {label} Entry @ {entry}",
                trigger_type="price",
                trigger_config={"condition": entry_cond, "price": entry, "reference": "ltp"},
                action_type="place_order",
                action_config={
                    "symbol": symbol, "transaction_type": side_entry,
                    "quantity": qty, "order_type": "MARKET", "product": product,
                },
                max_fires=max_entries,
                role="entry",
            ),
            # SL (fires for each entry)
            RuleSpec(
                name=f"{symbol} Scalp SL @ {sl}",
                trigger_type="price",
                trigger_config={"condition": sl_cond, "price": sl, "reference": "ltp"},
                action_type="place_order",
                action_config={
                    "symbol": symbol, "transaction_type": side_exit,
                    "quantity": qty, "order_type": "MARKET", "product": product,
                },
                max_fires=max_entries,
                role="sl",
                kills_roles=["target", "trailing", "squareoff"],
            ),
            # Target
            RuleSpec(
                name=f"{symbol} Scalp Target @ {target}",
                trigger_type="price",
                trigger_config={"condition": target_cond, "price": target, "reference": "ltp"},
                action_type="place_order",
                action_config={
                    "symbol": symbol, "transaction_type": side_exit,
                    "quantity": qty, "order_type": "MARKET", "product": product,
                },
                max_fires=max_entries,
                role="target",
                kills_roles=["sl", "trailing", "squareoff"],
            ),
            # Trailing stop
            RuleSpec(
                name=f"{symbol} Scalp Trail {trail_pct}%",
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
                kills_roles=["sl", "target", "squareoff"],
            ),
            # Auto square-off
            RuleSpec(
                name=f"{symbol} Scalp Square-Off @ {squareoff}",
                trigger_type="time",
                trigger_config={"at": squareoff, "on_days": ["mon", "tue", "wed", "thu", "fri"], "market_only": True},
                action_type="place_order",
                action_config={
                    "symbol": symbol, "transaction_type": side_exit,
                    "quantity": qty, "order_type": "MARKET", "product": product,
                },
                role="squareoff",
                kills_roles=["sl", "target", "trailing"],
            ),
        ]

        return plan
