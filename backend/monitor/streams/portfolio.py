"""Upstox Portfolio Stream Feed -- order, position, and holding updates."""
from __future__ import annotations

import json
import logging
from typing import Any, Callable, Coroutine

import aiohttp

from monitor.streams.connection import BaseWebSocketStream

logger = logging.getLogger(__name__)

PORTFOLIO_AUTH_URL = "https://api.upstox.com/v2/feed/portfolio-stream-feed/authorize"


class PortfolioStream(BaseWebSocketStream):
    """Connects to Upstox Portfolio Stream Feed for order/position updates.

    Uses the /v2/feed/portfolio-stream-feed/authorize endpoint to get a
    one-time WSS URL, then connects and receives JSON events.

    Events contain fields like:
    - For orders: order_id, status, transaction_type, quantity, average_price
    - For positions: instrument_token, quantity, pnl
    - For holdings: instrument_token, quantity, average_price

    Args:
        access_token: Upstox API access token.
        on_message: Async callback for each parsed message dict.
        update_types: Comma-separated update types (order, position, holding).
    """

    def __init__(
        self,
        access_token: str,
        on_message: Callable[[dict], Coroutine[Any, Any, None]],
        update_types: str = "order,position,holding",
    ):
        self._access_token = access_token
        self._update_types = update_types

        async def get_url() -> str:
            return await self._authorize()

        super().__init__(
            name="PortfolioStream",
            get_auth_url=get_url,
            on_message=on_message,
        )

    async def _authorize(self) -> str:
        """Get one-time WebSocket URL from Upstox authorize endpoint.

        Calls GET /v2/feed/portfolio-stream-feed/authorize with
        update_types query param. Returns the authorized_redirect_uri.
        """
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Accept": "application/json",
        }
        # Build query params: update_types=order%2Cposition%2Cholding
        params = {"update_types": self._update_types}

        async with aiohttp.ClientSession() as session:
            async with session.get(
                PORTFOLIO_AUTH_URL, headers=headers, params=params
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise ConnectionError(
                        f"Portfolio auth failed ({resp.status}): {text}"
                    )
                data = await resp.json()
                url = data.get("data", {}).get("authorizedRedirectUri")
                if not url:
                    raise ConnectionError(
                        f"No redirect URI in response: {data}"
                    )
                return url

    def _parse_message(self, raw: bytes | str) -> dict | None:
        """Parse JSON portfolio event.

        Returns None for empty pings or malformed messages.
        """
        try:
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            data = json.loads(raw)
            # Upstox sends periodic empty pings -- skip them
            if not data or data == {}:
                return None
            return data
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.warning(f"[PortfolioStream] Failed to parse message: {e}")
            return None
