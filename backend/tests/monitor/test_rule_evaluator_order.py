"""Tests for evaluate_order_status_trigger — pure function, no I/O."""
from monitor.models import MonitorRule
from monitor.rule_evaluator import evaluate_order_status_trigger


def _make_order_rule(order_id: str, status: str) -> MonitorRule:
    return MonitorRule(
        id=3,
        user_id=999,
        name="order-test",
        trigger_type="order_status",
        trigger_config={"order_id": order_id, "status": status},
        action_type="cancel_order",
        action_config={"order_id": "some-other-order"},
    )


class TestOrderStatusTrigger:
    def test_fires_on_matching_order_and_status(self):
        rule = _make_order_rule("ORD-123", "complete")
        event = {"order_id": "ORD-123", "status": "complete"}
        assert evaluate_order_status_trigger(rule, event) is True

    def test_does_not_fire_on_wrong_status(self):
        rule = _make_order_rule("ORD-123", "complete")
        event = {"order_id": "ORD-123", "status": "rejected"}
        assert evaluate_order_status_trigger(rule, event) is False

    def test_does_not_fire_on_wrong_order_id(self):
        rule = _make_order_rule("ORD-123", "complete")
        event = {"order_id": "ORD-999", "status": "complete"}
        assert evaluate_order_status_trigger(rule, event) is False

    def test_does_not_fire_on_empty_event(self):
        rule = _make_order_rule("ORD-123", "complete")
        assert evaluate_order_status_trigger(rule, {}) is False
