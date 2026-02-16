"""Tests for evaluate_compound_trigger — pure function, no I/O."""
from datetime import datetime

from monitor.models import MonitorRule
from monitor.rule_evaluator import evaluate_compound_trigger


def _make_compound_rule(operator, conditions):
    return MonitorRule(
        id=1,
        user_id=999,
        name="test",
        trigger_type="compound",
        trigger_config={"operator": operator, "conditions": conditions},
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


# ── AND operator ────────────────────────────────────────────────────

class TestCompoundAnd:
    def test_fires_when_all_conditions_met(self):
        """Two price conditions both true => fires."""
        rule = _make_compound_rule("and", [
            {"type": "price", "condition": "gte", "price": 100.0, "reference": "ltp"},
            {"type": "price", "condition": "lte", "price": 200.0, "reference": "ltp"},
        ])
        ctx = {"market_data": {"ltp": 150.0}, "now": None, "order_event": None}
        assert evaluate_compound_trigger(rule, ctx) is True

    def test_does_not_fire_when_one_fails(self):
        """One of two price conditions is false => doesn't fire."""
        rule = _make_compound_rule("and", [
            {"type": "price", "condition": "gte", "price": 100.0, "reference": "ltp"},
            {"type": "price", "condition": "lte", "price": 120.0, "reference": "ltp"},
        ])
        ctx = {"market_data": {"ltp": 150.0}, "now": None, "order_event": None}
        assert evaluate_compound_trigger(rule, ctx) is False


# ── OR operator ─────────────────────────────────────────────────────

class TestCompoundOr:
    def test_fires_when_one_condition_met(self):
        """One of two price conditions is true => fires."""
        rule = _make_compound_rule("or", [
            {"type": "price", "condition": "gte", "price": 200.0, "reference": "ltp"},
            {"type": "price", "condition": "lte", "price": 120.0, "reference": "ltp"},
        ])
        ctx = {"market_data": {"ltp": 100.0}, "now": None, "order_event": None}
        assert evaluate_compound_trigger(rule, ctx) is True

    def test_does_not_fire_when_none_met(self):
        """Neither condition true => doesn't fire."""
        rule = _make_compound_rule("or", [
            {"type": "price", "condition": "gte", "price": 200.0, "reference": "ltp"},
            {"type": "price", "condition": "lte", "price": 50.0, "reference": "ltp"},
        ])
        ctx = {"market_data": {"ltp": 100.0}, "now": None, "order_event": None}
        assert evaluate_compound_trigger(rule, ctx) is False


# ── Mixed types ─────────────────────────────────────────────────────

class TestCompoundMixed:
    def test_price_and_time_both_true_fires(self):
        """Price AND time both true => fires."""
        # Monday 2026-02-16 09:15:00
        now = datetime(2026, 2, 16, 9, 15, 0)
        rule = _make_compound_rule("and", [
            {"type": "price", "condition": "gte", "price": 100.0, "reference": "ltp"},
            {"type": "time", "at": "09:15", "on_days": ["mon"], "market_only": True},
        ])
        ctx = {"market_data": {"ltp": 150.0}, "now": now, "order_event": None}
        assert evaluate_compound_trigger(rule, ctx) is True
