"""Broker-agnostic contracts: BrokerAccount, BrokerAuth, instrument identity.

These are the load-bearing interfaces. Adding a new broker = implement these
three (account adapter, auth strategy, instrument resolver) and register a
``BrokerBundle`` in ``brokers.registry`` — no change to any of these classes.

Design notes
------------
* **Return types reuse the existing normalized DTOs** in ``models.trading``
  (``TradeResult``, ``Portfolio``, ``PortfolioPosition``). Those are already
  broker-neutral; brokers translate their native shapes into them.
* **Instrument identity is the centerpiece.** Callers speak in a broker-neutral
  ``OrderSpec`` (an equity symbol, or an F&O ``InstrumentDescriptor``). The
  adapter — never the caller — turns that into the broker's native instrument
  id via its ``InstrumentResolver``.
* **Capabilities, not assumptions.** Core methods are abstract; richer ones
  (GTT, multi-leg, P&L reports) default to raising ``BrokerCapabilityError`` so
  a thin broker can implement only what it supports and callers can probe.
"""

from __future__ import annotations

import enum
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Optional, Protocol, runtime_checkable

from models.trading import Portfolio, TradeResult


# ──────────────────────────────────────────────────────────────────────────
# Errors
# ──────────────────────────────────────────────────────────────────────────
class BrokerError(Exception):
    """Base class for all broker-layer errors."""


class BrokerCapabilityError(BrokerError, NotImplementedError):
    """Raised when a broker does not support a requested operation.

    Subclasses ``NotImplementedError`` so existing ``except NotImplementedError``
    guards keep working, while callers that want to probe capabilities can catch
    the more specific type.
    """


class BrokerAuthError(BrokerError):
    """Raised when credentials are missing/invalid or a token cannot be obtained."""


# ──────────────────────────────────────────────────────────────────────────
# Broker-neutral enums (each adapter maps these to native codes)
# ──────────────────────────────────────────────────────────────────────────
class TransactionType(str, enum.Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, enum.Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    SL = "SL"        # stop-loss limit
    SL_M = "SL-M"    # stop-loss market


class ProductType(str, enum.Enum):
    """Position product. Upstox: DELIVERY->'D', INTRADAY->'I'."""

    DELIVERY = "DELIVERY"   # CNC / overnight
    INTRADAY = "INTRADAY"   # MIS


class OptionType(str, enum.Enum):
    CE = "CE"
    PE = "PE"


# ──────────────────────────────────────────────────────────────────────────
# Instrument identity
# ──────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class InstrumentDescriptor:
    """Canonical, broker-neutral description of a tradeable instrument.

    Equity / index:  ``InstrumentDescriptor(exchange="NSE", symbol="RELIANCE")``
    F&O option:      ``InstrumentDescriptor(exchange="NSE", underlying="NIFTY",
                         expiry=date(2026, 2, 26), strike=25500, option_type=OptionType.CE)``
    F&O future:      same, with ``instrument_kind="FUT"`` and no strike/option_type.

    ``native_id`` is an optional escape hatch: when a caller already holds the
    broker-native id (e.g. resolved earlier from an F&O cache), it can pass it
    through and the resolver will use it verbatim.
    """

    exchange: str = "NSE"
    symbol: Optional[str] = None            # equity/index human symbol
    instrument_kind: str = "EQ"             # EQ | IDX | OPT | FUT
    underlying: Optional[str] = None        # for OPT/FUT
    expiry: Optional[date] = None
    strike: Optional[float] = None
    option_type: Optional[OptionType] = None
    native_id: Optional[str] = None         # pre-resolved broker id, if known

    def describe(self) -> str:
        if self.instrument_kind in ("OPT", "FUT"):
            parts = [self.underlying or self.symbol or "?", self.exchange,
                     self.instrument_kind]
            if self.expiry:
                parts.append(self.expiry.isoformat())
            if self.strike is not None:
                parts.append(str(self.strike))
            if self.option_type:
                parts.append(self.option_type.value)
            return ":".join(parts)
        return f"{self.exchange}:{self.symbol}"


@runtime_checkable
class InstrumentResolver(Protocol):
    """Maps the canonical descriptor <-> a broker's native instrument id.

    For Upstox the native id is the instrument_key (``NSE_EQ|INE002A01018``,
    ``NSE_FO|43885``, ``NSE_INDEX|Nifty 50``). For an api-key broker it might be
    a numeric token or an exchange tradingsymbol — that's exactly what stays
    pluggable.
    """

    def resolve_order_instrument(self, descriptor: InstrumentDescriptor) -> str:
        """Return the broker-native instrument id to place an order against."""
        ...

    def to_canonical(self, native_id: str) -> InstrumentDescriptor:
        """Inverse: best-effort reconstruct a descriptor from a native id."""
        ...


# ──────────────────────────────────────────────────────────────────────────
# Order specs (broker-neutral)
# ──────────────────────────────────────────────────────────────────────────
@dataclass
class OrderSpec:
    """A broker-neutral order request.

    Provide either ``symbol`` (equity/index, resolved by the adapter) or
    ``instrument`` (an ``InstrumentDescriptor``, required for F&O). If both are
    given, ``instrument`` wins.
    """

    transaction_type: TransactionType
    quantity: int
    order_type: OrderType = OrderType.MARKET
    price: float = 0.0
    trigger_price: float = 0.0
    product: ProductType = ProductType.DELIVERY
    symbol: Optional[str] = None
    instrument: Optional[InstrumentDescriptor] = None
    is_amo: Optional[bool] = None           # None -> adapter auto-detects
    client_request_id: Optional[str] = None  # idempotency key
    tag: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.symbol and not self.instrument:
            raise BrokerError("OrderSpec requires either 'symbol' or 'instrument'")
        if self.quantity <= 0:
            raise BrokerError("OrderSpec.quantity must be positive")

    def descriptor(self) -> InstrumentDescriptor:
        """The instrument descriptor for this order (synthesizing one from a
        bare equity symbol when needed)."""
        if self.instrument is not None:
            return self.instrument
        return InstrumentDescriptor(symbol=self.symbol)


@dataclass
class GttSpec:
    """A Good-Till-Triggered (resting) order request."""

    transaction_type: TransactionType
    quantity: int
    trigger_price: float
    price: float = 0.0
    order_type: OrderType = OrderType.LIMIT
    product: ProductType = ProductType.DELIVERY
    trigger_direction: str = "BELOW"        # ABOVE | BELOW
    symbol: Optional[str] = None
    instrument: Optional[InstrumentDescriptor] = None

    def descriptor(self) -> InstrumentDescriptor:
        if self.instrument is not None:
            return self.instrument
        return InstrumentDescriptor(symbol=self.symbol)


# ──────────────────────────────────────────────────────────────────────────
# Auth contract
# ──────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class CredentialField:
    """One field a broker needs a user to supply, for a dynamic settings form."""

    key: str                         # e.g. "api_key"
    label: str                       # e.g. "API Key"
    secret: bool = True              # render masked + store encrypted
    required: bool = True
    help_text: str = ""


@dataclass(frozen=True)
class LoginDescriptor:
    """How a user connects this broker, so the frontend renders the right flow.

    ``flow`` is "oauth" (redirect the user to ``auth_url``) or "api_key"
    (collect ``credential_fields`` in a form and POST them). This is what lets
    the UI stop hardcoding Upstox's OAuth dance.
    """

    broker: str
    flow: str                                  # "oauth" | "api_key"
    credential_fields: tuple[CredentialField, ...] = ()
    auth_url: Optional[str] = None             # for oauth flow
    notes: str = ""


class BrokerAuth(ABC):
    """Per-broker auth/token lifecycle. No OAuth assumption."""

    broker: str = "unknown"

    @abstractmethod
    async def get_access_token(self, user_id: int, *, force_refresh: bool = False) -> Optional[str]:
        """Return a currently-valid access token for the user (refresh if needed).

        Returns None when the user has no usable connection (not connected,
        expired with no auto-refresh path). Raises ``BrokerAuthError`` only on
        hard failures the caller should surface, not on "simply not connected".
        """

    @abstractmethod
    def credential_fields(self) -> tuple[CredentialField, ...]:
        """The credential schema this broker needs from a user."""

    @abstractmethod
    async def login_descriptor(self, user_id: int) -> LoginDescriptor:
        """Describe how this user should connect (oauth url or api-key form)."""


# ──────────────────────────────────────────────────────────────────────────
# Account contract
# ──────────────────────────────────────────────────────────────────────────
class BrokerAccount(ABC):
    """Account-specific operations for one user on one broker.

    Implementations wrap a broker SDK/HTTP client. They must NOT serve market
    data — quotes/candles/chains/ticks come from the shared market-data feed.

    Core methods are abstract. Capability methods default to raising
    ``BrokerCapabilityError`` so a minimal adapter stays small and callers can
    feature-detect with ``supports(...)``.
    """

    #: broker id, e.g. "upstox" | "paper"
    broker: str = "unknown"
    #: capability flags a broker can flip on; checked by ``supports()``
    capabilities: frozenset[str] = frozenset()

    def supports(self, capability: str) -> bool:
        return capability in self.capabilities

    # ── Instrument identity ──────────────────────────────────────────────
    def resolve_instrument(self, target: "str | InstrumentDescriptor | OrderSpec") -> str:
        """Resolve a symbol / descriptor / order to this broker's native
        instrument id (e.g. Upstox ``NSE_EQ|INE002A01018``).

        Used by callers that must resolve client-side before crossing the
        SEBI order-node boundary (the node receives a pre-resolved token).
        Defaults to a capability error so brokers that never need it stay thin.
        """
        raise BrokerCapabilityError(f"{self.broker}: resolve_instrument not supported")

    # ── Orders (core) ────────────────────────────────────────────────────
    @abstractmethod
    async def place_order(self, spec: OrderSpec) -> TradeResult:
        ...

    @abstractmethod
    async def cancel_order(self, order_id: str) -> dict[str, Any]:
        ...

    @abstractmethod
    async def get_orders(self) -> list[dict[str, Any]]:
        """Today's order book (broker-native dicts, lightly normalized keys)."""
        ...

    async def get_order_details(self, order_id: str) -> dict[str, Any]:
        raise BrokerCapabilityError(f"{self.broker}: get_order_details not supported")

    async def get_order_history(self, order_id: str) -> list[dict[str, Any]]:
        raise BrokerCapabilityError(f"{self.broker}: get_order_history not supported")

    async def get_order_trades(self, order_id: str) -> list[dict[str, Any]]:
        raise BrokerCapabilityError(f"{self.broker}: get_order_trades not supported")

    # ── Orders (capability) ──────────────────────────────────────────────
    async def modify_order(
        self,
        order_id: str,
        *,
        quantity: Optional[int] = None,
        price: Optional[float] = None,
        order_type: Optional[OrderType] = None,
        trigger_price: Optional[float] = None,
    ) -> dict[str, Any]:
        raise BrokerCapabilityError(f"{self.broker}: modify_order not supported")

    async def cancel_all(self, *, tag: Optional[str] = None, segment: Optional[str] = None) -> dict[str, Any]:
        raise BrokerCapabilityError(f"{self.broker}: cancel_all not supported")

    async def exit_all(self) -> dict[str, Any]:
        raise BrokerCapabilityError(f"{self.broker}: exit_all not supported")

    async def place_multi_order(self, specs: list[OrderSpec]) -> dict[str, Any]:
        raise BrokerCapabilityError(f"{self.broker}: place_multi_order not supported")

    async def place_gtt(self, spec: GttSpec) -> dict[str, Any]:
        raise BrokerCapabilityError(f"{self.broker}: place_gtt not supported")

    async def modify_gtt(self, gtt_id: str, **kwargs: Any) -> dict[str, Any]:
        raise BrokerCapabilityError(f"{self.broker}: modify_gtt not supported")

    async def cancel_gtt(self, gtt_id: str) -> dict[str, Any]:
        raise BrokerCapabilityError(f"{self.broker}: cancel_gtt not supported")

    async def get_gtt_orders(self) -> list[dict[str, Any]]:
        raise BrokerCapabilityError(f"{self.broker}: get_gtt_orders not supported")

    async def convert_position(
        self,
        symbol: str,
        transaction_type: TransactionType,
        quantity: int,
        old_product: ProductType,
        new_product: ProductType,
    ) -> dict[str, Any]:
        raise BrokerCapabilityError(f"{self.broker}: convert_position not supported")

    # ── Portfolio (core) ─────────────────────────────────────────────────
    @abstractmethod
    async def get_portfolio(self) -> Portfolio:
        ...

    @abstractmethod
    async def get_positions(self) -> list[Any]:
        """Raw/native today's positions (used for intraday P&L, squareoff)."""
        ...

    # ── Funds (core) ─────────────────────────────────────────────────────
    @abstractmethod
    async def get_funds_and_margin(self) -> dict[str, Any]:
        ...

    # ── Profile (core) ───────────────────────────────────────────────────
    @abstractmethod
    async def get_profile(self) -> dict[str, Any]:
        ...

    # ── Trades / P&L (capability) ────────────────────────────────────────
    async def get_trades_for_day(self) -> list[dict[str, Any]]:
        raise BrokerCapabilityError(f"{self.broker}: get_trades_for_day not supported")

    async def get_historical_trades(self, **kwargs: Any) -> dict[str, Any]:
        raise BrokerCapabilityError(f"{self.broker}: get_historical_trades not supported")

    async def get_pnl_report(self, **kwargs: Any) -> dict[str, Any]:
        raise BrokerCapabilityError(f"{self.broker}: get_pnl_report not supported")

    async def get_pnl_report_range(
        self, from_date: date, to_date: date, segments: Optional[list[str]] = None
    ) -> list[dict[str, Any]]:
        raise BrokerCapabilityError(f"{self.broker}: get_pnl_report_range not supported")

    async def get_trade_charges(self, **kwargs: Any) -> dict[str, Any]:
        raise BrokerCapabilityError(f"{self.broker}: get_trade_charges not supported")

    async def get_brokerage(
        self,
        symbol: str,
        quantity: int,
        transaction_type: TransactionType,
        product: ProductType,
        price: float,
    ) -> dict[str, Any]:
        raise BrokerCapabilityError(f"{self.broker}: get_brokerage not supported")
