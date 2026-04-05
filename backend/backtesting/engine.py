"""Backtest engine — simulates candle-by-candle execution of strategy rules."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from backtesting.metrics import compute_metrics
from backtesting.simulator import Trade, TradeSimulator
from monitor.indicator_engine import compute_indicator
from strategies.templates import RuleSpec


@dataclass
class BacktestResult:
    """Result of a single backtest run."""
    symbol: str
    strategy: str
    trades: list[Trade]
    metrics: dict[str, Any]
    candle_count: int
    days: int


@dataclass
class _RenkoState:
    """Tracks Renko brick state across candles."""
    brick_size: float = 15.0
    base_price: float = 0.0
    current_direction: str = ""  # "up" or "down" or "" (no bricks yet)
    initialized: bool = False


@dataclass
class _RuleState:
    """Mutable state for a rule during backtesting."""
    spec: RuleSpec
    fire_count: int = 0
    enabled: bool = True
    # Trailing stop state
    highest_price: float = 0.0
    lowest_price: float = float("inf")

    @property
    def is_entry(self) -> bool:
        return "entry" in self.spec.role

    @property
    def is_exit(self) -> bool:
        return self.spec.role in ("sl", "target", "trailing", "squareoff",
                                   "sl_long", "sl_short", "target_long",
                                   "target_short", "trailing_long", "trailing_short")

    @property
    def should_evaluate(self) -> bool:
        if not self.enabled:
            return False
        max_fires = self.spec.max_fires
        if max_fires is not None and self.fire_count >= max_fires:
            return False
        return True

    @property
    def direction(self) -> str | None:
        """Infer long/short from action_config or role."""
        role = self.spec.role
        if "long" in role:
            return "long"
        if "short" in role:
            return "short"
        # Infer from action: BUY entry = long, SELL entry = short
        ac = self.spec.action_config
        if self.is_entry:
            return "long" if ac.get("transaction_type") == "BUY" else "short"
        return None


class BacktestEngine:
    """Simulates candle-by-candle execution of strategy rules against historical data.

    Args:
        candles: list of dicts with keys: timestamp, open, high, low, close, volume
        rules: list of RuleSpec from a StrategyPlan
        symbol: trading symbol name
        strategy_name: name of the strategy template
        initial_capital: starting capital for metrics
    """

    def __init__(
        self,
        candles: list[dict],
        rules: list[RuleSpec],
        symbol: str,
        strategy_name: str = "",
        initial_capital: float = 100_000,
    ):
        self.candles = sorted(candles, key=lambda c: c["timestamp"])
        self.symbol = symbol
        self.strategy_name = strategy_name
        self.initial_capital = initial_capital

        # Build rule states
        self._rules: list[_RuleState] = [_RuleState(spec=r) for r in rules]
        self._sim = TradeSimulator(symbol)

        # Renko state: keyed by brick_size so multiple brick sizes can coexist
        self._renko: dict[float, _RenkoState] = {}

    def run(self) -> BacktestResult:
        """Run the backtest candle by candle."""
        candle_history: list[dict] = []

        for i, candle in enumerate(self.candles):
            candle_history.append(candle)
            ts = self._parse_timestamp(candle["timestamp"])

            # Evaluate all rules against this candle
            fired_rules = self._evaluate_candle(candle, candle_history, ts)

            # Process fired rules in priority order: entry first, then exits
            # But only process exits if we have a position, entries if we're flat
            for rs in fired_rules:
                self._process_fire(rs, candle, ts)

        # Close any remaining open position at last candle's close
        if not self._sim.is_flat and self.candles:
            last = self.candles[-1]
            ts = self._parse_timestamp(last["timestamp"])
            self._sim.close_position(last["close"], ts, "end_of_data")

        trades = self._sim.trades
        metrics = compute_metrics(trades, self.initial_capital)

        # Count unique days
        day_set = set()
        for c in self.candles:
            t = self._parse_timestamp(c["timestamp"])
            day_set.add(t.date())

        return BacktestResult(
            symbol=self.symbol,
            strategy=self.strategy_name,
            trades=trades,
            metrics=metrics,
            candle_count=len(self.candles),
            days=len(day_set),
        )

    def _evaluate_candle(
        self, candle: dict, history: list[dict], ts: datetime
    ) -> list[_RuleState]:
        """Evaluate all rules against a candle, return list of fired rules."""
        fired: list[_RuleState] = []

        for rs in self._rules:
            if not rs.should_evaluate:
                continue
            if self._check_rule(rs, candle, history, ts):
                fired.append(rs)

        # Sort: entries first (so position opens before exit rules check),
        # but actually we want to process in a sensible order:
        # If flat: only process entries. If in position: only process exits.
        return fired

    def _check_rule(
        self, rs: _RuleState, candle: dict, history: list[dict], ts: datetime
    ) -> bool:
        """Check if a single rule fires on this candle."""
        spec = rs.spec
        tc = spec.trigger_config

        if spec.trigger_type == "price":
            return self._check_price(tc, candle)

        if spec.trigger_type == "indicator":
            return self._check_indicator(tc, history)

        if spec.trigger_type == "time":
            return self._check_time(tc, ts)

        if spec.trigger_type == "trailing_stop":
            return self._check_trailing(rs, candle)

        if spec.trigger_type == "renko":
            return self._check_renko(tc, candle)

        return False

    def _check_price(self, tc: dict, candle: dict) -> bool:
        """Check price trigger using candle high/low for intra-candle crossing."""
        condition = tc.get("condition", "")
        price = tc.get("price", 0)

        if condition == "gte":
            return candle["high"] >= price
        if condition == "lte":
            return candle["low"] <= price
        if condition == "crosses_above":
            # Previous candle's close was below, this candle's high reached above
            return candle["open"] < price and candle["high"] >= price
        if condition == "crosses_below":
            return candle["open"] > price and candle["low"] <= price
        return False

    def _check_indicator(self, tc: dict, history: list[dict]) -> bool:
        """Check indicator trigger against rolling candle history."""
        indicator = tc.get("indicator", "")
        condition = tc.get("condition", "")
        value = tc.get("value", 0)
        params = tc.get("params", {})

        computed = compute_indicator(indicator, history, params)
        if computed is None:
            return False

        if condition == "lte":
            return computed <= value
        if condition == "gte":
            return computed >= value
        # For crosses_above/below we'd need previous value — approximate by
        # checking current vs threshold (indicators change slowly across candles)
        if condition == "crosses_above":
            # Check if we just crossed: compute with history[:-1] too
            if len(history) < 4:
                return False
            prev = compute_indicator(indicator, history[:-1], params)
            if prev is None:
                return False
            return prev < value and computed >= value
        if condition == "crosses_below":
            if len(history) < 4:
                return False
            prev = compute_indicator(indicator, history[:-1], params)
            if prev is None:
                return False
            return prev > value and computed <= value
        return False

    def _check_time(self, tc: dict, ts: datetime) -> bool:
        """Check time trigger against candle timestamp."""
        at = tc.get("at", "")
        if not at:
            return False
        parts = at.split(":")
        if len(parts) != 2:
            return False
        hour, minute = int(parts[0]), int(parts[1])
        return ts.hour == hour and ts.minute == minute

    def _check_trailing(self, rs: _RuleState, candle: dict) -> bool:
        """Check trailing stop trigger, updating highest/lowest price."""
        tc = rs.spec.trigger_config
        trail_pct = tc.get("trail_percent", 1.5)
        direction = tc.get("direction", "long")

        if direction == "long":
            # Update highest price
            if candle["high"] > rs.highest_price:
                rs.highest_price = candle["high"]
            if rs.highest_price <= 0:
                return False
            stop = rs.highest_price * (1 - trail_pct / 100)
            return candle["low"] <= stop
        else:
            # Short: track lowest, fire when price rises above stop
            if candle["low"] < rs.lowest_price:
                rs.lowest_price = candle["low"]
            if rs.lowest_price <= 0 or rs.lowest_price == float("inf"):
                return False
            stop = rs.lowest_price * (1 + trail_pct / 100)
            return candle["high"] >= stop

    def _check_renko(self, tc: dict, candle: dict) -> bool:
        """Check Renko reversal trigger.

        Builds Renko bricks from candle closes and detects direction changes.
        """
        brick_size = tc.get("brick_size", 15.0)
        condition = tc.get("condition", "")

        # Get or create Renko state for this brick size
        if brick_size not in self._renko:
            self._renko[brick_size] = _RenkoState(brick_size=brick_size)

        rs = self._renko[brick_size]
        price = candle["close"]

        if not rs.initialized:
            rs.base_price = price
            rs.initialized = True
            return False

        prev_direction = rs.current_direction
        new_bricks = False

        # Build bricks from current price
        diff = price - rs.base_price
        while diff >= brick_size:
            rs.base_price += brick_size
            rs.current_direction = "up"
            new_bricks = True
            diff = price - rs.base_price
        while diff <= -brick_size:
            rs.base_price -= brick_size
            rs.current_direction = "down"
            new_bricks = True
            diff = price - rs.base_price

        if not new_bricks:
            return False

        # Detect reversals
        if condition == "reversal_up":
            return prev_direction == "down" and rs.current_direction == "up"
        elif condition == "reversal_down":
            return prev_direction == "up" and rs.current_direction == "down"
        elif condition == "new_brick_up":
            return rs.current_direction == "up"
        elif condition == "new_brick_down":
            return rs.current_direction == "down"

        return False

    def _process_fire(self, rs: _RuleState, candle: dict, ts: datetime) -> None:
        """Process a fired rule — open or close position as appropriate."""
        spec = rs.spec
        ac = spec.action_config
        qty = ac.get("quantity", 1)

        # Determine execution price
        exec_price = self._get_exec_price(rs, candle)

        if rs.is_entry:
            # Only enter if flat (or if this is an opposite-direction entry)
            if self._sim.is_flat:
                direction = rs.direction or "long"
                self._sim.open_position(direction, exec_price, ts, qty)
                rs.fire_count += 1
                # Initialize trailing stops with entry price
                self._init_trailing_on_entry(exec_price, direction)
                # Enable exit rules for this direction
                self._enable_exit_rules(direction)
            elif rs.direction and rs.direction != self._sim.position.side:
                # Opposite direction entry — close current, open new
                direction = rs.direction
                self._sim.open_position(direction, exec_price, ts, qty)
                rs.fire_count += 1
                self._init_trailing_on_entry(exec_price, direction)
                self._enable_exit_rules(direction)

        elif rs.is_exit:
            # Only exit if we have a position in the matching direction
            if self._sim.is_flat:
                return

            pos_side = self._sim.position.side
            # Check direction compatibility
            rule_dir = self._infer_exit_direction(rs)
            if rule_dir and rule_dir != pos_side:
                return

            reason = self._exit_reason(spec.role)
            self._sim.close_position(exec_price, ts, reason)
            rs.fire_count += 1

            # Disable all exit rules after position closed
            self._disable_exit_rules()

    def _get_exec_price(self, rs: _RuleState, candle: dict) -> float:
        """Determine execution price for a fired rule."""
        spec = rs.spec
        tc = spec.trigger_config

        if spec.trigger_type == "price":
            # Use the trigger price (simulates limit-like execution)
            return tc.get("price", candle["close"])

        if spec.trigger_type == "trailing_stop":
            direction = tc.get("direction", "long")
            trail_pct = tc.get("trail_percent", 1.5)
            if direction == "long":
                return rs.highest_price * (1 - trail_pct / 100)
            else:
                return rs.lowest_price * (1 + trail_pct / 100)

        if spec.trigger_type == "time":
            # Time-based exit: use candle close
            return candle["close"]

        # Indicator-based: use candle close
        return candle["close"]

    def _init_trailing_on_entry(self, entry_price: float, direction: str) -> None:
        """Initialize trailing stop states after an entry."""
        for rs in self._rules:
            if rs.spec.trigger_type == "trailing_stop":
                trail_dir = rs.spec.trigger_config.get("direction", "long")
                if trail_dir == direction:
                    if direction == "long":
                        rs.highest_price = entry_price
                    else:
                        rs.lowest_price = entry_price

    def _enable_exit_rules(self, direction: str) -> None:
        """Enable exit rules matching the given direction after entry."""
        for rs in self._rules:
            if not rs.is_exit:
                continue
            rule_dir = self._infer_exit_direction(rs)
            # Enable if direction matches or rule is direction-agnostic
            if rule_dir is None or rule_dir == direction:
                rs.enabled = True

    def _disable_exit_rules(self) -> None:
        """Disable all exit rules after position closed."""
        for rs in self._rules:
            if rs.is_exit:
                rs.enabled = False

    def _infer_exit_direction(self, rs: _RuleState) -> str | None:
        """Infer which position direction this exit rule applies to."""
        role = rs.spec.role
        if "long" in role:
            return "long"
        if "short" in role:
            return "short"
        return None  # direction-agnostic

    def _exit_reason(self, role: str) -> str:
        """Map rule role to exit reason string."""
        if "sl" in role:
            return "sl"
        if "target" in role:
            return "target"
        if "trailing" in role:
            return "trailing"
        if "squareoff" in role:
            return "squareoff"
        return "rule"

    @staticmethod
    def _parse_timestamp(ts: str | datetime) -> datetime:
        """Parse a timestamp string to datetime."""
        if isinstance(ts, datetime):
            return ts
        # Try common formats
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S%z",
                     "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S.%f%z"):
            try:
                dt = datetime.strptime(ts, fmt)
                return dt.replace(tzinfo=None)  # strip tz for consistency
            except ValueError:
                continue
        # Last resort
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).replace(tzinfo=None)


def run_backtest_for_day(
    day_candles: list[dict],
    rules: list[RuleSpec],
    symbol: str,
    strategy_name: str,
    initial_capital: float,
) -> BacktestResult:
    """Run a backtest on a single day's candles with fresh rule state."""
    engine = BacktestEngine(
        candles=day_candles,
        rules=rules,
        symbol=symbol,
        strategy_name=strategy_name,
        initial_capital=initial_capital,
    )
    # For intraday strategies: disable exit rules initially (wait for entry)
    for rs in engine._rules:
        if rs.is_exit:
            rs.enabled = False
    return engine.run()
