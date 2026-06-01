"""HTTP-level proof that the order node binds + dispatches the `broker` field.

Unlike the offline factory/model checks, this drives the real FastAPI app via
TestClient, proving the broker field is actually bound on BOTH request shapes —
body (POST) and query param (DELETE / exit) — and that the `_order_api` factory
dispatches on it. AsyncUpstoxOrderApi is mocked, so NO real order is placed.
"""

import sys
import os

import pytest

_NODE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "order_node",
)
if _NODE_DIR not in sys.path:
    sys.path.insert(0, _NODE_DIR)

from fastapi.testclient import TestClient  # noqa: E402
import order_node.app as node_app  # noqa: E402


class _FakeOrderApi:
    """Records the broker-resolved token and returns canned successes."""

    instances = []

    def __init__(self, token):
        self.token = token
        _FakeOrderApi.instances.append(self)

    async def place_order(self, **kwargs):
        return {"success": True, "order_id": "OID1", "status": "PENDING",
                "message": "ok"}

    async def cancel_order(self, order_id):
        return {"success": True, "order_id": order_id, "message": "cancelled"}

    async def exit_positions(self, *, cancel_orders=True):
        return {"success": True, "message": "exited"}


@pytest.fixture(autouse=True)
def _mock_order_api(monkeypatch):
    _FakeOrderApi.instances = []
    # Patch the symbol the factory uses, and clear any dedup state.
    monkeypatch.setattr(node_app, "AsyncUpstoxOrderApi", _FakeOrderApi)
    node_app._recent_orders.clear()
    yield


@pytest.fixture
def client():
    return TestClient(node_app.app)


HEADERS = {"Authorization": "Bearer test-broker-token"}


def _place_body(**over):
    body = {
        "symbol": "RELIANCE",
        "instrument_token": "NSE_EQ|INE002A01018",
        "transaction_type": "BUY",
        "quantity": 1,
        "order_type": "MARKET",
    }
    body.update(over)
    return body


def test_place_binds_broker_in_body_and_dispatches(client):
    r = client.post("/orders/place", json=_place_body(broker="upstox"), headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["success"] is True
    assert len(_FakeOrderApi.instances) == 1  # factory dispatched to upstox


def test_place_without_broker_is_backward_compatible(client):
    # An old caller that doesn't send `broker` must still work (defaults upstox).
    r = client.post("/orders/place", json=_place_body(), headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["success"] is True


def test_place_unknown_broker_fails_closed(client):
    r = client.post("/orders/place", json=_place_body(broker="kotak"), headers=HEADERS)
    assert r.status_code == 400
    assert "Unsupported broker" in r.json()["detail"]
    assert _FakeOrderApi.instances == []  # never dispatched


def test_cancel_binds_broker_as_query_param(client):
    # DELETE has no body — broker must bind from the query string.
    r = client.delete("/orders/OID9?broker=upstox", headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["success"] is True


def test_cancel_unknown_broker_query_fails_closed(client):
    r = client.delete("/orders/OID9?broker=kotak", headers=HEADERS)
    assert r.status_code == 400


def test_exit_all_binds_broker_as_query_param(client):
    r = client.post("/orders/exit-all?broker=upstox", headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["success"] is True
