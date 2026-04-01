"""Order Node — thin FastAPI proxy for Upstox order operations.

Accepts order requests from the main NiftyStrategist instance and forwards
them to the Upstox API. Runs on a per-user static IP to comply with SEBI
regulations requiring registered IPs for order placement.

Stateless: receives the Upstox access token per-request, never stores it.
Auth: Bearer token (Upstox) + X-Node-Secret (shared secret with main instance).
"""

import logging
import os

import upstox_client
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from upstox_client.rest import ApiException

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("order-node")

NODE_SECRET = os.environ.get("NF_ORDER_NODE_SECRET", "")

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
    api_client = _make_client(token)
    order_api = upstox_client.OrderApiV3(api_client)

    is_amo = req.is_amo if req.is_amo is not None else not _is_market_open()

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
        )
        response = order_api.place_order(body)
        order_ids = response.data.order_ids if response.data else []
        order_id = order_ids[0] if order_ids else None
        amo_label = " [AMO]" if is_amo else ""
        logger.info("Order placed: %s %s %s x%d (id=%s)%s",
                     req.transaction_type, req.symbol, req.order_type, req.quantity, order_id, amo_label)
        return OrderResult(
            success=True,
            order_id=order_id,
            status="PENDING",
            message=f"Order placed successfully{amo_label} (ID: {order_id})",
        )
    except ApiException as e:
        msg = _parse_api_error(e)
        logger.error("Place order failed: %s", msg)
        return OrderResult(success=False, status="REJECTED", message=f"Order rejected: {msg}")
    except Exception as e:
        logger.error("Place order error: %s", e)
        return OrderResult(success=False, status="REJECTED", message=f"Order failed: {e}")


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
        response = order_api.modify_order(body)
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
        response = order_api.cancel_order(order_id)
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
        response = order_api.cancel_multi_order(**kwargs)
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
        response = order_api.exit_positions(cancel_orders=True)
        logger.info("Exit-all positions executed")
        return OrderResult(success=True, message="All positions exit orders placed")
    except ApiException as e:
        msg = _parse_api_error(e)
        return OrderResult(success=False, message=f"Exit-all failed: {msg}")
    except Exception as e:
        return OrderResult(success=False, message=f"Exit-all failed: {e}")


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
                correlation_id=o.get("correlation_id"),
                tag=o.get("tag"),
            ))
        response = order_api.place_multi_order(order_requests)
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
