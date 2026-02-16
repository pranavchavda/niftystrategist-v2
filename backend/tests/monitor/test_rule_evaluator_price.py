"""Tests for evaluate_price_trigger — pure function, no I/O."""
from monitor.models import MonitorRule
from monitor.rule_evaluator import evaluate_price_trigger


def _make_price_rule(condition: str, price: float, reference: str = "ltp") -> MonitorRule:
    return MonitorRule(
        id=1,
        user_id=999,
        name="test",
        trigger_type="price",
        trigger_config={"condition": condition, "price": price, "reference": reference},
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

class TestLte:
    def test_fires_at_threshold(self):
        rule = _make_price_rule("lte", 100.0)
        assert evaluate_price_trigger(rule, {"ltp": 100.0}) is True

    def test_fires_below_threshold(self):
        rule = _make_price_rule("lte", 100.0)
        assert evaluate_price_trigger(rule, {"ltp": 99.5}) is True

    def test_does_not_fire_above_threshold(self):
        rule = _make_price_rule("lte", 100.0)
        assert evaluate_price_trigger(rule, {"ltp": 100.5}) is False


# ── gte ──────────────────────────────────────────────────────────────

class TestGte:
    def test_fires_at_threshold(self):
        rule = _make_price_rule("gte", 200.0)
        assert evaluate_price_trigger(rule, {"ltp": 200.0}) is True

    def test_fires_above_threshold(self):
        rule = _make_price_rule("gte", 200.0)
        assert evaluate_price_trigger(rule, {"ltp": 210.0}) is True

    def test_does_not_fire_below_threshold(self):
        rule = _make_price_rule("gte", 200.0)
        assert evaluate_price_trigger(rule, {"ltp": 199.99}) is False


# ── crosses_above ────────────────────────────────────────────────────

class TestCrossesAbove:
    def test_fires_on_cross(self):
        rule = _make_price_rule("crosses_above", 150.0)
        assert evaluate_price_trigger(rule, {"ltp": 151.0}, prev_price=149.0) is True

    def test_does_not_fire_if_already_above(self):
        rule = _make_price_rule("crosses_above", 150.0)
        assert evaluate_price_trigger(rule, {"ltp": 155.0}, prev_price=152.0) is False

    def test_does_not_fire_if_still_below(self):
        rule = _make_price_rule("crosses_above", 150.0)
        assert evaluate_price_trigger(rule, {"ltp": 148.0}, prev_price=145.0) is False

    def test_returns_false_without_prev_price(self):
        rule = _make_price_rule("crosses_above", 150.0)
        assert evaluate_price_trigger(rule, {"ltp": 151.0}) is False


# ── crosses_below ────────────────────────────────────────────────────

class TestCrossesBelow:
    def test_fires_on_cross(self):
        rule = _make_price_rule("crosses_below", 100.0)
        assert evaluate_price_trigger(rule, {"ltp": 99.0}, prev_price=101.0) is True

    def test_does_not_fire_if_already_below(self):
        rule = _make_price_rule("crosses_below", 100.0)
        assert evaluate_price_trigger(rule, {"ltp": 95.0}, prev_price=97.0) is False

    def test_returns_false_without_prev_price(self):
        rule = _make_price_rule("crosses_below", 100.0)
        assert evaluate_price_trigger(rule, {"ltp": 99.0}) is False


# ── reference field ──────────────────────────────────────────────────

class TestReferenceField:
    def test_uses_bid_reference(self):
        rule = _make_price_rule("gte", 50.0, reference="bid")
        assert evaluate_price_trigger(rule, {"ltp": 49.0, "bid": 51.0}) is True

    def test_returns_false_if_reference_missing(self):
        rule = _make_price_rule("gte", 50.0, reference="bid")
        assert evaluate_price_trigger(rule, {"ltp": 100.0}) is False
