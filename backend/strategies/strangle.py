"""Strangle strategy template.

Buy or sell CE and PE at different (OTM) strikes.
"""
from __future__ import annotations

from typing import Any

from strategies.fno_utils import resolve_option_instrument
from strategies.templates import RuleSpec, StrategyPlan, StrategyTemplate


class StrangleTemplate(StrategyTemplate):
    name = "strangle"
    category = "fno"
    description = (
        "Strangle — buy or sell CE and PE at different strikes. "
        "Wider range than straddle; lower premium but needs bigger moves (long) "
        "or collects less but has wider safety (short)."
    )
    required_params = ["underlying", "expiry", "call_strike", "put_strike", "lots"]
    optional_params = {
        "direction": "sell",
        "product": "D",
        "squareoff_time": "15:15",
        "sl_percent": 30,
        "entry_time": "09:20",
    }

    def plan(self, symbol: str, params: dict[str, Any]) -> StrategyPlan:
        p = self.validate_params(params)
        underlying = p["underlying"].upper()
        expiry = p["expiry"]
        call_strike = float(p["call_strike"])
        put_strike = float(p["put_strike"])
        lots = int(p["lots"])
        direction = p["direction"].lower()
        product = p["product"]
        squareoff = p["squareoff_time"]
        sl_pct = float(p["sl_percent"])
        entry_time = p["entry_time"]

        ce = resolve_option_instrument(underlying, expiry, call_strike, "CE")
        pe = resolve_option_instrument(underlying, expiry, put_strike, "PE")
        lot_size = ce["lot_size"]
        qty = lots * lot_size

        entry_side = "SELL" if direction == "sell" else "BUY"
        exit_side = "BUY" if direction == "sell" else "SELL"
        label = "Short" if direction == "sell" else "Long"

        time_trigger = {
            "at": entry_time,
            "on_days": ["mon", "tue", "wed", "thu", "fri"],
            "market_only": True,
        }

        plan = StrategyPlan(
            template_name=self.name,
            symbol=underlying,
            summary=(
                f"{label} Strangle {underlying}: "
                f"{entry_side} {call_strike}CE + {put_strike}PE x{lots}L, "
                f"SL {sl_pct}%, squareoff {squareoff}"
            ),
            params=p,
        )

        legs = [
            ("CE", call_strike, ce),
            ("PE", put_strike, pe),
        ]

        rules: list[RuleSpec] = []

        # Entry legs
        for leg_name, strike, inst in legs:
            rules.append(RuleSpec(
                name=f"{underlying} {label} Strangle {entry_side} {strike}{leg_name}",
                trigger_type="time",
                trigger_config=time_trigger,
                action_type="place_order",
                action_config={
                    "symbol": underlying,
                    "instrument_token": inst["instrument_key"],
                    "transaction_type": entry_side,
                    "quantity": qty,
                    "order_type": "MARKET",
                    "product": product,
                },
                role="entry",
            ))

        # Stop-loss legs
        if direction == "sell":
            for leg_name, strike, inst in legs:
                rules.append(RuleSpec(
                    name=f"{underlying} Strangle SL {strike}{leg_name} (+{sl_pct}%)",
                    trigger_type="price",
                    trigger_config={
                        "condition": "gte",
                        "price": 0,
                        "reference": "ltp",
                        "note": f"Set to entry_premium * {1 + sl_pct/100:.2f} at deployment",
                    },
                    action_type="place_order",
                    action_config={
                        "symbol": underlying,
                        "instrument_token": inst["instrument_key"],
                        "transaction_type": exit_side,
                        "quantity": qty,
                        "order_type": "MARKET",
                        "product": product,
                    },
                    role="sl",
                ))

        # Auto square-off
        for leg_name, strike, inst in legs:
            rules.append(RuleSpec(
                name=f"{underlying} Strangle Squareoff {strike}{leg_name} @ {squareoff}",
                trigger_type="time",
                trigger_config={
                    "at": squareoff,
                    "on_days": ["mon", "tue", "wed", "thu", "fri"],
                    "market_only": True,
                },
                action_type="place_order",
                action_config={
                    "symbol": underlying,
                    "instrument_token": inst["instrument_key"],
                    "transaction_type": exit_side,
                    "quantity": qty,
                    "order_type": "MARKET",
                    "product": product,
                },
                role="squareoff",
            ))

        plan.rules = rules
        return plan
