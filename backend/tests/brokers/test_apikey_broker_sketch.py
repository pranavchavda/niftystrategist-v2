"""The leak test.

Sketch a hypothetical api-key (NON-OAuth) broker — the model the user said most
Indian brokers follow — implementing the broker contracts using ONLY the public
``brokers.base`` surface. If this compiles and passes with zero changes to
``brokers.base``, the abstraction generalizes beyond Upstox's OAuth+TOTP world.

This is intentionally a stub broker: numeric instrument tokens, an api_key +
session-token auth, no GTT/multi support. It exercises the capability defaults.
"""

import pytest

from brokers.base import (
    BrokerAccount,
    BrokerAuth,
    BrokerCapabilityError,
    CredentialField,
    GttSpec,
    InstrumentDescriptor,
    InstrumentResolver,
    LoginDescriptor,
    OrderSpec,
    OrderType,
    ProductType,
    TransactionType,
)
from models.trading import Portfolio, TradeResult


class _SketchResolver(InstrumentResolver):
    """A broker whose native ids are plain numeric tokens from a symbol map."""

    _MAP = {"RELIANCE": "2885", "TCS": "11536"}

    def resolve_order_instrument(self, descriptor: InstrumentDescriptor) -> str:
        if descriptor.native_id:
            return descriptor.native_id
        sym = (descriptor.symbol or descriptor.underlying or "").upper()
        token = self._MAP.get(sym)
        if not token:
            raise ValueError(f"sketch broker can't map {sym}")
        return token

    def to_canonical(self, native_id: str) -> InstrumentDescriptor:
        for sym, tok in self._MAP.items():
            if tok == native_id:
                return InstrumentDescriptor(symbol=sym, native_id=native_id)
        return InstrumentDescriptor(native_id=native_id)


class _SketchAuth(BrokerAuth):
    broker = "sketch"

    async def get_access_token(self, user_id, *, force_refresh=False):
        # api-key brokers: exchange api_key+secret(+TOTP) for a daily session token.
        return f"session-token-for-{user_id}"

    def credential_fields(self):
        return (
            CredentialField("api_key", "API Key"),
            CredentialField("api_secret", "API Secret"),
            CredentialField("totp", "TOTP", required=False),
        )

    async def login_descriptor(self, user_id):
        return LoginDescriptor(
            broker="sketch", flow="api_key",
            credential_fields=self.credential_fields(),
        )


class _SketchAccount(BrokerAccount):
    broker = "sketch"
    capabilities = frozenset()  # minimal broker: only core ops

    def __init__(self, resolver: InstrumentResolver):
        self._resolver = resolver
        self._orders = []

    async def place_order(self, spec: OrderSpec) -> TradeResult:
        native = self._resolver.resolve_order_instrument(spec.descriptor())
        self._orders.append(native)
        return TradeResult(
            success=True, order_id=f"SK-{len(self._orders)}", status="PENDING",
            message=f"sketch order on token {native}",
        )

    async def cancel_order(self, order_id):
        return {"success": True, "order_id": order_id}

    async def get_orders(self):
        return []

    async def get_portfolio(self):
        return Portfolio(
            total_value=0, available_cash=0, invested_value=0, day_pnl=0,
            day_pnl_percentage=0, total_pnl=0, total_pnl_percentage=0,
        )

    async def get_positions(self):
        return []

    async def get_funds_and_margin(self):
        return {"available_margin": 0}

    async def get_profile(self):
        return {"broker": "sketch"}


@pytest.mark.asyncio
async def test_apikey_broker_satisfies_contract():
    account = _SketchAccount(_SketchResolver())
    spec = OrderSpec(
        transaction_type=TransactionType.BUY, quantity=1,
        order_type=OrderType.MARKET, symbol="RELIANCE",
        product=ProductType.DELIVERY,
    )
    result = await account.place_order(spec)
    assert result.success
    assert isinstance(await account.get_portfolio(), Portfolio)


@pytest.mark.asyncio
async def test_apikey_auth_is_not_oauth():
    auth = _SketchAuth()
    desc = await auth.login_descriptor(42)
    assert desc.flow == "api_key"
    assert desc.auth_url is None
    token = await auth.get_access_token(42)
    assert token == "session-token-for-42"


@pytest.mark.asyncio
async def test_unsupported_capabilities_raise_clearly():
    account = _SketchAccount(_SketchResolver())
    assert not account.supports("gtt")
    with pytest.raises(BrokerCapabilityError):
        await account.place_gtt(
            GttSpec(transaction_type=TransactionType.SELL, quantity=1,
                    trigger_price=100, symbol="RELIANCE")
        )
    with pytest.raises(BrokerCapabilityError):
        await account.exit_all()
