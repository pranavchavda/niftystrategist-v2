"""Iron Condor strategy template.

Sell a call spread + sell a put spread. 4 legs, net credit.
Profits when underlying stays within the sold strikes range.
Max profit = net credit received.
Max loss = spread width - net credit (on either side).
"""
from __future__ import annotations

from typing import Any

from strategies.fno_utils import resolve_option_instrument
from strategies.templates import RuleSpec, StrategyPlan, StrategyTemplate


class IronCondorTemplate(StrategyTemplate):
    name = "iron-condor"
    category = "fno"
    description = (
        "Iron Condor — sell OTM call spread + sell OTM put spread (4 legs). "
        "Net credit strategy that profits when underlying stays range-bound."
    )
    required_params = [
        "underlying", "expiry",
        "call_sell_strike", "call_buy_strike",
        "put_sell_strike", "put_buy_strike",
        "lots",
    ]
    optional_params = {
        "product": "D",
        "squareoff_time": "15:15",
        "entry_time": "09:20",
    }

    def plan(self, symbol: str, params: dict[str, Any]) -> StrategyPlan:
        p = self.validate_params(params)
        underlying = p["underlying"].upper()
        expiry = p["expiry"]
        call_sell = float(p["call_sell_strike"])
        call_buy = float(p["call_buy_strike"])
        put_sell = float(p["put_sell_strike"])
        put_buy = float(p["put_buy_strike"])
        lots = int(p["lots"])
        product = p["product"]
        squareoff = p["squareoff_time"]
        entry_time = p["entry_time"]

        if call_buy <= call_sell:
            raise ValueError("call_buy_strike must be higher than call_sell_strike")
        if put_buy >= put_sell:
            raise ValueError("put_buy_strike must be lower than put_sell_strike")

        # Resolve all 4 instruments
        ce_sell = resolve_option_instrument(underlying, expiry, call_sell, "CE")
        ce_buy = resolve_option_instrument(underlying, expiry, call_buy, "CE")
        pe_sell = resolve_option_instrument(underlying, expiry, put_sell, "PE")
        pe_buy = resolve_option_instrument(underlying, expiry, put_buy, "PE")
        lot_size = ce_sell["lot_size"]
        qty = lots * lot_size

        time_trigger = {
            "at": entry_time,
            "on_days": ["mon", "tue", "wed", "thu", "fri"],
            "market_only": True,
        }
        squareoff_trigger = {
            "at": squareoff,
            "on_days": ["mon", "tue", "wed", "thu", "fri"],
            "market_only": True,
        }

        # Define all 4 legs: (label, instrument, entry_side, exit_side, role_suffix)
        legs = [
            (f"SELL {call_sell}CE", ce_sell, "SELL", "BUY", "short_call"),
            (f"BUY {call_buy}CE", ce_buy, "BUY", "SELL", "long_call"),
            (f"SELL {put_sell}PE", pe_sell, "SELL", "BUY", "short_put"),
            (f"BUY {put_buy}PE", pe_buy, "BUY", "SELL", "long_put"),
        ]

        plan = StrategyPlan(
            template_name=self.name,
            symbol=underlying,
            summary=(
                f"Iron Condor {underlying}: "
                f"SELL {call_sell}/{call_buy}CE + SELL {put_sell}/{put_buy}PE x{lots}L, "
                f"squareoff {squareoff}"
            ),
            params=p,
        )

        # Unique role per leg. Squareoffs start disabled; each entry
        # activates its own leg's squareoff. Prevents a rogue squareoff at
        # 15:15 if entry never fired (e.g. deploy after entry_time).
        rules: list[RuleSpec] = []

        for label, inst, entry_side, _, suffix in legs:
            rules.append(RuleSpec(
                name=f"{underlying} IC {label}",
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
                role=f"entry_{suffix}",
                activates_roles=[f"squareoff_{suffix}"],
            ))

        for label, inst, _, exit_side, suffix in legs:
            rules.append(RuleSpec(
                name=f"{underlying} IC Squareoff {label} @ {squareoff}",
                trigger_type="time",
                trigger_config=squareoff_trigger,
                action_type="place_order",
                action_config={
                    "symbol": underlying,
                    "instrument_token": inst["instrument_key"],
                    "transaction_type": exit_side,
                    "quantity": qty,
                    "order_type": "MARKET",
                    "product": product,
                },
                role=f"squareoff_{suffix}",
                enabled=False,
            ))

        plan.rules = rules
        return plan
