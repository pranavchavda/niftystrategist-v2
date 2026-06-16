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

import httpx
import upstox_client  # Still used for the order-book read in _reconcile_by_tag.
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from upstox_client.rest import ApiException

# Direct httpx client replaces SDK for write endpoints (place/modify/cancel/
# gtt/exit/multi). 2026-05-11: SDK was hanging at the urllib3 layer — orders
# Upstox processed in 26ms timed out at 40s in the SDK. httpx avoids urllib3.
import sys as _sys
_sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.upstox_order_api import AsyncUpstoxOrderApi  # noqa: E402

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

def _order_api(broker: str, token: str):
    """Return the per-broker order-write API client.

    This is the SEBI static-IP node's broker dispatch seam: every broker's
    order client shares the same method surface (place/modify/cancel/gtt/exit/
    multi), so endpoints don't change — only which client they get. Defaults to
    Upstox; a new broker registers one branch here. Unknown brokers fail closed
    rather than silently routing to Upstox.
    """
    if broker in ("upstox", "", None):
        return AsyncUpstoxOrderApi(token)
    raise HTTPException(
        status_code=400, detail=f"Unsupported broker '{broker}' on this order node"
    )


def _verify(authorization: str, x_node_secret: str) -> str:
    """Verify auth headers and return the broker access token."""
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


async def _live_legs_by_tag(api_client, tag: str) -> set[tuple[str, str]]:
    """Return the set of (instrument_token, transaction_type) already working
    under ``tag`` in today's order book — used to make basket placement
    idempotent across retries.

    A leg counts as "already placed" unless it's in a terminal-failed state
    (cancelled/rejected), which should be re-placed. Open/pending/complete legs
    are skipped so a retry of the same basket never re-fires a leg that landed
    (the 2026-06-16 duplicate-naked-short failure mode). Errors return an empty
    set — fail open to placement rather than silently skipping legs.
    """
    if not tag:
        return set()
    try:
        order_api = upstox_client.OrderApi(api_client)
        resp = await asyncio.wait_for(
            asyncio.to_thread(order_api.get_order_book, api_version="2"),
            timeout=_RECONCILE_TIMEOUT_SEC,
        )
        live: set[tuple[str, str]] = set()
        for o in (resp.data or []):
            if getattr(o, "tag", None) != tag:
                continue
            status = (getattr(o, "status", None) or "").lower()
            if status in ("cancelled", "rejected"):
                continue
            tok = getattr(o, "instrument_token", None)
            side = getattr(o, "transaction_type", None)
            if tok and side:
                live.add((tok, side))
        return live
    except Exception as e:
        logger.warning("Live-legs-by-tag scan failed for %s: %r", tag, e)
        return set()


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
    broker: str = "upstox"  # broker dispatch; default keeps old behavior
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
    broker: str = "upstox"


class CancelMultiRequest(BaseModel):
    tag: str | None = None
    segment: str | None = None
    broker: str = "upstox"


class PlaceMultiOrderRequest(BaseModel):
    orders: list[dict]
    broker: str = "upstox"


class PlaceGttRequest(BaseModel):
    instrument_token: str
    transaction_type: str
    quantity: int
    price: float
    trigger_price: float
    order_type: str = "LIMIT"
    product: str = "D"
    broker: str = "upstox"


class ModifyGttRequest(BaseModel):
    gtt_order_id: str
    quantity: int | None = None
    price: float | None = None
    trigger_price: float | None = None
    broker: str = "upstox"


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

    api = _order_api(req.broker, token)

    is_amo = req.is_amo if req.is_amo is not None else not _is_market_open()

    # Upstox tag limit is 40 chars (UDAPI1119). We use it as the post-timeout
    # reconciliation handle. Fall back to a synthetic tag when the caller
    # didn't supply a client_request_id so we still have a lookup key.
    upstox_tag = (req.client_request_id or f"{int(now)}-{req.instrument_token[-6:]}")[:40]

    try:
        result_dict = await api.place_order(
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
            # "Market orders are not allowed"). Ignored for LIMIT/SL types.
            market_protection=-1,
        )
        amo_label = " [AMO]" if is_amo else ""
        if result_dict.get("success"):
            order_id = result_dict.get("order_id")
            latency = result_dict.get("latency_ms")
            logger.info(
                "Order placed: %s %s %s x%d (id=%s tag=%s upstox_latency=%sms)%s",
                req.transaction_type, req.symbol, req.order_type, req.quantity,
                order_id, upstox_tag, latency, amo_label,
            )
            result = OrderResult(
                success=True,
                order_id=order_id,
                status="PENDING",
                message=f"Order placed successfully{amo_label} (ID: {order_id})",
            )
            _recent_orders[key] = (time.time(), result.model_dump())
            return result
        # Definitive REJECTED from Upstox.
        msg = result_dict.get("message") or "Order rejected"
        logger.error("Place order failed: %s", msg)
        result = OrderResult(
            success=False, status="REJECTED", message=f"Order rejected: {msg}",
        )
        _recent_orders[key] = (time.time(), result.model_dump())
        return result
    except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError) as e:
        # Transport-level failure — request may have reached Upstox even if
        # we didn't get a response. Scan the order book for our tag before
        # declaring failure (2026-05-11 TATACONSUM cascade origin).
        logger.error("Place order transport error: %r — reconciling by tag=%s", e, upstox_tag)
        api_client_sdk = _make_client(token)
        recovered = await _reconcile_by_tag(api_client_sdk, upstox_tag)
        if recovered and recovered.get("order_id"):
            amo_label = " [AMO]" if is_amo else ""
            logger.warning(
                "Place order: transport %s but Upstox accepted (id=%s tag=%s)",
                type(e).__name__, recovered["order_id"], upstox_tag,
            )
            result = OrderResult(
                success=True,
                order_id=recovered["order_id"],
                status=recovered.get("status") or "PENDING",
                message=f"Order placed via post-error reconcile (ID: {recovered['order_id']})",
            )
            _recent_orders[key] = (time.time(), result.model_dump())
            return result
        result = OrderResult(
            success=False, status="REJECTED",
            message=f"Order transport error: {type(e).__name__}: {e}".rstrip(": "),
        )
        # Don't cache transport errors — let the caller retry.
        return result
    except Exception as e:
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
    api = _order_api(req.broker, token)

    try:
        r = await api.modify_order(
            order_id=req.order_id,
            quantity=req.quantity,
            price=req.price,
            order_type=req.order_type,
            trigger_price=req.trigger_price,
        )
        if r.get("success"):
            logger.info("Order modified: %s", req.order_id)
            return OrderResult(
                success=True,
                order_id=req.order_id,
                status="MODIFIED",
                message=f"Order {req.order_id} modified",
            )
        return OrderResult(success=False, message=f"Modify failed: {r.get('message')}")
    except Exception as e:
        logger.error("Modify error: %r", e, exc_info=True)
        return OrderResult(success=False, message=f"Modify failed: {e}")


@app.delete("/orders/{order_id}", response_model=OrderResult)
async def cancel_order(
    order_id: str,
    broker: str = "upstox",
    authorization: str = Header(""),
    x_node_secret: str = Header("", alias="X-Node-Secret"),
):
    token = _verify(authorization, x_node_secret)
    api = _order_api(broker, token)

    try:
        r = await api.cancel_order(order_id)
        if r.get("success"):
            logger.info("Order cancelled: %s", order_id)
            return OrderResult(success=True, order_id=order_id, message=f"Order {order_id} cancelled")
        return OrderResult(success=False, message=f"Cancel failed: {r.get('message')}")
    except Exception as e:
        logger.error("Cancel error: %r", e, exc_info=True)
        return OrderResult(success=False, message=f"Cancel failed: {e}")


@app.post("/orders/cancel-all", response_model=OrderResult)
async def cancel_all_orders(
    req: CancelMultiRequest,
    authorization: str = Header(""),
    x_node_secret: str = Header("", alias="X-Node-Secret"),
):
    token = _verify(authorization, x_node_secret)
    api = _order_api(req.broker, token)

    try:
        r = await api.cancel_multi_order(tag=req.tag, segment=req.segment)
        if r.get("success"):
            logger.info("Cancel-all: tag=%s segment=%s", req.tag, req.segment)
            return OrderResult(success=True, message="All matching orders cancelled")
        return OrderResult(success=False, message=f"Cancel-all failed: {r.get('message')}")
    except Exception as e:
        logger.error("Cancel-all error: %r", e, exc_info=True)
        return OrderResult(success=False, message=f"Cancel-all failed: {e}")


@app.post("/orders/exit-all", response_model=OrderResult)
async def exit_all_positions(
    broker: str = "upstox",
    authorization: str = Header(""),
    x_node_secret: str = Header("", alias="X-Node-Secret"),
):
    token = _verify(authorization, x_node_secret)
    api = _order_api(broker, token)

    try:
        r = await api.exit_positions(cancel_orders=True)
        if r.get("success"):
            logger.info("Exit-all positions executed")
            return OrderResult(success=True, message="All positions exit orders placed")
        return OrderResult(success=False, message=f"Exit-all failed: {r.get('message')}")
    except Exception as e:
        logger.error("Exit-all error: %r", e, exc_info=True)
        return OrderResult(success=False, message=f"Exit-all failed: {e}")


@app.post("/gtt/place", response_model=OrderResult)
async def place_gtt(
    req: PlaceGttRequest,
    authorization: str = Header(""),
    x_node_secret: str = Header("", alias="X-Node-Secret"),
):
    """Place a single-leg GTT order via the order node proxy."""
    token = _verify(authorization, x_node_secret)
    api = _order_api(req.broker, token)

    try:
        r = await api.place_gtt_order(
            instrument_token=req.instrument_token,
            transaction_type=req.transaction_type,
            quantity=req.quantity,
            product=req.product,
            type="SINGLE",
            rules=[{
                "strategy": "ENTRY",
                "trigger_type": "BELOW",
                "trigger_price": req.trigger_price,
            }],
        )
        if r.get("success"):
            gtt_id = r.get("order_id")  # AsyncUpstoxOrderApi maps gtt_order_ids[0] → order_id
            logger.info("GTT placed: %s %s x%d trigger=%s (id=%s)",
                        req.transaction_type, req.instrument_token, req.quantity,
                        req.trigger_price, gtt_id)
            return OrderResult(
                success=True,
                order_id=str(gtt_id) if gtt_id else None,
                status="PENDING",
                message=f"GTT order placed (ID: {gtt_id})",
            )
        return OrderResult(success=False, status="REJECTED",
                           message=f"GTT rejected: {r.get('message')}")
    except Exception as e:
        logger.error("GTT place error: %r", e, exc_info=True)
        return OrderResult(success=False, status="REJECTED", message=f"GTT failed: {e}")


@app.post("/gtt/modify", response_model=OrderResult)
async def modify_gtt(
    req: ModifyGttRequest,
    authorization: str = Header(""),
    x_node_secret: str = Header("", alias="X-Node-Secret"),
):
    """Modify an existing GTT order's quantity or trigger price."""
    token = _verify(authorization, x_node_secret)
    api = _order_api(req.broker, token)

    try:
        r = await api.modify_gtt_order(
            gtt_order_id=req.gtt_order_id,
            quantity=req.quantity,
            trigger_price=req.trigger_price,
        )
        if r.get("success"):
            logger.info("GTT modified: %s", req.gtt_order_id)
            return OrderResult(
                success=True,
                order_id=req.gtt_order_id,
                status="MODIFIED",
                message=f"GTT {req.gtt_order_id} modified",
            )
        return OrderResult(success=False, message=f"GTT modify failed: {r.get('message')}")
    except Exception as e:
        logger.error("GTT modify error: %r", e, exc_info=True)
        return OrderResult(success=False, message=f"GTT modify failed: {e}")


@app.delete("/gtt/{gtt_order_id}", response_model=OrderResult)
async def cancel_gtt(
    gtt_order_id: str,
    broker: str = "upstox",
    authorization: str = Header(""),
    x_node_secret: str = Header("", alias="X-Node-Secret"),
):
    """Cancel an existing GTT order."""
    token = _verify(authorization, x_node_secret)
    api = _order_api(broker, token)

    try:
        r = await api.cancel_gtt_order(gtt_order_id)
        if r.get("success"):
            logger.info("GTT cancelled: %s", gtt_order_id)
            return OrderResult(success=True, order_id=gtt_order_id,
                               message=f"GTT {gtt_order_id} cancelled")
        return OrderResult(success=False, message=f"GTT cancel failed: {r.get('message')}")
    except Exception as e:
        logger.error("GTT cancel error: %r", e, exc_info=True)
        return OrderResult(success=False, message=f"GTT cancel failed: {e}")


@app.get("/gtt/list", response_model=OrderResult)
async def list_gtt(
    broker: str = "upstox",
    authorization: str = Header(""),
    x_node_secret: str = Header("", alias="X-Node-Secret"),
):
    """List all GTT orders for the user."""
    token = _verify(authorization, x_node_secret)
    api = _order_api(broker, token)

    try:
        r = await api.get_gtt_orders()
        if not r.get("success"):
            return OrderResult(success=False, message=f"GTT list failed: {r.get('message')}")
        # Upstox V3 returns ``data`` as a list or single item depending on count.
        raw = r.get("raw") or {}
        items = raw.get("data") or []
        if not isinstance(items, list):
            items = [items]
        orders = []
        for item in items:
            if not isinstance(item, dict):
                continue
            order: dict = {}
            for attr in ("gtt_order_id", "type", "quantity", "product",
                         "instrument_token", "trading_symbol", "exchange",
                         "created_at", "expires_at", "status"):
                val = item.get(attr)
                if val is not None:
                    order[attr] = str(val) if attr.endswith("_at") else val
            rules = item.get("rules")
            if rules:
                order["rules"] = rules if isinstance(rules, list) else [rules]
            orders.append(order)
        return OrderResult(success=True, message="GTT orders fetched",
                           data={"orders": orders})
    except Exception as e:
        logger.error("GTT list error: %r", e, exc_info=True)
        return OrderResult(success=False, message=f"GTT list failed: {e}")


@app.post("/orders/place-multi", response_model=OrderResult)
async def place_multi_order(
    req: PlaceMultiOrderRequest,
    authorization: str = Header(""),
    x_node_secret: str = Header("", alias="X-Node-Secret"),
):
    token = _verify(authorization, x_node_secret)
    api = _order_api(req.broker, token)

    is_amo = not _is_market_open()

    # Idempotency guard: all legs of a basket share one `tag`. On a retry of the
    # same basket, skip legs already working in the order book so a partial fill
    # is *completed*, never duplicated (2026-06-16 naked-short incident). The tag
    # is durable (survives process/agent retries), unlike the request-scoped
    # correlation_id or the 25s in-memory dedup window.
    basket_tag = next((o.get("tag") for o in req.orders if o.get("tag")), None)
    skipped = []
    orders_to_place = req.orders
    if basket_tag:
        live = await _live_legs_by_tag(_make_client(token), basket_tag)
        if live:
            orders_to_place = []
            for o in req.orders:
                if (o["instrument_token"], o["transaction_type"]) in live:
                    skipped.append(o.get("correlation_id") or o["instrument_token"])
                else:
                    orders_to_place.append(o)
            if not orders_to_place:
                logger.info("Multi-order idempotent no-op: all %d legs already live under tag=%s",
                            len(req.orders), basket_tag)
                return OrderResult(
                    success=True,
                    status="DUPLICATE",
                    message=f"All {len(req.orders)} legs already placed under tag {basket_tag} (idempotent)",
                    data={"placed": [], "failed": [], "skipped": skipped, "partial": False},
                )
            logger.warning("Multi-order retry: %d/%d legs already live under tag=%s, placing %d remaining",
                           len(skipped), len(req.orders), basket_tag, len(orders_to_place))

    try:
        order_payloads = []
        for o in orders_to_place:
            payload = {
                "quantity": o["quantity"],
                "product": o.get("product", "D"),
                "validity": "DAY",
                "price": o.get("price", 0),
                "trigger_price": o.get("trigger_price", 0),
                "instrument_token": o["instrument_token"],
                "order_type": o.get("order_type", "LIMIT"),
                "transaction_type": o["transaction_type"],
                "disclosed_quantity": 0,
                "is_amo": is_amo,
                "tag": o.get("tag"),
                # Per-leg id so the caller can map results back to legs. Request-
                # scoped per the API contract; dropped previously, which is why
                # partial fills couldn't be attributed to specific legs.
                "correlation_id": o.get("correlation_id"),
                "market_protection": -1,
            }
            order_payloads.append(payload)
        r = await api.place_multi_order(order_payloads)

        breakdown = {
            "placed": r.get("placed", []),
            "failed": r.get("failed", []),
            "skipped": skipped,
            "summary": r.get("summary", {}),
            "partial": bool(r.get("partial")),
        }
        n_placed = len(breakdown["placed"])
        n_failed = len(breakdown["failed"])

        if r.get("success") and not skipped:
            logger.info("Multi-order placed: %d legs (tag=%s)", n_placed, basket_tag)
            return OrderResult(success=True, message=f"Multi-order placed ({n_placed} legs)", data=breakdown)
        if r.get("success") and skipped:
            # Retry that completed a previously-partial basket.
            logger.info("Multi-order completed: +%d legs, %d already live (tag=%s)", n_placed, len(skipped), basket_tag)
            return OrderResult(
                success=True,
                message=f"Basket completed: {n_placed} placed, {len(skipped)} already live",
                data=breakdown,
            )
        # Partial or full failure — surface per-leg truth so the caller can
        # finish or unwind rather than blindly retry.
        logger.error("Multi-order %s: %d placed, %d failed (tag=%s): %s",
                     "partial" if breakdown["partial"] else "failed", n_placed, n_failed, basket_tag, r.get("message"))
        return OrderResult(
            success=False,
            status="PARTIAL" if breakdown["partial"] else "REJECTED",
            message=f"Multi-order {'partial' if breakdown['partial'] else 'failed'}: {r.get('message')}",
            data=breakdown,
        )
    except Exception as e:
        logger.error("Multi-order error: %r", e, exc_info=True)
        return OrderResult(success=False, message=f"Multi-order failed: {e}")
