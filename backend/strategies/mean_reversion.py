"""Mean reversion strategy template.

Enters on RSI oversold/overbought, exits on the opposite extreme.
"""
from __future__ import annotations

from typing import Any

from strategies.sizing import compute_quantity
from strategies.templates import RuleSpec, StrategyPlan, StrategyTemplate


class MeanReversionTemplate(StrategyTemplate):
    name = "mean-reversion"
    description = (
        "Mean reversion — enters when RSI hits oversold/overbought levels. "
        "Creates RSI entry, RSI exit, and stop-loss rules."
    )
    required_params = ["capital", "sl"]
    optional_params = {
        "risk_percent": 2.0,
        "product": "I",
        "side": "long",           # "long" (buy oversold) or "short" (sell overbought)
        "rsi_entry": None,        # Auto: 30 for long, 70 for short
        "rsi_exit": None,         # Auto: 70 for long, 30 for short
        "rsi_timeframe": "5m",
        "entry_price": None,      # Approximate entry for sizing (uses SL distance)
        "squareoff_time": "15:15",
        "sl_pct": None,           # If set, the SL is anchored to the actual
                                  # entry FILL (entry-relative), not a static
                                  # day-open level — see SL rule below.
    }

    def plan(self, symbol: str, params: dict[str, Any]) -> StrategyPlan:
        p = self.validate_params(params)
        capital = p["capital"]
        risk_pct = p["risk_percent"]
        product = p["product"]
        side = p["side"]
        sl = p["sl"]
        timeframe = p["rsi_timeframe"]
        squareoff = p["squareoff_time"]

        is_long = side == "long"
        rsi_entry = p.get("rsi_entry") or (30 if is_long else 70)
        rsi_exit = p.get("rsi_exit") or (70 if is_long else 30)
        entry_cond = "lte" if is_long else "gte"   # RSI <= 30 (oversold)
        exit_cond = "gte" if is_long else "lte"     # RSI >= 70 (overbought)

        side_entry = "BUY" if is_long else "SELL"
        side_exit = "SELL" if is_long else "BUY"
        sl_cond = "lte" if is_long else "gte"

        # A percentage stop must be relative to the ENTRY fill, not a static
        # day-open level. A mean-reversion entry fires on an RSI spike away
        # from the open, so a day-open-anchored stop can land on the wrong
        # (profit) side of the entry and fire as a fake "sl" win — every
        # spike-short booked the reversion as a guaranteed gain. When sl_pct
        # is given, tag the SL rule so the backtest engine re-anchors its
        # price to the actual fill on entry: short stop ABOVE entry (+pct),
        # long stop BELOW entry (-pct).
        sl_pct = p.get("sl_pct")
        sl_trigger = {"condition": sl_cond, "price": sl, "reference": "ltp"}
        if sl_pct is not None:
            sl_trigger["entry_anchor_pct"] = sl_pct if not is_long else -sl_pct

        # For sizing we need an approximate entry price
        entry_price = p.get("entry_price") or sl * (1.02 if is_long else 0.98)
        qty = compute_quantity(capital, risk_pct, entry_price, sl, product=product)

        label = "Long (Oversold)" if is_long else "Short (Overbought)"

        plan = StrategyPlan(
            template_name=self.name,
            symbol=symbol,
            summary=f"Mean Reversion {label} {symbol}: RSI entry {rsi_entry}, exit {rsi_exit}, SL {sl}",
            params=p,
        )

        # Exits start disabled; entry activates them. Prevents rogue exits.
        plan.rules = [
            RuleSpec(
                name=f"{symbol} MeanRev RSI Entry (RSI {entry_cond} {rsi_entry})",
                trigger_type="indicator",
                trigger_config={
                    "indicator": "rsi", "timeframe": timeframe,
                    "condition": entry_cond, "value": rsi_entry,
                },
                action_type="place_order",
                action_config={
                    "symbol": symbol, "transaction_type": side_entry,
                    "quantity": qty, "order_type": "MARKET", "product": product,
                },
                role="entry",
                activates_roles=["target", "sl", "squareoff"],
            ),
            RuleSpec(
                name=f"{symbol} MeanRev RSI Exit (RSI {exit_cond} {rsi_exit})",
                trigger_type="indicator",
                trigger_config={
                    "indicator": "rsi", "timeframe": timeframe,
                    "condition": exit_cond, "value": rsi_exit,
                },
                action_type="place_order",
                action_config={
                    "symbol": symbol, "transaction_type": side_exit,
                    "quantity": qty, "order_type": "MARKET", "product": product,
                },
                role="target",
                enabled=False,
                kills_roles=["sl", "squareoff"],
            ),
            RuleSpec(
                name=f"{symbol} MeanRev SL @ {sl}",
                trigger_type="price",
                trigger_config=sl_trigger,
                action_type="place_order",
                action_config={
                    "symbol": symbol, "transaction_type": side_exit,
                    "quantity": qty, "order_type": "MARKET", "product": product,
                },
                role="sl",
                enabled=False,
                kills_roles=["target", "squareoff"],
            ),
            RuleSpec(
                name=f"{symbol} MeanRev Square-Off @ {squareoff}",
                trigger_type="time",
                trigger_config={"at": squareoff, "on_days": ["mon", "tue", "wed", "thu", "fri"], "market_only": True},
                action_type="place_order",
                action_config={
                    "symbol": symbol, "transaction_type": side_exit,
                    "quantity": qty, "order_type": "MARKET", "product": product,
                },
                role="squareoff",
                enabled=False,
                kills_roles=["sl", "target"],
            ),
        ]

        return plan
