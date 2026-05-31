"""PaperBroker — a fully simulated ``BrokerAccount``.

This is the interface proof (per the design's "leak test"): a *second,
independent* implementation of ``BrokerAccount`` that shares zero code with the
Upstox adapter yet satisfies the same contract. If this implements cleanly and a
future api-key broker can be sketched without changing ``brokers.base``, the
abstraction didn't leak.

It is self-contained:
* **Fills** are simulated against the shared market-data feed (an injected
  ``price_provider`` — in production a market-data ``UpstoxClient``), at the
  limit price for LIMIT orders or the live LTP for MARKET orders.
* **State** lives in the existing ``Trade`` table via
  ``services.trade_persistence``, so a paper portfolio reconstructs from trade
  history exactly like the legacy paper mode.

Dependencies are injected so tests can drive it with fakes.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Awaitable, Callable, Optional

from brokers.base import (
    BrokerAccount,
    BrokerError,
    OrderSpec,
    OrderType,
    ProductType,
    TransactionType,
)
from models.trading import Portfolio, PortfolioPosition, TradeResult

logger = logging.getLogger(__name__)

PriceProvider = Callable[[str], Awaitable[float]]


class PaperBroker(BrokerAccount):
    broker = "paper"
    # Paper supports the everyday surface; advanced order types stay unsupported
    # so callers feature-detect rather than silently mis-simulate them.
    capabilities = frozenset({"trades"})

    DEFAULT_STARTING_CAPITAL = 1_000_000.0

    def __init__(
        self,
        user_id: int,
        *,
        price_provider: Optional[PriceProvider] = None,
        persistence: Any = None,
        starting_capital: float = DEFAULT_STARTING_CAPITAL,
    ):
        self.user_id = user_id
        self._price_provider = price_provider
        self._persistence = persistence
        self._starting_capital = starting_capital
        self._order_seq = 1

    # ── helpers ──────────────────────────────────────────────────────────
    def _get_persistence(self) -> Any:
        if self._persistence is not None:
            return self._persistence
        from services.trade_persistence import get_trade_persistence

        p = get_trade_persistence()
        if p is None:
            raise BrokerError("Paper trade persistence is not initialised")
        return p

    async def _price_for(self, spec: OrderSpec) -> float:
        if spec.order_type in (OrderType.LIMIT, OrderType.SL) and spec.price > 0:
            return spec.price
        symbol = spec.symbol or spec.descriptor().symbol or spec.descriptor().underlying
        if not symbol:
            raise BrokerError("Paper MARKET order needs a symbol to price the fill")
        if self._price_provider is None:
            raise BrokerError(
                "Paper MARKET order needs a price_provider (live LTP) or a LIMIT price"
            )
        price = await self._price_provider(symbol)
        if not price or price <= 0:
            raise BrokerError(f"Could not obtain a paper fill price for {symbol}")
        return float(price)

    # ── Orders ───────────────────────────────────────────────────────────
    async def place_order(self, spec: OrderSpec) -> TradeResult:
        symbol = spec.symbol or spec.descriptor().symbol or spec.descriptor().underlying
        if not symbol:
            raise BrokerError("Paper order requires a symbol")
        try:
            fill_price = await self._price_for(spec)
        except BrokerError as e:
            return TradeResult(success=False, status="REJECTED", message=str(e))

        order_id = f"PAPER_{self._order_seq}"
        self._order_seq += 1

        persistence = self._get_persistence()
        await persistence.save_trade(
            user_id=self.user_id,
            symbol=symbol,
            direction=spec.transaction_type.value,
            quantity=spec.quantity,
            executed_price=fill_price,
            order_type=spec.order_type.value,
            order_id=order_id,
        )
        return TradeResult(
            success=True,
            order_id=order_id,
            status="COMPLETE",
            executed_price=fill_price,
            executed_quantity=spec.quantity,
            message=f"[PAPER] {spec.transaction_type.value} {spec.quantity} {symbol} "
                    f"@ ₹{fill_price:.2f} (ID: {order_id})",
        )

    async def cancel_order(self, order_id: str) -> dict[str, Any]:
        # Paper fills are immediate, so there's nothing resting to cancel.
        return {
            "success": False,
            "message": "Paper orders fill immediately; nothing to cancel.",
        }

    async def get_orders(self) -> list[dict[str, Any]]:
        # No resting order book in paper mode.
        return []

    # ── Portfolio / funds / profile ──────────────────────────────────────
    async def get_portfolio(self) -> Portfolio:
        portfolio = await self._get_persistence().get_portfolio_for_user(self.user_id)
        # Overlay paper cash so available_cash reflects simulated capital.
        portfolio.available_cash = max(
            0.0, self._starting_capital - portfolio.invested_value
        )
        portfolio.total_value = portfolio.available_cash + portfolio.invested_value
        return portfolio

    async def get_positions(self) -> list[PortfolioPosition]:
        portfolio = await self.get_portfolio()
        return list(portfolio.positions) + list(portfolio.intraday_positions)

    async def get_funds_and_margin(self) -> dict[str, Any]:
        portfolio = await self.get_portfolio()
        return {
            "equity": {
                "available_margin": portfolio.available_cash,
                "used_margin": portfolio.invested_value,
                "total": self._starting_capital,
            },
            "paper": True,
        }

    async def get_profile(self) -> dict[str, Any]:
        return {
            "user_id": str(self.user_id),
            "user_name": "Paper Trader",
            "broker": "paper",
            "email": None,
            "active_segments": ["EQ", "FO"],
            "exchanges": ["NSE", "BSE"],
        }

    # ── Trades / P&L ─────────────────────────────────────────────────────
    async def get_trades_for_day(self) -> list[dict[str, Any]]:
        # NOTE: TradePersistence.get_trade_history returns a list of *dicts*
        # (not ORM rows), with ``executed_at`` as an ISO-8601 string.
        persistence = self._get_persistence()
        history = await persistence.get_trade_history(self.user_id)
        today = datetime.utcnow().date().isoformat()
        out: list[dict[str, Any]] = []
        for t in history:
            executed_at = t.get("executed_at") if isinstance(t, dict) else None
            if executed_at and str(executed_at).startswith(today):
                out.append(
                    {
                        "symbol": t.get("symbol"),
                        "transaction_type": t.get("direction"),
                        "quantity": t.get("quantity"),
                        "price": t.get("executed_price"),
                        "order_id": t.get("id"),
                        "paper": True,
                    }
                )
        return out
