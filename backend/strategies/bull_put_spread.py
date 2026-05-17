"""Bull Put Spread strategy template.

Sell higher strike PE, buy lower strike PE. Net credit spread ("earn first").
Credit lands in the account on entry; you keep it if the underlying closes
above the sold strike. Bullish / sideways view.
Max profit = net credit received.
Max loss = (sell_strike - buy_strike) * qty - net_credit.
"""
from __future__ import annotations

from typing import Any

from strategies.fno_utils import resolve_option_instrument
from strategies.templates import RuleSpec, StrategyPlan, StrategyTemplate


class BullPutSpreadTemplate(StrategyTemplate):
    name = "bull-put-spread"
    category = "fno"
    description = (
        "Bull Put Spread — sell higher strike PE, buy lower strike PE. "
        "Net credit ('earn first'); profits when underlying stays above the "
        "sold strike. Limited risk, limited reward. Bullish / sideways view."
    )
    required_params = ["underlying", "expiry", "sell_strike", "buy_strike", "lots"]
    optional_params = {
        "product": "D",
        "squareoff_time": "15:15",
        "entry_time": "09:20",
    }

    def plan(self, symbol: str, params: dict[str, Any]) -> StrategyPlan:
        p = self.validate_params(params)
        underlying = p["underlying"].upper()
        expiry = p["expiry"]
        sell_strike = float(p["sell_strike"])
        buy_strike = float(p["buy_strike"])
        lots = int(p["lots"])
        product = p["product"]
        squareoff = p["squareoff_time"]
        entry_time = p["entry_time"]

        if buy_strike >= sell_strike:
            raise ValueError("buy_strike must be lower than sell_strike for a bull put spread")

        sell_pe = resolve_option_instrument(underlying, expiry, sell_strike, "PE")
        buy_pe = resolve_option_instrument(underlying, expiry, buy_strike, "PE")
        lot_size = sell_pe["lot_size"]
        qty = lots * lot_size

        spread_width = sell_strike - buy_strike

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

        plan = StrategyPlan(
            template_name=self.name,
            symbol=underlying,
            summary=(
                f"Bull Put Spread {underlying}: "
                f"SELL {sell_strike}PE + BUY {buy_strike}PE x{lots}L, "
                f"spread width {spread_width}, net credit, squareoff {squareoff}"
            ),
            params=p,
        )

        # Unique role per leg. Squareoffs start disabled; each entry
        # activates its own leg's squareoff. Prevents rogue exits if entry
        # never fired.
        plan.rules = [
            RuleSpec(
                name=f"{underlying} BuPS SELL {sell_strike}PE",
                trigger_type="time",
                trigger_config=time_trigger,
                action_type="place_order",
                action_config={
                    "symbol": underlying,
                    "instrument_token": sell_pe["instrument_key"],
                    "transaction_type": "SELL",
                    "quantity": qty,
                    "order_type": "MARKET",
                    "product": product,
                },
                role="entry_short_pe",
                activates_roles=["squareoff_short_pe"],
            ),
            RuleSpec(
                name=f"{underlying} BuPS BUY {buy_strike}PE",
                trigger_type="time",
                trigger_config=time_trigger,
                action_type="place_order",
                action_config={
                    "symbol": underlying,
                    "instrument_token": buy_pe["instrument_key"],
                    "transaction_type": "BUY",
                    "quantity": qty,
                    "order_type": "MARKET",
                    "product": product,
                },
                role="entry_long_pe",
                activates_roles=["squareoff_long_pe"],
            ),
            RuleSpec(
                name=f"{underlying} BuPS Squareoff SELL {sell_strike}PE @ {squareoff}",
                trigger_type="time",
                trigger_config=squareoff_trigger,
                action_type="place_order",
                action_config={
                    "symbol": underlying,
                    "instrument_token": sell_pe["instrument_key"],
                    "transaction_type": "BUY",
                    "quantity": qty,
                    "order_type": "MARKET",
                    "product": product,
                },
                role="squareoff_short_pe",
                enabled=False,
            ),
            RuleSpec(
                name=f"{underlying} BuPS Squareoff BUY {buy_strike}PE @ {squareoff}",
                trigger_type="time",
                trigger_config=squareoff_trigger,
                action_type="place_order",
                action_config={
                    "symbol": underlying,
                    "instrument_token": buy_pe["instrument_key"],
                    "transaction_type": "SELL",
                    "quantity": qty,
                    "order_type": "MARKET",
                    "product": product,
                },
                role="squareoff_long_pe",
                enabled=False,
            ),
        ]

        return plan
