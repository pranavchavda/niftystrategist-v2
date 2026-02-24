"""Tests for stream auth failure detection + TOTP auto-refresh in daemon."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from monitor.models import MonitorRule
from monitor.streams.connection import AuthenticationError


# ── Helpers ──────────────────────────────────────────────────────────


def _make_rule(
    rule_id: int = 1,
    user_id: int = 999,
    trigger_type: str = "price",
    instrument_token: str = "NSE_EQ|INE002A01018",
) -> MonitorRule:
    return MonitorRule(
        id=rule_id,
        user_id=user_id,
        name=f"test-rule-{rule_id}",
        trigger_type=trigger_type,
        trigger_config={"condition": "gte", "price": 100.0, "reference": "ltp"},
        action_type="place_order",
        action_config={
            "symbol": "RELIANCE",
            "transaction_type": "BUY",
            "quantity": 1,
            "order_type": "MARKET",
            "product": "I",
            "price": None,
        },
        instrument_token=instrument_token,
    )


def _mock_aiohttp_response(status: int, text: str = "", json_data: dict | None = None):
    """Create a mock aiohttp response with context manager support."""
    mock_response = AsyncMock()
    mock_response.status = status
    mock_response.text = AsyncMock(return_value=text)
    if json_data is not None:
        mock_response.json = AsyncMock(return_value=json_data)
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=False)
    return mock_response


def _mock_aiohttp_session(response):
    """Create a mock aiohttp.ClientSession that returns the given response."""
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.get = MagicMock(return_value=response)
    return mock_session


# ══════════════════════════════════════════════════════════════════════
# Stream-level tests
# ══════════════════════════════════════════════════════════════════════


class TestAuthErrorStopsRetryLoop:
    """AuthenticationError in _run_loop() should break the loop, no retry."""

    @pytest.mark.asyncio
    async def test_auth_error_stops_retry_loop(self):
        from monitor.streams.connection import BaseWebSocketStream

        class FailStream(BaseWebSocketStream):
            def _parse_message(self, raw):
                return raw

        call_count = 0

        async def auth_url_that_fails():
            nonlocal call_count
            call_count += 1
            raise AuthenticationError("Token expired")

        stream = FailStream(
            name="test",
            get_auth_url=auth_url_that_fails,
            on_message=AsyncMock(),
        )
        stream._running = True
        await stream._run_loop()

        # Should only be called once (no retry)
        assert call_count == 1
        assert stream._running is False

    @pytest.mark.asyncio
    async def test_auth_error_fires_callback(self):
        from monitor.streams.connection import BaseWebSocketStream

        class FailStream(BaseWebSocketStream):
            def _parse_message(self, raw):
                return raw

        callback = AsyncMock()

        async def auth_url_that_fails():
            raise AuthenticationError("Token expired")

        stream = FailStream(
            name="test",
            get_auth_url=auth_url_that_fails,
            on_message=AsyncMock(),
            on_auth_failure=callback,
        )
        stream._running = True
        await stream._run_loop()

        callback.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_auth_error_no_callback_still_stops(self):
        from monitor.streams.connection import BaseWebSocketStream

        class FailStream(BaseWebSocketStream):
            def _parse_message(self, raw):
                return raw

        async def auth_url_that_fails():
            raise AuthenticationError("Token expired")

        stream = FailStream(
            name="test",
            get_auth_url=auth_url_that_fails,
            on_message=AsyncMock(),
            # No on_auth_failure callback
        )
        stream._running = True
        await stream._run_loop()

        assert stream._running is False

    @pytest.mark.asyncio
    async def test_generic_error_still_retries(self):
        """ConnectionError should trigger normal backoff retry."""
        from monitor.streams.connection import BaseWebSocketStream

        class FailStream(BaseWebSocketStream):
            def _parse_message(self, raw):
                return raw

        call_count = 0

        async def auth_url_that_fails():
            nonlocal call_count
            call_count += 1
            if call_count >= 3:
                # Stop after 3 attempts to prevent infinite loop
                raise asyncio.CancelledError()
            raise ConnectionError("Network blip")

        stream = FailStream(
            name="test",
            get_auth_url=auth_url_that_fails,
            on_message=AsyncMock(),
            max_reconnect_delay=0.01,  # Fast for test
        )
        stream._running = True

        with patch("asyncio.sleep", new_callable=AsyncMock):
            await stream._run_loop()

        # Should have retried (called more than once)
        assert call_count >= 2


class TestMarketDataAuth401:
    """MarketDataStream._authorize() should raise AuthenticationError on 401/403."""

    @pytest.mark.asyncio
    async def test_market_data_401_raises_auth_error(self):
        from monitor.streams.market_data import MarketDataStream

        stream = MarketDataStream(
            access_token="expired-token",
            on_message=AsyncMock(),
        )

        response = _mock_aiohttp_response(401, "Unauthorized")

        with patch("aiohttp.ClientSession", return_value=_mock_aiohttp_session(response)):
            with pytest.raises(AuthenticationError, match="401"):
                await stream._authorize()

    @pytest.mark.asyncio
    async def test_market_data_403_raises_auth_error(self):
        from monitor.streams.market_data import MarketDataStream

        stream = MarketDataStream(
            access_token="expired-token",
            on_message=AsyncMock(),
        )

        response = _mock_aiohttp_response(403, "Forbidden")

        with patch("aiohttp.ClientSession", return_value=_mock_aiohttp_session(response)):
            with pytest.raises(AuthenticationError, match="403"):
                await stream._authorize()

    @pytest.mark.asyncio
    async def test_market_data_500_raises_connection_error(self):
        from monitor.streams.market_data import MarketDataStream

        stream = MarketDataStream(
            access_token="valid-token",
            on_message=AsyncMock(),
        )

        response = _mock_aiohttp_response(500, "Internal Server Error")

        with patch("aiohttp.ClientSession", return_value=_mock_aiohttp_session(response)):
            with pytest.raises(ConnectionError, match="500"):
                # Should be ConnectionError, NOT AuthenticationError
                await stream._authorize()


class TestPortfolioAuth401:
    """PortfolioStream._authorize() should raise AuthenticationError on 401/403."""

    @pytest.mark.asyncio
    async def test_portfolio_401_raises_auth_error(self):
        from monitor.streams.portfolio import PortfolioStream

        stream = PortfolioStream(
            access_token="expired-token",
            on_message=AsyncMock(),
        )

        response = _mock_aiohttp_response(401, "Unauthorized")

        with patch("aiohttp.ClientSession", return_value=_mock_aiohttp_session(response)):
            with pytest.raises(AuthenticationError, match="401"):
                await stream._authorize()

    @pytest.mark.asyncio
    async def test_portfolio_403_raises_auth_error(self):
        from monitor.streams.portfolio import PortfolioStream

        stream = PortfolioStream(
            access_token="expired-token",
            on_message=AsyncMock(),
        )

        response = _mock_aiohttp_response(403, "Forbidden")

        with patch("aiohttp.ClientSession", return_value=_mock_aiohttp_session(response)):
            with pytest.raises(AuthenticationError, match="403"):
                await stream._authorize()


# ══════════════════════════════════════════════════════════════════════
# UserManager tests
# ══════════════════════════════════════════════════════════════════════


class TestUserManagerAuthFailure:

    @pytest.mark.asyncio
    @patch("monitor.user_manager.MarketDataStream")
    @patch("monitor.user_manager.PortfolioStream")
    async def test_start_user_passes_auth_failure_callback(
        self, MockPortfolio, MockMarket
    ):
        """Streams should receive on_auth_failure when UserManager has one."""
        from monitor.user_manager import UserManager

        MockPortfolio.return_value = AsyncMock()
        MockMarket.return_value = AsyncMock()

        on_auth = AsyncMock()
        mgr = UserManager(
            on_tick=AsyncMock(),
            on_portfolio_event=AsyncMock(),
            on_auth_failure=on_auth,
        )

        rules = [_make_rule(1)]
        await mgr.start_user(999, "test-token", rules)

        # Both streams should have received on_auth_failure kwarg
        portfolio_kwargs = MockPortfolio.call_args[1]
        market_kwargs = MockMarket.call_args[1]
        assert portfolio_kwargs["on_auth_failure"] is not None
        assert market_kwargs["on_auth_failure"] is not None

    @pytest.mark.asyncio
    @patch("monitor.user_manager.MarketDataStream")
    @patch("monitor.user_manager.PortfolioStream")
    async def test_auth_failure_callback_forwards_user_id(
        self, MockPortfolio, MockMarket
    ):
        """The closure should call on_auth_failure with the correct user_id."""
        from monitor.user_manager import UserManager

        MockPortfolio.return_value = AsyncMock()
        MockMarket.return_value = AsyncMock()

        on_auth = AsyncMock()
        mgr = UserManager(
            on_tick=AsyncMock(),
            on_portfolio_event=AsyncMock(),
            on_auth_failure=on_auth,
        )

        rules = [_make_rule(1)]
        await mgr.start_user(999, "test-token", rules)

        # Get the closure that was passed to the stream
        market_kwargs = MockMarket.call_args[1]
        closure = market_kwargs["on_auth_failure"]

        # Call the closure and verify it forwards user_id
        await closure()
        on_auth.assert_awaited_once_with(999)

    @pytest.mark.asyncio
    @patch("monitor.user_manager.MarketDataStream")
    @patch("monitor.user_manager.PortfolioStream")
    async def test_no_auth_callback_passes_none(self, MockPortfolio, MockMarket):
        """When UserManager has no on_auth_failure, streams get None."""
        from monitor.user_manager import UserManager

        MockPortfolio.return_value = AsyncMock()
        MockMarket.return_value = AsyncMock()

        mgr = UserManager(
            on_tick=AsyncMock(),
            on_portfolio_event=AsyncMock(),
            # No on_auth_failure
        )

        rules = [_make_rule(1)]
        await mgr.start_user(999, "test-token", rules)

        portfolio_kwargs = MockPortfolio.call_args[1]
        market_kwargs = MockMarket.call_args[1]
        assert portfolio_kwargs["on_auth_failure"] is None
        assert market_kwargs["on_auth_failure"] is None


# ══════════════════════════════════════════════════════════════════════
# Daemon tests
# ══════════════════════════════════════════════════════════════════════


class TestDaemonAuthFailure:

    @pytest.mark.asyncio
    async def test_on_stream_auth_failure_refreshes_and_restarts(self):
        """New token obtained → restarts streams."""
        from monitor.daemon import MonitorDaemon

        daemon = MonitorDaemon()
        daemon._access_tokens = {999: "stale-token"}
        daemon._rules_by_user = {999: [_make_rule(1)]}
        daemon._user_manager = AsyncMock()
        daemon._user_manager.get_session.return_value = None

        with patch.object(
            daemon, "_load_access_token",
            new_callable=AsyncMock,
            return_value="fresh-token",
        ):
            await daemon._on_stream_auth_failure(999)

        # Should have stopped and restarted
        daemon._user_manager.stop_user.assert_awaited_once_with(999)
        daemon._user_manager.start_user.assert_awaited_once()
        call_args = daemon._user_manager.start_user.call_args
        assert call_args[0][1] == "fresh-token"
        assert daemon._access_tokens[999] == "fresh-token"

    @pytest.mark.asyncio
    async def test_on_stream_auth_failure_refresh_fails_stays_stopped(self):
        """No token returned → user stays stopped."""
        from monitor.daemon import MonitorDaemon

        daemon = MonitorDaemon()
        daemon._access_tokens = {999: "stale-token"}
        daemon._rules_by_user = {999: [_make_rule(1)]}
        daemon._user_manager = AsyncMock()

        with patch.object(
            daemon, "_load_access_token",
            new_callable=AsyncMock,
            return_value=None,
        ):
            await daemon._on_stream_auth_failure(999)

        daemon._user_manager.stop_user.assert_awaited_once_with(999)
        daemon._user_manager.start_user.assert_not_awaited()
        assert 999 not in daemon._access_tokens

    @pytest.mark.asyncio
    async def test_on_stream_auth_failure_same_token_stays_stopped(self):
        """Same stale token returned → user stays stopped."""
        from monitor.daemon import MonitorDaemon

        daemon = MonitorDaemon()
        daemon._access_tokens = {999: "stale-token"}
        daemon._rules_by_user = {999: [_make_rule(1)]}
        daemon._user_manager = AsyncMock()

        with patch.object(
            daemon, "_load_access_token",
            new_callable=AsyncMock,
            return_value="stale-token",  # Same token
        ):
            await daemon._on_stream_auth_failure(999)

        daemon._user_manager.stop_user.assert_awaited_once_with(999)
        daemon._user_manager.start_user.assert_not_awaited()
        assert 999 not in daemon._access_tokens

    @pytest.mark.asyncio
    async def test_concurrent_auth_failures_deduplicated(self):
        """Two concurrent auth failures for same user → only 1 refresh."""
        from monitor.daemon import MonitorDaemon

        daemon = MonitorDaemon()
        daemon._access_tokens = {999: "stale-token"}
        daemon._rules_by_user = {999: [_make_rule(1)]}
        daemon._user_manager = AsyncMock()

        load_call_count = 0

        async def slow_load(user_id):
            nonlocal load_call_count
            load_call_count += 1
            await asyncio.sleep(0.05)  # Simulate work
            return "fresh-token"

        with patch.object(daemon, "_load_access_token", side_effect=slow_load):
            # Fire both concurrently
            await asyncio.gather(
                daemon._on_stream_auth_failure(999),
                daemon._on_stream_auth_failure(999),
            )

        # Only one refresh should have happened
        assert load_call_count == 1

    @pytest.mark.asyncio
    async def test_daemon_passes_on_auth_failure_to_user_manager(self):
        """MonitorDaemon wires _on_stream_auth_failure to UserManager."""
        from monitor.daemon import MonitorDaemon

        daemon = MonitorDaemon()
        assert daemon._user_manager._on_auth_failure is not None
