"""Tests for evaluate_rule (top-level entry point) — pure function, no I/O."""
from datetime import datetime, timedelta

from monitor.models import MonitorRule
from monitor.rule_evaluator import EvalContext, RuleResult, evaluate_rule


def _make_price_rule(**overrides) -> MonitorRule:
    defaults = dict(
        id=1,
        user_id=999,
        name="test",
        trigger_type="price",
        trigger_config={"condition": "gte", "price": 100.0, "reference": "ltp"},
        action_type="place_order",
        action_config={
            "symbol": "X",
            "transaction_type": "BUY",
            "quantity": 10,
            "order_type": "MARKET",
            "product": "I",
            "price": None,
        },
        instrument_token="NSE_EQ|TEST",
    )
    defaults.update(overrides)
    return MonitorRule(**defaults)


# ── Firing ──────────────────────────────────────────────────────────

class TestEvaluateRuleFired:
    def test_fired_true_when_price_trigger_fires(self):
        rule = _make_price_rule()
        ctx = EvalContext(market_data={"ltp": 150.0})
        result = evaluate_rule(rule, ctx)
        assert result.fired is True
        assert result.skipped is False
        assert result.rule_id == 1
        assert result.action_type == "place_order"
        assert result.action_config["symbol"] == "X"

    def test_fired_false_when_not_triggered(self):
        rule = _make_price_rule()
        ctx = EvalContext(market_data={"ltp": 50.0})
        result = evaluate_rule(rule, ctx)
        assert result.fired is False
        assert result.skipped is False
        assert result.rule_id == 1


# ── Skipping ────────────────────────────────────────────────────────

class TestEvaluateRuleSkipped:
    def test_skipped_for_disabled_rule(self):
        rule = _make_price_rule(enabled=False)
        ctx = EvalContext(market_data={"ltp": 150.0})
        result = evaluate_rule(rule, ctx)
        assert result.skipped is True
        assert result.fired is False

    def test_skipped_for_expired_rule(self):
        rule = _make_price_rule(expires_at=datetime.utcnow() - timedelta(hours=1))
        ctx = EvalContext(market_data={"ltp": 150.0})
        result = evaluate_rule(rule, ctx)
        assert result.skipped is True
        assert result.fired is False


# ── Cancel-rule action (OCO) ────────────────────────────────────────

class TestCancelRuleAction:
    def test_cancel_rule_populates_rules_to_cancel(self):
        rule = MonitorRule(
            id=10,
            user_id=999,
            name="oco-cancel",
            trigger_type="price",
            trigger_config={"condition": "lte", "price": 90.0, "reference": "ltp"},
            action_type="cancel_rule",
            action_config={"rule_id": 11},
            instrument_token="NSE_EQ|TEST",
        )
        ctx = EvalContext(market_data={"ltp": 85.0})
        result = evaluate_rule(rule, ctx)
        assert result.fired is True
        assert result.action_type == "cancel_rule"
        assert result.rules_to_cancel == [11]


# ── prev_prices integration ─────────────────────────────────────────

class TestPrevPrices:
    def test_prev_price_passed_from_context(self):
        rule = _make_price_rule(
            trigger_config={"condition": "crosses_above", "price": 100.0, "reference": "ltp"},
        )
        ctx = EvalContext(
            market_data={"ltp": 105.0},
            prev_prices={"NSE_EQ|TEST": 95.0},
        )
        result = evaluate_rule(rule, ctx)
        assert result.fired is True


# ── Trailing stop dispatch ─────────────────────────────────────────

class TestTrailingStopDispatch:
    def test_trailing_stop_fires_through_evaluate_rule(self):
        """trailing_stop trigger type dispatches correctly and fires."""
        rule = MonitorRule(
            id=20,
            user_id=999,
            name="trailing test",
            trigger_type="trailing_stop",
            trigger_config={
                "trail_percent": 10.0,
                "initial_price": 100.0,
                "highest_price": 100.0,
            },
            action_type="place_order",
            action_config={
                "symbol": "X",
                "transaction_type": "SELL",
                "quantity": 5,
                "order_type": "MARKET",
                "product": "D",
                "price": None,
            },
            instrument_token="NSE_EQ|TEST",
        )
        # Stop at 90.0 (10% below 100). Price at 85 fires.
        ctx = EvalContext(market_data={"ltp": 85.0})
        result = evaluate_rule(rule, ctx)
        assert result.fired is True
        assert result.action_type == "place_order"
        assert result.trigger_config_update is None

    def test_trailing_stop_updates_highest_through_evaluate_rule(self):
        """trailing_stop returns trigger_config_update when price rises."""
        rule = MonitorRule(
            id=21,
            user_id=999,
            name="trailing test",
            trigger_type="trailing_stop",
            trigger_config={
                "trail_percent": 10.0,
                "initial_price": 100.0,
                "highest_price": 100.0,
            },
            action_type="place_order",
            action_config={
                "symbol": "X",
                "transaction_type": "SELL",
                "quantity": 5,
                "order_type": "MARKET",
                "product": "D",
                "price": None,
            },
            instrument_token="NSE_EQ|TEST",
        )
        ctx = EvalContext(market_data={"ltp": 120.0})
        result = evaluate_rule(rule, ctx)
        assert result.fired is False
        assert result.trigger_config_update is not None
        assert result.trigger_config_update["highest_price"] == 120.0
