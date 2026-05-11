"""Order Node — thin FastAPI proxy for Upstox order operations.

Accepts order requests from the main NiftyStrategist instance and forwards
them to the Upstox API. Runs on a per-user static IP to comply with SEBI
regulations requiring registered IPs for order placement.

Stateless: receives the Upstox access token per-request, never stores it.
Auth: Bearer token (Upstox) + X-Node-Secret (shared secret with main instance).
"""

import asyncio
import logging
import os
import time

import upstox_client
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from upstox_client.rest import ApiException

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("order-node")

NODE_SECRET = os.environ.get("NF_ORDER_NODE_SECRET", "")

# ---------------------------------------------------------------------------
# Place-order dedup — defense-in-depth against the 2026-05-06 dump-on-recovery
# scenario. Client-side backoff (scalp_session.py) is the primary defense;
# this catches anything that slips through (retry tools, manual chat orders
# racing daemon retries, etc.). Window must be ≤ the client's minimum backoff
# so legitimate retries aren't blocked. Client's first-retry backoff is 30s,
# so we use 25s here.
# ---------------------------------------------------------------------------

_DEDUP_WINDOW_SEC = 25
# key → (placed_at_epoch, last_result_dict)
_recent_orders: dict[str, tuple[float, dict]] = {}


def _dedup_key(instrument_token: str, transaction_type: str, quantity: int, order_type: str) -> str:
    return f"{instrument_token}|{transaction_type}|{quantity}|{order_type}"


def _purge_expired(now: float) -> None:
    """Remove dedup entries older than the window. O(n) but n stays small."""
    expired = [k for k, (t, _) in _recent_orders.items() if now - t > _DEDUP_WINDOW_SEC]
    for k in expired:
        _recent_orders.pop(k, None)

app = FastAPI(title="NiftyStrategist Order Node", docs_url=None, redoc_url=None)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def _verify(authorization: str, x_node_secret: str) -> str:
    """Verify auth headers and return the Upstox access token."""
    if NODE_SECRET and x_node_secret != NODE_SECRET:
        raise HTTPException(status_code=403, detail="Invalid node secret")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    return authorization[7:]


def _make_client(token: str) -> upstox_client.ApiClient:
    """Create an Upstox ApiClient configured with the given access token."""
    config = upstox_client.Configuration()
    config.access_token = token
    return upstox_client.ApiClient(config)


# Cap on each Upstox SDK call. The SDK doesn't expose a hard timeout, so we
# wrap every call with asyncio.wait_for. If Upstox stalls, the handler returns
# an error and the daemon's backoff path takes over — instead of pinning the
# worker thread (and previously, blocking the whole event loop). Bumped 20→40
# 2026-05-08 evening: Upstox latency spikes on busy ticks routinely run 20–35s
# but do return — premature timeout was causing failed-fill ambiguity.
_UPSTOX_CALL_TIMEOUT_SEC = 40


async def _call_sdk(fn, *args, **kwargs):
    """Run a sync Upstox SDK call in a worker thread with a timeout."""
    return await asyncio.wait_for(
        asyncio.to_thread(fn, *args, **kwargs),
        timeout=_UPSTOX_CALL_TIMEOUT_SEC,
    )


# Budget for the order-book lookup we run after a place-order timeout to figure
# out whether Upstox actually received the order. Kept short so a stuck Upstox
# API doesn't keep the request hanging past the proxy's 60s timeout.
_RECONCILE_TIMEOUT_SEC = 10


async def _reconcile_by_tag(api_client, tag: str) -> dict | None:
    """Scan today's order book for an order with the given tag.

    Used after a place-order SDK timeout — Upstox may have accepted the order
    despite the SDK not returning. Returns a minimal dict ({order_id, status})
    on a match, None otherwise. Swallowed errors so callers always get a
    decision instead of a second-order exception.
    """
    try:
        order_api = upstox_client.OrderApi(api_client)
        resp = await asyncio.wait_for(
            asyncio.to_thread(order_api.get_order_book, api_version="2"),
            timeout=_RECONCILE_TIMEOUT_SEC,
        )
        orders = resp.data or []
        for o in orders:
            if getattr(o, "tag", None) == tag:
                return {
                    "order_id": getattr(o, "order_id", None),
                    "status": getattr(o, "status", None) or "PLACED",
                }
        return None
    except Exception as e:
        logger.warning("Reconcile-by-tag failed for %s: %r", tag, e)
        return None


def _is_market_open() -> bool:
    """Check if NSE is currently open (simple time-based heuristic)."""
    from datetime import datetime, timezone, timedelta
    ist = timezone(timedelta(hours=5, minutes=30))
    now = datetime.now(ist)
    if now.weekday() >= 5:  # Sat/Sun
        return False
    market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
    market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
    return market_open <= now <= market_close


def _parse_api_error(e: ApiException) -> str:
    """Extract a readable error message from an Upstox ApiException."""
    detail = ""
    if e.body:
        try:
            import json
            body = json.loads(e.body) if isinstance(e.body, str) else e.body
            detail = body.get("message", "") or body.get("errors", "")
        except Exception:
            detail = str(e.body)[:200]
    msg = f"{e.status} - {e.reason}"
    if detail:
        msg += f" ({detail})"
    return msg


# ---------------------------------------------------------------------------
# Request/Response models
# ---------------------------------------------------------------------------

class PlaceOrderRequest(BaseModel):
    symbol: str  # Human-readable symbol (used for logging only on equity path)
    instrument_token: str  # Pre-resolved instrument key (e.g., NSE_EQ|INE002A01018)
    transaction_type: str  # BUY or SELL
    quantity: int
    order_type: str = "MARKET"  # MARKET or LIMIT
    price: float = 0
    product: str = "D"  # D=Delivery, I=Intraday
    is_amo: bool | None = None  # None = auto-detect
    # Optional idempotency key. When supplied, dedup is keyed on this id and
    # the (instrument, side, qty, order_type) tuple is ignored — letting two
    # legitimately-parallel same-tuple orders from different sources both
    # proceed (each gets a unique id). When absent, falls back to tuple dedup
    # as a safety net for callers that don't generate ids (CLI, manual chat).
    client_request_id: str | None = None


class ModifyOrderRequest(BaseModel):
    order_id: str
    quantity: int | None = None
    price: float | None = None
    order_type: str | None = None
    trigger_price: float | None = None


class CancelMultiRequest(BaseModel):
    tag: str | None = None
    segment: str | None = None


class PlaceMultiOrderRequest(BaseModel):
    orders: list[dict]


class PlaceGttRequest(BaseModel):
    instrument_token: str
    transaction_type: str
    quantity: int
    price: float
    trigger_price: float
    order_type: str = "LIMIT"
    product: str = "D"


class ModifyGttRequest(BaseModel):
    gtt_order_id: str
    quantity: int | None = None
    price: float | None = None
    trigger_price: float | None = None


class OrderResult(BaseModel):
    success: bool
    order_id: str | None = None
    message: str = ""
    status: str = ""
    data: dict | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"ok": True}


@app.post("/orders/place", response_model=OrderResult)
async def place_order(
    req: PlaceOrderRequest,
    authorization: str = Header(""),
    x_node_secret: str = Header("", alias="X-Node-Secret"),
):
    token = _verify(authorization, x_node_secret)

    # Dedup against the 2026-05-06 dump-on-recovery flood: same instrument +
    # side + qty + order_type within _DEDUP_WINDOW_SEC returns the prior
    # outcome instead of re-submitting. Single-thread asyncio loop makes
    # check-then-set atomic between awaits.
    now = time.time()
    _purge_expired(now)
    if req.client_request_id:
        key = f"id:{req.client_request_id}"
    else:
        key = _dedup_key(req.instrument_token, req.transaction_type, req.quantity, req.order_type)
    prior = _recent_orders.get(key)
    if prior is not None:
        prior_at, prior_result = prior
        logger.warning(
            "Duplicate order suppressed: %s (prior %.1fs ago, success=%s, order_id=%s)",
            key, now - prior_at, prior_result.get("success"), prior_result.get("order_id"),
        )
        # Mirror the prior outcome so the daemon's success/failure handling
        # stays correct: prior-success → daemon transitions IDLE; prior-failure
        # → daemon stays HOLDING and lets backoff/reconcile retry. Annotate
        # the message so the dedup is visible in logs.
        return OrderResult(
            success=prior_result.get("success", False),
            order_id=prior_result.get("order_id"),
            status=prior_result.get("status") or "DUPLICATE",
            message=f"[deduped {now - prior_at:.0f}s] {prior_result.get('message', '')}",
        )

    api_client = _make_client(token)
    order_api = upstox_client.OrderApiV3(api_client)

    is_amo = req.is_amo if req.is_amo is not None else not _is_market_open()

    # Upstox tag is capped at ~20 chars and we use it for post-timeout
    # reconciliation. Fall back to a synthetic tag when the caller didn't
    # supply a client_request_id so we still have a handle to look up.
    upstox_tag = (req.client_request_id or f"{int(now)}-{req.instrument_token[-6:]}")[:40]

    try:
        body = upstox_client.PlaceOrderV3Request(
            quantity=req.quantity,
            product=req.product,
            validity="DAY",
            price=req.price if req.order_type == "LIMIT" else 0,
            trigger_price=0,
            instrument_token=req.instrument_token,
            order_type=req.order_type,
            transaction_type=req.transaction_type,
            disclosed_quantity=0,
            is_amo=is_amo,
            tag=upstox_tag,
            # -1 = automatic market protection per Upstox guidelines. Without
            # this, bare MARKET orders from API may be rejected (UDAPI1158:
            # "Market orders are not allowed. Try placing a limit order.").
            # Ignored for LIMIT/SL order types — safe to pass always.
            market_protection=-1,
        )
        response = await _call_sdk(order_api.place_order, body)
        order_ids = response.data.order_ids if response.data else []
        order_id = order_ids[0] if order_ids else None
        amo_label = " [AMO]" if is_amo else ""
        logger.info("Order placed: %s %s %s x%d (id=%s tag=%s)%s",
                     req.transaction_type, req.symbol, req.order_type, req.quantity, order_id, upstox_tag, amo_label)
        result = OrderResult(
            success=True,
            order_id=order_id,
            status="PENDING",
            message=f"Order placed successfully{amo_label} (ID: {order_id})",
        )
        _recent_orders[key] = (time.time(), result.model_dump())
        return result
    except ApiException as e:
        msg = _parse_api_error(e)
        logger.error("Place order failed: %s", msg)
        result = OrderResult(success=False, status="REJECTED", message=f"Order rejected: {msg}")
        _recent_orders[key] = (time.time(), result.model_dump())
        return result
    except asyncio.TimeoutError:
        # SDK didn't return — Upstox may still have accepted the order. Scan
        # the order book for our tag before declaring failure. 2026-05-11:
        # session 69 NIFTY 23950PE filled despite a 30s proxy timeout; daemon
        # then left the position naked. Reconcile here so success/failure
        # reflects reality.
        msg = f"Upstox SDK call exceeded {_UPSTOX_CALL_TIMEOUT_SEC}s timeout"
        logger.error("Place order timeout: %s — reconciling by tag=%s", msg, upstox_tag)
        recovered = await _reconcile_by_tag(api_client, upstox_tag)
        if recovered and recovered.get("order_id"):
            amo_label = " [AMO]" if is_amo else ""
            logger.warning(
                "Place order: SDK timeout but Upstox accepted (id=%s tag=%s)",
                recovered["order_id"], upstox_tag,
            )
            result = OrderResult(
                success=True,
                order_id=recovered["order_id"],
                status=recovered.get("status") or "PENDING",
                message=f"Order placed{amo_label} via post-timeout reconcile (ID: {recovered['order_id']})",
            )
            _recent_orders[key] = (time.time(), result.model_dump())
            return result
        result = OrderResult(success=False, status="REJECTED", message=f"Order timed out: {msg}")
        # Don't cache timeouts — let the caller's retry hit Upstox directly
        return result
    except Exception as e:
        # exc_info captures the traceback for empty-str exceptions (httpx, etc.)
        logger.error("Place order error: %r", e, exc_info=True)
        result = OrderResult(
            success=False,
            status="REJECTED",
            message=f"Order failed: {type(e).__name__}: {e}".rstrip(": "),
        )
        _recent_orders[key] = (time.time(), result.model_dump())
        return result


@app.post("/orders/modify", response_model=OrderResult)
async def modify_order(
    req: ModifyOrderRequest,
    authorization: str = Header(""),
    x_node_secret: str = Header("", alias="X-Node-Secret"),
):
    token = _verify(authorization, x_node_secret)
    api_client = _make_client(token)
    order_api = upstox_client.OrderApiV3(api_client)

    try:
        body = upstox_client.ModifyOrderRequest(
            order_id=req.order_id,
            quantity=req.quantity or 0,
            price=req.price or 0,
            order_type=req.order_type or "LIMIT",
            trigger_price=req.trigger_price or 0,
            validity="DAY",
            disclosed_quantity=0,
        )
        response = await _call_sdk(order_api.modify_order, body)
        logger.info("Order modified: %s", req.order_id)
        return OrderResult(
            success=True,
            order_id=req.order_id,
            status="MODIFIED",
            message=f"Order {req.order_id} modified",
        )
    except ApiException as e:
        msg = _parse_api_error(e)
        return OrderResult(success=False, message=f"Modify failed: {msg}")
    except Exception as e:
        return OrderResult(success=False, message=f"Modify failed: {e}")


@app.delete("/orders/{order_id}", response_model=OrderResult)
async def cancel_order(
    order_id: str,
    authorization: str = Header(""),
    x_node_secret: str = Header("", alias="X-Node-Secret"),
):
    token = _verify(authorization, x_node_secret)
    api_client = _make_client(token)
    order_api = upstox_client.OrderApiV3(api_client)

    try:
        response = await _call_sdk(order_api.cancel_order, order_id)
        logger.info("Order cancelled: %s", order_id)
        return OrderResult(success=True, order_id=order_id, message=f"Order {order_id} cancelled")
    except ApiException as e:
        msg = _parse_api_error(e)
        return OrderResult(success=False, message=f"Cancel failed: {msg}")
    except Exception as e:
        return OrderResult(success=False, message=f"Cancel failed: {e}")


@app.post("/orders/cancel-all", response_model=OrderResult)
async def cancel_all_orders(
    req: CancelMultiRequest,
    authorization: str = Header(""),
    x_node_secret: str = Header("", alias="X-Node-Secret"),
):
    token = _verify(authorization, x_node_secret)
    api_client = _make_client(token)
    order_api = upstox_client.OrderApiV3(api_client)

    try:
        # Build kwargs for cancel_multi_order
        kwargs = {}
        if req.tag:
            kwargs["tag"] = req.tag
        if req.segment:
            kwargs["segment"] = req.segment
        response = await _call_sdk(order_api.cancel_multi_order, **kwargs)
        logger.info("Cancel-all: tag=%s segment=%s", req.tag, req.segment)
        return OrderResult(success=True, message="All matching orders cancelled")
    except ApiException as e:
        msg = _parse_api_error(e)
        return OrderResult(success=False, message=f"Cancel-all failed: {msg}")
    except Exception as e:
        return OrderResult(success=False, message=f"Cancel-all failed: {e}")


@app.post("/orders/exit-all", response_model=OrderResult)
async def exit_all_positions(
    authorization: str = Header(""),
    x_node_secret: str = Header("", alias="X-Node-Secret"),
):
    token = _verify(authorization, x_node_secret)
    api_client = _make_client(token)
    order_api = upstox_client.OrderApiV3(api_client)

    try:
        response = await _call_sdk(order_api.exit_positions, cancel_orders=True)
        logger.info("Exit-all positions executed")
        return OrderResult(success=True, message="All positions exit orders placed")
    except ApiException as e:
        msg = _parse_api_error(e)
        return OrderResult(success=False, message=f"Exit-all failed: {msg}")
    except Exception as e:
        return OrderResult(success=False, message=f"Exit-all failed: {e}")


@app.post("/gtt/place", response_model=OrderResult)
async def place_gtt(
    req: PlaceGttRequest,
    authorization: str = Header(""),
    x_node_secret: str = Header("", alias="X-Node-Secret"),
):
    """Place a single-leg GTT order via the order node proxy."""
    token = _verify(authorization, x_node_secret)
    api_client = _make_client(token)
    order_api = upstox_client.OrderApiV3(api_client)

    try:
        body = upstox_client.GttPlaceOrderRequest(
            instrument_token=req.instrument_token,
            transaction_type=req.transaction_type,
            quantity=req.quantity,
            product=req.product,
            type="SINGLE",
            rules=[upstox_client.GttRule(
                strategy="ENTRY",
                trigger_type="BELOW",
                trigger_price=req.trigger_price,
            )],
        )
        response = await _call_sdk(order_api.place_gtt_order, body)
        gtt_ids = response.data.gtt_order_ids if response.data else []
        gtt_id = gtt_ids[0] if gtt_ids else None
        logger.info("GTT placed: %s %s x%d trigger=%s (id=%s)",
                    req.transaction_type, req.instrument_token, req.quantity,
                    req.trigger_price, gtt_id)
        return OrderResult(
            success=True,
            order_id=str(gtt_id) if gtt_id else None,
            status="PENDING",
            message=f"GTT order placed (ID: {gtt_id})",
        )
    except ApiException as e:
        msg = _parse_api_error(e)
        logger.error("GTT place failed: %s", msg)
        return OrderResult(success=False, status="REJECTED", message=f"GTT rejected: {msg}")
    except Exception as e:
        logger.error("GTT place error: %s", e)
        return OrderResult(success=False, status="REJECTED", message=f"GTT failed: {e}")


@app.post("/gtt/modify", response_model=OrderResult)
async def modify_gtt(
    req: ModifyGttRequest,
    authorization: str = Header(""),
    x_node_secret: str = Header("", alias="X-Node-Secret"),
):
    """Modify an existing GTT order's quantity or trigger price."""
    token = _verify(authorization, x_node_secret)
    api_client = _make_client(token)
    order_api = upstox_client.OrderApiV3(api_client)

    try:
        body = upstox_client.GttModifyOrderRequest(
            gtt_order_id=req.gtt_order_id,
            quantity=req.quantity,
            trigger_price=req.trigger_price,
        )
        response = await _call_sdk(order_api.modify_gtt_order, body)
        logger.info("GTT modified: %s", req.gtt_order_id)
        return OrderResult(
            success=True,
            order_id=req.gtt_order_id,
            status="MODIFIED",
            message=f"GTT {req.gtt_order_id} modified",
        )
    except ApiException as e:
        msg = _parse_api_error(e)
        return OrderResult(success=False, message=f"GTT modify failed: {msg}")
    except Exception as e:
        return OrderResult(success=False, message=f"GTT modify failed: {e}")


@app.delete("/gtt/{gtt_order_id}", response_model=OrderResult)
async def cancel_gtt(
    gtt_order_id: str,
    authorization: str = Header(""),
    x_node_secret: str = Header("", alias="X-Node-Secret"),
):
    """Cancel an existing GTT order."""
    token = _verify(authorization, x_node_secret)
    api_client = _make_client(token)
    order_api = upstox_client.OrderApiV3(api_client)

    try:
        body = upstox_client.GttCancelOrderRequest(gtt_order_id=gtt_order_id)
        response = await _call_sdk(order_api.cancel_gtt_order, body)
        logger.info("GTT cancelled: %s", gtt_order_id)
        return OrderResult(success=True, order_id=gtt_order_id,
                           message=f"GTT {gtt_order_id} cancelled")
    except ApiException as e:
        msg = _parse_api_error(e)
        return OrderResult(success=False, message=f"GTT cancel failed: {msg}")
    except Exception as e:
        return OrderResult(success=False, message=f"GTT cancel failed: {e}")


@app.get("/gtt/list", response_model=OrderResult)
async def list_gtt(
    authorization: str = Header(""),
    x_node_secret: str = Header("", alias="X-Node-Secret"),
):
    """List all GTT orders for the user."""
    token = _verify(authorization, x_node_secret)
    api_client = _make_client(token)
    order_api = upstox_client.OrderApiV3(api_client)

    try:
        response = await _call_sdk(order_api.get_gtt_order_details)
        orders = []
        if response.data:
            items = response.data if isinstance(response.data, list) else [response.data]
            for item in items:
                order = {}
                for attr in ("gtt_order_id", "type", "quantity", "product",
                             "instrument_token", "trading_symbol", "exchange",
                             "created_at", "expires_at", "status"):
                    val = getattr(item, attr, None)
                    if val is not None:
                        order[attr] = str(val) if attr.endswith("_at") else val
                item_rules = getattr(item, "rules", None)
                if item_rules:
                    order["rules"] = []
                    for r in (item_rules if isinstance(item_rules, list) else [item_rules]):
                        if isinstance(r, dict):
                            order["rules"].append(r)
                        else:
                            order["rules"].append({
                                "strategy": getattr(r, "strategy", None),
                                "trigger_type": getattr(r, "trigger_type", None),
                                "trigger_price": getattr(r, "trigger_price", None),
                                "transaction_type": getattr(r, "transaction_type", None),
                            })
                orders.append(order)
        return OrderResult(success=True, message="GTT orders fetched",
                           data={"orders": orders})
    except ApiException as e:
        msg = _parse_api_error(e)
        return OrderResult(success=False, message=f"GTT list failed: {msg}")
    except Exception as e:
        return OrderResult(success=False, message=f"GTT list failed: {e}")


@app.post("/orders/place-multi", response_model=OrderResult)
async def place_multi_order(
    req: PlaceMultiOrderRequest,
    authorization: str = Header(""),
    x_node_secret: str = Header("", alias="X-Node-Secret"),
):
    token = _verify(authorization, x_node_secret)
    api_client = _make_client(token)
    order_api = upstox_client.OrderApiV3(api_client)

    is_amo = not _is_market_open()

    try:
        order_requests = []
        for o in req.orders:
            order_requests.append(upstox_client.PlaceOrderV3Request(
                quantity=o["quantity"],
                product=o.get("product", "D"),
                validity="DAY",
                price=o.get("price", 0),
                trigger_price=o.get("trigger_price", 0),
                instrument_token=o["instrument_token"],
                order_type=o.get("order_type", "LIMIT"),
                transaction_type=o["transaction_type"],
                disclosed_quantity=0,
                is_amo=is_amo,
                tag=o.get("tag"),
                market_protection=-1,
            ))
        response = await _call_sdk(order_api.place_multi_order, order_requests)
        logger.info("Multi-order placed: %d legs", len(order_requests))
        return OrderResult(
            success=True,
            message=f"Multi-order placed ({len(order_requests)} legs)",
            data={"response": str(response.data) if response.data else None},
        )
    except ApiException as e:
        msg = _parse_api_error(e)
        return OrderResult(success=False, message=f"Multi-order failed: {msg}")
    except Exception as e:
        return OrderResult(success=False, message=f"Multi-order failed: {e}")
