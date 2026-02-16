"""Tests for intraday/delivery product type support."""
import pytest
from unittest.mock import MagicMock, patch


@pytest.mark.asyncio
async def test_place_order_passes_product_to_api():
    """place_order should pass the product parameter to PlaceOrderV3Request."""
    from services.upstox_client import UpstoxClient

    client = UpstoxClient(access_token="test-token", user_id=1, paper_trading=False)
    client._get_instrument_key = MagicMock(return_value="NSE_EQ|INE002A01018")
    client._is_market_open = MagicMock(return_value=True)

    with patch("services.upstox_client.upstox_client") as mock_sdk:
        mock_api = MagicMock()
        mock_response = MagicMock()
        mock_response.data.order_ids = ["ORD123"]
        mock_api.place_order.return_value = mock_response
        mock_sdk.OrderApiV3.return_value = mock_api
        mock_sdk.ApiClient.return_value = MagicMock()

        await client.place_order(
            symbol="RELIANCE",
            transaction_type="BUY",
            quantity=10,
            price=0,
            order_type="MARKET",
            product="I",
        )

        call_args = mock_sdk.PlaceOrderV3Request.call_args
        assert call_args is not None, "PlaceOrderV3Request was never called"
        assert call_args.kwargs["product"] == "I"


@pytest.mark.asyncio
async def test_place_order_defaults_to_delivery():
    """place_order should default to product='D' if not specified."""
    from services.upstox_client import UpstoxClient

    client = UpstoxClient(access_token="test-token", user_id=1, paper_trading=False)
    client._get_instrument_key = MagicMock(return_value="NSE_EQ|INE002A01018")
    client._is_market_open = MagicMock(return_value=True)

    with patch("services.upstox_client.upstox_client") as mock_sdk:
        mock_api = MagicMock()
        mock_response = MagicMock()
        mock_response.data.order_ids = ["ORD123"]
        mock_api.place_order.return_value = mock_response
        mock_sdk.OrderApiV3.return_value = mock_api
        mock_sdk.ApiClient.return_value = MagicMock()

        await client.place_order(
            symbol="RELIANCE",
            transaction_type="BUY",
            quantity=10,
            price=0,
            order_type="MARKET",
        )

        call_args = mock_sdk.PlaceOrderV3Request.call_args
        assert call_args is not None, "PlaceOrderV3Request was never called"
        assert call_args.kwargs["product"] == "D"
