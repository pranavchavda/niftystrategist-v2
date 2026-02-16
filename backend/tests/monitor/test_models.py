"""Tests for monitor rule Pydantic models -- validation and serialization."""
import pytest
from datetime import datetime


def test_price_trigger_valid():
    from monitor.models import PriceTrigger
    t = PriceTrigger(condition="lte", price=2400.0, reference="ltp")
    assert t.condition == "lte"
    assert t.price == 2400.0


def test_price_trigger_invalid_condition():
    from monitor.models import PriceTrigger
    with pytest.raises(ValueError):
        PriceTrigger(condition="invalid", price=2400.0, reference="ltp")


def test_time_trigger_valid():
    from monitor.models import TimeTrigger
    t = TimeTrigger(at="15:15", on_days=["mon", "tue", "wed", "thu", "fri"], market_only=True)
    assert t.at == "15:15"


def test_time_trigger_invalid_time_format():
    from monitor.models import TimeTrigger
    with pytest.raises(ValueError):
        TimeTrigger(at="25:99", on_days=["mon"], market_only=True)


def test_indicator_trigger_valid():
    from monitor.models import IndicatorTrigger
    t = IndicatorTrigger(indicator="rsi", timeframe="5m", condition="lte", value=30, params={"period": 14})
    assert t.indicator == "rsi"


def test_order_status_trigger_valid():
    from monitor.models import OrderStatusTrigger
    t = OrderStatusTrigger(order_id="ORD123", status="complete")
    assert t.status == "complete"


def test_compound_trigger_and():
    from monitor.models import CompoundTrigger
    ct = CompoundTrigger(
        operator="and",
        conditions=[
            {"type": "price", "condition": "lte", "price": 2400, "reference": "ltp"},
            {"type": "time", "condition": "after", "at": "14:00"},
        ],
    )
    assert ct.operator == "and"
    assert len(ct.conditions) == 2


def test_place_order_action_valid():
    from monitor.models import PlaceOrderAction
    a = PlaceOrderAction(
        symbol="RELIANCE", transaction_type="SELL", quantity=10,
        order_type="MARKET", product="I", price=None,
    )
    assert a.transaction_type == "SELL"


def test_cancel_rule_action_valid():
    from monitor.models import CancelRuleAction
    a = CancelRuleAction(rule_id=42)
    assert a.rule_id == 42


def test_monitor_rule_full():
    from monitor.models import MonitorRule
    rule = MonitorRule(
        id=1,
        user_id=999,
        name="RELIANCE stop-loss",
        enabled=True,
        trigger_type="price",
        trigger_config={"condition": "lte", "price": 2400.0, "reference": "ltp"},
        action_type="place_order",
        action_config={
            "symbol": "RELIANCE", "transaction_type": "SELL",
            "quantity": 10, "order_type": "MARKET", "product": "I", "price": None,
        },
        instrument_token="NSE_EQ|INE002A01018",
        symbol="RELIANCE",
        max_fires=1,
        fire_count=0,
    )
    assert rule.name == "RELIANCE stop-loss"
    assert rule.should_evaluate  # enabled, not expired, fires remaining


def test_monitor_rule_expired_should_not_evaluate():
    from monitor.models import MonitorRule
    rule = MonitorRule(
        id=1, user_id=999, name="expired", enabled=True,
        trigger_type="price",
        trigger_config={"condition": "lte", "price": 100, "reference": "ltp"},
        action_type="place_order",
        action_config={"symbol": "X", "transaction_type": "SELL", "quantity": 1, "order_type": "MARKET", "product": "D", "price": None},
        expires_at=datetime(2020, 1, 1),
        fire_count=0,
    )
    assert not rule.should_evaluate


def test_monitor_rule_max_fires_reached():
    from monitor.models import MonitorRule
    rule = MonitorRule(
        id=1, user_id=999, name="maxed", enabled=True,
        trigger_type="price",
        trigger_config={"condition": "lte", "price": 100, "reference": "ltp"},
        action_type="place_order",
        action_config={"symbol": "X", "transaction_type": "SELL", "quantity": 1, "order_type": "MARKET", "product": "D", "price": None},
        max_fires=1, fire_count=1,
    )
    assert not rule.should_evaluate
