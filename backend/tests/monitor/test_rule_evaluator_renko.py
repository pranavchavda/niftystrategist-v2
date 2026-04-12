"""Tests for evaluate_renko_trigger — pure function, no I/O."""
from monitor.models import MonitorRule
from monitor.rule_evaluator import evaluate_renko_trigger


def _make_renko_rule(
    brick_size: float = 10.0,
    condition: str = "reversal_up",
    base_price: float | None = None,
    trend: str | None = None,
) -> MonitorRule:
    return MonitorRule(
        id=1,
        user_id=999,
        name="test renko",
        trigger_type="renko",
        trigger_config={
            "brick_size": brick_size,
            "condition": condition,
            "base_price": base_price,
            "trend": trend,
        },
        action_type="place_order",
        action_config={
            "symbol": "RELIANCE",
            "transaction_type": "BUY",
            "quantity": 1,
            "order_type": "MARKET",
            "product": "I",
        },
        instrument_token="NSE_EQ|INE002A01018",
    )


# -- Initialization -------------------------------------------------------

class TestRenkoInitialization:
    def test_first_tick_seeds_base_price(self):
        """First tick should set base_price and not fire."""
        rule = _make_renko_rule(base_price=None, trend=None)
        fired, update = evaluate_renko_trigger(rule, {"ltp": 500.0})
        assert fired is False
        assert update is not None
        assert update["base_price"] == 500.0

    def test_no_ltp_returns_false(self):
        """Missing LTP in market data should not fire or update."""
        rule = _make_renko_rule(base_price=500.0, trend="up")
        fired, update = evaluate_renko_trigger(rule, {})
        assert fired is False
        assert update is None


# -- Brick formation (no reversal) ----------------------------------------

class TestRenkoBrickFormation:
    def test_up_brick_forms(self):
        """LTP moves +brick_size above base → up brick, config updates."""
        rule = _make_renko_rule(brick_size=10.0, base_price=500.0, trend="up")
        fired, update = evaluate_renko_trigger(rule, {"ltp": 510.5})
        assert fired is False  # Continuation, not reversal
        assert update is not None
        assert update["base_price"] == 510.0
        assert update["trend"] == "up"

    def test_down_brick_forms(self):
        """LTP moves -brick_size below base → down brick."""
        rule = _make_renko_rule(brick_size=10.0, base_price=500.0, trend="down")
        fired, update = evaluate_renko_trigger(rule, {"ltp": 489.0})
        assert fired is False
        assert update is not None
        assert update["base_price"] == 490.0
        assert update["trend"] == "down"

    def test_no_brick_on_small_move(self):
        """LTP moves less than brick_size → no brick, no update."""
        rule = _make_renko_rule(brick_size=10.0, base_price=500.0, trend="up")
        fired, update = evaluate_renko_trigger(rule, {"ltp": 505.0})
        assert fired is False
        assert update is None

    def test_multi_brick_jump_up(self):
        """LTP jumps +35 with brick_size=10 → 3 up bricks formed."""
        rule = _make_renko_rule(brick_size=10.0, base_price=500.0, trend="up")
        fired, update = evaluate_renko_trigger(rule, {"ltp": 535.0})
        assert fired is False
        assert update["base_price"] == 530.0
        assert update["trend"] == "up"

    def test_multi_brick_jump_down(self):
        """LTP jumps -25 with brick_size=10 → 2 down bricks formed."""
        rule = _make_renko_rule(brick_size=10.0, base_price=500.0, trend="down")
        fired, update = evaluate_renko_trigger(rule, {"ltp": 475.0})
        assert fired is False
        assert update["base_price"] == 480.0
        assert update["trend"] == "down"


# -- Reversal detection (fires) -------------------------------------------

class TestRenkoReversalFires:
    def test_reversal_up_fires(self):
        """Trend was down, LTP rises a brick → reversal_up fires."""
        rule = _make_renko_rule(
            brick_size=10.0, condition="reversal_up",
            base_price=500.0, trend="down",
        )
        fired, update = evaluate_renko_trigger(rule, {"ltp": 510.5})
        assert fired is True
        assert update is not None
        assert update["trend"] == "up"
        assert update["base_price"] == 510.0

    def test_reversal_down_fires(self):
        """Trend was up, LTP drops a brick → reversal_down fires."""
        rule = _make_renko_rule(
            brick_size=10.0, condition="reversal_down",
            base_price=500.0, trend="up",
        )
        fired, update = evaluate_renko_trigger(rule, {"ltp": 489.0})
        assert fired is True
        assert update is not None
        assert update["trend"] == "down"
        assert update["base_price"] == 490.0

    def test_reversal_up_with_multi_brick_jump(self):
        """Trend was down, LTP jumps +25 → reversal_up fires, 2 up bricks."""
        rule = _make_renko_rule(
            brick_size=10.0, condition="reversal_up",
            base_price=500.0, trend="down",
        )
        fired, update = evaluate_renko_trigger(rule, {"ltp": 525.0})
        assert fired is True
        assert update["base_price"] == 520.0
        assert update["trend"] == "up"


# -- Reversal does NOT fire ------------------------------------------------

class TestRenkoReversalDoesNotFire:
    def test_continuation_does_not_fire(self):
        """Trend is up, more up bricks → no reversal."""
        rule = _make_renko_rule(
            brick_size=10.0, condition="reversal_up",
            base_price=500.0, trend="up",
        )
        fired, update = evaluate_renko_trigger(rule, {"ltp": 515.0})
        assert fired is False

    def test_wrong_reversal_direction(self):
        """Trend was down, LTP goes further down → no reversal_up."""
        rule = _make_renko_rule(
            brick_size=10.0, condition="reversal_up",
            base_price=500.0, trend="down",
        )
        fired, update = evaluate_renko_trigger(rule, {"ltp": 488.0})
        assert fired is False

    def test_reversal_down_does_not_fire_on_up_reversal(self):
        """Condition is reversal_down but trend reverses up → no fire."""
        rule = _make_renko_rule(
            brick_size=10.0, condition="reversal_down",
            base_price=500.0, trend="down",
        )
        fired, update = evaluate_renko_trigger(rule, {"ltp": 511.0})
        assert fired is False

    def test_no_fire_when_trend_is_none(self):
        """First real brick (trend was None) should NOT fire as reversal."""
        rule = _make_renko_rule(
            brick_size=10.0, condition="reversal_up",
            base_price=500.0, trend=None,
        )
        fired, update = evaluate_renko_trigger(rule, {"ltp": 511.0})
        assert fired is False
        # But trend should be set now
        assert update is not None
        assert update["trend"] == "up"


# -- State persistence (config updates) ------------------------------------

class TestRenkoStateUpdates:
    def test_config_not_updated_when_no_bricks(self):
        """No brick formed → no config update returned."""
        rule = _make_renko_rule(brick_size=10.0, base_price=500.0, trend="up")
        _, update = evaluate_renko_trigger(rule, {"ltp": 504.0})
        assert update is None

    def test_config_preserves_immutable_fields(self):
        """Config update carries forward brick_size and condition."""
        rule = _make_renko_rule(
            brick_size=15.0, condition="reversal_down",
            base_price=500.0, trend="up",
        )
        _, update = evaluate_renko_trigger(rule, {"ltp": 515.5})
        assert update is not None
        assert update["brick_size"] == 15.0
        assert update["condition"] == "reversal_down"

    def test_sequential_ticks_accumulate_state(self):
        """Simulate 3 ticks: seed → up brick → reversal down."""
        # Tick 1: seed
        rule = _make_renko_rule(brick_size=10.0, condition="reversal_down", base_price=None)
        _, u1 = evaluate_renko_trigger(rule, {"ltp": 100.0})
        assert u1["base_price"] == 100.0

        # Tick 2: up brick (trend established)
        rule.trigger_config = u1
        _, u2 = evaluate_renko_trigger(rule, {"ltp": 111.0})
        assert u2["trend"] == "up"
        assert u2["base_price"] == 110.0

        # Tick 3: reversal down
        rule.trigger_config = u2
        fired, u3 = evaluate_renko_trigger(rule, {"ltp": 99.0})
        assert fired is True
        assert u3["trend"] == "down"
        assert u3["base_price"] == 100.0
