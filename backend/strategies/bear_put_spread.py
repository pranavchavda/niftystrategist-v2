"""Bear Put Spread strategy template.

Buy higher strike PE, sell lower strike PE. Net debit spread.
Max profit = (buy_strike - sell_strike) * qty - net_debit.
Max loss = net_debit.
"""
from __future__ import annotations

from typing import Any

from strategies.fno_utils import resolve_option_instrument
from strategies.templates import RuleSpec, StrategyPlan, StrategyTemplate


class BearPutSpreadTemplate(StrategyTemplate):
    name = "bear-put-spread"
    category = "fno"
    description = (
        "Bear Put Spread — buy higher strike PE, sell lower strike PE. "
        "Limited risk (net debit), limited reward. Bearish directional bet."
    )
    required_params = ["underlying", "expiry", "buy_strike", "sell_strike", "lots"]
    optional_params = {
        "product": "D",
        "squareoff_time": "15:15",
        "entry_time": "09:20",
    }

    def plan(self, symbol: str, params: dict[str, Any]) -> StrategyPlan:
        p = self.validate_params(params)
        underlying = p["underlying"].upper()
        expiry = p["expiry"]
        buy_strike = float(p["buy_strike"])
        sell_strike = float(p["sell_strike"])
        lots = int(p["lots"])
        product = p["product"]
        squareoff = p["squareoff_time"]
        entry_time = p["entry_time"]

        if buy_strike <= sell_strike:
            raise ValueError("buy_strike must be higher than sell_strike for a bear put spread")

        buy_pe = resolve_option_instrument(underlying, expiry, buy_strike, "PE")
        sell_pe = resolve_option_instrument(underlying, expiry, sell_strike, "PE")
        lot_size = buy_pe["lot_size"]
        qty = lots * lot_size

        spread_width = buy_strike - sell_strike

        time_trigger = {
            "at": entry_time,
            "on_days": ["mon", "tue", "wed", "thu", "fri"],
            "market_only": True,
        }

        plan = StrategyPlan(
            template_name=self.name,
            symbol=underlying,
            summary=(
                f"Bear Put Spread {underlying}: "
                f"BUY {buy_strike}PE + SELL {sell_strike}PE x{lots}L, "
                f"spread width {spread_width}, squareoff {squareoff}"
            ),
            params=p,
        )

        plan.rules = [
            # Buy higher strike PE
            RuleSpec(
                name=f"{underlying} BPS BUY {buy_strike}PE",
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
                role="entry",
            ),
            # Sell lower strike PE
            RuleSpec(
                name=f"{underlying} BPS SELL {sell_strike}PE",
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
                role="entry",
            ),
            # Squareoff
            RuleSpec(
                name=f"{underlying} BPS Squareoff {buy_strike}PE @ {squareoff}",
                trigger_type="time",
                trigger_config={
                    "at": squareoff,
                    "on_days": ["mon", "tue", "wed", "thu", "fri"],
                    "market_only": True,
                },
                action_type="place_order",
                action_config={
                    "symbol": underlying,
                    "instrument_token": buy_pe["instrument_key"],
                    "transaction_type": "SELL",
                    "quantity": qty,
                    "order_type": "MARKET",
                    "product": product,
                },
                role="squareoff",
            ),
            RuleSpec(
                name=f"{underlying} BPS Squareoff {sell_strike}PE @ {squareoff}",
                trigger_type="time",
                trigger_config={
                    "at": squareoff,
                    "on_days": ["mon", "tue", "wed", "thu", "fri"],
                    "market_only": True,
                },
                action_type="place_order",
                action_config={
                    "symbol": underlying,
                    "instrument_token": sell_pe["instrument_key"],
                    "transaction_type": "BUY",
                    "quantity": qty,
                    "order_type": "MARKET",
                    "product": product,
                },
                role="squareoff",
            ),
        ]

        return plan
