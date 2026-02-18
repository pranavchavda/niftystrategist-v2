"""Tests for indicator trigger evaluation."""
from monitor.models import MonitorRule


def _make_indicator_rule(indicator="rsi", timeframe="5m", condition="lte", value=30.0):
    return MonitorRule(
        id=1,
        user_id=999,
        name="test",
        trigger_type="indicator",
        trigger_config={
            "indicator": indicator,
            "timeframe": timeframe,
            "condition": condition,
            "value": value,
            "params": {"period": 14},
        },
        action_type="place_order",
        action_config={
            "symbol": "X",
            "transaction_type": "SELL",
            "quantity": 1,
            "order_type": "MARKET",
            "product": "I",
            "price": None,
        },
        instrument_token="NSE_EQ|TEST",
    )


# ── lte ──────────────────────────────────────────────────────────────


class TestIndicatorTriggerLte:
    def test_fires_when_below(self):
        from monitor.rule_evaluator import evaluate_indicator_trigger

        rule = _make_indicator_rule("rsi", "5m", "lte", 30.0)
        assert evaluate_indicator_trigger(rule, {"rsi_5m": 25.0}) is True

    def test_fires_at_threshold(self):
        from monitor.rule_evaluator import evaluate_indicator_trigger

        rule = _make_indicator_rule("rsi", "5m", "lte", 30.0)
        assert evaluate_indicator_trigger(rule, {"rsi_5m": 30.0}) is True

    def test_does_not_fire_above(self):
        from monitor.rule_evaluator import evaluate_indicator_trigger

        rule = _make_indicator_rule("rsi", "5m", "lte", 30.0)
        assert evaluate_indicator_trigger(rule, {"rsi_5m": 45.0}) is False


# ── gte ──────────────────────────────────────────────────────────────


class TestIndicatorTriggerGte:
    def test_fires_when_above(self):
        from monitor.rule_evaluator import evaluate_indicator_trigger

        rule = _make_indicator_rule("rsi", "5m", "gte", 70.0)
        assert evaluate_indicator_trigger(rule, {"rsi_5m": 75.0}) is True

    def test_fires_at_threshold(self):
        from monitor.rule_evaluator import evaluate_indicator_trigger

        rule = _make_indicator_rule("rsi", "5m", "gte", 70.0)
        assert evaluate_indicator_trigger(rule, {"rsi_5m": 70.0}) is True

    def test_does_not_fire_below(self):
        from monitor.rule_evaluator import evaluate_indicator_trigger

        rule = _make_indicator_rule("rsi", "5m", "gte", 70.0)
        assert evaluate_indicator_trigger(rule, {"rsi_5m": 55.0}) is False


# ── crosses_above / crosses_below ───────────────────────────────────


class TestIndicatorTriggerCrosses:
    def test_crosses_above(self):
        from monitor.rule_evaluator import evaluate_indicator_trigger

        rule = _make_indicator_rule("macd", "5m", "crosses_above", 0.0)
        assert evaluate_indicator_trigger(
            rule, {"macd_5m": 0.5}, prev_indicator_values={"macd_5m": -0.3}
        ) is True

    def test_crosses_above_not_crossed(self):
        from monitor.rule_evaluator import evaluate_indicator_trigger

        rule = _make_indicator_rule("macd", "5m", "crosses_above", 0.0)
        assert evaluate_indicator_trigger(
            rule, {"macd_5m": 0.5}, prev_indicator_values={"macd_5m": 0.2}
        ) is False

    def test_crosses_above_no_prev(self):
        from monitor.rule_evaluator import evaluate_indicator_trigger

        rule = _make_indicator_rule("macd", "5m", "crosses_above", 0.0)
        assert evaluate_indicator_trigger(rule, {"macd_5m": 0.5}) is False

    def test_crosses_below(self):
        from monitor.rule_evaluator import evaluate_indicator_trigger

        rule = _make_indicator_rule("rsi", "15m", "crosses_below", 30.0)
        assert evaluate_indicator_trigger(
            rule, {"rsi_15m": 28.0}, prev_indicator_values={"rsi_15m": 32.0}
        ) is True

    def test_crosses_below_not_crossed(self):
        from monitor.rule_evaluator import evaluate_indicator_trigger

        rule = _make_indicator_rule("rsi", "15m", "crosses_below", 30.0)
        assert evaluate_indicator_trigger(
            rule, {"rsi_15m": 28.0}, prev_indicator_values={"rsi_15m": 25.0}
        ) is False

    def test_crosses_below_no_prev(self):
        from monitor.rule_evaluator import evaluate_indicator_trigger

        rule = _make_indicator_rule("rsi", "15m", "crosses_below", 30.0)
        assert evaluate_indicator_trigger(rule, {"rsi_15m": 28.0}) is False


# ── Missing / None values ───────────────────────────────────────────


class TestIndicatorMissingValue:
    def test_returns_false_for_missing_indicator(self):
        from monitor.rule_evaluator import evaluate_indicator_trigger

        rule = _make_indicator_rule("rsi", "5m", "lte", 30.0)
        assert evaluate_indicator_trigger(rule, {}) is False

    def test_returns_false_for_none_value(self):
        from monitor.rule_evaluator import evaluate_indicator_trigger

        rule = _make_indicator_rule("rsi", "5m", "lte", 30.0)
        assert evaluate_indicator_trigger(rule, {"rsi_5m": None}) is False


# ── Integration with evaluate_rule ──────────────────────────────────


class TestIndicatorViaEvaluateRule:
    def test_indicator_trigger_fires_through_evaluate_rule(self):
        from monitor.rule_evaluator import EvalContext, evaluate_rule

        rule = _make_indicator_rule("rsi", "5m", "lte", 30.0)
        ctx = EvalContext(indicator_values={"rsi_5m": 25.0})
        result = evaluate_rule(rule, ctx)
        assert result.fired is True

    def test_indicator_trigger_does_not_fire_through_evaluate_rule(self):
        from monitor.rule_evaluator import EvalContext, evaluate_rule

        rule = _make_indicator_rule("rsi", "5m", "lte", 30.0)
        ctx = EvalContext(indicator_values={"rsi_5m": 45.0})
        result = evaluate_rule(rule, ctx)
        assert result.fired is False

    def test_crosses_above_through_evaluate_rule(self):
        from monitor.rule_evaluator import EvalContext, evaluate_rule

        rule = _make_indicator_rule("macd", "5m", "crosses_above", 0.0)
        ctx = EvalContext(
            indicator_values={"macd_5m": 0.5},
            prev_indicator_values={"macd_5m": -0.3},
        )
        result = evaluate_rule(rule, ctx)
        assert result.fired is True

    def test_crosses_below_through_evaluate_rule(self):
        from monitor.rule_evaluator import EvalContext, evaluate_rule

        rule = _make_indicator_rule("rsi", "15m", "crosses_below", 30.0)
        ctx = EvalContext(
            indicator_values={"rsi_15m": 28.0},
            prev_indicator_values={"rsi_15m": 32.0},
        )
        result = evaluate_rule(rule, ctx)
        assert result.fired is True


# ── Compound trigger with indicator sub-condition ───────────────────


class TestIndicatorInCompound:
    def test_compound_and_with_indicator_and_price(self):
        from monitor.rule_evaluator import EvalContext, evaluate_rule

        rule = MonitorRule(
            id=10,
            user_id=999,
            name="compound-indicator-test",
            trigger_type="compound",
            trigger_config={
                "operator": "and",
                "conditions": [
                    {
                        "type": "indicator",
                        "indicator": "rsi",
                        "timeframe": "5m",
                        "condition": "lte",
                        "value": 30.0,
                        "params": {},
                    },
                    {
                        "type": "price",
                        "condition": "lte",
                        "price": 100.0,
                        "reference": "ltp",
                    },
                ],
            },
            action_type="place_order",
            action_config={
                "symbol": "X",
                "transaction_type": "BUY",
                "quantity": 1,
                "order_type": "MARKET",
                "product": "I",
                "price": None,
            },
            instrument_token="NSE_EQ|TEST",
        )
        ctx = EvalContext(
            market_data={"ltp": 95.0},
            indicator_values={"rsi_5m": 25.0},
        )
        result = evaluate_rule(rule, ctx)
        assert result.fired is True

    def test_compound_and_indicator_not_met(self):
        from monitor.rule_evaluator import EvalContext, evaluate_rule

        rule = MonitorRule(
            id=10,
            user_id=999,
            name="compound-indicator-test",
            trigger_type="compound",
            trigger_config={
                "operator": "and",
                "conditions": [
                    {
                        "type": "indicator",
                        "indicator": "rsi",
                        "timeframe": "5m",
                        "condition": "lte",
                        "value": 30.0,
                        "params": {},
                    },
                    {
                        "type": "price",
                        "condition": "lte",
                        "price": 100.0,
                        "reference": "ltp",
                    },
                ],
            },
            action_type="place_order",
            action_config={
                "symbol": "X",
                "transaction_type": "BUY",
                "quantity": 1,
                "order_type": "MARKET",
                "product": "I",
                "price": None,
            },
            instrument_token="NSE_EQ|TEST",
        )
        # Price condition met, but RSI too high (not met)
        ctx = EvalContext(
            market_data={"ltp": 95.0},
            indicator_values={"rsi_5m": 55.0},
        )
        result = evaluate_rule(rule, ctx)
        assert result.fired is False

    def test_compound_or_indicator_met_price_not(self):
        from monitor.rule_evaluator import EvalContext, evaluate_rule

        rule = MonitorRule(
            id=10,
            user_id=999,
            name="compound-or-test",
            trigger_type="compound",
            trigger_config={
                "operator": "or",
                "conditions": [
                    {
                        "type": "indicator",
                        "indicator": "rsi",
                        "timeframe": "5m",
                        "condition": "lte",
                        "value": 30.0,
                        "params": {},
                    },
                    {
                        "type": "price",
                        "condition": "lte",
                        "price": 100.0,
                        "reference": "ltp",
                    },
                ],
            },
            action_type="place_order",
            action_config={
                "symbol": "X",
                "transaction_type": "BUY",
                "quantity": 1,
                "order_type": "MARKET",
                "product": "I",
                "price": None,
            },
            instrument_token="NSE_EQ|TEST",
        )
        # Price NOT met, but RSI IS met => OR => fires
        ctx = EvalContext(
            market_data={"ltp": 150.0},
            indicator_values={"rsi_5m": 25.0},
        )
        result = evaluate_rule(rule, ctx)
        assert result.fired is True
