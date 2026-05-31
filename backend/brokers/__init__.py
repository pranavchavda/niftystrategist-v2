"""Broker-agnostic account layer.

This package decouples *account-specific* trading operations (auth, orders,
portfolio, funds, trades/P&L, profile) from any single broker. Market data
(quotes, candles, chains, live ticks) deliberately stays OUT of scope — it is
served from a shared Upstox analytics-token feed regardless of which broker a
user trades through. See docs / the plan for the scope rationale.

Public surface:
    from brokers import get_broker_account, get_broker_auth, BrokerAccount
"""

from brokers.base import (
    BrokerAccount,
    BrokerAuth,
    BrokerError,
    BrokerCapabilityError,
    InstrumentResolver,
    InstrumentDescriptor,
    OrderSpec,
    GttSpec,
    TransactionType,
    OrderType,
    ProductType,
    OptionType,
    LoginDescriptor,
    CredentialField,
)
from brokers.registry import (
    get_broker_account,
    get_broker_auth,
    get_instrument_resolver,
    register_broker,
    available_brokers,
    BrokerBundle,
)

__all__ = [
    "BrokerAccount",
    "BrokerAuth",
    "BrokerError",
    "BrokerCapabilityError",
    "InstrumentResolver",
    "InstrumentDescriptor",
    "OrderSpec",
    "GttSpec",
    "TransactionType",
    "OrderType",
    "ProductType",
    "OptionType",
    "LoginDescriptor",
    "CredentialField",
    "get_broker_account",
    "get_broker_auth",
    "get_instrument_resolver",
    "register_broker",
    "available_brokers",
    "BrokerBundle",
]
