"""KotakBrokerAccount — Kotak Neo implementation of BrokerAccount (pure REST).

Carries a minted session (base_url + edit_sid/edit_token + serverId) and makes
form-encoded REST calls to Kotak's ``/quick/*`` and ``/portfolio/*`` endpoints,
normalizing responses into the shared DTOs (``Portfolio``, ``TradeResult``).

Order/field mappings (from hf-tools cmd_order):
    exchange_segment es: nse_cm / bse_cm / nse_fo …   (via KotakInstrumentResolver)
    product pc:  DELIVERY->CNC, INTRADAY->MIS  (NRML for F&O, deferred)
    order_type pt: MARKET->MKT, LIMIT->L, SL->SL, SL-M->SL-M
    place body: am dq es mp pc pf pr pt qt rt tp ts tt os   POST /quick/order/rule/ms/place
    response: data.nOrdNo = order id
"""

from __future__ import annotations

import json
import logging
import urllib.parse
from typing import Any, Optional

import httpx

from brokers.base import (
    BrokerAccount,
    BrokerError,
    OrderSpec,
    OrderType,
    ProductType,
    TransactionType,
)
from brokers.kotak.instruments import KotakInstrumentResolver
from models.trading import Portfolio, PortfolioPosition, TradeResult

logger = logging.getLogger(__name__)

_PRODUCT_CODE = {ProductType.DELIVERY: "CNC", ProductType.INTRADAY: "MIS"}
_ORDER_TYPE_CODE = {
    OrderType.MARKET: "MKT",
    OrderType.LIMIT: "L",
    OrderType.SL: "SL",
    OrderType.SL_M: "SL-M",
}
# Kotak's ``tt`` wants B/S (not BUY/SELL) — confirmed by the SDK validator and a
# live reject. hf-tools sent "BUY"/"SELL", which Kotak rejects ("valid
# transaction type") — its order path was never actually exercised.
_TXN_CODE = {TransactionType.BUY: "B", TransactionType.SELL: "S"}


def _to_float(v: Any) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _check(resp: dict) -> dict:
    """Raise on a Kotak error envelope, else return resp.

    Kotak signals errors several ways: an ``error``/``Error`` list, ``stat ==
    "Not_Ok"``, or — as a rejected cancel/modify shows — a non-empty ``errMsg``
    with a numeric ``stCode`` (e.g. {stCode:1022, errMsg:"order is rejected"}).
    """
    if isinstance(resp, dict):
        errs = resp.get("error") or resp.get("Error")
        if errs:
            msg = "; ".join(e.get("message", str(e)) for e in errs) if isinstance(errs, list) else str(errs)
            raise BrokerError(f"Kotak API error: {msg}")
        if resp.get("stat") == "Not_Ok" or resp.get("errMsg"):
            detail = resp.get("errMsg") or resp.get("emsg") or resp.get("stat") or resp
            raise BrokerError(f"Kotak API error: {detail}")
    return resp


def _rows(resp: dict) -> list[dict]:
    if isinstance(resp, dict):
        data = resp.get("data")
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return [data]
    return resp if isinstance(resp, list) else []


class KotakBrokerAccount(BrokerAccount):
    broker = "kotak"
    capabilities = frozenset({"modify_order", "trades"})

    def __init__(self, session: dict, resolver: Optional[KotakInstrumentResolver] = None):
        self._session = session
        self._resolver = resolver or KotakInstrumentResolver()

    # ── transport ────────────────────────────────────────────────────────
    def _headers(self) -> dict:
        return {
            "Sid": self._session.get("edit_sid", ""),
            "Auth": self._session.get("edit_token", ""),
            "accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        }

    async def _rest(self, method: str, path: str, *, body: Optional[dict] = None) -> dict:
        base = self._session.get("base_url", "https://e22.kotaksecurities.com")
        url = f"{base}{path}"
        server_id = self._session.get("serverId", "")
        if server_id:
            url += "?sId=" + urllib.parse.quote(server_id)
        # Kotak form-encoded POSTs wrap the whole payload as ``jData={json}`` —
        # this is what the official neo_api_client SDK does (rest.py) and what a
        # live limits call confirmed. hf-tools sent flat bodies (untested); we
        # don't repeat that bug. The single wrap here covers place/cancel/modify/
        # limits uniformly.
        data = None
        if body is not None:
            data = urllib.parse.urlencode({"jData": json.dumps(body)})
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.request(method, url, headers=self._headers(), content=data)
        try:
            return resp.json()
        except Exception:
            return {"error": [{"message": (resp.text or "")[:300]}]}

    def resolve_instrument(self, target) -> str:
        from brokers.base import InstrumentDescriptor

        if isinstance(target, str):
            descriptor = InstrumentDescriptor(symbol=target)
        elif isinstance(target, OrderSpec):
            descriptor = target.descriptor()
        else:
            descriptor = target
        return self._resolver.resolve_order_instrument(descriptor)

    # ── Orders ─────────────────────────────────────────────────────────--
    async def place_order(self, spec: OrderSpec) -> TradeResult:
        es, ts = self._resolver.resolve_pair(spec.descriptor())
        order_type = _ORDER_TYPE_CODE[spec.order_type]
        price = "0" if spec.order_type == OrderType.MARKET else str(spec.price)
        body = {
            "am": "YES" if spec.is_amo else "NO",
            "dq": "0",
            "es": es,
            "mp": "0",
            "pc": _PRODUCT_CODE[spec.product],
            "pf": "N",
            "pr": price,
            "pt": order_type,
            "qt": str(spec.quantity),
            "rt": "DAY",
            "tp": str(spec.trigger_price or 0),
            "ts": ts,
            "tt": _TXN_CODE[spec.transaction_type],
            "os": "WEB",
        }
        if spec.tag:
            body["ig"] = spec.tag
        try:
            resp = _check(await self._rest("POST", "/quick/order/rule/ms/place", body=body))
        except BrokerError as e:
            return TradeResult(success=False, status="REJECTED", message=str(e))
        data = resp.get("data", resp) if isinstance(resp, dict) else {}
        order_id = (data or {}).get("nOrdNo")
        return TradeResult(
            success=bool(order_id),
            order_id=order_id,
            status="PENDING" if order_id else "REJECTED",
            message=f"Kotak order placed (ID: {order_id})" if order_id else f"Rejected: {data}",
        )

    async def cancel_order(self, order_id: str) -> dict[str, Any]:
        try:
            resp = _check(await self._rest("POST", "/quick/order/cancel",
                                           body={"on": order_id, "am": "NO"}))
        except BrokerError as e:
            return {"success": False, "order_id": order_id, "message": str(e)}
        return {"success": True, "order_id": order_id, "data": resp.get("data", resp)}

    async def modify_order(self, order_id, *, quantity=None, price=None,
                           order_type=None, trigger_price=None) -> dict[str, Any]:
        body = {
            "on": order_id,
            "pr": str(price) if price is not None else "0",
            "qt": str(quantity) if quantity is not None else "0",
            "tp": str(trigger_price) if trigger_price is not None else "0",
            "pt": _ORDER_TYPE_CODE[order_type] if order_type else "L",
            "rt": "DAY",
        }
        try:
            resp = _check(await self._rest("POST", "/quick/order/vr/modify", body=body))
        except BrokerError as e:
            return {"success": False, "order_id": order_id, "message": str(e)}
        return {"success": True, "order_id": order_id, "data": resp.get("data", resp)}

    async def get_orders(self) -> list[dict[str, Any]]:
        resp = _check(await self._rest("GET", "/quick/user/orders"))
        return _rows(resp)

    # ── Portfolio / positions / funds ────────────────────────────────────
    @staticmethod
    def _empty_portfolio() -> Portfolio:
        return Portfolio(
            total_value=0.0, available_cash=0.0, invested_value=0.0, day_pnl=0.0,
            day_pnl_percentage=0.0, total_pnl=0.0, total_pnl_percentage=0.0,
        )

    async def get_portfolio(self) -> Portfolio:
        # Kotak returns an error envelope ("No holdings found for this client …")
        # when the account holds no delivery stock — that's an empty portfolio,
        # not a failure (e.g. an F&O/intraday-only account).
        try:
            resp = _check(await self._rest("GET", "/portfolio/v1/holdings"))
        except BrokerError as e:
            if "no holdings" in str(e).lower() or "not found" in str(e).lower():
                return self._empty_portfolio()
            raise
        rows = _rows(resp)
        positions: list[PortfolioPosition] = []
        invested = 0.0
        market_value = 0.0
        for r in rows:
            qty = int(_to_float(r.get("quantity")))
            if qty == 0:
                continue
            avg = _to_float(r.get("averagePrice"))
            ltp = _to_float(r.get("closingPrice"))
            cost = _to_float(r.get("holdingCost")) or (avg * qty)
            mval = _to_float(r.get("mktValue")) or (ltp * qty)
            pnl = mval - cost
            invested += cost
            market_value += mval
            positions.append(PortfolioPosition(
                symbol=(r.get("displaySymbol") or r.get("symbol") or "").upper(),
                quantity=qty,
                average_price=avg,
                current_price=ltp,
                pnl=pnl,
                pnl_percentage=(pnl / cost * 100) if cost else 0.0,
                day_change=0.0,
                day_change_percentage=0.0,
                product="D",
            ))
        total_pnl = market_value - invested
        return Portfolio(
            total_value=market_value,
            available_cash=0.0,  # filled from get_funds_and_margin by callers if needed
            invested_value=invested,
            day_pnl=0.0,
            day_pnl_percentage=0.0,
            total_pnl=total_pnl,
            total_pnl_percentage=(total_pnl / invested * 100) if invested else 0.0,
            positions=positions,
        )

    async def get_positions(self) -> list[Any]:
        resp = _check(await self._rest("GET", "/quick/user/positions"))
        return _rows(resp)

    async def get_funds_and_margin(self) -> dict[str, Any]:
        # Kotak limits is a POST that returns a FLAT NEST-style margin dict
        # (Net / MarginUsed / CollateralValue …), not a ``data``-wrapped list.
        # The jData wrapping is applied centrally in _rest. Verified live 2026-06-01.
        resp = _check(await self._rest("POST", "/quick/user/limits",
                                       body={"seg": "ALL", "exch": "ALL", "prod": "ALL"}))
        row = resp if isinstance(resp, dict) else {}
        return {
            "equity": {
                "available_margin": _to_float(row.get("Net")),
                "used_margin": _to_float(row.get("MarginUsed")),
                "collateral": _to_float(row.get("CollateralValue")),
                "realized_pnl": _to_float(row.get("RealizedMtomPrsnt")),
            },
            "raw": row,
        }

    async def get_profile(self) -> dict[str, Any]:
        return {
            "user_id": self._session.get("ucc"),
            "user_name": self._session.get("greeting_name") or "Kotak User",
            "broker": "kotak",
            "ucc": self._session.get("ucc"),
            "active_segments": ["EQ", "FO"],
            "exchanges": ["NSE", "BSE"],
        }

    async def get_trades_for_day(self) -> list[dict[str, Any]]:
        resp = _check(await self._rest("GET", "/quick/user/trades"))
        return _rows(resp)
