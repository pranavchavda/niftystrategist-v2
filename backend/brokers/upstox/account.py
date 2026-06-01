"""UpstoxBrokerAccount — the Upstox implementation of ``BrokerAccount``.

This is a *thin wrapper*, not a rewrite. It delegates to the existing,
battle-tested ``services.upstox_client.UpstoxClient`` and
``services.upstox_order_api.AsyncUpstoxOrderApi``, translating the broker-neutral
``OrderSpec`` / enums into Upstox's native codes via ``UpstoxInstrumentResolver``.

It represents a *live* Upstox account. Paper trading is a separate adapter
(``brokers.paper.PaperBroker``).
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Optional

from brokers.base import (
    BrokerAccount,
    BrokerAuthError,
    GttSpec,
    OrderSpec,
    OrderType,
    ProductType,
    TransactionType,
)
from brokers.upstox.instruments import UpstoxInstrumentResolver
from models.trading import Portfolio, TradeResult

logger = logging.getLogger(__name__)

_PRODUCT_CODE = {ProductType.DELIVERY: "D", ProductType.INTRADAY: "I"}
_ORDER_TYPE_CODE = {
    OrderType.MARKET: "MARKET",
    OrderType.LIMIT: "LIMIT",
    OrderType.SL: "SL",
    OrderType.SL_M: "SL-M",
}


class UpstoxBrokerAccount(BrokerAccount):
    broker = "upstox"
    capabilities = frozenset(
        {
            "modify_order", "cancel_all", "exit_all", "place_multi_order",
            "gtt", "trades", "pnl_report", "trade_charges", "brokerage",
            "convert_position",
        }
    )

    def __init__(self, client: Any, resolver: Optional[UpstoxInstrumentResolver] = None):
        """``client`` is a ``services.upstox_client.UpstoxClient`` (or a stand-in
        exposing the same async methods, for tests)."""
        self._client = client
        self._resolver = resolver or UpstoxInstrumentResolver()

    # ── Instrument identity ──────────────────────────────────────────────
    def _resolve_native(self, descriptor) -> str:
        """Resolve a descriptor to an Upstox instrument_key.

        Equity/index goes through the *live client's* ``_get_instrument_key`` so
        the holdings-derived dynamic cache (built from this user's positions) is
        honored — byte-identical to the pre-broker-layer path. F&O and explicit
        ``native_id`` go through the stateless resolver. Falls back to the
        stateless resolver if the client lacks the method (e.g. test stand-ins).
        """
        if descriptor.native_id:
            return descriptor.native_id
        if descriptor.instrument_kind in ("OPT", "FUT"):
            return self._resolver.resolve_order_instrument(descriptor)
        sym = descriptor.symbol or descriptor.underlying
        get_key = getattr(self._client, "_get_instrument_key", None)
        if get_key and sym:
            return get_key(sym)
        return self._resolver.resolve_order_instrument(descriptor)

    def resolve_instrument(self, target) -> str:
        from brokers.base import InstrumentDescriptor, OrderSpec

        if isinstance(target, str):
            descriptor = InstrumentDescriptor(symbol=target)
        elif isinstance(target, OrderSpec):
            descriptor = target.descriptor()
        else:
            descriptor = target
        return self._resolve_native(descriptor)

    # ── Orders ───────────────────────────────────────────────────────────
    async def place_order(self, spec: OrderSpec) -> TradeResult:
        desc = spec.descriptor()
        is_fno = desc.instrument_kind in ("OPT", "FUT") or bool(desc.native_id)

        if not is_fno:
            # Equity/index: delegate to UpstoxClient.place_order — preserves the
            # exact pre-broker-layer behavior (paper simulation, AMO auto-detect,
            # live placement via AsyncUpstoxOrderApi, symbol→key resolution incl.
            # the holdings dynamic cache). Byte-identical to the old direct path.
            return await self._client.place_order(
                symbol=desc.symbol or desc.underlying,
                transaction_type=spec.transaction_type.value,
                quantity=spec.quantity,
                price=spec.price,
                order_type=_ORDER_TYPE_CODE[spec.order_type],
                is_amo=spec.is_amo,
                product=_PRODUCT_CODE[spec.product],
            )

        # F&O / pre-resolved instrument: the client's symbol-based place_order
        # can't resolve these, so place directly against the order API.
        token = getattr(self._client, "access_token", None)
        if not token:
            raise BrokerAuthError("No Upstox access token for live order placement")

        instrument_token = self._resolve_native(desc)

        is_amo = spec.is_amo
        if is_amo is None:
            try:
                is_amo = not self._client._is_market_open()
            except Exception:
                is_amo = False

        # Same path production uses (httpx, avoids the urllib3 SDK hang).
        from services.upstox_order_api import AsyncUpstoxOrderApi

        try:
            api = AsyncUpstoxOrderApi(token)
            price = spec.price if spec.order_type in (OrderType.LIMIT, OrderType.SL) else 0
            r = await api.place_order(
                quantity=spec.quantity,
                product=_PRODUCT_CODE[spec.product],
                validity="DAY",
                price=price,
                trigger_price=spec.trigger_price,
                instrument_token=instrument_token,
                order_type=_ORDER_TYPE_CODE[spec.order_type],
                transaction_type=spec.transaction_type.value,
                disclosed_quantity=0,
                is_amo=is_amo,
                market_protection=-1,
                tag=spec.tag,
            )
            amo_label = " [AMO]" if is_amo else ""
            if r.get("success"):
                return TradeResult(
                    success=True,
                    order_id=r.get("order_id"),
                    status="PENDING",
                    message=f"Order placed successfully{amo_label} (ID: {r.get('order_id')})",
                )
            return TradeResult(
                success=False,
                status="REJECTED",
                message=f"Order rejected: {r.get('message')}",
            )
        except Exception as e:
            return TradeResult(
                success=False, status="REJECTED", message=f"Order failed: {e}",
            )

    async def cancel_order(self, order_id: str) -> dict[str, Any]:
        return await self._client.cancel_order(order_id)

    async def get_orders(self) -> list[dict[str, Any]]:
        return await self._client.get_orders()

    async def get_order_details(self, order_id: str) -> dict[str, Any]:
        return await self._client.get_order_details(order_id)

    async def get_order_history(self, order_id: str) -> list[dict[str, Any]]:
        return await self._client.get_order_history(order_id)

    async def get_order_trades(self, order_id: str) -> list[dict[str, Any]]:
        return await self._client.get_order_trades(order_id)

    async def modify_order(
        self,
        order_id: str,
        *,
        quantity: Optional[int] = None,
        price: Optional[float] = None,
        order_type: Optional[OrderType] = None,
        trigger_price: Optional[float] = None,
    ) -> dict[str, Any]:
        return await self._client.modify_order(
            order_id,
            quantity=quantity,
            price=price,
            order_type=_ORDER_TYPE_CODE[order_type] if order_type else None,
            trigger_price=trigger_price,
        )

    async def cancel_all(self, *, tag: Optional[str] = None, segment: Optional[str] = None) -> dict[str, Any]:
        return await self._client.cancel_multi_order(tag=tag, segment=segment)

    async def exit_all(self) -> dict[str, Any]:
        return await self._client.exit_all_positions()

    async def place_multi_order(self, specs: list[OrderSpec]) -> dict[str, Any]:
        orders = []
        for i, spec in enumerate(specs):
            instrument_token = self._resolve_native(spec.descriptor())
            orders.append(
                {
                    "instrument_token": instrument_token,
                    "quantity": spec.quantity,
                    "product": _PRODUCT_CODE[spec.product],
                    "order_type": _ORDER_TYPE_CODE[spec.order_type],
                    "transaction_type": spec.transaction_type.value,
                    "price": spec.price if spec.order_type in (OrderType.LIMIT, OrderType.SL) else 0,
                    "trigger_price": spec.trigger_price,
                    "correlation_id": spec.client_request_id or f"multi-{i}",
                }
            )
        return await self._client.place_multi_order(orders)

    async def place_gtt(self, spec: GttSpec) -> dict[str, Any]:
        if not spec.symbol:
            from brokers.base import BrokerCapabilityError

            raise BrokerCapabilityError(
                "upstox: GTT requires an equity symbol (F&O GTT not wired)"
            )
        rules = [
            {
                "strategy": "ENTRY",
                "trigger_type": spec.trigger_direction,
                "trigger_price": spec.trigger_price,
                "price": spec.price,
                "order_type": _ORDER_TYPE_CODE[spec.order_type],
            }
        ]
        return await self._client.place_gtt_order(
            symbol=spec.symbol,
            transaction_type=spec.transaction_type.value,
            quantity=spec.quantity,
            product=_PRODUCT_CODE[spec.product],
            gtt_type="SINGLE",
            rules=rules,
        )

    async def modify_gtt(self, gtt_id: str, **kwargs: Any) -> dict[str, Any]:
        return await self._client.modify_gtt_order(gtt_id, **kwargs)

    async def cancel_gtt(self, gtt_id: str) -> dict[str, Any]:
        return await self._client.cancel_gtt_order(gtt_id)

    async def get_gtt_orders(self) -> list[dict[str, Any]]:
        return await self._client.get_gtt_orders()

    async def convert_position(
        self,
        symbol: str,
        transaction_type: TransactionType,
        quantity: int,
        old_product: ProductType,
        new_product: ProductType,
    ) -> dict[str, Any]:
        return await self._client.convert_position(
            symbol=symbol,
            transaction_type=transaction_type.value,
            quantity=quantity,
            old_product=_PRODUCT_CODE[old_product],
            new_product=_PRODUCT_CODE[new_product],
        )

    # ── Portfolio / funds / profile ──────────────────────────────────────
    async def get_portfolio(self) -> Portfolio:
        return await self._client.get_portfolio()

    async def get_positions(self) -> list[Any]:
        return await self._client.get_positions()

    async def get_funds_and_margin(self) -> dict[str, Any]:
        return await self._client.get_funds_and_margin()

    async def get_profile(self) -> dict[str, Any]:
        return await self._client.get_profile()

    # ── Trades / P&L ─────────────────────────────────────────────────────
    async def get_trades_for_day(self) -> list[dict[str, Any]]:
        return await self._client.get_trades_for_day()

    async def get_historical_trades(self, **kwargs: Any) -> dict[str, Any]:
        return await self._client.get_historical_trades(**kwargs)

    async def get_pnl_report(self, **kwargs: Any) -> dict[str, Any]:
        return await self._client.get_pnl_report(**kwargs)

    async def get_pnl_report_range(
        self, from_date: date, to_date: date, segments: Optional[list[str]] = None
    ) -> list[dict[str, Any]]:
        return await self._client.get_pnl_report_range(from_date, to_date, segments)

    async def get_trade_charges(self, **kwargs: Any) -> dict[str, Any]:
        return await self._client.get_trade_charges(**kwargs)

    async def get_brokerage(
        self,
        symbol: str,
        quantity: int,
        transaction_type: TransactionType,
        product: ProductType,
        price: float,
    ) -> dict[str, Any]:
        return await self._client.get_brokerage(
            symbol, quantity, transaction_type.value, _PRODUCT_CODE[product], price
        )
