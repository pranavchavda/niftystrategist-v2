"""Order node dedup — defense-in-depth against the 2026-05-06 dump-on-recovery
flood. Client-side backoff (scalp_session.py) is the primary guard; this
catches duplicates from any source (manual chat, retry tools, multiple daemons)
within a 25s window.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def app_module():
    """Import order_node.app and reset its global dedup dict before each test."""
    import order_node.app as app
    app._recent_orders.clear()
    return app


def _request(symbol="NIFTY26MAY24350CE", instrument_token="NSE_FO|72241",
             transaction_type="BUY", quantity=65, order_type="MARKET", price=0,
             client_request_id=None):
    from order_node.app import PlaceOrderRequest
    return PlaceOrderRequest(
        symbol=symbol,
        instrument_token=instrument_token,
        transaction_type=transaction_type,
        quantity=quantity,
        order_type=order_type,
        price=price,
        product="I",
        is_amo=False,
        client_request_id=client_request_id,
    )


@pytest.mark.asyncio
async def test_first_call_records_recent_order(app_module):
    req = _request()
    fake_response = MagicMock()
    fake_response.data.order_ids = ["ORD-1"]
    with patch.object(app_module.upstox_client, 'OrderApiV3') as mock_cls:
        mock_cls.return_value.place_order.return_value = fake_response
        with patch.object(app_module, 'NODE_SECRET', ''):
            result = await app_module.place_order(
                req, authorization="Bearer tok", x_node_secret="",
            )
    assert result.success is True
    assert result.order_id == "ORD-1"
    key = app_module._dedup_key(req.instrument_token, req.transaction_type, req.quantity, req.order_type)
    assert key in app_module._recent_orders


@pytest.mark.asyncio
async def test_duplicate_within_window_returns_prior_success(app_module):
    """Prior attempt succeeded → dup mirrors success so daemon transitions IDLE."""
    req = _request()
    fake_response = MagicMock()
    fake_response.data.order_ids = ["ORD-1"]
    with patch.object(app_module.upstox_client, 'OrderApiV3') as mock_cls:
        mock_cls.return_value.place_order.return_value = fake_response
        with patch.object(app_module, 'NODE_SECRET', ''):
            first = await app_module.place_order(req, authorization="Bearer t", x_node_secret="")
            assert first.success is True

            # Second identical request — should NOT call place_order again
            mock_cls.return_value.place_order.reset_mock()
            second = await app_module.place_order(req, authorization="Bearer t", x_node_secret="")

    assert mock_cls.return_value.place_order.call_count == 0
    assert second.success is True  # mirrors prior
    assert second.order_id == "ORD-1"
    assert "deduped" in second.message


@pytest.mark.asyncio
async def test_duplicate_within_window_returns_prior_failure(app_module):
    """Prior attempt failed → dup mirrors failure so daemon retries via backoff."""
    req = _request()
    from upstox_client.rest import ApiException
    err = ApiException(status=500, reason="Bad Gateway")
    err.body = '{"message": "broker timeout"}'
    with patch.object(app_module.upstox_client, 'OrderApiV3') as mock_cls:
        mock_cls.return_value.place_order.side_effect = err
        with patch.object(app_module, 'NODE_SECRET', ''):
            first = await app_module.place_order(req, authorization="Bearer t", x_node_secret="")
            assert first.success is False

            mock_cls.return_value.place_order.reset_mock()
            second = await app_module.place_order(req, authorization="Bearer t", x_node_secret="")

    assert mock_cls.return_value.place_order.call_count == 0
    assert second.success is False
    assert "deduped" in second.message


@pytest.mark.asyncio
async def test_different_instrument_not_deduped(app_module):
    req1 = _request(instrument_token="NSE_FO|72241")
    req2 = _request(instrument_token="NSE_FO|72243")
    fake_response = MagicMock()
    fake_response.data.order_ids = ["ORD-1"]
    with patch.object(app_module.upstox_client, 'OrderApiV3') as mock_cls:
        mock_cls.return_value.place_order.return_value = fake_response
        with patch.object(app_module, 'NODE_SECRET', ''):
            await app_module.place_order(req1, authorization="Bearer t", x_node_secret="")
            await app_module.place_order(req2, authorization="Bearer t", x_node_secret="")

    assert mock_cls.return_value.place_order.call_count == 2


@pytest.mark.asyncio
async def test_different_side_not_deduped(app_module):
    req_buy = _request(transaction_type="BUY")
    req_sell = _request(transaction_type="SELL")
    fake_response = MagicMock()
    fake_response.data.order_ids = ["ORD-1"]
    with patch.object(app_module.upstox_client, 'OrderApiV3') as mock_cls:
        mock_cls.return_value.place_order.return_value = fake_response
        with patch.object(app_module, 'NODE_SECRET', ''):
            await app_module.place_order(req_buy, authorization="Bearer t", x_node_secret="")
            await app_module.place_order(req_sell, authorization="Bearer t", x_node_secret="")

    assert mock_cls.return_value.place_order.call_count == 2


@pytest.mark.asyncio
async def test_after_window_expires_request_proceeds(app_module):
    req = _request()
    fake_response = MagicMock()
    fake_response.data.order_ids = ["ORD-1"]
    import time as time_module

    with patch.object(app_module.upstox_client, 'OrderApiV3') as mock_cls:
        mock_cls.return_value.place_order.return_value = fake_response
        with patch.object(app_module, 'NODE_SECRET', ''):
            await app_module.place_order(req, authorization="Bearer t", x_node_secret="")

            # Force the prior entry past the window by rewriting its timestamp.
            key = app_module._dedup_key(
                req.instrument_token, req.transaction_type, req.quantity, req.order_type
            )
            stale_at = time_module.time() - (app_module._DEDUP_WINDOW_SEC + 5)
            _, prior_result = app_module._recent_orders[key]
            app_module._recent_orders[key] = (stale_at, prior_result)

            mock_cls.return_value.place_order.reset_mock()
            second = await app_module.place_order(req, authorization="Bearer t", x_node_secret="")

    assert mock_cls.return_value.place_order.call_count == 1
    assert second.success is True


# ── client_request_id path ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_same_id_dedupes(app_module):
    """Same client_request_id within window → second call is suppressed."""
    fake_response = MagicMock()
    fake_response.data.order_ids = ["ORD-1"]
    with patch.object(app_module.upstox_client, 'OrderApiV3') as mock_cls:
        mock_cls.return_value.place_order.return_value = fake_response
        with patch.object(app_module, 'NODE_SECRET', ''):
            req = _request(client_request_id="scalp:1:abc123")
            first = await app_module.place_order(req, authorization="Bearer t", x_node_secret="")
            assert first.success is True

            mock_cls.return_value.place_order.reset_mock()
            req2 = _request(client_request_id="scalp:1:abc123")  # same id
            second = await app_module.place_order(req2, authorization="Bearer t", x_node_secret="")

    assert mock_cls.return_value.place_order.call_count == 0
    assert second.success is True
    assert second.order_id == "ORD-1"


@pytest.mark.asyncio
async def test_different_ids_same_tuple_both_proceed(app_module):
    """Two parallel orders for the same instrument/side/qty from different
    sources (each with its own id) must BOTH proceed — the false-positive case
    that motivated the id field."""
    fake_response = MagicMock()
    fake_response.data.order_ids = ["ORD-1"]
    with patch.object(app_module.upstox_client, 'OrderApiV3') as mock_cls:
        mock_cls.return_value.place_order.return_value = fake_response
        with patch.object(app_module, 'NODE_SECRET', ''):
            scalp_req = _request(client_request_id="scalp:1:aaa")
            chat_req = _request(client_request_id="chat:1:bbb")  # same tuple, different id
            await app_module.place_order(scalp_req, authorization="Bearer t", x_node_secret="")
            await app_module.place_order(chat_req, authorization="Bearer t", x_node_secret="")

    assert mock_cls.return_value.place_order.call_count == 2


@pytest.mark.asyncio
async def test_id_path_ignores_tuple_collision(app_module):
    """When id is supplied, tuple is not consulted — even if a tuple-keyed
    entry exists from a prior id-less call, an id-supplied request proceeds."""
    fake_response = MagicMock()
    fake_response.data.order_ids = ["ORD-1"]
    with patch.object(app_module.upstox_client, 'OrderApiV3') as mock_cls:
        mock_cls.return_value.place_order.return_value = fake_response
        with patch.object(app_module, 'NODE_SECRET', ''):
            tuple_req = _request()  # no id → tuple key
            await app_module.place_order(tuple_req, authorization="Bearer t", x_node_secret="")

            id_req = _request(client_request_id="scalp:1:xyz")  # same tuple, but with id
            mock_cls.return_value.place_order.reset_mock()
            second = await app_module.place_order(id_req, authorization="Bearer t", x_node_secret="")

    assert mock_cls.return_value.place_order.call_count == 1
    assert second.success is True
