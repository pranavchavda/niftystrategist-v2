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
    conditions: list[dict[str, Any]]


class TrailingStopTrigger(BaseModel):
    trail_percent: float
    initial_price: float
    highest_price: float
    reference: Literal["ltp", "bid", "ask", "open", "high", "low"] = "ltp"


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

    trigger_type: Literal["price", "time", "indicator", "order_status", "compound", "trailing_stop"]
    trigger_config: dict[str, Any]

    action_type: Literal["place_order", "cancel_order", "modify_order", "cancel_rule"]
    action_config: dict[str, Any]

    instrument_token: str | None = None
    symbol: str | None = None
    linked_trade_id: int | None = None
    linked_order_id: str | None = None

    fire_count: int = 0
    max_fires: int | None = None
    expires_at: datetime | None = None
    fired_at: datetime | None = None

    @property
    def should_evaluate(self) -> bool:
        if not self.enabled:
            return False
        if self.expires_at and datetime.utcnow() > self.expires_at:
            return False
        if self.max_fires is not None and self.fire_count >= self.max_fires:
            return False
        return True
