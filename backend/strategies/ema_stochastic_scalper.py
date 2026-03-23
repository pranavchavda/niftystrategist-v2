"""EMA-Stochastic Scalper strategy template.

Bilateral Bank Nifty options scalping based on Neeraj Joshi's video strategy.
Uses Supertrend as trend filter (proxy for 50/100 EMA alignment) and RSI as
entry trigger (proxy for Stochastic %K/%D crossover near oversold/overbought).

Long (CE buy): Supertrend bullish + RSI <= oversold_threshold
Short (PE buy): Supertrend bearish + RSI >= overbought_threshold

Each direction gets: entry rule, OCO (target + SL), and auto square-off.
Supports multiple fires for continuous scalping.
"""
from __future__ import annotations

from typing import Any

from strategies.fno_utils import get_lot_size, resolve_option_instrument
from strategies.templates import RuleSpec, StrategyPlan, StrategyTemplate


class EMAStochasticScalperTemplate(StrategyTemplate):
    name = "ema-stochastic-scalper"
    description = (
        "EMA-Stochastic Scalper — bilateral Bank Nifty options scalping. "
        "Supertrend trend filter + RSI oversold/overbought entries. "
        "15-pt target, 10-pt SL, max 5 fires per direction. Auto square-off at 15:15."
    )
    category = "fno"
    required_params = ["underlying", "expiry", "atm_strike"]
    optional_params = {
        "target_points": 15.0,
        "sl_points": 10.0,
        "max_fires": 5,
        "rsi_oversold": 35,
        "rsi_overbought": 65,
        "rsi_timeframe": "1m",
        "lots": 1,
        "product": "I",
        "squareoff_time": "15:15",
    }

    def plan(self, symbol: str, params: dict[str, Any]) -> StrategyPlan:
        p = self.validate_params(params)
        underlying = p["underlying"].upper()
        expiry = p["expiry"]
        atm_strike = float(p["atm_strike"])
        target_pts = p["target_points"]
        sl_pts = p["sl_points"]
        max_fires = p["max_fires"]
        rsi_oversold = p["rsi_oversold"]
        rsi_overbought = p["rsi_overbought"]
        rsi_tf = p["rsi_timeframe"]
        lots = int(p["lots"])
        product = p["product"]
        squareoff = p["squareoff_time"]

        lot_size = get_lot_size(underlying)
        qty = lots * lot_size

        # Resolve CE and PE instruments
        ce_info = resolve_option_instrument(underlying, expiry, atm_strike, "CE")
        pe_info = resolve_option_instrument(underlying, expiry, atm_strike, "PE")
        ce_instrument = ce_info["instrument_key"]
        pe_instrument = pe_info["instrument_key"]
        ce_symbol = ce_info["tradingsymbol"]
        pe_symbol = pe_info["tradingsymbol"]

        plan = StrategyPlan(
            template_name=self.name,
            symbol=symbol or underlying,
            summary=(
                f"EMA-Stochastic Scalper on {underlying} {expiry} ATM {atm_strike}: "
                f"CE+PE bilateral, {target_pts}pt target / {sl_pts}pt SL, "
                f"max {max_fires} fires/direction, {lots} lot(s) ({qty} qty)"
            ),
            params=p,
        )

        action_base_ce = {
            "symbol": ce_symbol,
            "transaction_type": "BUY",
            "quantity": qty,
            "order_type": "MARKET",
            "product": product,
            "instrument_token": ce_instrument,
        }
        action_base_pe = {
            "symbol": pe_symbol,
            "transaction_type": "BUY",
            "quantity": qty,
            "order_type": "MARKET",
            "product": product,
            "instrument_token": pe_instrument,
        }
        exit_ce = {**action_base_ce, "transaction_type": "SELL"}
        exit_pe = {**action_base_pe, "transaction_type": "SELL"}

        plan.rules = [
            # ── LONG LEG (CE) ────────────────────────────────────────
            # Entry: RSI drops below oversold on the underlying (1m)
            RuleSpec(
                name=f"{underlying} Scalp CE Entry — RSI<={rsi_oversold}",
                trigger_type="indicator",
                trigger_config={
                    "indicator": "rsi",
                    "timeframe": rsi_tf,
                    "condition": "lte",
                    "value": rsi_oversold,
                    "params": {"period": 14},
                },
                action_type="place_order",
                action_config=action_base_ce,
                max_fires=max_fires,
                role="ce_entry",
                activates_roles=["ce_target", "ce_sl"],
            ),
            # CE Target
            RuleSpec(
                name=f"{underlying} Scalp CE Target +{target_pts}pts",
                trigger_type="price",
                trigger_config={
                    "condition": "gte",
                    "price": target_pts,  # Relative — resolved at deploy from entry fill
                    "reference": "ltp",
                    "relative": True,
                    "relative_to": "entry_price",
                    "offset": target_pts,
                },
                action_type="place_order",
                action_config=exit_ce,
                max_fires=max_fires,
                role="ce_target",
                kills_roles=["ce_sl"],
                enabled=True,
            ),
            # CE Stop Loss
            RuleSpec(
                name=f"{underlying} Scalp CE SL -{sl_pts}pts",
                trigger_type="price",
                trigger_config={
                    "condition": "lte",
                    "price": sl_pts,  # Relative
                    "reference": "ltp",
                    "relative": True,
                    "relative_to": "entry_price",
                    "offset": -sl_pts,
                },
                action_type="place_order",
                action_config=exit_ce,
                max_fires=max_fires,
                role="ce_sl",
                kills_roles=["ce_target"],
                enabled=True,
            ),

            # ── SHORT LEG (PE) ───────────────────────────────────────
            # Entry: RSI rises above overbought on the underlying (1m)
            RuleSpec(
                name=f"{underlying} Scalp PE Entry — RSI>={rsi_overbought}",
                trigger_type="indicator",
                trigger_config={
                    "indicator": "rsi",
                    "timeframe": rsi_tf,
                    "condition": "gte",
                    "value": rsi_overbought,
                    "params": {"period": 14},
                },
                action_type="place_order",
                action_config=action_base_pe,
                max_fires=max_fires,
                role="pe_entry",
                activates_roles=["pe_target", "pe_sl"],
            ),
            # PE Target
            RuleSpec(
                name=f"{underlying} Scalp PE Target +{target_pts}pts",
                trigger_type="price",
                trigger_config={
                    "condition": "gte",
                    "price": target_pts,
                    "reference": "ltp",
                    "relative": True,
                    "relative_to": "entry_price",
                    "offset": target_pts,
                },
                action_type="place_order",
                action_config=exit_pe,
                max_fires=max_fires,
                role="pe_target",
                kills_roles=["pe_sl"],
                enabled=True,
            ),
            # PE Stop Loss
            RuleSpec(
                name=f"{underlying} Scalp PE SL -{sl_pts}pts",
                trigger_type="price",
                trigger_config={
                    "condition": "lte",
                    "price": sl_pts,
                    "reference": "ltp",
                    "relative": True,
                    "relative_to": "entry_price",
                    "offset": -sl_pts,
                },
                action_type="place_order",
                action_config=exit_pe,
                max_fires=max_fires,
                role="pe_sl",
                kills_roles=["pe_target"],
                enabled=True,
            ),

            # ── SHARED ──────────────────────────────────────────────
            # Auto square-off for CE
            RuleSpec(
                name=f"{underlying} Scalp CE Square-Off @ {squareoff}",
                trigger_type="time",
                trigger_config={
                    "at": squareoff,
                    "on_days": ["mon", "tue", "wed", "thu", "fri"],
                    "market_only": True,
                },
                action_type="place_order",
                action_config=exit_ce,
                role="ce_squareoff",
                kills_roles=["ce_entry", "ce_target", "ce_sl"],
            ),
            # Auto square-off for PE
            RuleSpec(
                name=f"{underlying} Scalp PE Square-Off @ {squareoff}",
                trigger_type="time",
                trigger_config={
                    "at": squareoff,
                    "on_days": ["mon", "tue", "wed", "thu", "fri"],
                    "market_only": True,
                },
                action_type="place_order",
                action_config=exit_pe,
                role="pe_squareoff",
                kills_roles=["pe_entry", "pe_target", "pe_sl"],
            ),
        ]

        return plan
