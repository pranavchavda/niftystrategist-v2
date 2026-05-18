"""Bear Call Spread strategy template.

Sell lower strike CE, buy higher strike CE. Net credit spread ("earn first").
Credit lands in the account on entry; you keep it if the underlying closes
below the sold strike. Bearish / sideways view.
Max profit = net credit received.
Max loss = (buy_strike - sell_strike) * qty - net_credit.
"""
from __future__ import annotations

from typing import Any

from strategies.fno_utils import resolve_option_instrument
from strategies.templates import RuleSpec, StrategyPlan, StrategyTemplate


class BearCallSpreadTemplate(StrategyTemplate):
    name = "bear-call-spread"
    category = "fno"
    description = (
        "Bear Call Spread — sell lower strike CE, buy higher strike CE. "
        "Net credit ('earn first'); profits when underlying stays below the "
        "sold strike. Limited risk, limited reward. Bearish / sideways view."
    )
    required_params = ["underlying", "expiry", "sell_strike", "buy_strike", "lots"]
    optional_params = {
        "product": "D",
        "squareoff_time": "15:14",
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

        if buy_strike <= sell_strike:
            raise ValueError("buy_strike must be higher than sell_strike for a bear call spread")

        sell_ce = resolve_option_instrument(underlying, expiry, sell_strike, "CE")
        buy_ce = resolve_option_instrument(underlying, expiry, buy_strike, "CE")
        lot_size = sell_ce["lot_size"]
        qty = lots * lot_size

        spread_width = buy_strike - sell_strike

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
                f"Bear Call Spread {underlying}: "
                f"SELL {sell_strike}CE + BUY {buy_strike}CE x{lots}L, "
                f"spread width {spread_width}, net credit, squareoff {squareoff}"
            ),
            params=p,
        )

        # Unique role per leg so the deploy-time role_to_id map doesn't
        # collapse duplicates. Squareoffs start disabled; each entry
        # activates its own leg's squareoff. Prevents a rogue squareoff
        # from firing at 15:15 if entry never ran.
        plan.rules = [
            RuleSpec(
                name=f"{underlying} BeCS SELL {sell_strike}CE",
                trigger_type="time",
                trigger_config=time_trigger,
                action_type="place_order",
                action_config={
                    "symbol": underlying,
                    "instrument_token": sell_ce["instrument_key"],
                    "transaction_type": "SELL",
                    "quantity": qty,
                    "order_type": "MARKET",
                    "product": product,
                },
                role="entry_short_ce",
                activates_roles=["squareoff_short_ce"],
            ),
            RuleSpec(
                name=f"{underlying} BeCS BUY {buy_strike}CE",
                trigger_type="time",
                trigger_config=time_trigger,
                action_type="place_order",
                action_config={
                    "symbol": underlying,
                    "instrument_token": buy_ce["instrument_key"],
                    "transaction_type": "BUY",
                    "quantity": qty,
                    "order_type": "MARKET",
                    "product": product,
                },
                role="entry_long_ce",
                activates_roles=["squareoff_long_ce"],
            ),
            RuleSpec(
                name=f"{underlying} BeCS Squareoff SELL {sell_strike}CE @ {squareoff}",
                trigger_type="time",
                trigger_config=squareoff_trigger,
                action_type="place_order",
                action_config={
                    "symbol": underlying,
                    "instrument_token": sell_ce["instrument_key"],
                    "transaction_type": "BUY",
                    "quantity": qty,
                    "order_type": "MARKET",
                    "product": product,
                },
                role="squareoff_short_ce",
                enabled=False,
            ),
            RuleSpec(
                name=f"{underlying} BeCS Squareoff BUY {buy_strike}CE @ {squareoff}",
                trigger_type="time",
                trigger_config=squareoff_trigger,
                action_type="place_order",
                action_config={
                    "symbol": underlying,
                    "instrument_token": buy_ce["instrument_key"],
                    "transaction_type": "SELL",
                    "quantity": qty,
                    "order_type": "MARKET",
                    "product": product,
                },
                role="squareoff_long_ce",
                enabled=False,
            ),
        ]

        return plan
