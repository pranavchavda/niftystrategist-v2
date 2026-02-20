"""Tests for WebSocket stream connection management, portfolio, and market data."""
import asyncio
import json

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from websockets.protocol import State as WsState


# ---------------------------------------------------------------------------
# BaseWebSocketStream
# ---------------------------------------------------------------------------


class TestBaseWebSocketStream:
    """Tests for the base connection manager."""

    def _make_stream(self, **kwargs):
        from monitor.streams.connection import BaseWebSocketStream

        class DummyStream(BaseWebSocketStream):
            def _parse_message(self, raw):
                return raw

        defaults = dict(
            name="test",
            get_auth_url=AsyncMock(return_value="wss://example.com"),
            on_message=AsyncMock(),
        )
        defaults.update(kwargs)
        return DummyStream(**defaults)

    def test_initial_state(self):
        stream = self._make_stream()
        assert not stream.connected
        assert stream._running is False
        assert stream._task is None
        assert stream._reconnect_delay == 1.0

    def test_connected_false_when_no_ws(self):
        stream = self._make_stream()
        assert not stream.connected

    def test_connected_false_when_ws_closed(self):
        stream = self._make_stream()
        ws = MagicMock()
        ws.state = WsState.CLOSED
        stream._ws = ws
        assert not stream.connected

    def test_connected_true_when_ws_open(self):
        stream = self._make_stream()
        ws = MagicMock()
        ws.state = WsState.OPEN
        stream._ws = ws
        assert stream.connected

    def test_reconnect_delay_exponential_backoff(self):
        stream = self._make_stream(max_reconnect_delay=16.0)
        assert stream._reconnect_delay == 1.0
        stream._reconnect_delay = min(
            stream._reconnect_delay * 2, stream._max_reconnect_delay
        )
        assert stream._reconnect_delay == 2.0
        stream._reconnect_delay = min(
            stream._reconnect_delay * 2, stream._max_reconnect_delay
        )
        assert stream._reconnect_delay == 4.0
        stream._reconnect_delay = min(
            stream._reconnect_delay * 2, stream._max_reconnect_delay
        )
        assert stream._reconnect_delay == 8.0
        stream._reconnect_delay = min(
            stream._reconnect_delay * 2, stream._max_reconnect_delay
        )
        assert stream._reconnect_delay == 16.0
        # Should cap at max
        stream._reconnect_delay = min(
            stream._reconnect_delay * 2, stream._max_reconnect_delay
        )
        assert stream._reconnect_delay == 16.0

    def test_parse_message_returns_raw(self):
        stream = self._make_stream()
        assert stream._parse_message("hello") == "hello"
        assert stream._parse_message(b"binary") == b"binary"

    @pytest.mark.asyncio
    async def test_start_sets_running(self):
        stream = self._make_stream()
        # Patch _run_loop to avoid actual connection
        with patch.object(stream, "_run_loop", new_callable=AsyncMock):
            await stream.start()
            assert stream._running is True
            assert stream._task is not None
            # Cleanup
            await stream.stop()

    @pytest.mark.asyncio
    async def test_stop_clears_state(self):
        stream = self._make_stream()
        with patch.object(stream, "_run_loop", new_callable=AsyncMock):
            await stream.start()
            await stream.stop()
            assert stream._running is False
            assert stream._task is None

    @pytest.mark.asyncio
    async def test_start_idempotent_when_already_running(self):
        """Calling start() when already running should not create a second task."""
        stream = self._make_stream()
        with patch.object(stream, "_run_loop", new_callable=AsyncMock):
            await stream.start()
            first_task = stream._task
            await stream.start()
            assert stream._task is first_task  # Same task, not replaced
            await stream.stop()

    @pytest.mark.asyncio
    async def test_send_warns_when_not_connected(self, caplog):
        stream = self._make_stream()
        import logging

        with caplog.at_level(logging.WARNING):
            await stream.send("test data")
        assert "not connected" in caplog.text.lower()

    @pytest.mark.asyncio
    async def test_send_delegates_to_ws(self):
        stream = self._make_stream()
        ws = AsyncMock()
        ws.state = WsState.OPEN
        stream._ws = ws
        await stream.send("test data")
        ws.send.assert_called_once_with("test data")

    @pytest.mark.asyncio
    async def test_receive_loop_dispatches_parsed_messages(self):
        on_message = AsyncMock()
        stream = self._make_stream(on_message=on_message)

        # Simulate a WebSocket that yields two messages then stops
        class FakeWS:
            def __init__(self):
                self.messages = ["msg1", "msg2"]
                self._idx = 0

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self._idx >= len(self.messages):
                    raise StopAsyncIteration
                msg = self.messages[self._idx]
                self._idx += 1
                return msg

        fake_ws = FakeWS()
        await stream._receive_loop(fake_ws)
        assert on_message.call_count == 2
        on_message.assert_any_call("msg1")
        on_message.assert_any_call("msg2")

    @pytest.mark.asyncio
    async def test_receive_loop_skips_none_parsed(self):
        """Messages parsed as None should not be dispatched."""
        on_message = AsyncMock()
        stream = self._make_stream(on_message=on_message)

        # Override parse to return None for "skip" messages
        original_parse = stream._parse_message
        stream._parse_message = lambda raw: None if raw == "skip" else raw

        class FakeWS:
            def __init__(self):
                self.messages = ["skip", "keep"]
                self._idx = 0

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self._idx >= len(self.messages):
                    raise StopAsyncIteration
                msg = self.messages[self._idx]
                self._idx += 1
                return msg

        await stream._receive_loop(FakeWS())
        on_message.assert_called_once_with("keep")

    @pytest.mark.asyncio
    async def test_receive_loop_continues_on_callback_error(self, caplog):
        """Errors in on_message should not crash the receive loop."""
        on_message = AsyncMock(side_effect=[Exception("boom"), None])
        stream = self._make_stream(on_message=on_message)

        class FakeWS:
            def __init__(self):
                self.messages = ["msg1", "msg2"]
                self._idx = 0

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self._idx >= len(self.messages):
                    raise StopAsyncIteration
                msg = self.messages[self._idx]
                self._idx += 1
                return msg

        import logging

        with caplog.at_level(logging.ERROR):
            await stream._receive_loop(FakeWS())
        # Both messages should have been attempted
        assert on_message.call_count == 2
        assert "error processing message" in caplog.text.lower()


# ---------------------------------------------------------------------------
# PortfolioStream
# ---------------------------------------------------------------------------


class TestPortfolioStreamParse:
    """Tests for PortfolioStream message parsing."""

    def _make_stream(self):
        from monitor.streams.portfolio import PortfolioStream

        return PortfolioStream(
            access_token="test-token",
            on_message=AsyncMock(),
        )

    def test_parses_json_order_message(self):
        stream = self._make_stream()
        result = stream._parse_message(
            '{"order_id": "123", "status": "complete"}'
        )
        assert result == {"order_id": "123", "status": "complete"}

    def test_parses_bytes_message(self):
        stream = self._make_stream()
        result = stream._parse_message(
            b'{"order_id": "456", "status": "rejected"}'
        )
        assert result == {"order_id": "456", "status": "rejected"}

    def test_skips_empty_dict(self):
        stream = self._make_stream()
        assert stream._parse_message("{}") is None

    def test_skips_empty_string(self):
        stream = self._make_stream()
        assert stream._parse_message("") is None

    def test_skips_invalid_json(self):
        stream = self._make_stream()
        assert stream._parse_message("not json at all") is None

    def test_skips_malformed_bytes(self):
        stream = self._make_stream()
        # Invalid UTF-8 bytes
        assert stream._parse_message(b"\xff\xfe") is None

    def test_parses_complex_order_update(self):
        stream = self._make_stream()
        event = {
            "order_id": "ORD-789",
            "status": "complete",
            "transaction_type": "BUY",
            "quantity": 10,
            "average_price": 2540.50,
            "instrument_token": "NSE_EQ|INE002A01018",
        }
        result = stream._parse_message(json.dumps(event))
        assert result == event

    def test_update_types_stored(self):
        from monitor.streams.portfolio import PortfolioStream

        stream = PortfolioStream(
            access_token="test",
            on_message=AsyncMock(),
            update_types="order,position",
        )
        assert stream._update_types == "order,position"

    def test_default_update_types(self):
        stream = self._make_stream()
        assert stream._update_types == "order,position,holding"


class TestPortfolioStreamAuth:
    """Tests for PortfolioStream authorization."""

    @pytest.mark.asyncio
    async def test_authorize_success(self):
        from monitor.streams.portfolio import PortfolioStream

        stream = PortfolioStream(
            access_token="test-token",
            on_message=AsyncMock(),
        )

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "status": "success",
                "data": {
                    "authorizedRedirectUri": "wss://feed.upstox.com/abc123"
                },
            }
        )

        with patch("aiohttp.ClientSession") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_session.get = MagicMock(return_value=mock_response)
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=False)
            mock_session_cls.return_value = mock_session

            url = await stream._authorize()
            assert url == "wss://feed.upstox.com/abc123"

    @pytest.mark.asyncio
    async def test_authorize_failure(self):
        from monitor.streams.portfolio import PortfolioStream

        stream = PortfolioStream(
            access_token="bad-token",
            on_message=AsyncMock(),
        )

        mock_response = AsyncMock()
        mock_response.status = 401
        mock_response.text = AsyncMock(return_value="Unauthorized")

        with patch("aiohttp.ClientSession") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_session.get = MagicMock(return_value=mock_response)
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=False)
            mock_session_cls.return_value = mock_session

            with pytest.raises(ConnectionError, match="401"):
                await stream._authorize()

    @pytest.mark.asyncio
    async def test_authorize_missing_uri(self):
        from monitor.streams.portfolio import PortfolioStream

        stream = PortfolioStream(
            access_token="test-token",
            on_message=AsyncMock(),
        )

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={"status": "success", "data": {}}
        )

        with patch("aiohttp.ClientSession") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_session.get = MagicMock(return_value=mock_response)
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=False)
            mock_session_cls.return_value = mock_session

            with pytest.raises(ConnectionError, match="No redirect URI"):
                await stream._authorize()


# ---------------------------------------------------------------------------
# MarketDataStream
# ---------------------------------------------------------------------------


class TestMarketDataStreamSubscription:
    """Tests for MarketDataStream subscription management."""

    def _make_stream(self, mode="ltpc"):
        from monitor.streams.market_data import MarketDataStream

        return MarketDataStream(
            access_token="test-token",
            on_message=AsyncMock(),
            mode=mode,
        )

    def test_initial_state(self):
        stream = self._make_stream()
        assert stream._subscribed_keys == set()
        assert stream._mode == "ltpc"
        assert stream._proto_module is None

    def test_subscribe_tracks_keys(self):
        stream = self._make_stream()
        stream._subscribed_keys.add("NSE_EQ|INE002A01018")
        stream._subscribed_keys.add("NSE_EQ|INE009A01021")
        assert "NSE_EQ|INE002A01018" in stream._subscribed_keys
        assert "NSE_EQ|INE009A01021" in stream._subscribed_keys
        assert len(stream._subscribed_keys) == 2

    def test_unsubscribe_removes_keys(self):
        stream = self._make_stream()
        stream._subscribed_keys = {"NSE_EQ|A", "NSE_EQ|B", "NSE_EQ|C"}
        stream._subscribed_keys -= {"NSE_EQ|A", "NSE_EQ|C"}
        assert stream._subscribed_keys == {"NSE_EQ|B"}

    def test_mode_stored(self):
        stream = self._make_stream(mode="full")
        assert stream._mode == "full"

    @pytest.mark.asyncio
    async def test_subscribe_sends_binary_json(self):
        stream = self._make_stream()
        stream._ws = AsyncMock()
        stream._ws.state = WsState.OPEN

        await stream.subscribe(["NSE_EQ|INE002A01018"])

        assert "NSE_EQ|INE002A01018" in stream._subscribed_keys

        # Verify the send was called with binary-encoded JSON
        stream._ws.send.assert_called_once()
        sent_data = stream._ws.send.call_args[0][0]
        assert isinstance(sent_data, bytes)
        parsed = json.loads(sent_data.decode("utf-8"))
        assert parsed["method"] == "sub"
        assert parsed["data"]["mode"] == "ltpc"
        assert "NSE_EQ|INE002A01018" in parsed["data"]["instrumentKeys"]

    @pytest.mark.asyncio
    async def test_subscribe_empty_list_noop(self):
        stream = self._make_stream()
        stream._ws = AsyncMock()
        stream._ws.state = WsState.OPEN

        await stream.subscribe([])
        stream._ws.send.assert_not_called()

    @pytest.mark.asyncio
    async def test_unsubscribe_sends_unsub_message(self):
        stream = self._make_stream()
        stream._ws = AsyncMock()
        stream._ws.state = WsState.OPEN
        stream._subscribed_keys = {"NSE_EQ|A", "NSE_EQ|B"}

        await stream.unsubscribe(["NSE_EQ|A"])

        assert stream._subscribed_keys == {"NSE_EQ|B"}
        stream._ws.send.assert_called_once()
        sent_data = stream._ws.send.call_args[0][0]
        parsed = json.loads(sent_data.decode("utf-8"))
        assert parsed["method"] == "unsub"

    @pytest.mark.asyncio
    async def test_change_mode_sends_message(self):
        stream = self._make_stream(mode="ltpc")
        stream._ws = AsyncMock()
        stream._ws.state = WsState.OPEN

        await stream.change_mode(["NSE_EQ|A"], "full")

        assert stream._mode == "full"
        stream._ws.send.assert_called_once()
        sent_data = stream._ws.send.call_args[0][0]
        parsed = json.loads(sent_data.decode("utf-8"))
        assert parsed["method"] == "change_mode"
        assert parsed["data"]["mode"] == "full"

    @pytest.mark.asyncio
    async def test_on_connected_resubscribes(self):
        stream = self._make_stream()
        stream._ws = AsyncMock()
        stream._ws.state = WsState.OPEN
        stream._subscribed_keys = {"NSE_EQ|A", "NSE_EQ|B"}

        ws_mock = AsyncMock()
        await stream._on_connected(ws_mock)

        # Should have called send via subscribe()
        stream._ws.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_connected_no_keys_no_subscribe(self):
        stream = self._make_stream()
        stream._ws = AsyncMock()
        stream._ws.state = WsState.OPEN

        ws_mock = AsyncMock()
        await stream._on_connected(ws_mock)

        stream._ws.send.assert_not_called()


class TestMarketDataStreamParse:
    """Tests for MarketDataStream message parsing."""

    def _make_stream(self):
        from monitor.streams.market_data import MarketDataStream

        return MarketDataStream(
            access_token="test-token",
            on_message=AsyncMock(),
            mode="ltpc",
        )

    def test_json_string_returns_none(self):
        """JSON string messages (connection ack) should be skipped."""
        stream = self._make_stream()
        result = stream._parse_message('{"type": "connected"}')
        assert result is None

    def test_proto_module_lazy_loaded(self):
        """Proto module should not be loaded until first binary message."""
        stream = self._make_stream()
        assert stream._proto_module is None

    def test_parse_with_proto_ltpc_mode(self):
        """Test parsing a real protobuf LTPC message."""
        from upstox_client.feeder.proto import MarketDataFeedV3_pb2 as proto

        stream = self._make_stream()
        stream._proto_module = proto

        # Build a FeedResponse with LTPC data
        feed_response = proto.FeedResponse()
        feed_response.type = proto.Type.Value("live_feed")
        feed_response.currentTs = 1708012345

        ltpc = proto.LTPC()
        ltpc.ltp = 2545.50
        ltpc.cp = 2530.00
        ltpc.ltt = 1708012340
        ltpc.ltq = 100

        feed = proto.Feed()
        feed.ltpc.CopyFrom(ltpc)

        feed_response.feeds["NSE_EQ|INE002A01018"].CopyFrom(feed)

        raw = feed_response.SerializeToString()
        result = stream._parse_message(raw)

        assert result is not None
        assert "NSE_EQ|INE002A01018" in result
        entry = result["NSE_EQ|INE002A01018"]
        assert entry["ltp"] == 2545.50
        assert entry["close"] == 2530.00
        assert entry["ltt"] == 1708012340
        assert entry["ltq"] == 100
        assert entry["instrument_key"] == "NSE_EQ|INE002A01018"

    def test_parse_with_proto_full_market_feed(self):
        """Test parsing a full market feed with OHLC data."""
        from upstox_client.feeder.proto import MarketDataFeedV3_pb2 as proto

        stream = self._make_stream()
        stream._proto_module = proto

        feed_response = proto.FeedResponse()
        feed_response.type = proto.Type.Value("live_feed")

        # Build MarketFullFeed
        mff = proto.MarketFullFeed()
        mff.ltpc.ltp = 2545.50
        mff.ltpc.cp = 2530.00
        mff.ltpc.ltt = 1708012340
        mff.ltpc.ltq = 100
        mff.vtt = 5000000
        mff.oi = 150000.0

        ohlc_1d = mff.marketOHLC.ohlc.add()
        ohlc_1d.interval = "1d"
        ohlc_1d.open = 2532.00
        ohlc_1d.high = 2560.00
        ohlc_1d.low = 2525.00
        ohlc_1d.close = 2530.00
        ohlc_1d.vol = 5000000

        full_feed = proto.FullFeed()
        full_feed.marketFF.CopyFrom(mff)

        feed = proto.Feed()
        feed.fullFeed.CopyFrom(full_feed)

        feed_response.feeds["NSE_EQ|INE002A01018"].CopyFrom(feed)

        raw = feed_response.SerializeToString()
        result = stream._parse_message(raw)

        assert result is not None
        entry = result["NSE_EQ|INE002A01018"]
        assert entry["ltp"] == 2545.50
        assert entry["close"] == 2530.00
        assert entry["open"] == 2532.00
        assert entry["high"] == 2560.00
        assert entry["low"] == 2525.00
        assert entry["volume"] == 5000000
        assert entry["oi"] == 150000.0

    def test_parse_with_proto_index_feed(self):
        """Test parsing an index full feed."""
        from upstox_client.feeder.proto import MarketDataFeedV3_pb2 as proto

        stream = self._make_stream()
        stream._proto_module = proto

        feed_response = proto.FeedResponse()
        feed_response.type = proto.Type.Value("live_feed")

        iff = proto.IndexFullFeed()
        iff.ltpc.ltp = 22500.00
        iff.ltpc.cp = 22450.00
        iff.ltpc.ltt = 1708012340
        iff.ltpc.ltq = 0

        ohlc_1d = iff.marketOHLC.ohlc.add()
        ohlc_1d.interval = "1d"
        ohlc_1d.open = 22460.00
        ohlc_1d.high = 22550.00
        ohlc_1d.low = 22400.00
        ohlc_1d.close = 22450.00
        ohlc_1d.vol = 0

        full_feed = proto.FullFeed()
        full_feed.indexFF.CopyFrom(iff)

        feed = proto.Feed()
        feed.fullFeed.CopyFrom(full_feed)

        feed_response.feeds["NSE_INDEX|Nifty 50"].CopyFrom(feed)

        raw = feed_response.SerializeToString()
        result = stream._parse_message(raw)

        assert result is not None
        entry = result["NSE_INDEX|Nifty 50"]
        assert entry["ltp"] == 22500.00
        assert entry["close"] == 22450.00
        assert entry["open"] == 22460.00
        assert entry["high"] == 22550.00
        assert entry["low"] == 22400.00

    def test_parse_multiple_instruments(self):
        """Test parsing a message with multiple instruments."""
        from upstox_client.feeder.proto import MarketDataFeedV3_pb2 as proto

        stream = self._make_stream()
        stream._proto_module = proto

        feed_response = proto.FeedResponse()
        feed_response.type = proto.Type.Value("live_feed")

        for key, ltp, cp in [
            ("NSE_EQ|INE002A01018", 2545.50, 2530.00),
            ("NSE_EQ|INE009A01021", 1800.25, 1795.00),
        ]:
            ltpc = proto.LTPC()
            ltpc.ltp = ltp
            ltpc.cp = cp
            feed = proto.Feed()
            feed.ltpc.CopyFrom(ltpc)
            feed_response.feeds[key].CopyFrom(feed)

        raw = feed_response.SerializeToString()
        result = stream._parse_message(raw)

        assert result is not None
        assert len(result) == 2
        assert result["NSE_EQ|INE002A01018"]["ltp"] == 2545.50
        assert result["NSE_EQ|INE009A01021"]["ltp"] == 1800.25

    def test_parse_empty_feed_returns_none(self):
        """A FeedResponse with no feeds should return None."""
        from upstox_client.feeder.proto import MarketDataFeedV3_pb2 as proto

        stream = self._make_stream()
        stream._proto_module = proto

        feed_response = proto.FeedResponse()
        feed_response.type = proto.Type.Value("live_feed")
        # No feeds added

        raw = feed_response.SerializeToString()
        result = stream._parse_message(raw)
        assert result is None

    def test_parse_invalid_binary_returns_none(self):
        """Invalid binary data should return None, not crash."""
        stream = self._make_stream()
        # Force proto module to load
        stream._load_proto()
        result = stream._parse_message(b"\x00\x01\x02invalid")
        # Should return None (proto parse error caught)
        assert result is None

    def test_parse_with_proto_unavailable(self):
        """When proto module is False, should return None."""
        stream = self._make_stream()
        stream._proto_module = False
        result = stream._parse_message(b"\x00\x01\x02data")
        assert result is None


class TestMarketDataStreamAuth:
    """Tests for MarketDataStream authorization."""

    @pytest.mark.asyncio
    async def test_authorize_success(self):
        from monitor.streams.market_data import MarketDataStream

        stream = MarketDataStream(
            access_token="test-token",
            on_message=AsyncMock(),
        )

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "status": "success",
                "data": {
                    "authorizedRedirectUri": "wss://feed.upstox.com/v3/abc"
                },
            }
        )

        with patch("aiohttp.ClientSession") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_session.get = MagicMock(return_value=mock_response)
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=False)
            mock_session_cls.return_value = mock_session

            url = await stream._authorize()
            assert url == "wss://feed.upstox.com/v3/abc"

    @pytest.mark.asyncio
    async def test_authorize_failure(self):
        from monitor.streams.market_data import MarketDataStream

        stream = MarketDataStream(
            access_token="bad-token",
            on_message=AsyncMock(),
        )

        mock_response = AsyncMock()
        mock_response.status = 403
        mock_response.text = AsyncMock(return_value="Forbidden")

        with patch("aiohttp.ClientSession") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_session.get = MagicMock(return_value=mock_response)
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=False)
            mock_session_cls.return_value = mock_session

            with pytest.raises(ConnectionError, match="403"):
                await stream._authorize()
