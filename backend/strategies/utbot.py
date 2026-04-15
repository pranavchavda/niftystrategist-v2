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

from strategies.fno_utils import get_strike_interval, resolve_option_instrument
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


class UTBotScalpTemplate(StrategyTemplate):
    name = "utbot-scalp"
    description = (
        "UT Bot Scalp — cyclical long-only scalper that buys on every bullish "
        "UT Bot flip and sells on every bearish flip throughout the day. "
        "Mutual activate chain with self-kill so each side re-arms the other. "
        "Cooldown suppresses rapid re-fires in chop. Max cycles caps runaway. "
        "Optional LR channel exits (lr_exit_enabled=True) add a profit-take on "
        "upper-band touches and a dynamic SL on lower-band breaks."
    )
    category = "equity"
    required_params = ["quantity"]
    optional_params = {
        "period": 10,
        "sensitivity": 1.0,
        "timeframe": "5m",
        "product": "I",
        "squareoff_time": "15:15",
        "cycles": 20,
        "cooldown_seconds": 60,
        "lr_exit_enabled": False,
        "lr_period": 20,
        "lr_stdev": 2.0,
    }

    def plan(self, symbol: str, params: dict[str, Any]) -> StrategyPlan:
        p = self.validate_params(params)
        qty = int(p["quantity"])
        period = int(p["period"])
        sensitivity = float(p["sensitivity"])
        tf = p["timeframe"]
        product = p["product"]
        squareoff = p["squareoff_time"]
        cycles = int(p["cycles"])
        cooldown = int(p["cooldown_seconds"])
        lr_enabled = bool(p["lr_exit_enabled"])
        lr_period = int(p["lr_period"])
        lr_stdev = float(p["lr_stdev"])

        if cycles < 1:
            raise ValueError("cycles must be >= 1")
        if cooldown < 0:
            raise ValueError("cooldown_seconds must be >= 0")
        if lr_enabled and lr_period < 3:
            raise ValueError("lr_period must be >= 3 when lr_exit_enabled")
        if lr_enabled and lr_stdev <= 0:
            raise ValueError("lr_stdev must be > 0 when lr_exit_enabled")

        lr_suffix = f", LR({lr_period},{lr_stdev}σ)" if lr_enabled else ""
        plan = StrategyPlan(
            template_name=self.name,
            symbol=symbol,
            summary=(
                f"UT Bot Scalp ({period}, {sensitivity}) on {tf} — "
                f"cycling BUY/SELL {qty} {symbol}, up to {cycles} cycles, "
                f"{cooldown}s cooldown{lr_suffix}"
            ),
            params=p,
        )

        def _utbot_trig(condition: str) -> dict:
            cfg = _utbot_trigger_config(tf, condition, period, sensitivity)
            if cooldown > 0:
                cfg["cooldown_seconds"] = cooldown
            return cfg

        def _lr_trig(condition: str, threshold: float) -> dict:
            cfg = {
                "indicator": "linear_regression",
                "timeframe": tf,
                "condition": condition,
                "value": threshold,
                "params": {"period": lr_period, "stdev": lr_stdev, "output": "pctb"},
            }
            if cooldown > 0:
                cfg["cooldown_seconds"] = cooldown
            return cfg

        # Entry activates all currently-enabled exits plus squareoff.
        # When lr_exit_enabled is False, only the UT Bot flip exit exists.
        exit_roles = ["exit_utbot"]
        if lr_enabled:
            exit_roles += ["exit_lr_upper", "exit_lr_lower"]

        # Every exit mutually kills every other exit AND the squareoff, so
        # only one fires per cycle and the squareoff can't fire at 15:15
        # against a flat position. Re-entry re-activates squareoff via
        # entry.activates_roles.
        exits_kill_roles = list(exit_roles) + ["squareoff"]

        order_config = {
            "symbol": symbol,
            "quantity": qty,
            "order_type": "MARKET",
            "product": product,
        }

        plan.rules = [
            RuleSpec(
                name=f"{symbol} UT Bot Scalp Bullish Flip — BUY",
                trigger_type="indicator",
                trigger_config=_utbot_trig("crosses_above"),
                action_type="place_order",
                action_config={**order_config, "transaction_type": "BUY"},
                role="entry",
                max_fires=cycles,
                activates_roles=exit_roles + ["squareoff"],
                kills_roles=["entry"],
            ),
            RuleSpec(
                name=f"{symbol} UT Bot Scalp Bearish Flip — SELL",
                trigger_type="indicator",
                trigger_config=_utbot_trig("crosses_below"),
                action_type="place_order",
                action_config={**order_config, "transaction_type": "SELL"},
                role="exit_utbot",
                max_fires=cycles,
                enabled=False,
                activates_roles=["entry"],
                kills_roles=exits_kill_roles,
            ),
        ]

        if lr_enabled:
            plan.rules.extend([
                RuleSpec(
                    name=f"{symbol} UT Bot Scalp LR Upper Band Exit — SELL",
                    trigger_type="indicator",
                    trigger_config=_lr_trig("crosses_above", 1.0),
                    action_type="place_order",
                    action_config={**order_config, "transaction_type": "SELL"},
                    role="exit_lr_upper",
                    max_fires=cycles,
                    enabled=False,
                    activates_roles=["entry"],
                    kills_roles=exits_kill_roles,
                ),
                RuleSpec(
                    name=f"{symbol} UT Bot Scalp LR Lower Band SL — SELL",
                    trigger_type="indicator",
                    trigger_config=_lr_trig("crosses_below", 0.0),
                    action_type="place_order",
                    action_config={**order_config, "transaction_type": "SELL"},
                    role="exit_lr_lower",
                    max_fires=cycles,
                    enabled=False,
                    activates_roles=["entry"],
                    kills_roles=exits_kill_roles,
                ),
            ])

        plan.rules.append(
            RuleSpec(
                name=f"{symbol} UT Bot Scalp Square-Off @ {squareoff}",
                trigger_type="time",
                trigger_config={
                    "at": squareoff,
                    "on_days": ["mon", "tue", "wed", "thu", "fri"],
                    "market_only": True,
                },
                action_type="place_order",
                action_config={**order_config, "transaction_type": "SELL"},
                role="squareoff",
                enabled=False,
                kills_roles=["entry"] + exit_roles,
            )
        )
        return plan


def _build_scalp_options_rules(
    *,
    underlying: str,
    expiry: str,
    strike: float,
    option_type: str,
    lots: int,
    period: int,
    sensitivity: float,
    timeframe: str,
    product: str,
    cycles: int,
    cooldown: int,
    lr_period: int,
    lr_stdev: float,
    squareoff_time: str,
    role_suffix: str = "",
) -> list[RuleSpec]:
    """Construct the 5-rule chain for one utbot-scalp-options strike.

    Shared by ``UTBotScalpOptionsTemplate`` (single strike, empty suffix)
    and ``UTBotScalpOptionsLadderTemplate`` (N strikes, unique suffix per
    strike). Suffix is appended to every role name and every reference in
    ``activates_roles`` / ``kills_roles`` so multiple instances of this
    chain can coexist in one plan without role collision during deploy.

    Rules produced (suffix applied to each role):
      entry            UT Bot bullish flip → BUY option premium
      exit_utbot       UT Bot bearish flip → SELL (trend exit)
      exit_lr_upper    LR pctb crosses above 1.0 → SELL (profit take)
      exit_lr_lower    LR pctb crosses below 0.0 → SELL (dynamic SL)
      squareoff        Time trigger at ``squareoff_time`` → SELL (safety net)

    The mutual-activate chain is fully self-contained within the suffix:
    entry activates all exits + squareoff, exits kill themselves + each
    other + squareoff and re-activate entry, squareoff kills everything.
    This is the same post-2026-04-15 pattern that survived live testing
    (see commit d655b92 and project_stateful_strategies_direction.md).

    Caller is responsible for numeric param validation — the helper only
    raises ValueError on option_type mismatch.
    """
    if option_type not in ("CE", "PE"):
        raise ValueError(f"option_type must be CE or PE, got {option_type}")

    inst = resolve_option_instrument(underlying, expiry, strike, option_type)
    instrument_key = inst["instrument_key"]
    lot_size = inst["lot_size"]
    qty = lots * lot_size

    def _utbot_trig(condition: str) -> dict:
        cfg = _utbot_trigger_config(timeframe, condition, period, sensitivity)
        if cooldown > 0:
            cfg["cooldown_seconds"] = cooldown
        return cfg

    def _lr_trig(condition: str, threshold: float) -> dict:
        cfg = {
            "indicator": "linear_regression",
            "timeframe": timeframe,
            "condition": condition,
            "value": threshold,
            "params": {
                "period": lr_period,
                "stdev": lr_stdev,
                "output": "pctb",
            },
        }
        if cooldown > 0:
            cfg["cooldown_seconds"] = cooldown
        return cfg

    r_entry = f"entry{role_suffix}"
    r_exit_utbot = f"exit_utbot{role_suffix}"
    r_exit_lr_upper = f"exit_lr_upper{role_suffix}"
    r_exit_lr_lower = f"exit_lr_lower{role_suffix}"
    r_squareoff = f"squareoff{role_suffix}"

    all_exits = [r_exit_utbot, r_exit_lr_upper, r_exit_lr_lower]
    # Exits also kill the squareoff so 15:15 can't fire against a flat
    # position. Re-entry re-activates squareoff via entry.activates_roles.
    exits_kill_roles = all_exits + [r_squareoff]

    base_action = {
        "symbol": underlying,
        "instrument_token": instrument_key,
        "quantity": qty,
        "order_type": "MARKET",
        "product": product,
    }

    return [
        RuleSpec(
            name=f"{underlying} {strike}{option_type} UT Bot Bullish Flip — BUY",
            trigger_type="indicator",
            trigger_config=_utbot_trig("crosses_above"),
            action_type="place_order",
            action_config={**base_action, "transaction_type": "BUY"},
            role=r_entry,
            max_fires=cycles,
            activates_roles=all_exits + [r_squareoff],
            kills_roles=[r_entry],
        ),
        RuleSpec(
            name=f"{underlying} {strike}{option_type} UT Bot Bearish Flip — SELL",
            trigger_type="indicator",
            trigger_config=_utbot_trig("crosses_below"),
            action_type="place_order",
            action_config={**base_action, "transaction_type": "SELL"},
            role=r_exit_utbot,
            max_fires=cycles,
            enabled=False,
            activates_roles=[r_entry],
            kills_roles=exits_kill_roles,
        ),
        RuleSpec(
            name=f"{underlying} {strike}{option_type} LR Upper Band Exit — SELL",
            trigger_type="indicator",
            trigger_config=_lr_trig("crosses_above", 1.0),
            action_type="place_order",
            action_config={**base_action, "transaction_type": "SELL"},
            role=r_exit_lr_upper,
            max_fires=cycles,
            enabled=False,
            activates_roles=[r_entry],
            kills_roles=exits_kill_roles,
        ),
        RuleSpec(
            name=f"{underlying} {strike}{option_type} LR Lower Band SL — SELL",
            trigger_type="indicator",
            trigger_config=_lr_trig("crosses_below", 0.0),
            action_type="place_order",
            action_config={**base_action, "transaction_type": "SELL"},
            role=r_exit_lr_lower,
            max_fires=cycles,
            enabled=False,
            activates_roles=[r_entry],
            kills_roles=exits_kill_roles,
        ),
        RuleSpec(
            name=f"{underlying} {strike}{option_type} Scalp Square-Off @ {squareoff_time}",
            trigger_type="time",
            trigger_config={
                "at": squareoff_time,
                "on_days": ["mon", "tue", "wed", "thu", "fri"],
                "market_only": True,
            },
            action_type="place_order",
            action_config={**base_action, "transaction_type": "SELL"},
            role=r_squareoff,
            enabled=False,
            kills_roles=[r_entry] + all_exits,
        ),
    ]


def _validate_scalp_options_common(p: dict[str, Any]) -> None:
    """Shared validation for scalp-options templates (single + ladder)."""
    if int(p["cycles"]) < 1:
        raise ValueError("cycles must be >= 1")
    if int(p["cooldown_seconds"]) < 0:
        raise ValueError("cooldown_seconds must be >= 0")
    if int(p["lr_period"]) < 3:
        raise ValueError("lr_period must be >= 3")
    if float(p["lr_stdev"]) <= 0:
        raise ValueError("lr_stdev must be > 0")


class UTBotScalpOptionsTemplate(StrategyTemplate):
    name = "utbot-scalp-options"
    category = "fno"
    description = (
        "UT Bot Scalp (Options) — cyclical long-only scalper on a single "
        "option contract (CE or PE). Buys on every bullish UT Bot flip of "
        "the option's own premium, exits on any of three conditions: "
        "(1) bearish UT Bot flip, (2) LR channel upper-band touch (profit "
        "take, price overextended above fair trend), (3) LR channel lower-"
        "band break (dynamic volatility-based SL). The first exit to fire "
        "re-arms the entry for the next cycle. Cooldown prevents rapid "
        "re-fires in chop."
    )
    required_params = ["underlying", "expiry", "strike", "option_type", "lots"]
    optional_params = {
        "period": 10,
        "sensitivity": 1.0,
        "timeframe": "5m",
        "product": "I",
        "squareoff_time": "15:15",
        "cycles": 20,
        "cooldown_seconds": 60,
        "lr_period": 20,
        "lr_stdev": 2.0,
    }

    def plan(self, symbol: str, params: dict[str, Any]) -> StrategyPlan:
        p = self.validate_params(params)
        underlying = p["underlying"].upper()
        expiry = p["expiry"]
        strike = float(p["strike"])
        option_type = p["option_type"].upper()
        lots = int(p["lots"])

        if option_type not in ("CE", "PE"):
            raise ValueError(f"option_type must be CE or PE, got {option_type}")
        _validate_scalp_options_common(p)

        lot_size = resolve_option_instrument(underlying, expiry, strike, option_type)["lot_size"]
        qty = lots * lot_size

        plan = StrategyPlan(
            template_name=self.name,
            symbol=underlying,
            summary=(
                f"UT Bot Scalp {option_type} {underlying} {strike} ({expiry}): "
                f"cycling BUY/SELL {lots}L ({qty} qty), up to {int(p['cycles'])} cycles, "
                f"LR({int(p['lr_period'])},{float(p['lr_stdev'])}σ) exits, "
                f"{int(p['cooldown_seconds'])}s cooldown"
            ),
            params=p,
        )

        plan.rules = _build_scalp_options_rules(
            underlying=underlying,
            expiry=expiry,
            strike=strike,
            option_type=option_type,
            lots=lots,
            period=int(p["period"]),
            sensitivity=float(p["sensitivity"]),
            timeframe=p["timeframe"],
            product=p["product"],
            cycles=int(p["cycles"]),
            cooldown=int(p["cooldown_seconds"]),
            lr_period=int(p["lr_period"]),
            lr_stdev=float(p["lr_stdev"]),
            squareoff_time=p["squareoff_time"],
            role_suffix="",
        )
        return plan


class UTBotScalpOptionsLadderTemplate(StrategyTemplate):
    name = "utbot-scalp-options-ladder"
    category = "fno"
    description = (
        "Strike-ladder of utbot-scalp-options instances. Deploys N parallel "
        "cycling scalpers centered on a specified strike, spaced by the "
        "underlying's strike interval. As the underlying drifts during the "
        "day, whichever strike is closest to ATM will generate the cleanest "
        "UT Bot / LR signals; off-ATM strikes naturally go quiet (flat "
        "premium = no flips). Each strike has an independent entry/exit "
        "chain, its own cycles budget, its own cooldown, and its own "
        "squareoff. Capital scales linearly with ladder_size, so size the "
        "ladder to your margin tolerance on high-vol days. Use an odd "
        "ladder_size so center_strike is one of the deployed strikes."
    )
    required_params = ["underlying", "expiry", "option_type", "lots", "center_strike"]
    optional_params = {
        "ladder_size": 3,
        "strike_interval": None,  # auto-detect from underlying
        "period": 10,
        "sensitivity": 1.0,
        "timeframe": "5m",
        "product": "I",
        "squareoff_time": "15:15",
        "cycles": 20,
        "cooldown_seconds": 60,
        "lr_period": 20,
        "lr_stdev": 2.0,
    }

    def plan(self, symbol: str, params: dict[str, Any]) -> StrategyPlan:
        p = self.validate_params(params)
        underlying = p["underlying"].upper()
        expiry = p["expiry"]
        option_type = p["option_type"].upper()
        lots = int(p["lots"])
        center_strike = float(p["center_strike"])
        ladder_size = int(p["ladder_size"])

        if option_type not in ("CE", "PE"):
            raise ValueError(f"option_type must be CE or PE, got {option_type}")
        if ladder_size < 1:
            raise ValueError("ladder_size must be >= 1")
        if ladder_size > 9:
            raise ValueError("ladder_size must be <= 9 (capital safety guard)")
        if ladder_size % 2 == 0:
            raise ValueError(
                "ladder_size must be odd so center_strike is one of the "
                "deployed strikes. Use 1, 3, 5, 7, or 9."
            )

        strike_interval = p["strike_interval"]
        if strike_interval is None:
            strike_interval = get_strike_interval(underlying)
        else:
            strike_interval = float(strike_interval)
        if strike_interval <= 0:
            raise ValueError("strike_interval must be > 0")

        _validate_scalp_options_common(p)

        # Generate strikes symmetric around the center. Odd ladder_size
        # guarantees center_strike is one of them and all strikes sit on
        # the underlying's standard interval grid.
        half = ladder_size // 2
        strikes = [
            center_strike + (i - half) * strike_interval
            for i in range(ladder_size)
        ]

        plan = StrategyPlan(
            template_name=self.name,
            symbol=underlying,
            summary=(
                f"UT Bot Scalp {option_type} ladder on {underlying} {expiry}: "
                f"{ladder_size} strikes around {center_strike} "
                f"(±{strike_interval} steps), {lots}L each, "
                f"up to {int(p['cycles'])} cycles per strike, "
                f"LR({int(p['lr_period'])},{float(p['lr_stdev'])}σ) exits"
            ),
            params=p,
        )

        all_rules: list[RuleSpec] = []
        for strike in strikes:
            # Suffix keeps each strike's activate/kill chain isolated.
            # int() cast is safe here because all strikes sit on the
            # underlying's integer-multiple interval grid.
            suffix = f"_s{int(strike)}"
            rules = _build_scalp_options_rules(
                underlying=underlying,
                expiry=expiry,
                strike=strike,
                option_type=option_type,
                lots=lots,
                period=int(p["period"]),
                sensitivity=float(p["sensitivity"]),
                timeframe=p["timeframe"],
                product=p["product"],
                cycles=int(p["cycles"]),
                cooldown=int(p["cooldown_seconds"]),
                lr_period=int(p["lr_period"]),
                lr_stdev=float(p["lr_stdev"]),
                squareoff_time=p["squareoff_time"],
                role_suffix=suffix,
            )
            all_rules.extend(rules)

        plan.rules = all_rules
        return plan
