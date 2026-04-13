"""Bull Call Spread strategy template.

Buy lower strike CE, sell higher strike CE. Net debit spread.
Max profit = (sell_strike - buy_strike) * qty - net_debit.
Max loss = net_debit.
"""
from __future__ import annotations

from typing import Any

from strategies.fno_utils import resolve_option_instrument
from strategies.templates import RuleSpec, StrategyPlan, StrategyTemplate


class BullCallSpreadTemplate(StrategyTemplate):
    name = "bull-call-spread"
    category = "fno"
    description = (
        "Bull Call Spread — buy lower strike CE, sell higher strike CE. "
        "Limited risk (net debit), limited reward. Bullish directional bet."
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

        if sell_strike <= buy_strike:
            raise ValueError("sell_strike must be higher than buy_strike for a bull call spread")

        buy_ce = resolve_option_instrument(underlying, expiry, buy_strike, "CE")
        sell_ce = resolve_option_instrument(underlying, expiry, sell_strike, "CE")
        lot_size = buy_ce["lot_size"]
        qty = lots * lot_size

        spread_width = sell_strike - buy_strike
        max_profit_per_unit = spread_width  # minus net debit (unknown until live)

        time_trigger = {
            "at": entry_time,
            "on_days": ["mon", "tue", "wed", "thu", "fri"],
            "market_only": True,
        }

        plan = StrategyPlan(
            template_name=self.name,
            symbol=underlying,
            summary=(
                f"Bull Call Spread {underlying}: "
                f"BUY {buy_strike}CE + SELL {sell_strike}CE x{lots}L, "
                f"spread width {spread_width}, squareoff {squareoff}"
            ),
            params=p,
        )

        # Unique role per leg so the deploy-time role_to_id map doesn't
        # collapse duplicates. Squareoffs start disabled; each entry
        # activates its own leg's squareoff. Prevents a rogue squareoff
        # from firing at 15:15 if entry_time never ran (e.g. deploy after
        # 09:20 or the instrument_token lookup failed silently).
        plan.rules = [
            RuleSpec(
                name=f"{underlying} BCS BUY {buy_strike}CE",
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
                name=f"{underlying} BCS SELL {sell_strike}CE",
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
                name=f"{underlying} BCS Squareoff BUY {buy_strike}CE @ {squareoff}",
                trigger_type="time",
                trigger_config={
                    "at": squareoff,
                    "on_days": ["mon", "tue", "wed", "thu", "fri"],
                    "market_only": True,
                },
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
            RuleSpec(
                name=f"{underlying} BCS Squareoff SELL {sell_strike}CE @ {squareoff}",
                trigger_type="time",
                trigger_config={
                    "at": squareoff,
                    "on_days": ["mon", "tue", "wed", "thu", "fri"],
                    "market_only": True,
                },
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
        ]

        return plan
