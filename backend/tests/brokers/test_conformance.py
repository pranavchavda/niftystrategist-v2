"""Conformance suite: the SAME contract run against every BrokerAccount.

If both the Upstox adapter (over a fake Upstox client) and the self-contained
PaperBroker satisfy this, the ``BrokerAccount`` contract is genuinely
broker-neutral. Neither path touches the network or the DB.
"""

import pytest

from brokers.base import (
    BrokerAccount,
    OrderSpec,
    OrderType,
    ProductType,
    TransactionType,
)
from brokers.paper.account import PaperBroker
from brokers.upstox.account import UpstoxBrokerAccount
from models.trading import Portfolio


# ── Fakes ──────────────────────────────────────────────────────────────────
class _FakeOrderApi:
    """Stand-in for AsyncUpstoxOrderApi — records the placed body."""

    last_body = None

    def __init__(self, token, **kwargs):
        self.token = token

    async def place_order(self, **body):
        _FakeOrderApi.last_body = body
        return {"success": True, "order_id": "UPX123"}


class _FakeUpstoxClient:
    """Minimal stand-in exposing only what UpstoxBrokerAccount delegates to."""

    def __init__(self):
        self.access_token = "fake-token"

    def _is_market_open(self):
        return True

    async def cancel_order(self, order_id):
        return {"success": True, "order_id": order_id}

    async def get_orders(self):
        return [{"order_id": "UPX123", "status": "PENDING"}]

    async def get_portfolio(self):
        return Portfolio(
            total_value=100000, available_cash=100000, invested_value=0,
            day_pnl=0, day_pnl_percentage=0, total_pnl=0, total_pnl_percentage=0,
        )

    async def get_positions(self):
        return []

    async def get_funds_and_margin(self):
        return {"equity": {"available_margin": 100000}}

    async def get_profile(self):
        return {"user_name": "Test", "broker": "upstox"}


class _FakeTrade:
    def __init__(self, symbol, direction, quantity, price):
        self.symbol = symbol
        self.direction = direction
        self.quantity = quantity
        self.executed_price = price
        self.upstox_order_id = "PAPER_1"
        from datetime import datetime

        self.executed_at = datetime.utcnow()


class _FakePersistence:
    def __init__(self):
        self.trades = []

    async def save_trade(self, *, user_id, symbol, direction, quantity,
                         executed_price, order_type, order_id, reasoning=None):
        t = _FakeTrade(symbol, direction, quantity, executed_price)
        self.trades.append(t)
        return t

    async def get_portfolio_for_user(self, user_id):
        invested = sum(
            t.executed_price * t.quantity for t in self.trades if t.direction == "BUY"
        )
        positions = []
        if self.trades:
            from models.trading import PortfolioPosition

            t = self.trades[0]
            positions.append(
                PortfolioPosition(
                    symbol=t.symbol, quantity=t.quantity,
                    average_price=t.executed_price, current_price=t.executed_price,
                    pnl=0, pnl_percentage=0, day_change=0, day_change_percentage=0,
                )
            )
        return Portfolio(
            total_value=invested, available_cash=0, invested_value=invested,
            day_pnl=0, day_pnl_percentage=0, total_pnl=0, total_pnl_percentage=0,
            positions=positions,
        )

    async def get_trade_history(self, user_id, **kwargs):
        # Mirror the real TradePersistence contract: list of dicts, ISO dates.
        return [
            {
                "id": i,
                "symbol": t.symbol,
                "direction": t.direction,
                "quantity": t.quantity,
                "executed_price": t.executed_price,
                "executed_at": t.executed_at.isoformat(),
            }
            for i, t in enumerate(self.trades)
        ]


# ── Account builders (parametrized) ─────────────────────────────────────────
def _build_upstox(monkeypatch) -> BrokerAccount:
    import services.upstox_order_api as order_api_mod

    monkeypatch.setattr(order_api_mod, "AsyncUpstoxOrderApi", _FakeOrderApi)
    return UpstoxBrokerAccount(_FakeUpstoxClient())


def _build_paper(monkeypatch) -> BrokerAccount:
    persistence = _FakePersistence()

    async def price_provider(symbol):
        return 1500.0

    return PaperBroker(user_id=999, price_provider=price_provider, persistence=persistence)


ACCOUNT_BUILDERS = {"upstox": _build_upstox, "paper": _build_paper}


@pytest.fixture(params=list(ACCOUNT_BUILDERS))
def account(request, monkeypatch):
    return ACCOUNT_BUILDERS[request.param](monkeypatch)


# ── The contract ────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_place_market_order_succeeds(account):
    spec = OrderSpec(
        transaction_type=TransactionType.BUY,
        quantity=1,
        order_type=OrderType.MARKET,
        symbol="RELIANCE",
        product=ProductType.DELIVERY,
    )
    result = await account.place_order(spec)
    assert result.success is True
    assert result.order_id


@pytest.mark.asyncio
async def test_get_portfolio_returns_portfolio(account):
    portfolio = await account.get_portfolio()
    assert isinstance(portfolio, Portfolio)


@pytest.mark.asyncio
async def test_get_positions_returns_list(account):
    positions = await account.get_positions()
    assert isinstance(positions, list)


@pytest.mark.asyncio
async def test_get_funds_returns_dict(account):
    funds = await account.get_funds_and_margin()
    assert isinstance(funds, dict)


@pytest.mark.asyncio
async def test_get_profile_returns_dict(account):
    profile = await account.get_profile()
    assert isinstance(profile, dict)


@pytest.mark.asyncio
async def test_get_orders_returns_list(account):
    orders = await account.get_orders()
    assert isinstance(orders, list)


@pytest.mark.asyncio
async def test_order_spec_requires_symbol_or_instrument():
    from brokers.base import BrokerError

    with pytest.raises(BrokerError):
        OrderSpec(transaction_type=TransactionType.BUY, quantity=1)


@pytest.mark.asyncio
async def test_upstox_enum_translation(monkeypatch):
    """Broker-neutral enums must reach Upstox as native codes."""
    account = _build_upstox(monkeypatch)
    spec = OrderSpec(
        transaction_type=TransactionType.SELL,
        quantity=5,
        order_type=OrderType.LIMIT,
        price=1490.0,
        symbol="RELIANCE",
        product=ProductType.INTRADAY,
    )
    await account.place_order(spec)
    body = _FakeOrderApi.last_body
    assert body["product"] == "I"            # INTRADAY -> "I"
    assert body["order_type"] == "LIMIT"
    assert body["transaction_type"] == "SELL"
    assert body["instrument_token"] == "NSE_EQ|INE002A01018"
    assert body["price"] == 1490.0


@pytest.mark.asyncio
async def test_paper_fill_records_trade():
    persistence = _FakePersistence()

    async def price_provider(symbol):
        return 1500.0

    paper = PaperBroker(user_id=999, price_provider=price_provider, persistence=persistence)
    spec = OrderSpec(
        transaction_type=TransactionType.BUY, quantity=2,
        order_type=OrderType.MARKET, symbol="RELIANCE",
    )
    result = await paper.place_order(spec)
    assert result.success and result.status == "COMPLETE"
    assert result.executed_price == 1500.0
    assert len(persistence.trades) == 1
    portfolio = await paper.get_portfolio()
    assert portfolio.invested_value == 3000.0
