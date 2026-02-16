# Trade Monitor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build an IFTTT-style trade monitoring daemon that evaluates user-defined rules against real-time market data and executes actions (place/cancel orders). Also fix intraday order placement.

**Architecture:** Standalone Python daemon (`nf-monitor`) using Upstox WebSocket streams. Rules stored in PostgreSQL (`MonitorRule` table), created via CLI tool or future Rule Builder UI. Pure data model + rule evaluation logic first (TDD), then WebSocket/daemon infrastructure.

**Tech Stack:** Python 3.14, asyncio, websockets, protobuf (Upstox Market Data V3), SQLAlchemy (existing), pandas-ta (existing), pytest

**Design doc:** `docs/plans/2026-02-16-trade-monitor-design.md`

---

## Task 1: Fix Intraday Orders — Add `--product` flag

**Files:**
- Modify: `backend/services/upstox_client.py:577-638` (place_order method)
- Modify: `backend/cli-tools/nf-order:20-79` (place_order function + argparse)
- Test: `backend/tests/monitor/test_order_product.py`

**Step 1: Write failing test for upstox_client product parameter**

```python
# backend/tests/monitor/test_order_product.py
"""Tests for intraday/delivery product type support."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_place_order_passes_product_to_api():
    """place_order should pass the product parameter to PlaceOrderV3Request."""
    from services.upstox_client import UpstoxClient

    client = UpstoxClient(access_token="test-token", user_id="test-user")
    client._get_instrument_key = MagicMock(return_value="NSE_EQ|INE002A01018")
    client._is_market_open = MagicMock(return_value=True)

    with patch("services.upstox_client.upstox_client") as mock_sdk:
        mock_api = MagicMock()
        mock_response = MagicMock()
        mock_response.data.order_ids = ["ORD123"]
        mock_api.place_order.return_value = mock_response
        mock_sdk.OrderApiV3.return_value = mock_api
        mock_sdk.ApiClient.return_value = MagicMock()

        await client.place_order(
            symbol="RELIANCE",
            transaction_type="BUY",
            quantity=10,
            price=0,
            order_type="MARKET",
            product="I",  # Intraday
        )

        call_args = mock_sdk.PlaceOrderV3Request.call_args
        assert call_args.kwargs["product"] == "I"


@pytest.mark.asyncio
async def test_place_order_defaults_to_delivery():
    """place_order should default to product='D' if not specified."""
    from services.upstox_client import UpstoxClient

    client = UpstoxClient(access_token="test-token", user_id="test-user")
    client._get_instrument_key = MagicMock(return_value="NSE_EQ|INE002A01018")
    client._is_market_open = MagicMock(return_value=True)

    with patch("services.upstox_client.upstox_client") as mock_sdk:
        mock_api = MagicMock()
        mock_response = MagicMock()
        mock_response.data.order_ids = ["ORD123"]
        mock_api.place_order.return_value = mock_response
        mock_sdk.OrderApiV3.return_value = mock_api
        mock_sdk.ApiClient.return_value = MagicMock()

        await client.place_order(
            symbol="RELIANCE",
            transaction_type="BUY",
            quantity=10,
            price=0,
            order_type="MARKET",
            # product not specified — should default to "D"
        )

        call_args = mock_sdk.PlaceOrderV3Request.call_args
        assert call_args.kwargs["product"] == "D"
```

**Step 2: Run test, confirm it fails**

Run: `cd /home/pranav/niftystrategist-v2/backend && source venv/bin/activate && python -m pytest tests/monitor/test_order_product.py -v`
Expected: FAIL — `place_order()` doesn't accept `product` parameter

**Step 3: Implement — update `upstox_client.py` and `nf-order`**

In `backend/services/upstox_client.py:577`, add `product` parameter:
```python
async def place_order(
    self,
    symbol: str,
    transaction_type: Literal["BUY", "SELL"],
    quantity: int,
    price: float,
    order_type: Literal["MARKET", "LIMIT"] = "LIMIT",
    is_amo: bool | None = None,
    product: Literal["D", "I"] = "D",  # D=Delivery/CNC, I=Intraday/MIS
) -> TradeResult:
```

In the `PlaceOrderV3Request` call (~line 615), change `product="D"` to `product=product`.

In `backend/cli-tools/nf-order`, add `--product` argument to buy/sell subparsers:
```python
p.add_argument("--product", default="D", choices=["D", "I"],
               help="Product type: D=Delivery/CNC, I=Intraday/MIS (default: D)")
```

Pass it through in `place_order()` call (~line 72):
```python
order_result = run_async(client.place_order(
    symbol=sym,
    transaction_type=act,
    quantity=quantity,
    order_type=order_type,
    price=price if price else 0,
    is_amo=True if amo else None,
    product=product,
))
```

And in the `main()` function (~line 223), add `product=args.product` to the `place_order()` call.

Also add `product` to dry_run output dict and display.

**Step 4: Run test, confirm it passes**

Run: `cd /home/pranav/niftystrategist-v2/backend && python -m pytest tests/monitor/test_order_product.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/services/upstox_client.py backend/cli-tools/nf-order backend/tests/monitor/test_order_product.py
git commit -m "feat: add --product flag for intraday (MIS) vs delivery (CNC) orders"
```

---

## Task 2: Rule Data Models — Pydantic models for triggers, actions, rules

**Files:**
- Create: `backend/monitor/__init__.py`
- Create: `backend/monitor/models.py`
- Test: `backend/tests/monitor/test_models.py`

These are pure Pydantic models (not SQLAlchemy) used by the rule evaluator. The DB model comes in Task 3.

**Step 1: Write failing tests for rule models**

```python
# backend/tests/monitor/test_models.py
"""Tests for monitor rule Pydantic models — validation and serialization."""
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
    from monitor.models import CompoundTrigger, PriceTrigger, TimeTrigger
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
        expires_at=datetime(2020, 1, 1),  # In the past
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
```

**Step 2: Run tests, confirm they fail**

Run: `cd /home/pranav/niftystrategist-v2/backend && python -m pytest tests/monitor/test_models.py -v`
Expected: FAIL — `monitor.models` doesn't exist

**Step 3: Implement the Pydantic models**

```python
# backend/monitor/__init__.py
# (empty)

# backend/monitor/models.py
"""Pydantic models for the trade monitor rule engine."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, field_validator


class PriceTrigger(BaseModel):
    condition: Literal["lte", "gte", "crosses_above", "crosses_below"]
    price: float
    reference: Literal["ltp", "bid", "ask", "open", "high", "low"] = "ltp"


class TimeTrigger(BaseModel):
    at: str  # "HH:MM" in IST
    on_days: list[Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"]] = [
        "mon", "tue", "wed", "thu", "fri"
    ]
    market_only: bool = True

    @field_validator("at")
    @classmethod
    def validate_time_format(cls, v: str) -> str:
        parts = v.split(":")
        if len(parts) != 2:
            raise ValueError(f"Time must be HH:MM, got: {v}")
        h, m = int(parts[0]), int(parts[1])
        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise ValueError(f"Invalid time: {v}")
        return v


class IndicatorTrigger(BaseModel):
    indicator: Literal["rsi", "macd", "ema_crossover", "volume_spike"]
    timeframe: Literal["1m", "5m", "15m", "30m", "1h", "1d"] = "5m"
    condition: Literal["lte", "gte", "crosses_above", "crosses_below"]
    value: float
    params: dict[str, Any] = {}


class OrderStatusTrigger(BaseModel):
    order_id: str
    status: Literal["complete", "rejected", "cancelled", "partially_filled"]


class CompoundTrigger(BaseModel):
    operator: Literal["and", "or"]
    conditions: list[dict[str, Any]]  # Each has a "type" key + trigger-specific fields


class PlaceOrderAction(BaseModel):
    symbol: str
    transaction_type: Literal["BUY", "SELL"]
    quantity: int
    order_type: Literal["MARKET", "LIMIT"] = "MARKET"
    product: Literal["D", "I"] = "I"
    price: float | None = None


class CancelOrderAction(BaseModel):
    order_id: str


class CancelRuleAction(BaseModel):
    rule_id: int


class MonitorRule(BaseModel):
    """In-memory representation of a monitor rule, loaded from DB."""
    id: int
    user_id: int
    name: str
    enabled: bool = True

    trigger_type: Literal["price", "time", "indicator", "order_status", "compound"]
    trigger_config: dict[str, Any]

    action_type: Literal["place_order", "cancel_order", "modify_order", "cancel_rule"]
    action_config: dict[str, Any]

    instrument_token: str | None = None
    symbol: str | None = None
    linked_trade_id: int | None = None
    linked_order_id: str | None = None

    fire_count: int = 0
    max_fires: int | None = None  # None = unlimited
    expires_at: datetime | None = None
    fired_at: datetime | None = None

    @property
    def should_evaluate(self) -> bool:
        """Whether this rule should be evaluated right now."""
        if not self.enabled:
            return False
        if self.expires_at and datetime.utcnow() > self.expires_at:
            return False
        if self.max_fires is not None and self.fire_count >= self.max_fires:
            return False
        return True
```

**Step 4: Run tests, confirm they pass**

Run: `cd /home/pranav/niftystrategist-v2/backend && python -m pytest tests/monitor/test_models.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/monitor/__init__.py backend/monitor/models.py backend/tests/monitor/test_models.py
git commit -m "feat: add Pydantic models for monitor rules, triggers, and actions"
```

---

## Task 3: DB Models — SQLAlchemy MonitorRule + MonitorLog

**Files:**
- Modify: `backend/database/models.py` (add MonitorRule, MonitorLog models)
- Test: `backend/tests/monitor/test_db_models.py`

**Step 1: Write test that MonitorRule SQLAlchemy model has expected columns**

```python
# backend/tests/monitor/test_db_models.py
"""Tests for MonitorRule and MonitorLog SQLAlchemy models."""


def test_monitor_rule_table_exists():
    from database.models import MonitorRule
    assert MonitorRule.__tablename__ == "monitor_rules"


def test_monitor_rule_has_required_columns():
    from database.models import MonitorRule
    columns = {c.name for c in MonitorRule.__table__.columns}
    expected = {
        "id", "user_id", "name", "enabled",
        "trigger_type", "trigger_config",
        "action_type", "action_config",
        "instrument_token", "symbol",
        "linked_trade_id", "linked_order_id",
        "fire_count", "max_fires",
        "expires_at", "created_at", "updated_at", "fired_at",
    }
    assert expected.issubset(columns)


def test_monitor_log_table_exists():
    from database.models import MonitorLog
    assert MonitorLog.__tablename__ == "monitor_logs"


def test_monitor_log_has_required_columns():
    from database.models import MonitorLog
    columns = {c.name for c in MonitorLog.__table__.columns}
    expected = {"id", "user_id", "rule_id", "trigger_snapshot", "action_taken", "action_result", "created_at"}
    assert expected.issubset(columns)
```

**Step 2: Run tests, confirm fail**

Run: `cd /home/pranav/niftystrategist-v2/backend && python -m pytest tests/monitor/test_db_models.py -v`
Expected: FAIL — MonitorRule not defined in models.py

**Step 3: Add SQLAlchemy models to `database/models.py`**

Add at end of file (after WatchlistItem), before any final comments:
```python
class MonitorRule(Base):
    """IFTTT-style trade monitoring rules evaluated by nf-monitor daemon."""
    __tablename__ = "monitor_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)

    trigger_type = Column(String(20), nullable=False)  # price, time, indicator, order_status, compound
    trigger_config = Column(JSON, nullable=False)

    action_type = Column(String(20), nullable=False)  # place_order, cancel_order, modify_order, cancel_rule
    action_config = Column(JSON, nullable=False)

    instrument_token = Column(String(50), nullable=True)
    symbol = Column(String(50), nullable=True, index=True)
    linked_trade_id = Column(Integer, ForeignKey("trades.id", ondelete="SET NULL"), nullable=True)
    linked_order_id = Column(String(100), nullable=True)

    fire_count = Column(Integer, default=0, nullable=False)
    max_fires = Column(Integer, nullable=True)  # NULL = unlimited
    expires_at = Column(DateTime, nullable=True)
    fired_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    user = relationship("User")

    __table_args__ = (
        Index('idx_monitor_rules_user_enabled', 'user_id', 'enabled'),
        Index('idx_monitor_rules_instrument', 'instrument_token'),
    )


class MonitorLog(Base):
    """Audit log for monitor rule firings."""
    __tablename__ = "monitor_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    rule_id = Column(Integer, ForeignKey("monitor_rules.id", ondelete="SET NULL"), nullable=True)

    trigger_snapshot = Column(JSON, nullable=True)
    action_taken = Column(String(50), nullable=False)
    action_result = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=utc_now, nullable=False)

    rule = relationship("MonitorRule")

    __table_args__ = (
        Index('idx_monitor_logs_user', 'user_id', 'created_at'),
        Index('idx_monitor_logs_rule', 'rule_id', 'created_at'),
    )
```

**Step 4: Run tests, confirm pass**

Run: `cd /home/pranav/niftystrategist-v2/backend && python -m pytest tests/monitor/test_db_models.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/database/models.py backend/tests/monitor/test_db_models.py
git commit -m "feat: add MonitorRule and MonitorLog SQLAlchemy models"
```

---

## Task 4: Rule Evaluator — Price Triggers

**Files:**
- Create: `backend/monitor/rule_evaluator.py`
- Test: `backend/tests/monitor/test_rule_evaluator_price.py`

This is the core logic. Pure functions, no I/O. Takes a rule + current market data → returns whether it fires.

**Step 1: Write failing tests for price trigger evaluation**

```python
# backend/tests/monitor/test_rule_evaluator_price.py
"""Tests for price trigger evaluation logic."""
import pytest
from monitor.models import MonitorRule


def _make_price_rule(condition: str, price: float, reference: str = "ltp") -> MonitorRule:
    return MonitorRule(
        id=1, user_id=999, name="test",
        trigger_type="price",
        trigger_config={"condition": condition, "price": price, "reference": reference},
        action_type="place_order",
        action_config={"symbol": "X", "transaction_type": "SELL", "quantity": 1, "order_type": "MARKET", "product": "I", "price": None},
        instrument_token="NSE_EQ|TEST",
    )


class TestPriceTriggerLTE:
    def test_fires_when_price_at_threshold(self):
        from monitor.rule_evaluator import evaluate_price_trigger
        rule = _make_price_rule("lte", 2400.0)
        assert evaluate_price_trigger(rule, {"ltp": 2400.0}) is True

    def test_fires_when_price_below_threshold(self):
        from monitor.rule_evaluator import evaluate_price_trigger
        rule = _make_price_rule("lte", 2400.0)
        assert evaluate_price_trigger(rule, {"ltp": 2350.0}) is True

    def test_does_not_fire_when_price_above_threshold(self):
        from monitor.rule_evaluator import evaluate_price_trigger
        rule = _make_price_rule("lte", 2400.0)
        assert evaluate_price_trigger(rule, {"ltp": 2500.0}) is False


class TestPriceTriggerGTE:
    def test_fires_when_price_at_threshold(self):
        from monitor.rule_evaluator import evaluate_price_trigger
        rule = _make_price_rule("gte", 2700.0)
        assert evaluate_price_trigger(rule, {"ltp": 2700.0}) is True

    def test_fires_when_price_above_threshold(self):
        from monitor.rule_evaluator import evaluate_price_trigger
        rule = _make_price_rule("gte", 2700.0)
        assert evaluate_price_trigger(rule, {"ltp": 2800.0}) is True

    def test_does_not_fire_when_price_below_threshold(self):
        from monitor.rule_evaluator import evaluate_price_trigger
        rule = _make_price_rule("gte", 2700.0)
        assert evaluate_price_trigger(rule, {"ltp": 2600.0}) is False


class TestPriceTriggerCrossesAbove:
    def test_fires_on_cross(self):
        from monitor.rule_evaluator import evaluate_price_trigger
        rule = _make_price_rule("crosses_above", 2700.0)
        # previous price was below, now above
        assert evaluate_price_trigger(rule, {"ltp": 2710.0}, prev_price=2690.0) is True

    def test_does_not_fire_if_already_above(self):
        from monitor.rule_evaluator import evaluate_price_trigger
        rule = _make_price_rule("crosses_above", 2700.0)
        assert evaluate_price_trigger(rule, {"ltp": 2710.0}, prev_price=2705.0) is False

    def test_does_not_fire_if_still_below(self):
        from monitor.rule_evaluator import evaluate_price_trigger
        rule = _make_price_rule("crosses_above", 2700.0)
        assert evaluate_price_trigger(rule, {"ltp": 2690.0}, prev_price=2680.0) is False


class TestPriceTriggerCrossesBelow:
    def test_fires_on_cross(self):
        from monitor.rule_evaluator import evaluate_price_trigger
        rule = _make_price_rule("crosses_below", 2400.0)
        assert evaluate_price_trigger(rule, {"ltp": 2390.0}, prev_price=2410.0) is True

    def test_does_not_fire_if_already_below(self):
        from monitor.rule_evaluator import evaluate_price_trigger
        rule = _make_price_rule("crosses_below", 2400.0)
        assert evaluate_price_trigger(rule, {"ltp": 2390.0}, prev_price=2395.0) is False


class TestPriceTriggerReference:
    def test_uses_bid_reference(self):
        from monitor.rule_evaluator import evaluate_price_trigger
        rule = _make_price_rule("lte", 2400.0, reference="bid")
        assert evaluate_price_trigger(rule, {"ltp": 2500.0, "bid": 2350.0}) is True

    def test_returns_false_if_reference_missing(self):
        from monitor.rule_evaluator import evaluate_price_trigger
        rule = _make_price_rule("lte", 2400.0, reference="bid")
        assert evaluate_price_trigger(rule, {"ltp": 2350.0}) is False
```

**Step 2: Run tests, confirm fail**

Run: `cd /home/pranav/niftystrategist-v2/backend && python -m pytest tests/monitor/test_rule_evaluator_price.py -v`
Expected: FAIL — `monitor.rule_evaluator` doesn't exist

**Step 3: Implement `evaluate_price_trigger`**

```python
# backend/monitor/rule_evaluator.py
"""Rule evaluation logic for the trade monitor.

Pure functions — no I/O, no DB, no network. Takes a rule + market state,
returns whether the rule fires.
"""
from __future__ import annotations

from monitor.models import MonitorRule, PriceTrigger


def evaluate_price_trigger(
    rule: MonitorRule,
    market_data: dict,
    prev_price: float | None = None,
) -> bool:
    """Evaluate a price trigger against current market data.

    Args:
        rule: The monitor rule with trigger_type="price".
        market_data: Dict with keys like "ltp", "bid", "ask", etc.
        prev_price: Previous price for the same reference field (needed for crosses_above/below).

    Returns:
        True if the trigger condition is met.
    """
    cfg = PriceTrigger(**rule.trigger_config)
    current = market_data.get(cfg.reference)
    if current is None:
        return False

    if cfg.condition == "lte":
        return current <= cfg.price
    elif cfg.condition == "gte":
        return current >= cfg.price
    elif cfg.condition == "crosses_above":
        if prev_price is None:
            return False
        return prev_price < cfg.price and current >= cfg.price
    elif cfg.condition == "crosses_below":
        if prev_price is None:
            return False
        return prev_price > cfg.price and current <= cfg.price
    return False
```

**Step 4: Run tests, confirm pass**

Run: `cd /home/pranav/niftystrategist-v2/backend && python -m pytest tests/monitor/test_rule_evaluator_price.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/monitor/rule_evaluator.py backend/tests/monitor/test_rule_evaluator_price.py
git commit -m "feat: implement price trigger evaluation with crosses_above/below support"
```

---

## Task 5: Rule Evaluator — Time Triggers

**Files:**
- Modify: `backend/monitor/rule_evaluator.py`
- Test: `backend/tests/monitor/test_rule_evaluator_time.py`

**Step 1: Write failing tests for time trigger evaluation**

```python
# backend/tests/monitor/test_rule_evaluator_time.py
"""Tests for time trigger evaluation logic."""
import pytest
from datetime import datetime
from monitor.models import MonitorRule


def _make_time_rule(at: str, on_days=None, market_only=True) -> MonitorRule:
    return MonitorRule(
        id=1, user_id=999, name="test",
        trigger_type="time",
        trigger_config={
            "at": at,
            "on_days": on_days or ["mon", "tue", "wed", "thu", "fri"],
            "market_only": market_only,
        },
        action_type="place_order",
        action_config={"symbol": "X", "transaction_type": "SELL", "quantity": 1, "order_type": "MARKET", "product": "I", "price": None},
    )


class TestTimeTrigger:
    def test_fires_at_exact_time(self):
        from monitor.rule_evaluator import evaluate_time_trigger
        rule = _make_time_rule("15:15")
        # Monday 15:15 IST
        now = datetime(2026, 2, 16, 15, 15, 0)  # Monday
        assert evaluate_time_trigger(rule, now) is True

    def test_fires_within_tolerance(self):
        from monitor.rule_evaluator import evaluate_time_trigger
        rule = _make_time_rule("15:15")
        # 30 seconds after target — should still fire within 60s tolerance
        now = datetime(2026, 2, 16, 15, 15, 30)
        assert evaluate_time_trigger(rule, now) is True

    def test_does_not_fire_outside_tolerance(self):
        from monitor.rule_evaluator import evaluate_time_trigger
        rule = _make_time_rule("15:15")
        now = datetime(2026, 2, 16, 15, 17, 0)  # 2 minutes late
        assert evaluate_time_trigger(rule, now) is False

    def test_does_not_fire_on_wrong_day(self):
        from monitor.rule_evaluator import evaluate_time_trigger
        rule = _make_time_rule("15:15", on_days=["mon", "tue"])
        now = datetime(2026, 2, 18, 15, 15, 0)  # Wednesday
        assert evaluate_time_trigger(rule, now) is False

    def test_fires_on_correct_day(self):
        from monitor.rule_evaluator import evaluate_time_trigger
        rule = _make_time_rule("15:15", on_days=["wed"])
        now = datetime(2026, 2, 18, 15, 15, 0)  # Wednesday
        assert evaluate_time_trigger(rule, now) is True

    def test_does_not_fire_on_weekend_if_market_only(self):
        from monitor.rule_evaluator import evaluate_time_trigger
        rule = _make_time_rule("10:00", on_days=["sat"], market_only=True)
        now = datetime(2026, 2, 21, 10, 0, 0)  # Saturday
        assert evaluate_time_trigger(rule, now) is False

    def test_fires_on_weekend_if_not_market_only(self):
        from monitor.rule_evaluator import evaluate_time_trigger
        rule = _make_time_rule("10:00", on_days=["sat"], market_only=False)
        now = datetime(2026, 2, 21, 10, 0, 0)  # Saturday
        assert evaluate_time_trigger(rule, now) is True
```

**Step 2: Run, confirm fail**

Run: `cd /home/pranav/niftystrategist-v2/backend && python -m pytest tests/monitor/test_rule_evaluator_time.py -v`

**Step 3: Implement `evaluate_time_trigger`**

Add to `backend/monitor/rule_evaluator.py`:
```python
from monitor.models import TimeTrigger

_DAY_MAP = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}

def evaluate_time_trigger(
    rule: MonitorRule,
    now: datetime,
    tolerance_seconds: int = 60,
) -> bool:
    """Evaluate a time trigger.

    Args:
        rule: Rule with trigger_type="time".
        now: Current datetime in IST (naive).
        tolerance_seconds: How many seconds after the target time to still fire.
    """
    cfg = TimeTrigger(**rule.trigger_config)

    # Check day of week
    current_day_idx = now.weekday()
    allowed_days = {_DAY_MAP[d] for d in cfg.on_days}
    if current_day_idx not in allowed_days:
        return False

    # Market-only check (weekdays 9:15-15:30)
    if cfg.market_only and current_day_idx >= 5:
        return False

    # Check time within tolerance
    h, m = map(int, cfg.at.split(":"))
    target = now.replace(hour=h, minute=m, second=0, microsecond=0)
    diff = (now - target).total_seconds()
    return 0 <= diff < tolerance_seconds
```

**Step 4: Run, confirm pass**

Run: `cd /home/pranav/niftystrategist-v2/backend && python -m pytest tests/monitor/test_rule_evaluator_time.py -v`

**Step 5: Commit**

```bash
git add backend/monitor/rule_evaluator.py backend/tests/monitor/test_rule_evaluator_time.py
git commit -m "feat: implement time trigger evaluation with day-of-week and market-only support"
```

---

## Task 6: Rule Evaluator — Order Status Triggers

**Files:**
- Modify: `backend/monitor/rule_evaluator.py`
- Test: `backend/tests/monitor/test_rule_evaluator_order.py`

**Step 1: Write failing tests**

```python
# backend/tests/monitor/test_rule_evaluator_order.py
"""Tests for order status trigger evaluation."""
from monitor.models import MonitorRule


def _make_order_rule(order_id: str, status: str) -> MonitorRule:
    return MonitorRule(
        id=1, user_id=999, name="test",
        trigger_type="order_status",
        trigger_config={"order_id": order_id, "status": status},
        action_type="cancel_rule",
        action_config={"rule_id": 2},
    )


class TestOrderStatusTrigger:
    def test_fires_on_matching_status(self):
        from monitor.rule_evaluator import evaluate_order_status_trigger
        rule = _make_order_rule("ORD123", "complete")
        event = {"order_id": "ORD123", "status": "complete"}
        assert evaluate_order_status_trigger(rule, event) is True

    def test_does_not_fire_on_wrong_status(self):
        from monitor.rule_evaluator import evaluate_order_status_trigger
        rule = _make_order_rule("ORD123", "complete")
        event = {"order_id": "ORD123", "status": "pending"}
        assert evaluate_order_status_trigger(rule, event) is False

    def test_does_not_fire_on_wrong_order(self):
        from monitor.rule_evaluator import evaluate_order_status_trigger
        rule = _make_order_rule("ORD123", "complete")
        event = {"order_id": "ORD456", "status": "complete"}
        assert evaluate_order_status_trigger(rule, event) is False

    def test_does_not_fire_on_empty_event(self):
        from monitor.rule_evaluator import evaluate_order_status_trigger
        rule = _make_order_rule("ORD123", "complete")
        assert evaluate_order_status_trigger(rule, {}) is False
```

**Step 2: Run, confirm fail**

Run: `cd /home/pranav/niftystrategist-v2/backend && python -m pytest tests/monitor/test_rule_evaluator_order.py -v`

**Step 3: Implement**

Add to `backend/monitor/rule_evaluator.py`:
```python
from monitor.models import OrderStatusTrigger

def evaluate_order_status_trigger(rule: MonitorRule, order_event: dict) -> bool:
    """Evaluate an order status trigger against an order update event."""
    cfg = OrderStatusTrigger(**rule.trigger_config)
    return (
        order_event.get("order_id") == cfg.order_id
        and order_event.get("status") == cfg.status
    )
```

**Step 4: Run, confirm pass**

**Step 5: Commit**

```bash
git add backend/monitor/rule_evaluator.py backend/tests/monitor/test_rule_evaluator_order.py
git commit -m "feat: implement order status trigger evaluation"
```

---

## Task 7: Rule Evaluator — Compound Triggers

**Files:**
- Modify: `backend/monitor/rule_evaluator.py`
- Test: `backend/tests/monitor/test_rule_evaluator_compound.py`

**Step 1: Write failing tests**

```python
# backend/tests/monitor/test_rule_evaluator_compound.py
"""Tests for compound (AND/OR) trigger evaluation."""
from datetime import datetime
from monitor.models import MonitorRule


def _make_compound_rule(operator: str, conditions: list) -> MonitorRule:
    return MonitorRule(
        id=1, user_id=999, name="test",
        trigger_type="compound",
        trigger_config={"operator": operator, "conditions": conditions},
        action_type="place_order",
        action_config={"symbol": "X", "transaction_type": "SELL", "quantity": 1, "order_type": "MARKET", "product": "I", "price": None},
        instrument_token="NSE_EQ|TEST",
    )


class TestCompoundTriggerAnd:
    def test_fires_when_all_conditions_met(self):
        from monitor.rule_evaluator import evaluate_compound_trigger
        rule = _make_compound_rule("and", [
            {"type": "price", "condition": "lte", "price": 2400, "reference": "ltp"},
            {"type": "price", "condition": "gte", "price": 2300, "reference": "ltp"},
        ])
        ctx = {"market_data": {"ltp": 2350.0}, "now": datetime(2026, 2, 16, 10, 0)}
        assert evaluate_compound_trigger(rule, ctx) is True

    def test_does_not_fire_when_one_fails(self):
        from monitor.rule_evaluator import evaluate_compound_trigger
        rule = _make_compound_rule("and", [
            {"type": "price", "condition": "lte", "price": 2400, "reference": "ltp"},
            {"type": "price", "condition": "gte", "price": 2500, "reference": "ltp"},
        ])
        ctx = {"market_data": {"ltp": 2350.0}, "now": datetime(2026, 2, 16, 10, 0)}
        assert evaluate_compound_trigger(rule, ctx) is False


class TestCompoundTriggerOr:
    def test_fires_when_one_condition_met(self):
        from monitor.rule_evaluator import evaluate_compound_trigger
        rule = _make_compound_rule("or", [
            {"type": "price", "condition": "lte", "price": 2000, "reference": "ltp"},
            {"type": "price", "condition": "gte", "price": 2300, "reference": "ltp"},
        ])
        ctx = {"market_data": {"ltp": 2350.0}, "now": datetime(2026, 2, 16, 10, 0)}
        assert evaluate_compound_trigger(rule, ctx) is True

    def test_does_not_fire_when_none_met(self):
        from monitor.rule_evaluator import evaluate_compound_trigger
        rule = _make_compound_rule("or", [
            {"type": "price", "condition": "lte", "price": 2000, "reference": "ltp"},
            {"type": "price", "condition": "gte", "price": 3000, "reference": "ltp"},
        ])
        ctx = {"market_data": {"ltp": 2350.0}, "now": datetime(2026, 2, 16, 10, 0)}
        assert evaluate_compound_trigger(rule, ctx) is False


class TestCompoundWithMixedTypes:
    def test_price_and_time(self):
        from monitor.rule_evaluator import evaluate_compound_trigger
        rule = _make_compound_rule("and", [
            {"type": "price", "condition": "lte", "price": 2400, "reference": "ltp"},
            {"type": "time", "at": "14:00", "on_days": ["mon"], "market_only": False},
        ])
        ctx = {"market_data": {"ltp": 2350.0}, "now": datetime(2026, 2, 16, 14, 0, 0)}  # Monday
        assert evaluate_compound_trigger(rule, ctx) is True
```

**Step 2: Run, confirm fail**

Run: `cd /home/pranav/niftystrategist-v2/backend && python -m pytest tests/monitor/test_rule_evaluator_compound.py -v`

**Step 3: Implement**

Add to `backend/monitor/rule_evaluator.py`:
```python
def _evaluate_single_condition(condition: dict, ctx: dict) -> bool:
    """Evaluate a single condition from a compound trigger."""
    ctype = condition.get("type")
    if ctype == "price":
        dummy_rule = MonitorRule(
            id=0, user_id=0, name="", trigger_type="price",
            trigger_config={k: v for k, v in condition.items() if k != "type"},
            action_type="place_order", action_config={},
        )
        return evaluate_price_trigger(dummy_rule, ctx.get("market_data", {}))
    elif ctype == "time":
        dummy_rule = MonitorRule(
            id=0, user_id=0, name="", trigger_type="time",
            trigger_config={k: v for k, v in condition.items() if k != "type"},
            action_type="place_order", action_config={},
        )
        return evaluate_time_trigger(dummy_rule, ctx.get("now", datetime.utcnow()))
    elif ctype == "order_status":
        dummy_rule = MonitorRule(
            id=0, user_id=0, name="", trigger_type="order_status",
            trigger_config={k: v for k, v in condition.items() if k != "type"},
            action_type="place_order", action_config={},
        )
        return evaluate_order_status_trigger(dummy_rule, ctx.get("order_event", {}))
    return False


def evaluate_compound_trigger(rule: MonitorRule, ctx: dict) -> bool:
    """Evaluate a compound (AND/OR) trigger."""
    cfg = CompoundTrigger(**rule.trigger_config)
    results = [_evaluate_single_condition(c, ctx) for c in cfg.conditions]
    if cfg.operator == "and":
        return all(results)
    elif cfg.operator == "or":
        return any(results)
    return False
```

**Step 4: Run, confirm pass**

**Step 5: Commit**

```bash
git add backend/monitor/rule_evaluator.py backend/tests/monitor/test_rule_evaluator_compound.py
git commit -m "feat: implement compound (AND/OR) trigger evaluation"
```

---

## Task 8: Rule Evaluator — Top-Level `evaluate_rule` + OCO

**Files:**
- Modify: `backend/monitor/rule_evaluator.py`
- Test: `backend/tests/monitor/test_rule_evaluator_toplevel.py`

This is the main entry point: takes a rule + context → returns `RuleResult` (fired, actions to take including OCO cancellations).

**Step 1: Write failing tests**

```python
# backend/tests/monitor/test_rule_evaluator_toplevel.py
"""Tests for top-level evaluate_rule and OCO linking."""
from datetime import datetime
from monitor.models import MonitorRule


def _make_sl_rule(rule_id=1) -> MonitorRule:
    return MonitorRule(
        id=rule_id, user_id=999, name="SL",
        trigger_type="price",
        trigger_config={"condition": "lte", "price": 2400, "reference": "ltp"},
        action_type="place_order",
        action_config={"symbol": "RELIANCE", "transaction_type": "SELL", "quantity": 10, "order_type": "MARKET", "product": "I", "price": None},
        instrument_token="NSE_EQ|TEST",
        max_fires=1, fire_count=0,
    )


def _make_target_rule(rule_id=2) -> MonitorRule:
    return MonitorRule(
        id=rule_id, user_id=999, name="TARGET",
        trigger_type="price",
        trigger_config={"condition": "gte", "price": 2700, "reference": "ltp"},
        action_type="place_order",
        action_config={"symbol": "RELIANCE", "transaction_type": "SELL", "quantity": 10, "order_type": "MARKET", "product": "I", "price": None},
        instrument_token="NSE_EQ|TEST",
        max_fires=1, fire_count=0,
    )


class TestEvaluateRule:
    def test_returns_fired_true_when_triggered(self):
        from monitor.rule_evaluator import evaluate_rule, EvalContext
        rule = _make_sl_rule()
        ctx = EvalContext(market_data={"ltp": 2350.0})
        result = evaluate_rule(rule, ctx)
        assert result.fired is True

    def test_returns_fired_false_when_not_triggered(self):
        from monitor.rule_evaluator import evaluate_rule, EvalContext
        rule = _make_sl_rule()
        ctx = EvalContext(market_data={"ltp": 2500.0})
        result = evaluate_rule(rule, ctx)
        assert result.fired is False

    def test_skips_disabled_rule(self):
        from monitor.rule_evaluator import evaluate_rule, EvalContext
        rule = _make_sl_rule()
        rule.enabled = False
        ctx = EvalContext(market_data={"ltp": 2350.0})
        result = evaluate_rule(rule, ctx)
        assert result.fired is False
        assert result.skipped is True

    def test_skips_expired_rule(self):
        from monitor.rule_evaluator import evaluate_rule, EvalContext
        rule = _make_sl_rule()
        rule.expires_at = datetime(2020, 1, 1)
        ctx = EvalContext(market_data={"ltp": 2350.0})
        result = evaluate_rule(rule, ctx)
        assert result.fired is False
        assert result.skipped is True


class TestCancelRuleAction:
    def test_cancel_rule_returns_rule_ids_to_cancel(self):
        from monitor.rule_evaluator import evaluate_rule, EvalContext
        rule = MonitorRule(
            id=1, user_id=999, name="cancel-other",
            trigger_type="price",
            trigger_config={"condition": "lte", "price": 2400, "reference": "ltp"},
            action_type="cancel_rule",
            action_config={"rule_id": 42},
            instrument_token="NSE_EQ|TEST",
            max_fires=1, fire_count=0,
        )
        ctx = EvalContext(market_data={"ltp": 2350.0})
        result = evaluate_rule(rule, ctx)
        assert result.fired is True
        assert 42 in result.rules_to_cancel
```

**Step 2: Run, confirm fail**

**Step 3: Implement**

Add to `backend/monitor/rule_evaluator.py`:
```python
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class EvalContext:
    """Context passed to rule evaluation."""
    market_data: dict = field(default_factory=dict)
    prev_prices: dict = field(default_factory=dict)  # {instrument_token: prev_ltp}
    order_event: dict = field(default_factory=dict)
    now: datetime = field(default_factory=datetime.utcnow)


@dataclass
class RuleResult:
    """Result of evaluating a single rule."""
    rule_id: int
    fired: bool = False
    skipped: bool = False
    action_type: str | None = None
    action_config: dict = field(default_factory=dict)
    rules_to_cancel: list[int] = field(default_factory=list)


def evaluate_rule(rule: MonitorRule, ctx: EvalContext) -> RuleResult:
    """Top-level rule evaluation entry point."""
    result = RuleResult(rule_id=rule.id)

    if not rule.should_evaluate:
        result.skipped = True
        return result

    fired = False
    if rule.trigger_type == "price":
        prev = ctx.prev_prices.get(rule.instrument_token)
        fired = evaluate_price_trigger(rule, ctx.market_data, prev_price=prev)
    elif rule.trigger_type == "time":
        fired = evaluate_time_trigger(rule, ctx.now)
    elif rule.trigger_type == "order_status":
        fired = evaluate_order_status_trigger(rule, ctx.order_event)
    elif rule.trigger_type == "compound":
        fired = evaluate_compound_trigger(rule, {
            "market_data": ctx.market_data,
            "now": ctx.now,
            "order_event": ctx.order_event,
        })

    if fired:
        result.fired = True
        result.action_type = rule.action_type
        result.action_config = rule.action_config
        if rule.action_type == "cancel_rule":
            cancel_cfg = CancelRuleAction(**rule.action_config)
            result.rules_to_cancel.append(cancel_cfg.rule_id)

    return result
```

**Step 4: Run, confirm pass**

**Step 5: Commit**

```bash
git add backend/monitor/rule_evaluator.py backend/tests/monitor/test_rule_evaluator_toplevel.py
git commit -m "feat: implement top-level evaluate_rule with skip logic and cancel_rule action"
```

---

## Task 9: Candle Buffer — Tick Aggregation

**Files:**
- Create: `backend/monitor/candle_buffer.py`
- Test: `backend/tests/monitor/test_candle_buffer.py`

Aggregates incoming price ticks into OHLCV candles of configurable timeframes.

**Step 1: Write failing tests**

```python
# backend/tests/monitor/test_candle_buffer.py
"""Tests for tick-to-candle aggregation."""
from datetime import datetime


class TestCandleBuffer:
    def test_first_tick_creates_candle(self):
        from monitor.candle_buffer import CandleBuffer
        buf = CandleBuffer(timeframe_minutes=5)
        buf.add_tick(100.0, volume=1000, timestamp=datetime(2026, 2, 16, 10, 1, 0))
        candles = buf.get_candles()
        assert len(candles) == 1
        assert candles[0]["open"] == 100.0
        assert candles[0]["high"] == 100.0
        assert candles[0]["low"] == 100.0
        assert candles[0]["close"] == 100.0

    def test_ticks_in_same_window_update_candle(self):
        from monitor.candle_buffer import CandleBuffer
        buf = CandleBuffer(timeframe_minutes=5)
        buf.add_tick(100.0, volume=1000, timestamp=datetime(2026, 2, 16, 10, 1, 0))
        buf.add_tick(105.0, volume=500, timestamp=datetime(2026, 2, 16, 10, 2, 0))
        buf.add_tick(98.0, volume=800, timestamp=datetime(2026, 2, 16, 10, 3, 0))
        candles = buf.get_candles()
        assert len(candles) == 1
        assert candles[0]["open"] == 100.0
        assert candles[0]["high"] == 105.0
        assert candles[0]["low"] == 98.0
        assert candles[0]["close"] == 98.0
        assert candles[0]["volume"] == 2300

    def test_new_window_creates_new_candle(self):
        from monitor.candle_buffer import CandleBuffer
        buf = CandleBuffer(timeframe_minutes=5)
        buf.add_tick(100.0, volume=1000, timestamp=datetime(2026, 2, 16, 10, 1, 0))
        buf.add_tick(110.0, volume=500, timestamp=datetime(2026, 2, 16, 10, 6, 0))  # Next 5m window
        candles = buf.get_candles()
        assert len(candles) == 2

    def test_completed_candles(self):
        from monitor.candle_buffer import CandleBuffer
        buf = CandleBuffer(timeframe_minutes=5)
        buf.add_tick(100.0, volume=1000, timestamp=datetime(2026, 2, 16, 10, 1, 0))
        buf.add_tick(110.0, volume=500, timestamp=datetime(2026, 2, 16, 10, 6, 0))
        completed = buf.get_completed_candles()
        assert len(completed) == 1  # Only the first (closed) candle
        assert completed[0]["close"] == 100.0

    def test_seed_with_historical(self):
        from monitor.candle_buffer import CandleBuffer
        buf = CandleBuffer(timeframe_minutes=5)
        historical = [
            {"open": 95, "high": 100, "low": 94, "close": 98, "volume": 5000,
             "timestamp": datetime(2026, 2, 16, 9, 15, 0)},
            {"open": 98, "high": 102, "low": 97, "close": 101, "volume": 3000,
             "timestamp": datetime(2026, 2, 16, 9, 20, 0)},
        ]
        buf.seed(historical)
        assert len(buf.get_candles()) == 2

    def test_max_candles_limit(self):
        from monitor.candle_buffer import CandleBuffer
        buf = CandleBuffer(timeframe_minutes=1, max_candles=3)
        for i in range(5):
            buf.add_tick(100.0 + i, volume=100, timestamp=datetime(2026, 2, 16, 10, i, 0))
        assert len(buf.get_candles()) <= 4  # 3 completed + 1 in-progress max
```

**Step 2: Run, confirm fail**

**Step 3: Implement**

```python
# backend/monitor/candle_buffer.py
"""Aggregates price ticks into OHLCV candles of configurable timeframes."""
from __future__ import annotations

from datetime import datetime
from collections import deque


class CandleBuffer:
    """Buffers incoming ticks and aggregates into OHLCV candles."""

    def __init__(self, timeframe_minutes: int = 5, max_candles: int = 200):
        self.tf_minutes = timeframe_minutes
        self.max_candles = max_candles
        self._candles: deque[dict] = deque(maxlen=max_candles + 1)  # +1 for in-progress
        self._current_window: datetime | None = None

    def _window_start(self, ts: datetime) -> datetime:
        """Get the start of the candle window for a given timestamp."""
        minutes = (ts.hour * 60 + ts.minute) // self.tf_minutes * self.tf_minutes
        return ts.replace(hour=minutes // 60, minute=minutes % 60, second=0, microsecond=0)

    def add_tick(self, price: float, volume: int = 0, timestamp: datetime | None = None):
        ts = timestamp or datetime.utcnow()
        window = self._window_start(ts)

        if self._current_window != window:
            # New candle
            self._current_window = window
            self._candles.append({
                "timestamp": window,
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "volume": volume,
            })
        else:
            # Update current candle
            candle = self._candles[-1]
            candle["high"] = max(candle["high"], price)
            candle["low"] = min(candle["low"], price)
            candle["close"] = price
            candle["volume"] += volume

    def seed(self, historical: list[dict]):
        """Seed with historical candles (must be sorted by time ascending)."""
        for c in historical:
            self._candles.append(c)
            self._current_window = c["timestamp"]

    def get_candles(self) -> list[dict]:
        """All candles including in-progress."""
        return list(self._candles)

    def get_completed_candles(self) -> list[dict]:
        """Only completed (closed) candles — excludes the current in-progress one."""
        if len(self._candles) <= 1:
            return []
        return list(self._candles)[:-1]
```

**Step 4: Run, confirm pass**

**Step 5: Commit**

```bash
git add backend/monitor/candle_buffer.py backend/tests/monitor/test_candle_buffer.py
git commit -m "feat: implement candle buffer for tick-to-OHLCV aggregation"
```

---

## Task 10: Indicator Engine — RSI/MACD from Candle Buffer

**Files:**
- Create: `backend/monitor/indicator_engine.py`
- Test: `backend/tests/monitor/test_indicator_engine.py`

Thin wrapper that computes indicators from candle data using pandas-ta (reusing existing `ta` library).

**Step 1: Write failing tests**

```python
# backend/tests/monitor/test_indicator_engine.py
"""Tests for indicator computation from candle buffers."""
import pytest
from datetime import datetime


def _make_candles(prices: list[float], start_minute: int = 0) -> list[dict]:
    """Generate synthetic candles from a list of close prices."""
    return [
        {
            "timestamp": datetime(2026, 2, 16, 10, start_minute + i * 5, 0),
            "open": p - 1, "high": p + 2, "low": p - 2, "close": p,
            "volume": 1000,
        }
        for i, p in enumerate(prices)
    ]


class TestIndicatorEngine:
    def test_rsi_returns_value(self):
        from monitor.indicator_engine import compute_indicator
        # 20 candles with uptrend — RSI should be > 50
        prices = [100 + i * 0.5 for i in range(20)]
        candles = _make_candles(prices)
        result = compute_indicator("rsi", candles, {"period": 14})
        assert result is not None
        assert 0 <= result <= 100

    def test_rsi_oversold_region(self):
        from monitor.indicator_engine import compute_indicator
        # Steady downtrend — RSI should be low
        prices = [200 - i * 2 for i in range(20)]
        candles = _make_candles(prices)
        result = compute_indicator("rsi", candles, {"period": 14})
        assert result is not None
        assert result < 40

    def test_macd_returns_value(self):
        from monitor.indicator_engine import compute_indicator
        prices = [100 + i * 0.3 for i in range(30)]
        candles = _make_candles(prices)
        result = compute_indicator("macd", candles, {})
        assert result is not None  # Returns MACD histogram value

    def test_insufficient_data_returns_none(self):
        from monitor.indicator_engine import compute_indicator
        candles = _make_candles([100, 101, 102])  # Only 3 candles
        result = compute_indicator("rsi", candles, {"period": 14})
        assert result is None

    def test_volume_spike(self):
        from monitor.indicator_engine import compute_indicator
        # 20 candles with normal volume, last one with 5x spike
        candles = _make_candles([100 + i for i in range(20)])
        for c in candles[:-1]:
            c["volume"] = 1000
        candles[-1]["volume"] = 5000  # 5x spike
        result = compute_indicator("volume_spike", candles, {"lookback": 20, "multiplier": 2.0})
        assert result is not None
        assert result > 2.0  # Returns ratio of current vol to average
```

**Step 2: Run, confirm fail**

**Step 3: Implement**

```python
# backend/monitor/indicator_engine.py
"""Compute technical indicators from candle data for the monitor."""
from __future__ import annotations

from typing import Any

import pandas as pd
import ta


def compute_indicator(
    indicator: str,
    candles: list[dict],
    params: dict[str, Any],
) -> float | None:
    """Compute a single indicator value from candle data.

    Returns the latest value of the indicator, or None if insufficient data.
    """
    if len(candles) < 3:
        return None

    df = pd.DataFrame(candles)
    df = df.sort_values("timestamp").reset_index(drop=True)

    try:
        if indicator == "rsi":
            period = params.get("period", 14)
            if len(df) < period + 1:
                return None
            rsi = ta.momentum.RSIIndicator(df["close"], window=period)
            val = rsi.rsi().iloc[-1]
            return None if pd.isna(val) else float(val)

        elif indicator == "macd":
            if len(df) < 26:
                return None
            macd = ta.trend.MACD(df["close"])
            val = macd.macd_diff().iloc[-1]  # Histogram
            return None if pd.isna(val) else float(val)

        elif indicator == "ema_crossover":
            fast = params.get("fast", 12)
            slow = params.get("slow", 26)
            if len(df) < slow:
                return None
            ema_fast = ta.trend.EMAIndicator(df["close"], window=fast).ema_indicator().iloc[-1]
            ema_slow = ta.trend.EMAIndicator(df["close"], window=slow).ema_indicator().iloc[-1]
            return float(ema_fast - ema_slow)  # Positive = fast above slow

        elif indicator == "volume_spike":
            lookback = params.get("lookback", 20)
            multiplier = params.get("multiplier", 2.0)
            if len(df) < lookback:
                return None
            avg_vol = df["volume"].iloc[-lookback:-1].mean()
            if avg_vol == 0:
                return None
            return float(df["volume"].iloc[-1] / avg_vol)

    except Exception:
        return None

    return None
```

**Step 4: Run, confirm pass**

**Step 5: Commit**

```bash
git add backend/monitor/indicator_engine.py backend/tests/monitor/test_indicator_engine.py
git commit -m "feat: implement indicator engine (RSI, MACD, EMA crossover, volume spike)"
```

---

## Tasks 11+: Future tasks (not yet detailed)

The following tasks will be planned in a follow-up once the core rule engine is stable:

- **Task 11:** Indicator trigger evaluation in rule_evaluator (wiring indicator_engine into evaluate_rule)
- **Task 12:** DB CRUD for MonitorRule (create, list, enable, disable, delete) — used by CLI + API
- **Task 13:** `nf-monitor` CLI tool — add-rule, add-oco, list, enable, disable, delete, logs
- **Task 14:** WebSocket connection manager (base class with reconnection, heartbeat)
- **Task 15:** Portfolio stream client (Upstox Portfolio Stream Feed)
- **Task 16:** Market data stream client (Upstox Market Data Feed V3, protobuf)
- **Task 17:** UserManager — per-user session lifecycle
- **Task 18:** ActionExecutor — execute order actions, log to MonitorLog
- **Task 19:** Main daemon loop — DB poller + event routing to rule evaluator
- **Task 20:** Daemon entry point, systemd service, `--paper` mode
- **Task 21:** Orchestrator system prompt updates (intraday guidance + nf-monitor usage)
- **Task 22:** Integration tests with mock WebSocket server
- **Task 23:** Rule Builder UI (frontend) — separate design doc

---

## Execution Notes

- All tests run from `backend/` with venv activated: `cd /home/pranav/niftystrategist-v2/backend && source venv/bin/activate`
- Test command: `python -m pytest tests/monitor/ -v`
- The `backend/tests/monitor/` directory and `backend/tests/__init__.py` need to be created
- `conftest.py` with `sys.path` setup may be needed — check if imports work without it first
- Never push without user testing and confirmation
