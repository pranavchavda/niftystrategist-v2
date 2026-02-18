"""Tests for evaluate_time_trigger — pure function, no I/O."""
from datetime import datetime

from monitor.models import MonitorRule
from monitor.rule_evaluator import evaluate_time_trigger


def _make_time_rule(
    at: str,
    on_days: list[str] | None = None,
    market_only: bool = True,
) -> MonitorRule:
    config: dict = {"at": at, "market_only": market_only}
    if on_days is not None:
        config["on_days"] = on_days
    return MonitorRule(
        id=2,
        user_id=999,
        name="time-test",
        trigger_type="time",
        trigger_config=config,
        action_type="place_order",
        action_config={
            "symbol": "X",
            "transaction_type": "BUY",
            "quantity": 1,
            "order_type": "MARKET",
            "product": "I",
            "price": None,
        },
    )


# Feb 16 2026 = Monday, Feb 18 = Wednesday, Feb 21 = Saturday


class TestTimeTrigger:
    def test_fires_at_exact_time(self):
        rule = _make_time_rule("09:15", on_days=["mon"])
        now = datetime(2026, 2, 16, 9, 15, 0)  # Monday 09:15:00
        assert evaluate_time_trigger(rule, now) is True

    def test_fires_within_30s_tolerance(self):
        rule = _make_time_rule("09:15", on_days=["mon"])
        now = datetime(2026, 2, 16, 9, 15, 30)  # Monday 09:15:30
        assert evaluate_time_trigger(rule, now, tolerance_seconds=60) is True

    def test_does_not_fire_2_minutes_after(self):
        rule = _make_time_rule("09:15", on_days=["mon"])
        now = datetime(2026, 2, 16, 9, 17, 0)  # Monday 09:17:00 (120s after)
        assert evaluate_time_trigger(rule, now, tolerance_seconds=60) is False

    def test_does_not_fire_on_wrong_day(self):
        rule = _make_time_rule("09:15", on_days=["wed"])
        now = datetime(2026, 2, 16, 9, 15, 0)  # Monday, rule expects Wednesday
        assert evaluate_time_trigger(rule, now) is False

    def test_fires_on_correct_day(self):
        rule = _make_time_rule("10:00", on_days=["wed"])
        now = datetime(2026, 2, 18, 10, 0, 0)  # Wednesday 10:00
        assert evaluate_time_trigger(rule, now) is True

    def test_does_not_fire_on_weekend_if_market_only(self):
        rule = _make_time_rule("09:15", on_days=["sat"], market_only=True)
        now = datetime(2026, 2, 21, 9, 15, 0)  # Saturday
        assert evaluate_time_trigger(rule, now) is False

    def test_fires_on_weekend_if_not_market_only(self):
        rule = _make_time_rule("09:15", on_days=["sat"], market_only=False)
        now = datetime(2026, 2, 21, 9, 15, 0)  # Saturday
        assert evaluate_time_trigger(rule, now) is True
