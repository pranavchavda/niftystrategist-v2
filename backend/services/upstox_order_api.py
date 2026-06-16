"""Direct httpx-based Upstox order API client.

Bypasses ``upstox-python-sdk`` for write/mutation endpoints to avoid the
2026-05-11 SDK hang: orders that Upstox processed in 26ms were timing out
at 40s+ because the SDK's urllib3 connection pool was holding sockets open
without reading the response. curl-direct of the same payload returned in
629ms. Today's TATACONSUM multi-fill cascade was caused by this hang, not
Upstox latency.

Read endpoints (get_order_book, get_positions, get_profile, …) stay on the
SDK — they hit ``api.upstox.com`` (not the HFT host) and don't exhibit the
hang. Migrating them is a separate scope.

Surface mirrors the SDK methods we use so call-site swaps are mechanical:

    place_order(body) → dict with keys {success, order_id, status, message, latency_ms}
    modify_order(...)
    cancel_order(order_id)
    cancel_multi_order(tag=..., segment=...)
    exit_positions(cancel_orders=True)
    place_multi_order(body)
    place_gtt_order(...), modify_gtt_order(...), cancel_gtt_order(...),
    get_gtt_orders()

Two flavors:
  - AsyncUpstoxOrderApi (httpx.AsyncClient) — used by order_node + backend daemon
  - SyncUpstoxOrderApi  (httpx.Client)      — used by CLI tools / sync paths

Both share ``_call`` semantics: short read timeout (10s default) since the
Upstox HFT endpoint normally responds in <50ms. On timeout the caller has to
reconcile via order-book scan — but the new median latency is so low we
rarely hit it.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

# api-hft.upstox.com for orders (V3 path), api.upstox.com for V2 multi/exit.
# Per SDK Configuration: self.host = "https://api.upstox.com",
# self.order_host = "https://api-hft.upstox.com".
# Both are env-overridable so the order stack can be pointed at the Upstox
# sandbox (https://api-sandbox.upstox.com) for end-to-end smoke tests. Sandbox
# supports place/multi-place/modify/cancel (but not order-book retrieval).
# Defaults are production; set UPSTOX_API_HOST + UPSTOX_HFT_HOST to switch.
HFT_HOST = os.environ.get("UPSTOX_HFT_HOST", "https://api-hft.upstox.com")
MAIN_HOST = os.environ.get("UPSTOX_API_HOST", "https://api.upstox.com")

# Default read timeout. Upstox HFT endpoint normally responds in <50ms;
# 10s is generous. Caller can override per-call.
DEFAULT_TIMEOUT = 10.0


def _build_headers(access_token: str, algo_name: Optional[str] = None) -> dict[str, str]:
    h = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if algo_name:
        h["X-Algo-Name"] = algo_name
    return h


def _flatten_v3_place_response(resp_json: dict) -> dict:
    """Convert Upstox V3 place_order response to a uniform dict.

    Successful V3 response:
        {"status":"success","data":{"order_ids":["123","124"]},"metadata":{"latency":26}}

    On error Upstox returns:
        {"status":"error","errors":[{"errorCode":"UDAPI...","message":"..."}]}
    """
    status = resp_json.get("status")
    if status == "success":
        data = resp_json.get("data") or {}
        order_ids = data.get("order_ids") or []
        return {
            "success": True,
            "order_id": order_ids[0] if order_ids else None,
            "order_ids": order_ids,
            "status": "PENDING",
            "message": "Order placed",
            "latency_ms": (resp_json.get("metadata") or {}).get("latency"),
            "raw": resp_json,
        }
    # Error path
    errs = resp_json.get("errors") or []
    err_msgs = "; ".join(
        f"{e.get('errorCode', '?')}: {e.get('message', '')}".strip()
        for e in errs
    ) or str(resp_json)
    return {
        "success": False,
        "order_id": None,
        "status": "REJECTED",
        "message": err_msgs,
        "raw": resp_json,
    }


def _flatten_v3_action_response(resp_json: dict) -> dict:
    """For non-place endpoints (modify/cancel/gtt/...) — same shape."""
    status = resp_json.get("status")
    if status == "success":
        data = resp_json.get("data") or {}
        order_ids = data.get("order_ids") or []
        gtt_ids = data.get("gtt_order_ids") or []
        return {
            "success": True,
            "order_id": (order_ids[0] if order_ids else None)
                        or (gtt_ids[0] if gtt_ids else None),
            "order_ids": order_ids,
            "gtt_order_ids": gtt_ids,
            "status": data.get("status") or "OK",
            "message": "OK",
            "data": data,
            "raw": resp_json,
        }
    errs = resp_json.get("errors") or []
    err_msgs = "; ".join(
        f"{e.get('errorCode', '?')}: {e.get('message', '')}".strip()
        for e in errs
    ) or str(resp_json)
    return {
        "success": False,
        "status": "REJECTED",
        "message": err_msgs,
        "raw": resp_json,
    }


def _flatten_multi_order_response(resp_json: dict) -> dict:
    """Parse Upstox ``/v2/order/multi/place`` — which is NOT atomic.

    Per the API contract, top-level ``status`` is one of ``success`` /
    ``partial_success`` / ``error``, with a ``summary`` (total/success/error/
    payload_error), a per-leg ``data`` array ({correlation_id, order_id}) and a
    per-leg ``errors`` array ({correlation_id, error_code, message}).

    The single-order flattener treats anything but ``status == "success"`` as a
    total failure — which mis-classifies ``partial_success`` as "nothing
    placed", the bug that turned a partial Iron Condor fill into a duplicate
    naked short on 2026-06-16. This parser preserves the per-leg truth so the
    caller can finish (or unwind) a partial basket instead of blindly retrying.

    Returns:
        {success, partial, status, summary, placed[], failed[], order_ids[],
         message, raw}
        - success: every requested leg was accepted (no errors, no payload errors)
        - partial: some legs accepted AND some failed (the dangerous state)
    """
    status = resp_json.get("status")
    data = resp_json.get("data") or []
    if isinstance(data, dict):
        data = [data]
    errors = resp_json.get("errors") or []
    summary = resp_json.get("summary") or {}

    placed = [
        {"correlation_id": d.get("correlation_id"), "order_id": d.get("order_id")}
        for d in data if isinstance(d, dict)
    ]
    failed = [
        {
            "correlation_id": e.get("correlation_id"),
            "error_code": e.get("error_code") or e.get("errorCode"),
            "message": e.get("message", ""),
        }
        for e in errors if isinstance(e, dict)
    ]

    n_err = summary.get("error", len(failed))
    n_payload_err = summary.get("payload_error", 0)
    ok = status == "success" and not failed and not n_err and not n_payload_err
    partial = bool(placed) and (status == "partial_success" or bool(failed))

    if ok:
        message = "OK"
    elif partial:
        message = (
            f"Partial fill — {len(placed)} placed, {len(failed)} failed: "
            + "; ".join(f"{f['correlation_id']}: {f['error_code']} {f['message']}".strip() for f in failed)
        )
    else:
        message = "; ".join(
            f"{f['correlation_id']}: {f['error_code']} {f['message']}".strip() for f in failed
        ) or str(resp_json)

    return {
        "success": ok,
        "partial": partial,
        "status": status,
        "summary": summary,
        "placed": placed,
        "failed": failed,
        "order_ids": [d.get("order_id") for d in data if isinstance(d, dict) and d.get("order_id")],
        "message": message,
        "raw": resp_json,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Async client
# ─────────────────────────────────────────────────────────────────────────────


class AsyncUpstoxOrderApi:
    """Async httpx client for Upstox order write endpoints.

    Stateless aside from the access token + algo_name. One instance per user
    per request is fine (httpx.AsyncClient is cheap to construct), or share
    across calls via the ``client`` kwarg.
    """

    def __init__(
        self,
        access_token: str,
        *,
        algo_name: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        self.access_token = access_token
        self.algo_name = algo_name
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        return _build_headers(self.access_token, self.algo_name)

    async def _call(
        self,
        method: str,
        host: str,
        path: str,
        *,
        params: Optional[dict] = None,
        json: Optional[dict] = None,
        timeout: Optional[float] = None,
    ) -> dict:
        url = f"{host}{path}"
        async with httpx.AsyncClient(timeout=timeout or self.timeout) as client:
            resp = await client.request(method, url, headers=self._headers(),
                                        params=params, json=json)
        try:
            return resp.json()
        except Exception:
            # Non-JSON response — wrap as a structured error so callers don't
            # need to special-case it.
            return {
                "status": "error",
                "errors": [{
                    "errorCode": f"HTTP{resp.status_code}",
                    "message": (resp.text or "")[:500],
                }],
            }

    # ── Order placement ─────────────────────────────────────────────────────

    async def place_order(
        self,
        *,
        quantity: int,
        product: str,
        validity: str = "DAY",
        price: float = 0,
        tag: Optional[str] = None,
        slice: bool = False,
        instrument_token: str,
        order_type: str,
        transaction_type: str,
        disclosed_quantity: int = 0,
        trigger_price: float = 0,
        is_amo: bool = False,
        market_protection: int = -1,
    ) -> dict:
        body = {
            "quantity": quantity,
            "product": product,
            "validity": validity,
            "price": price,
            "instrument_token": instrument_token,
            "order_type": order_type,
            "transaction_type": transaction_type,
            "disclosed_quantity": disclosed_quantity,
            "trigger_price": trigger_price,
            "is_amo": is_amo,
            "market_protection": market_protection,
        }
        if tag is not None:
            body["tag"] = tag
        if slice:
            body["slice"] = True
        result = await self._call("POST", HFT_HOST, "/v3/order/place", json=body)
        return _flatten_v3_place_response(result)

    async def modify_order(
        self,
        *,
        order_id: str,
        quantity: Optional[int] = None,
        price: Optional[float] = None,
        order_type: Optional[str] = None,
        trigger_price: Optional[float] = None,
        validity: str = "DAY",
        disclosed_quantity: int = 0,
    ) -> dict:
        body = {
            "order_id": order_id,
            "quantity": quantity or 0,
            "price": price or 0,
            "order_type": order_type or "LIMIT",
            "trigger_price": trigger_price or 0,
            "validity": validity,
            "disclosed_quantity": disclosed_quantity,
        }
        result = await self._call("PUT", HFT_HOST, "/v3/order/modify", json=body)
        return _flatten_v3_action_response(result)

    async def cancel_order(self, order_id: str) -> dict:
        result = await self._call(
            "DELETE", HFT_HOST, "/v3/order/cancel",
            params={"order_id": order_id},
        )
        return _flatten_v3_action_response(result)

    async def cancel_multi_order(
        self,
        *,
        tag: Optional[str] = None,
        segment: Optional[str] = None,
    ) -> dict:
        # Multi-cancel is still V2 (no V3 endpoint).
        params: dict = {}
        if tag:
            params["tag"] = tag
        if segment:
            params["segment"] = segment
        result = await self._call(
            "DELETE", MAIN_HOST, "/v2/order/multi/cancel",
            params=params if params else None,
        )
        return _flatten_v3_action_response(result)

    async def exit_positions(self, *, cancel_orders: bool = True) -> dict:
        result = await self._call(
            "POST", MAIN_HOST, "/v2/order/positions/exit",
            json={"cancel_orders": cancel_orders} if cancel_orders is not None else None,
        )
        return _flatten_v3_action_response(result)

    async def place_multi_order(self, orders: list[dict]) -> dict:
        """Place multiple orders in a single request.

        Each item is a dict with the same keys as ``place_order`` body.
        Returns a flattened response with ``order_ids``.
        """
        # Body is a RAW JSON ARRAY of order objects — NOT wrapped in {"orders": …}.
        # Wrapping it returns UDAPI100036 "Invalid input" (verified against the
        # Upstox sandbox 2026-06-16); the previous wrapper meant multi-leg/spread
        # placement never actually worked.
        result = await self._call(
            "POST", MAIN_HOST, "/v2/order/multi/place",
            json=orders,
        )
        return _flatten_multi_order_response(result)

    # ── GTT orders ──────────────────────────────────────────────────────────

    async def place_gtt_order(
        self,
        *,
        instrument_token: str,
        transaction_type: str,
        quantity: int,
        product: str = "D",
        rules: Optional[list[dict]] = None,
        type: str = "SINGLE",
    ) -> dict:
        """Place a GTT order. ``rules`` is a list of {strategy, trigger_type,
        trigger_price[, transaction_type]} dicts per Upstox docs."""
        body = {
            "type": type,
            "instrument_token": instrument_token,
            "transaction_type": transaction_type,
            "quantity": quantity,
            "product": product,
            "rules": rules or [],
        }
        result = await self._call("POST", HFT_HOST, "/v3/order/gtt/place", json=body)
        return _flatten_v3_action_response(result)

    async def modify_gtt_order(
        self,
        *,
        gtt_order_id: str,
        quantity: Optional[int] = None,
        trigger_price: Optional[float] = None,
        rules: Optional[list[dict]] = None,
    ) -> dict:
        body: dict = {"gtt_order_id": gtt_order_id}
        if quantity is not None:
            body["quantity"] = quantity
        if trigger_price is not None:
            body["trigger_price"] = trigger_price
        if rules is not None:
            body["rules"] = rules
        result = await self._call("PUT", HFT_HOST, "/v3/order/gtt/modify", json=body)
        return _flatten_v3_action_response(result)

    async def cancel_gtt_order(self, gtt_order_id: str) -> dict:
        result = await self._call(
            "DELETE", HFT_HOST, "/v3/order/gtt/cancel",
            params={"gtt_order_id": gtt_order_id},
        )
        return _flatten_v3_action_response(result)

    async def get_gtt_orders(self) -> dict:
        result = await self._call("GET", HFT_HOST, "/v3/order/gtt")
        return _flatten_v3_action_response(result)


# ─────────────────────────────────────────────────────────────────────────────
# Sync client (CLI tools)
# ─────────────────────────────────────────────────────────────────────────────


class SyncUpstoxOrderApi:
    """Sync httpx version of AsyncUpstoxOrderApi. Same surface."""

    def __init__(
        self,
        access_token: str,
        *,
        algo_name: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        self.access_token = access_token
        self.algo_name = algo_name
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        return _build_headers(self.access_token, self.algo_name)

    def _call(
        self,
        method: str,
        host: str,
        path: str,
        *,
        params: Optional[dict] = None,
        json: Optional[dict] = None,
        timeout: Optional[float] = None,
    ) -> dict:
        url = f"{host}{path}"
        with httpx.Client(timeout=timeout or self.timeout) as client:
            resp = client.request(method, url, headers=self._headers(),
                                  params=params, json=json)
        try:
            return resp.json()
        except Exception:
            return {
                "status": "error",
                "errors": [{
                    "errorCode": f"HTTP{resp.status_code}",
                    "message": (resp.text or "")[:500],
                }],
            }

    def place_order(
        self,
        *,
        quantity: int,
        product: str,
        validity: str = "DAY",
        price: float = 0,
        tag: Optional[str] = None,
        slice: bool = False,
        instrument_token: str,
        order_type: str,
        transaction_type: str,
        disclosed_quantity: int = 0,
        trigger_price: float = 0,
        is_amo: bool = False,
        market_protection: int = -1,
    ) -> dict:
        body = {
            "quantity": quantity,
            "product": product,
            "validity": validity,
            "price": price,
            "instrument_token": instrument_token,
            "order_type": order_type,
            "transaction_type": transaction_type,
            "disclosed_quantity": disclosed_quantity,
            "trigger_price": trigger_price,
            "is_amo": is_amo,
            "market_protection": market_protection,
        }
        if tag is not None:
            body["tag"] = tag
        if slice:
            body["slice"] = True
        result = self._call("POST", HFT_HOST, "/v3/order/place", json=body)
        return _flatten_v3_place_response(result)

    def modify_order(
        self,
        *,
        order_id: str,
        quantity: Optional[int] = None,
        price: Optional[float] = None,
        order_type: Optional[str] = None,
        trigger_price: Optional[float] = None,
        validity: str = "DAY",
        disclosed_quantity: int = 0,
    ) -> dict:
        body = {
            "order_id": order_id,
            "quantity": quantity or 0,
            "price": price or 0,
            "order_type": order_type or "LIMIT",
            "trigger_price": trigger_price or 0,
            "validity": validity,
            "disclosed_quantity": disclosed_quantity,
        }
        result = self._call("PUT", HFT_HOST, "/v3/order/modify", json=body)
        return _flatten_v3_action_response(result)

    def cancel_order(self, order_id: str) -> dict:
        result = self._call(
            "DELETE", HFT_HOST, "/v3/order/cancel",
            params={"order_id": order_id},
        )
        return _flatten_v3_action_response(result)

    def cancel_multi_order(
        self,
        *,
        tag: Optional[str] = None,
        segment: Optional[str] = None,
    ) -> dict:
        params: dict = {}
        if tag:
            params["tag"] = tag
        if segment:
            params["segment"] = segment
        result = self._call(
            "DELETE", MAIN_HOST, "/v2/order/multi/cancel",
            params=params if params else None,
        )
        return _flatten_v3_action_response(result)

    def exit_positions(self, *, cancel_orders: bool = True) -> dict:
        result = self._call(
            "POST", MAIN_HOST, "/v2/order/positions/exit",
            json={"cancel_orders": cancel_orders} if cancel_orders is not None else None,
        )
        return _flatten_v3_action_response(result)

    def place_multi_order(self, orders: list[dict]) -> dict:
        # Raw array body, not {"orders": …} — see async note above.
        result = self._call(
            "POST", MAIN_HOST, "/v2/order/multi/place",
            json=orders,
        )
        return _flatten_multi_order_response(result)

    def place_gtt_order(
        self,
        *,
        instrument_token: str,
        transaction_type: str,
        quantity: int,
        product: str = "D",
        rules: Optional[list[dict]] = None,
        type: str = "SINGLE",
    ) -> dict:
        body = {
            "type": type,
            "instrument_token": instrument_token,
            "transaction_type": transaction_type,
            "quantity": quantity,
            "product": product,
            "rules": rules or [],
        }
        result = self._call("POST", HFT_HOST, "/v3/order/gtt/place", json=body)
        return _flatten_v3_action_response(result)

    def modify_gtt_order(
        self,
        *,
        gtt_order_id: str,
        quantity: Optional[int] = None,
        trigger_price: Optional[float] = None,
        rules: Optional[list[dict]] = None,
    ) -> dict:
        body: dict = {"gtt_order_id": gtt_order_id}
        if quantity is not None:
            body["quantity"] = quantity
        if trigger_price is not None:
            body["trigger_price"] = trigger_price
        if rules is not None:
            body["rules"] = rules
        result = self._call("PUT", HFT_HOST, "/v3/order/gtt/modify", json=body)
        return _flatten_v3_action_response(result)

    def cancel_gtt_order(self, gtt_order_id: str) -> dict:
        result = self._call(
            "DELETE", HFT_HOST, "/v3/order/gtt/cancel",
            params={"gtt_order_id": gtt_order_id},
        )
        return _flatten_v3_action_response(result)

    def get_gtt_orders(self) -> dict:
        result = self._call("GET", HFT_HOST, "/v3/order/gtt")
        return _flatten_v3_action_response(result)
