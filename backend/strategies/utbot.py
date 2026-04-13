"""UT Bot strategy templates.

UT Bot is an ATR-based trailing-stop trend follower. When price crosses the
trailing stop, the trend flips (long ↔ short). These templates deploy
monitor rules that fire on those flips.

Three variants:
- Long only: buy when UT Bot flips long (crosses_above 0 on the trend output)
- Short only: sell when UT Bot flips short
- Pair: buy on long flip, auto-exit on short flip (complete round-trip)
"""
from __future__ import annotations

from typing import Any

from strategies.templates import RuleSpec, StrategyPlan, StrategyTemplate


def _utbot_trigger_config(timeframe: str, condition: str, period: int, sensitivity: float) -> dict:
    return {
        "indicator": "utbot",
        "timeframe": timeframe,
        "condition": condition,
        "value": 0,
        "params": {
            "period": period,
            "sensitivity": sensitivity,
            "output": "trend",
        },
    }


def _squareoff_rule(symbol: str, qty: int, side: str, product: str, squareoff: str) -> RuleSpec:
    # Starts disabled; entry rule activates it. Without this, the squareoff
    # time-trigger would fire at 15:15 even if no UT Bot flip ever triggered
    # an entry, opening a naked position on the exit side.
    return RuleSpec(
        name=f"{symbol} UT Bot Square-Off @ {squareoff}",
        trigger_type="time",
        trigger_config={
            "at": squareoff,
            "on_days": ["mon", "tue", "wed", "thu", "fri"],
            "market_only": True,
        },
        action_type="place_order",
        action_config={
            "symbol": symbol,
            "transaction_type": side,
            "quantity": qty,
            "order_type": "MARKET",
            "product": product,
        },
        role="squareoff",
        enabled=False,
    )


class UTBotLongTemplate(StrategyTemplate):
    name = "utbot-long"
    description = (
        "UT Bot Long — buy when UT Bot flips from short to long on the "
        "configured timeframe. Single-fire intraday entry with a time-based "
        "square-off. Default ATR period 10, sensitivity 1.0."
    )
    category = "equity"
    required_params = ["quantity"]
    optional_params = {
        "period": 10,
        "sensitivity": 1.0,
        "timeframe": "5m",
        "product": "I",
        "squareoff_time": "15:15",
    }

    def plan(self, symbol: str, params: dict[str, Any]) -> StrategyPlan:
        p = self.validate_params(params)
        qty = int(p["quantity"])
        period = int(p["period"])
        sensitivity = float(p["sensitivity"])
        tf = p["timeframe"]
        product = p["product"]
        squareoff = p["squareoff_time"]

        plan = StrategyPlan(
            template_name=self.name,
            symbol=symbol,
            summary=(
                f"UT Bot ({period}, {sensitivity}) bullish flip on {tf} → "
                f"BUY {qty} {symbol}"
            ),
            params=p,
        )

        plan.rules = [
            RuleSpec(
                name=f"{symbol} UT Bot ({period}, {sensitivity}) Bullish Flip — BUY",
                trigger_type="indicator",
                trigger_config=_utbot_trigger_config(tf, "crosses_above", period, sensitivity),
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
            _squareoff_rule(symbol, qty, "SELL", product, squareoff),
        ]
        return plan


class UTBotShortTemplate(StrategyTemplate):
    name = "utbot-short"
    description = (
        "UT Bot Short — sell when UT Bot flips from long to short on the "
        "configured timeframe. Single-fire intraday entry with a time-based "
        "square-off. Default ATR period 10, sensitivity 1.0."
    )
    category = "equity"
    required_params = ["quantity"]
    optional_params = {
        "period": 10,
        "sensitivity": 1.0,
        "timeframe": "5m",
        "product": "I",
        "squareoff_time": "15:15",
    }

    def plan(self, symbol: str, params: dict[str, Any]) -> StrategyPlan:
        p = self.validate_params(params)
        qty = int(p["quantity"])
        period = int(p["period"])
        sensitivity = float(p["sensitivity"])
        tf = p["timeframe"]
        product = p["product"]
        squareoff = p["squareoff_time"]

        plan = StrategyPlan(
            template_name=self.name,
            symbol=symbol,
            summary=(
                f"UT Bot ({period}, {sensitivity}) bearish flip on {tf} → "
                f"SELL {qty} {symbol}"
            ),
            params=p,
        )

        plan.rules = [
            RuleSpec(
                name=f"{symbol} UT Bot ({period}, {sensitivity}) Bearish Flip — SELL",
                trigger_type="indicator",
                trigger_config=_utbot_trigger_config(tf, "crosses_below", period, sensitivity),
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
            _squareoff_rule(symbol, qty, "BUY", product, squareoff),
        ]
        return plan


class UTBotPairTemplate(StrategyTemplate):
    name = "utbot-pair"
    description = (
        "UT Bot Long + Exit — buy on UT Bot bullish flip, auto-exit on bearish "
        "flip. Two rules on the same timeframe for a complete intraday "
        "round-trip. Default ATR period 10, sensitivity 1.0."
    )
    category = "equity"
    required_params = ["quantity"]
    optional_params = {
        "period": 10,
        "sensitivity": 1.0,
        "timeframe": "5m",
        "product": "I",
        "squareoff_time": "15:15",
    }

    def plan(self, symbol: str, params: dict[str, Any]) -> StrategyPlan:
        p = self.validate_params(params)
        qty = int(p["quantity"])
        period = int(p["period"])
        sensitivity = float(p["sensitivity"])
        tf = p["timeframe"]
        product = p["product"]
        squareoff = p["squareoff_time"]

        plan = StrategyPlan(
            template_name=self.name,
            symbol=symbol,
            summary=(
                f"UT Bot ({period}, {sensitivity}) pair on {tf} — BUY on bullish "
                f"flip, SELL on bearish flip, {qty} {symbol}"
            ),
            params=p,
        )

        # Exit + squareoff start disabled; entry activates them. Prevents a
        # bearish flip (or 15:15 squareoff) from opening a rogue short if the
        # bullish entry never fired.
        plan.rules = [
            RuleSpec(
                name=f"{symbol} UT Bot Bullish Flip — ENTRY BUY",
                trigger_type="indicator",
                trigger_config=_utbot_trigger_config(tf, "crosses_above", period, sensitivity),
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
                name=f"{symbol} UT Bot Bearish Flip — EXIT SELL",
                trigger_type="indicator",
                trigger_config=_utbot_trigger_config(tf, "crosses_below", period, sensitivity),
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
                name=f"{symbol} UT Bot Square-Off @ {squareoff}",
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
