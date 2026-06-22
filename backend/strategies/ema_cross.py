"""EMA Crossover strategy templates.

Entry (and optional exit) on EMA crossovers. Three variants:
- Long only: buy on bullish cross
- Short only: sell on bearish cross
- Long + Exit: buy on bullish, sell on bearish
"""
from __future__ import annotations

from typing import Any

from strategies.templates import RuleSpec, StrategyPlan, StrategyTemplate


class EMACrossLongTemplate(StrategyTemplate):
    name = "ema-cross-long"
    description = (
        "EMA Cross Long — buy when fast EMA crosses above slow EMA. "
        "Single-fire intraday entry on configurable timeframe and EMA periods."
    )
    category = "equity"
    required_params = ["quantity"]
    optional_params = {
        "fast_ema": 9,
        "slow_ema": 21,
        "timeframe": "5m",
        "product": "I",
        "squareoff_time": "15:15",
    }

    def plan(self, symbol: str, params: dict[str, Any]) -> StrategyPlan:
        p = self.validate_params(params)
        qty = int(p["quantity"])
        fast = int(p["fast_ema"])
        slow = int(p["slow_ema"])
        tf = p["timeframe"]
        product = p["product"]
        squareoff = p["squareoff_time"]

        plan = StrategyPlan(
            template_name=self.name,
            symbol=symbol,
            summary=f"EMA {fast}/{slow} bullish cross on {tf} → BUY {qty} {symbol}",
            params=p,
        )

        # Squareoff starts disabled; entry activates it to prevent a rogue
        # SELL at 15:15 if the bullish cross never fired (which would open a
        # naked short).
        plan.rules = [
            RuleSpec(
                name=f"{symbol} EMA {fast}/{slow} Bullish Cross — BUY",
                trigger_type="indicator",
                trigger_config={
                    "indicator": "ema_crossover",
                    "timeframe": tf,
                    "condition": "crosses_above",
                    "value": 0,
                    "params": {"fast": fast, "slow": slow},
                },
                action_type="place_order",
                action_config={
                    "symbol": symbol,
                    "transaction_type": "BUY",
                    "quantity": qty,
                    "order_type": "MARKET",
                    "product": product,
                },
                role="entry",
                activates_roles=["squareoff"],
            ),
            RuleSpec(
                name=f"{symbol} EMA Cross Square-Off @ {squareoff}",
                trigger_type="time",
                trigger_config={
                    "at": squareoff,
                    "on_days": ["mon", "tue", "wed", "thu", "fri"],
                    "market_only": True,
                },
                action_type="place_order",
                action_config={
                    "symbol": symbol,
                    "transaction_type": "SELL",
                    "quantity": qty,
                    "order_type": "MARKET",
                    "product": product,
                },
                role="squareoff",
                enabled=False,
            ),
        ]

        return plan


class EMACrossShortTemplate(StrategyTemplate):
    name = "ema-cross-short"
    description = (
        "EMA Cross Short — sell when fast EMA crosses below slow EMA. "
        "Single-fire intraday entry on configurable timeframe and EMA periods."
    )
    category = "equity"
    required_params = ["quantity"]
    optional_params = {
        "fast_ema": 9,
        "slow_ema": 21,
        "timeframe": "5m",
        "product": "I",
        "squareoff_time": "15:15",
    }

    def plan(self, symbol: str, params: dict[str, Any]) -> StrategyPlan:
        p = self.validate_params(params)
        qty = int(p["quantity"])
        fast = int(p["fast_ema"])
        slow = int(p["slow_ema"])
        tf = p["timeframe"]
        product = p["product"]
        squareoff = p["squareoff_time"]

        plan = StrategyPlan(
            template_name=self.name,
            symbol=symbol,
            summary=f"EMA {fast}/{slow} bearish cross on {tf} → SELL {qty} {symbol}",
            params=p,
        )

        plan.rules = [
            RuleSpec(
                name=f"{symbol} EMA {fast}/{slow} Bearish Cross — SELL",
                trigger_type="indicator",
                trigger_config={
                    "indicator": "ema_crossover",
                    "timeframe": tf,
                    "condition": "crosses_below",
                    "value": 0,
                    "params": {"fast": fast, "slow": slow},
                },
                action_type="place_order",
                action_config={
                    "symbol": symbol,
                    "transaction_type": "SELL",
                    "quantity": qty,
                    "order_type": "MARKET",
                    "product": product,
                },
                role="entry",
                activates_roles=["squareoff"],
            ),
            RuleSpec(
                name=f"{symbol} EMA Cross Square-Off @ {squareoff}",
                trigger_type="time",
                trigger_config={
                    "at": squareoff,
                    "on_days": ["mon", "tue", "wed", "thu", "fri"],
                    "market_only": True,
                },
                action_type="place_order",
                action_config={
                    "symbol": symbol,
                    "transaction_type": "BUY",
                    "quantity": qty,
                    "order_type": "MARKET",
                    "product": product,
                },
                role="squareoff",
                enabled=False,
            ),
        ]

        return plan


class EMACrossPairTemplate(StrategyTemplate):
    name = "ema-cross-pair"
    description = (
        "EMA Cross Long + Exit — buy on bullish EMA cross, auto-exit on bearish cross. "
        "Two rules on the same timeframe for a complete intraday round-trip."
    )
    category = "equity"
    required_params = ["quantity"]
    optional_params = {
        "fast_ema": 9,
        "slow_ema": 21,
        "timeframe": "5m",
        "product": "I",
        "squareoff_time": "15:15",
    }

    def plan(self, symbol: str, params: dict[str, Any]) -> StrategyPlan:
        p = self.validate_params(params)
        qty = int(p["quantity"])
        fast = int(p["fast_ema"])
        slow = int(p["slow_ema"])
        tf = p["timeframe"]
        product = p["product"]
        squareoff = p["squareoff_time"]

        plan = StrategyPlan(
            template_name=self.name,
            symbol=symbol,
            summary=f"EMA {fast}/{slow} pair on {tf} — BUY on bullish cross, SELL on bearish cross, {qty} {symbol}",
            params=p,
        )

        # Exit + squareoff start disabled; entry activates them. Prevents a
        # bearish cross (or 15:15 squareoff) from opening a rogue short when
        # no bullish cross ever fired.
        plan.rules = [
            RuleSpec(
                name=f"{symbol} EMA {fast}/{slow} Bullish Cross — ENTRY BUY",
                trigger_type="indicator",
                trigger_config={
                    "indicator": "ema_crossover",
                    "timeframe": tf,
                    "condition": "crosses_above",
                    "value": 0,
                    "params": {"fast": fast, "slow": slow},
                },
                action_type="place_order",
                action_config={
                    "symbol": symbol,
                    "transaction_type": "BUY",
                    "quantity": qty,
                    "order_type": "MARKET",
                    "product": product,
                },
                role="entry",
                activates_roles=["exit", "squareoff"],
            ),
            RuleSpec(
                name=f"{symbol} EMA {fast}/{slow} Bearish Cross — EXIT SELL",
                trigger_type="indicator",
                trigger_config={
                    "indicator": "ema_crossover",
                    "timeframe": tf,
                    "condition": "crosses_below",
                    "value": 0,
                    "params": {"fast": fast, "slow": slow},
                },
                action_type="place_order",
                action_config={
                    "symbol": symbol,
                    "transaction_type": "SELL",
                    "quantity": qty,
                    "order_type": "MARKET",
                    "product": product,
                },
                role="exit",
                enabled=False,
                kills_roles=["squareoff"],
            ),
            RuleSpec(
                name=f"{symbol} EMA Cross Square-Off @ {squareoff}",
                trigger_type="time",
                trigger_config={
                    "at": squareoff,
                    "on_days": ["mon", "tue", "wed", "thu", "fri"],
                    "market_only": True,
                },
                action_type="place_order",
                action_config={
                    "symbol": symbol,
                    "transaction_type": "SELL",
                    "quantity": qty,
                    "order_type": "MARKET",
                    "product": product,
                },
                role="squareoff",
                enabled=False,
                kills_roles=["exit"],
            ),
        ]

        return plan
