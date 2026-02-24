"""Upstox Market Data Feed V3 -- live price streaming via protobuf."""
from __future__ import annotations

import json
import logging
from typing import Any, Callable, Coroutine

import aiohttp
from google.protobuf import json_format

from monitor.streams.connection import AuthenticationError, BaseWebSocketStream

logger = logging.getLogger(__name__)

MARKET_DATA_AUTH_URL = (
    "https://api.upstox.com/v3/feed/market-data-feed/authorize"
)


class MarketDataStream(BaseWebSocketStream):
    """Connects to Upstox Market Data Feed V3 for live price streaming.

    Uses the authorize endpoint to get a one-time WSS URL, then connects
    and receives protobuf-encoded market data.

    Subscription modes:
    - "ltpc": Last traded price + close price (lightweight, default)
    - "full": LTPC + 5-level depth + OHLC + volume
    - "option_greeks": LTPC + first depth + option greeks
    - "full_d30": Full with 30-level depth

    The on_message callback receives a dict keyed by instrument_key, e.g.:
        {
            "NSE_EQ|INE002A01018": {
                "instrument_key": "NSE_EQ|INE002A01018",
                "ltp": 2545.50,
                "close": 2530.00,
                ...
            }
        }

    Args:
        access_token: Upstox API access token.
        on_message: Async callback for each parsed message dict.
        mode: Subscription mode (ltpc, full, option_greeks, full_d30).
    """

    def __init__(
        self,
        access_token: str,
        on_message: Callable[[dict], Coroutine[Any, Any, None]],
        mode: str = "ltpc",
        on_auth_failure: Callable[[], Coroutine[Any, Any, None]] | None = None,
    ):
        self._access_token = access_token
        self._mode = mode
        self._subscribed_keys: set[str] = set()
        self._proto_module: Any = None  # Lazy-loaded protobuf module

        async def get_url() -> str:
            return await self._authorize()

        super().__init__(
            name="MarketDataStream",
            get_auth_url=get_url,
            on_message=on_message,
            on_auth_failure=on_auth_failure,
        )

    async def _authorize(self) -> str:
        """Get one-time WSS URL from Upstox.

        Calls GET /v3/feed/market-data-feed/authorize and returns the
        authorized_redirect_uri from the response.
        """
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Accept": "application/json",
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(
                MARKET_DATA_AUTH_URL, headers=headers
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    if resp.status in (401, 403):
                        raise AuthenticationError(
                            f"Market data auth failed ({resp.status}): {text}"
                        )
                    raise ConnectionError(
                        f"Market data auth failed ({resp.status}): {text}"
                    )
                data = await resp.json()
                url = data.get("data", {}).get("authorizedRedirectUri")
                if not url:
                    raise ConnectionError(
                        f"No redirect URI in response: {data}"
                    )
                return url

    def _load_proto(self):
        """Lazy-load the protobuf module for Upstox market data.

        Uses the compiled proto from the upstox-python-sdk package:
        upstox_client.feeder.proto.MarketDataFeedV3_pb2
        """
        if self._proto_module is not None:
            return
        try:
            from upstox_client.feeder.proto import MarketDataFeedV3_pb2

            self._proto_module = MarketDataFeedV3_pb2
        except ImportError:
            logger.warning(
                "Upstox protobuf module not found "
                "(upstox-python-sdk not installed?), "
                "market data parsing will be unavailable"
            )
            # Set to False so we don't retry on every message
            self._proto_module = False

    async def subscribe(self, instrument_keys: list[str]):
        """Subscribe to instrument keys for live data.

        Sends a binary-encoded JSON subscription message to the V3 feed.

        Args:
            instrument_keys: List of keys like "NSE_EQ|INE002A01018".
        """
        if not instrument_keys:
            return
        self._subscribed_keys.update(instrument_keys)
        msg = json.dumps({
            "guid": "monitor-sub",
            "method": "sub",
            "data": {
                "mode": self._mode,
                "instrumentKeys": list(instrument_keys),
            },
        })
        # V3 feed expects binary-encoded messages
        await self.send(msg.encode("utf-8"))
        logger.info(
            f"[MarketDataStream] Subscribed to "
            f"{len(instrument_keys)} instruments"
        )

    async def unsubscribe(self, instrument_keys: list[str]):
        """Unsubscribe from instrument keys.

        Args:
            instrument_keys: List of keys to unsubscribe from.
        """
        if not instrument_keys:
            return
        self._subscribed_keys -= set(instrument_keys)
        msg = json.dumps({
            "guid": "monitor-unsub",
            "method": "unsub",
            "data": {
                "mode": self._mode,
                "instrumentKeys": list(instrument_keys),
            },
        })
        await self.send(msg.encode("utf-8"))
        logger.info(
            f"[MarketDataStream] Unsubscribed from "
            f"{len(instrument_keys)} instruments"
        )

    async def change_mode(self, instrument_keys: list[str], new_mode: str):
        """Change subscription mode for given instruments.

        Args:
            instrument_keys: Instruments to change mode for.
            new_mode: New mode (ltpc, full, option_greeks, full_d30).
        """
        if not instrument_keys:
            return
        msg = json.dumps({
            "guid": "monitor-mode",
            "method": "change_mode",
            "data": {
                "mode": new_mode,
                "instrumentKeys": list(instrument_keys),
            },
        })
        await self.send(msg.encode("utf-8"))
        self._mode = new_mode
        logger.info(
            f"[MarketDataStream] Changed mode to {new_mode} for "
            f"{len(instrument_keys)} instruments"
        )

    async def _on_connected(self, ws):
        """Re-subscribe to all keys after reconnect."""
        if self._subscribed_keys:
            await self.subscribe(list(self._subscribed_keys))

    def _parse_message(self, raw: bytes | str) -> dict | None:
        """Parse protobuf market data message into a dict.

        Returns a dict keyed by instrument_key with entries like:
            {
                "instrument_key": "NSE_EQ|INE002A01018",
                "ltp": 2545.50,
                "close": 2530.00,
                "ltt": 1708012345,    # last trade timestamp (epoch ms)
                "ltq": 100,           # last trade quantity
                "open": 2532.00,      # only in full mode
                "high": 2560.00,      # only in full mode
                "low": 2525.00,       # only in full mode
                "volume": 1234567,    # only in full mode
            }

        Returns None if the message cannot be parsed or contains no data.
        """
        if isinstance(raw, str):
            # Initial connection ack or market_info may come as text
            try:
                json.loads(raw)
                return None  # Skip non-data JSON messages
            except json.JSONDecodeError:
                pass
            raw = raw.encode("utf-8")

        self._load_proto()

        if self._proto_module is False:
            # Proto module not available
            logger.debug(
                f"[MarketDataStream] Received {len(raw)} bytes "
                "(no proto parser available)"
            )
            return None

        try:
            return self._parse_with_proto(raw)
        except Exception as e:
            logger.debug(f"[MarketDataStream] Parse error: {e}")
            return None

    def _parse_with_proto(self, raw: bytes) -> dict | None:
        """Parse using the Upstox SDK protobuf module.

        Deserializes the FeedResponse, then converts each Feed entry
        into a flat dict using google.protobuf.json_format for reliable
        field extraction.
        """
        feed_response = self._proto_module.FeedResponse()
        feed_response.ParseFromString(raw)

        results = {}
        for key, feed in feed_response.feeds.items():
            entry: dict[str, Any] = {"instrument_key": key}

            # Determine which Feed variant is set
            feed_union = feed.WhichOneof("FeedUnion")

            if feed_union == "ltpc":
                # LTPC-only mode
                ltpc = feed.ltpc
                entry["ltp"] = ltpc.ltp
                entry["close"] = ltpc.cp
                entry["ltt"] = ltpc.ltt
                entry["ltq"] = ltpc.ltq

            elif feed_union == "fullFeed":
                full_feed = feed.fullFeed
                # FullFeed is a oneof: marketFF or indexFF
                ff_union = full_feed.WhichOneof("FullFeedUnion")

                if ff_union == "marketFF":
                    mff = full_feed.marketFF
                    entry["ltp"] = mff.ltpc.ltp
                    entry["close"] = mff.ltpc.cp
                    entry["ltt"] = mff.ltpc.ltt
                    entry["ltq"] = mff.ltpc.ltq
                    entry["volume"] = mff.vtt
                    entry["oi"] = mff.oi
                    # Extract 1d OHLC if available
                    if mff.HasField("marketOHLC"):
                        for ohlc in mff.marketOHLC.ohlc:
                            if ohlc.interval == "1d":
                                entry["open"] = ohlc.open
                                entry["high"] = ohlc.high
                                entry["low"] = ohlc.low

                elif ff_union == "indexFF":
                    iff = full_feed.indexFF
                    entry["ltp"] = iff.ltpc.ltp
                    entry["close"] = iff.ltpc.cp
                    entry["ltt"] = iff.ltpc.ltt
                    entry["ltq"] = iff.ltpc.ltq
                    # Index has OHLC too
                    if iff.HasField("marketOHLC"):
                        for ohlc in iff.marketOHLC.ohlc:
                            if ohlc.interval == "1d":
                                entry["open"] = ohlc.open
                                entry["high"] = ohlc.high
                                entry["low"] = ohlc.low

            elif feed_union == "firstLevelWithGreeks":
                flwg = feed.firstLevelWithGreeks
                entry["ltp"] = flwg.ltpc.ltp
                entry["close"] = flwg.ltpc.cp
                entry["ltt"] = flwg.ltpc.ltt
                entry["ltq"] = flwg.ltpc.ltq
                entry["volume"] = flwg.vtt
                entry["oi"] = flwg.oi
                entry["iv"] = flwg.iv

            else:
                # Unknown feed variant, skip
                continue

            results[key] = entry

        return results if results else None
