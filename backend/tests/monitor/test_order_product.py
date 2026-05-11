"""Tests for intraday/delivery product type support.

2026-05-11: migrated from upstox-python-sdk to httpx-based AsyncUpstoxOrderApi.
Tests now verify product is forwarded into the new client's call.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_place_order_passes_product_to_api():
    """place_order should pass the product parameter to AsyncUpstoxOrderApi."""
    from services.upstox_client import UpstoxClient

    client = UpstoxClient(access_token="test-token", user_id=1, paper_trading=False)
    client._get_instrument_key = MagicMock(return_value="NSE_EQ|INE002A01018")
    client._is_market_open = MagicMock(return_value=True)

    mock_api = AsyncMock()
    mock_api.place_order = AsyncMock(return_value={
        "success": True, "order_id": "ORD123", "status": "PENDING",
    })

    with patch("services.upstox_order_api.AsyncUpstoxOrderApi", return_value=mock_api):
        await client.place_order(
            symbol="RELIANCE",
            transaction_type="BUY",
            quantity=10,
            price=0,
            order_type="MARKET",
            product="I",
        )

    mock_api.place_order.assert_awaited_once()
    kwargs = mock_api.place_order.await_args.kwargs
    assert kwargs["product"] == "I"


@pytest.mark.asyncio
async def test_place_order_defaults_to_delivery():
    """place_order should default to product='D' if not specified."""
    from services.upstox_client import UpstoxClient

    client = UpstoxClient(access_token="test-token", user_id=1, paper_trading=False)
    client._get_instrument_key = MagicMock(return_value="NSE_EQ|INE002A01018")
    client._is_market_open = MagicMock(return_value=True)

    mock_api = AsyncMock()
    mock_api.place_order = AsyncMock(return_value={
        "success": True, "order_id": "ORD123", "status": "PENDING",
    })

    with patch("services.upstox_order_api.AsyncUpstoxOrderApi", return_value=mock_api):
        await client.place_order(
            symbol="RELIANCE",
            transaction_type="BUY",
            quantity=10,
            price=0,
            order_type="MARKET",
        )

    mock_api.place_order.assert_awaited_once()
    kwargs = mock_api.place_order.await_args.kwargs
    assert kwargs["product"] == "D"
