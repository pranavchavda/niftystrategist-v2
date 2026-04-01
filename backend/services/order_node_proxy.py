"""Order Node Proxy — client for forwarding order operations to a user's order node.

Provides both async (OrderNodeProxy) and sync (OrderNodeClient) variants.
The async version is used by the monitor daemon's ActionExecutor.
The sync version is used by CLI tools (nf-order, nf-options).
"""

import logging
import os
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

NODE_SECRET = os.environ.get("NF_ORDER_NODE_SECRET", "")


@dataclass
class ProxyResult:
    """Standardized result from order node calls."""
    success: bool
    order_id: str | None = None
    message: str = ""
    status: str = ""
    data: dict | None = None


def _parse_response(resp: httpx.Response) -> ProxyResult:
    """Parse an order node JSON response into a ProxyResult."""
    if resp.status_code >= 400:
        return ProxyResult(success=False, message=f"Order node HTTP {resp.status_code}: {resp.text}")
    data = resp.json()
    return ProxyResult(
        success=data.get("success", False),
        order_id=data.get("order_id"),
        message=data.get("message", ""),
        status=data.get("status", ""),
        data=data.get("data"),
    )


class OrderNodeProxy:
    """Async proxy client for the order node (used by monitor daemon)."""

    def __init__(self, node_url: str, access_token: str):
        self.node_url = node_url.rstrip("/")
        self.access_token = access_token

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "X-Node-Secret": NODE_SECRET,
            "Content-Type": "application/json",
        }

    async def place_order(
        self,
        symbol: str,
        instrument_token: str,
        transaction_type: str,
        quantity: int,
        order_type: str = "MARKET",
        price: float = 0,
        product: str = "D",
        is_amo: bool | None = None,
    ) -> ProxyResult:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self.node_url}/orders/place",
                headers=self._headers(),
                json={
                    "symbol": symbol,
                    "instrument_token": instrument_token,
                    "transaction_type": transaction_type,
                    "quantity": quantity,
                    "order_type": order_type,
                    "price": price,
                    "product": product,
                    "is_amo": is_amo,
                },
            )
        return _parse_response(resp)

    async def cancel_order(self, order_id: str) -> ProxyResult:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.delete(
                f"{self.node_url}/orders/{order_id}",
                headers=self._headers(),
            )
        return _parse_response(resp)

    async def modify_order(
        self,
        order_id: str,
        quantity: int | None = None,
        price: float | None = None,
        order_type: str | None = None,
        trigger_price: float | None = None,
    ) -> ProxyResult:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self.node_url}/orders/modify",
                headers=self._headers(),
                json={
                    "order_id": order_id,
                    "quantity": quantity,
                    "price": price,
                    "order_type": order_type,
                    "trigger_price": trigger_price,
                },
            )
        return _parse_response(resp)

    async def cancel_multi_order(self, tag: str | None = None, segment: str | None = None) -> ProxyResult:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self.node_url}/orders/cancel-all",
                headers=self._headers(),
                json={"tag": tag, "segment": segment},
            )
        return _parse_response(resp)

    async def exit_all_positions(self) -> ProxyResult:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self.node_url}/orders/exit-all",
                headers=self._headers(),
            )
        return _parse_response(resp)

    async def place_multi_order(self, orders: list[dict]) -> ProxyResult:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self.node_url}/orders/place-multi",
                headers=self._headers(),
                json={"orders": orders},
            )
        return _parse_response(resp)


class OrderNodeClient:
    """Sync proxy client for the order node (used by CLI tools)."""

    def __init__(self, node_url: str, access_token: str):
        self.node_url = node_url.rstrip("/")
        self.access_token = access_token

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "X-Node-Secret": NODE_SECRET,
            "Content-Type": "application/json",
        }

    def place_order(
        self,
        symbol: str,
        instrument_token: str,
        transaction_type: str,
        quantity: int,
        order_type: str = "MARKET",
        price: float = 0,
        product: str = "D",
        is_amo: bool | None = None,
    ) -> ProxyResult:
        with httpx.Client(timeout=30) as client:
            resp = client.post(
                f"{self.node_url}/orders/place",
                headers=self._headers(),
                json={
                    "symbol": symbol,
                    "instrument_token": instrument_token,
                    "transaction_type": transaction_type,
                    "quantity": quantity,
                    "order_type": order_type,
                    "price": price,
                    "product": product,
                    "is_amo": is_amo,
                },
            )
        return _parse_response(resp)

    def cancel_order(self, order_id: str) -> ProxyResult:
        with httpx.Client(timeout=30) as client:
            resp = client.delete(
                f"{self.node_url}/orders/{order_id}",
                headers=self._headers(),
            )
        return _parse_response(resp)

    def modify_order(
        self,
        order_id: str,
        quantity: int | None = None,
        price: float | None = None,
        order_type: str | None = None,
        trigger_price: float | None = None,
    ) -> ProxyResult:
        with httpx.Client(timeout=30) as client:
            resp = client.post(
                f"{self.node_url}/orders/modify",
                headers=self._headers(),
                json={
                    "order_id": order_id,
                    "quantity": quantity,
                    "price": price,
                    "order_type": order_type,
                    "trigger_price": trigger_price,
                },
            )
        return _parse_response(resp)

    def cancel_multi_order(self, tag: str | None = None, segment: str | None = None) -> ProxyResult:
        with httpx.Client(timeout=30) as client:
            resp = client.post(
                f"{self.node_url}/orders/cancel-all",
                headers=self._headers(),
                json={"tag": tag, "segment": segment},
            )
        return _parse_response(resp)

    def exit_all_positions(self) -> ProxyResult:
        with httpx.Client(timeout=30) as client:
            resp = client.post(
                f"{self.node_url}/orders/exit-all",
                headers=self._headers(),
            )
        return _parse_response(resp)

    def place_multi_order(self, orders: list[dict]) -> ProxyResult:
        with httpx.Client(timeout=30) as client:
            resp = client.post(
                f"{self.node_url}/orders/place-multi",
                headers=self._headers(),
                json={"orders": orders},
            )
        return _parse_response(resp)


def init_order_client() -> OrderNodeClient | None:
    """Create an OrderNodeClient if NF_ORDER_NODE_URL is set.

    Used by CLI tools to determine whether to proxy through an order node.
    """
    node_url = os.environ.get("NF_ORDER_NODE_URL")
    token = os.environ.get("NF_ACCESS_TOKEN") or os.environ.get("UPSTOX_ACCESS_TOKEN")
    if node_url and token:
        return OrderNodeClient(node_url, token)
    return None
