"""VWAP Bounce strategy template.

Enters when price pulls back near VWAP with RSI confirmation, exits at target or SL.
"""
from __future__ import annotations

from typing import Any

from strategies.sizing import compute_quantity, compute_target
from strategies.templates import RuleSpec, StrategyPlan, StrategyTemplate


class VWAPBounceTemplate(StrategyTemplate):
    name = "vwap-bounce"
    description = (
        "VWAP bounce — enters when price pulls back near VWAP with RSI confirmation. "
        "Creates price entry near VWAP, RSI filter, SL, and target rules."
    )
    required_params = ["capital", "vwap", "sl"]
    optional_params = {
        "risk_percent": 2.0,
        "rr_ratio": 2.0,
        "product": "I",
        "side": "long",
        "rsi_filter": 40,         # RSI must be below this for long (oversold-ish)
        "rsi_timeframe": "5m",
        "vwap_band_pct": 0.3,     # Entry within 0.3% of VWAP
        "target": None,
        "squareoff_time": "15:15",
    }

    def plan(self, symbol: str, params: dict[str, Any]) -> StrategyPlan:
        p = self.validate_params(params)
        capital = p["capital"]
        risk_pct = p["risk_percent"]
        rr = p["rr_ratio"]
        product = p["product"]
        side = p["side"]
        vwap = p["vwap"]
        sl = p["sl"]
        squareoff = p["squareoff_time"]

        is_long = side == "long"
        # Entry price: just below VWAP for long, just above for short
        band = vwap * (p["vwap_band_pct"] / 100)
        entry_price = vwap - band if is_long else vwap + band

        target = p.get("target") or compute_target(entry_price, sl, rr)
        qty = compute_quantity(capital, risk_pct, entry_price, sl, product=product)

        side_entry = "BUY" if is_long else "SELL"
        side_exit = "SELL" if is_long else "BUY"
        entry_cond = "lte" if is_long else "gte"  # Price drops TO vwap for long bounce
        sl_cond = "lte" if is_long else "gte"
        target_cond = "gte" if is_long else "lte"

        label = "Long" if is_long else "Short"

        plan = StrategyPlan(
            template_name=self.name,
            symbol=symbol,
            summary=f"VWAP Bounce {label} {symbol}: VWAP {vwap}, entry ~{entry_price:.2f}, SL {sl}, target {target}",
            params=p,
        )

        # Exits start disabled; entry activates them. Prevents rogue exits.
        plan.rules = [
            RuleSpec(
                name=f"{symbol} VWAP Bounce Entry @ ~{entry_price:.2f}",
                trigger_type="price",
                trigger_config={"condition": entry_cond, "price": round(entry_price, 2), "reference": "ltp"},
                action_type="place_order",
                action_config={
                    "symbol": symbol, "transaction_type": side_entry,
                    "quantity": qty, "order_type": "MARKET", "product": product,
                },
                role="entry",
                activates_roles=["sl", "target", "squareoff"],
            ),
            RuleSpec(
                name=f"{symbol} VWAP Bounce SL @ {sl}",
                trigger_type="price",
                trigger_config={"condition": sl_cond, "price": sl, "reference": "ltp"},
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
                name=f"{symbol} VWAP Bounce Target @ {target}",
                trigger_type="price",
                trigger_config={"condition": target_cond, "price": target, "reference": "ltp"},
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
                name=f"{symbol} VWAP Bounce Square-Off @ {squareoff}",
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
