"""Tests for UserManager — per-user session lifecycle for the trade monitor."""
from __future__ import annotations

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from monitor.models import MonitorRule


# ── Helpers ──────────────────────────────────────────────────────────


def _make_rule(
    rule_id: int = 1,
    trigger_type: str = "price",
    instrument_token: str = "NSE_EQ|INE002A01018",
    trigger_config: dict | None = None,
) -> MonitorRule:
    """Create a minimal MonitorRule for testing."""
    if trigger_config is None:
        if trigger_type == "price":
            trigger_config = {"condition": "gte", "price": 100.0, "reference": "ltp"}
        elif trigger_type == "indicator":
            trigger_config = {
                "indicator": "rsi",
                "timeframe": "5m",
                "condition": "lte",
                "value": 30.0,
                "params": {"period": 14},
            }
        elif trigger_type == "time":
            trigger_config = {"at": "09:30", "on_days": ["mon", "tue", "wed", "thu", "fri"]}
        elif trigger_type == "order_status":
            trigger_config = {"order_id": "ORD-123", "status": "complete"}
        else:
            trigger_config = {}
    return MonitorRule(
        id=rule_id,
        user_id=999,
        name=f"test-rule-{rule_id}",
        trigger_type=trigger_type,
        trigger_config=trigger_config,
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


def _make_compound_rule(
    rule_id: int = 10,
    instrument_token: str = "NSE_EQ|INE002A01018",
) -> MonitorRule:
    """Create a compound rule referencing two different instruments via sub-conditions."""
    return MonitorRule(
        id=rule_id,
        user_id=999,
        name="compound-test",
        trigger_type="compound",
        trigger_config={
            "operator": "and",
            "conditions": [
                {
                    "type": "price",
                    "condition": "gte",
                    "price": 100.0,
                    "reference": "ltp",
                },
                {
                    "type": "indicator",
                    "indicator": "rsi",
                    "timeframe": "5m",
                    "condition": "lte",
                    "value": 30.0,
                    "params": {},
                },
            ],
        },
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


# ── Test: extract_instruments_from_rules ─────────────────────────────


class TestExtractInstruments:
    """Test the helper that extracts instrument tokens from mixed rule types."""

    def test_price_rules(self):
        from monitor.user_manager import extract_instruments_from_rules

        rules = [
            _make_rule(1, "price", "NSE_EQ|A"),
            _make_rule(2, "price", "NSE_EQ|B"),
        ]
        instruments = extract_instruments_from_rules(rules)
        assert instruments == {"NSE_EQ|A", "NSE_EQ|B"}

    def test_indicator_rules(self):
        from monitor.user_manager import extract_instruments_from_rules

        rules = [
            _make_rule(1, "indicator", "NSE_EQ|A"),
        ]
        instruments = extract_instruments_from_rules(rules)
        assert instruments == {"NSE_EQ|A"}

    def test_time_rule_has_no_instrument(self):
        from monitor.user_manager import extract_instruments_from_rules

        rules = [
            _make_rule(1, "time", instrument_token=None),
        ]
        instruments = extract_instruments_from_rules(rules)
        assert instruments == set()

    def test_order_status_rule_has_no_instrument(self):
        from monitor.user_manager import extract_instruments_from_rules

        rules = [
            _make_rule(1, "order_status", instrument_token=None),
        ]
        instruments = extract_instruments_from_rules(rules)
        assert instruments == set()

    def test_compound_rule_uses_parent_instrument(self):
        from monitor.user_manager import extract_instruments_from_rules

        rules = [_make_compound_rule(10, "NSE_EQ|COMP")]
        instruments = extract_instruments_from_rules(rules)
        assert "NSE_EQ|COMP" in instruments

    def test_mixed_rules_deduplicates(self):
        from monitor.user_manager import extract_instruments_from_rules

        rules = [
            _make_rule(1, "price", "NSE_EQ|A"),
            _make_rule(2, "indicator", "NSE_EQ|A"),
            _make_rule(3, "price", "NSE_EQ|B"),
        ]
        instruments = extract_instruments_from_rules(rules)
        assert instruments == {"NSE_EQ|A", "NSE_EQ|B"}


# ── Test: start_user ─────────────────────────────────────────────────


class TestStartUser:

    @pytest.mark.asyncio
    @patch("monitor.user_manager.MarketDataStream")
    @patch("monitor.user_manager.PortfolioStream")
    async def test_creates_session(self, MockPortfolio, MockMarket):
        from monitor.user_manager import UserManager

        MockPortfolio.return_value = AsyncMock()
        MockMarket.return_value = AsyncMock()

        on_tick = AsyncMock()
        on_portfolio = AsyncMock()
        mgr = UserManager(on_tick=on_tick, on_portfolio_event=on_portfolio)

        rules = [_make_rule(1, "price", "NSE_EQ|A")]
        await mgr.start_user(999, "test-token", rules)

        session = mgr.get_session(999)
        assert session is not None
        assert session.user_id == 999
        assert session.access_token == "test-token"
        assert len(session.rules) == 1

    @pytest.mark.asyncio
    @patch("monitor.user_manager.MarketDataStream")
    @patch("monitor.user_manager.PortfolioStream")
    async def test_starts_both_streams(self, MockPortfolio, MockMarket):
        from monitor.user_manager import UserManager

        mock_portfolio_instance = AsyncMock()
        mock_market_instance = AsyncMock()
        MockPortfolio.return_value = mock_portfolio_instance
        MockMarket.return_value = mock_market_instance

        mgr = UserManager(on_tick=AsyncMock(), on_portfolio_event=AsyncMock())

        rules = [_make_rule(1, "price", "NSE_EQ|A")]
        await mgr.start_user(999, "test-token", rules)

        mock_portfolio_instance.start.assert_awaited_once()
        mock_market_instance.start.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("monitor.user_manager.MarketDataStream")
    @patch("monitor.user_manager.PortfolioStream")
    async def test_subscribes_instruments_from_rules(self, MockPortfolio, MockMarket):
        from monitor.user_manager import UserManager

        mock_market_instance = AsyncMock()
        MockPortfolio.return_value = AsyncMock()
        MockMarket.return_value = mock_market_instance

        mgr = UserManager(on_tick=AsyncMock(), on_portfolio_event=AsyncMock())

        rules = [
            _make_rule(1, "price", "NSE_EQ|A"),
            _make_rule(2, "price", "NSE_EQ|B"),
        ]
        await mgr.start_user(999, "test-token", rules)

        mock_market_instance.subscribe.assert_awaited_once()
        subscribed = set(mock_market_instance.subscribe.call_args[0][0])
        assert subscribed == {"NSE_EQ|A", "NSE_EQ|B"}


# ── Test: stop_user ──────────────────────────────────────────────────


class TestStopUser:

    @pytest.mark.asyncio
    @patch("monitor.user_manager.MarketDataStream")
    @patch("monitor.user_manager.PortfolioStream")
    async def test_stops_both_streams(self, MockPortfolio, MockMarket):
        from monitor.user_manager import UserManager

        mock_portfolio_instance = AsyncMock()
        mock_market_instance = AsyncMock()
        MockPortfolio.return_value = mock_portfolio_instance
        MockMarket.return_value = mock_market_instance

        mgr = UserManager(on_tick=AsyncMock(), on_portfolio_event=AsyncMock())
        await mgr.start_user(999, "test-token", [_make_rule(1, "price", "NSE_EQ|A")])
        await mgr.stop_user(999)

        mock_portfolio_instance.stop.assert_awaited_once()
        mock_market_instance.stop.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("monitor.user_manager.MarketDataStream")
    @patch("monitor.user_manager.PortfolioStream")
    async def test_removes_session(self, MockPortfolio, MockMarket):
        from monitor.user_manager import UserManager

        MockPortfolio.return_value = AsyncMock()
        MockMarket.return_value = AsyncMock()

        mgr = UserManager(on_tick=AsyncMock(), on_portfolio_event=AsyncMock())
        await mgr.start_user(999, "test-token", [_make_rule(1, "price", "NSE_EQ|A")])
        assert mgr.get_session(999) is not None

        await mgr.stop_user(999)
        assert mgr.get_session(999) is None

    @pytest.mark.asyncio
    async def test_stop_nonexistent_user_is_noop(self):
        from monitor.user_manager import UserManager

        mgr = UserManager(on_tick=AsyncMock(), on_portfolio_event=AsyncMock())
        # Should not raise
        await mgr.stop_user(999)


# ── Test: sync_rules ─────────────────────────────────────────────────


class TestSyncRules:

    @pytest.mark.asyncio
    @patch("monitor.user_manager.MarketDataStream")
    @patch("monitor.user_manager.PortfolioStream")
    async def test_adds_new_subscriptions(self, MockPortfolio, MockMarket):
        from monitor.user_manager import UserManager

        mock_market_instance = AsyncMock()
        MockPortfolio.return_value = AsyncMock()
        MockMarket.return_value = mock_market_instance

        mgr = UserManager(on_tick=AsyncMock(), on_portfolio_event=AsyncMock())

        # Start with one instrument
        rules_v1 = [_make_rule(1, "price", "NSE_EQ|A")]
        await mgr.start_user(999, "test-token", rules_v1)
        mock_market_instance.subscribe.reset_mock()

        # Sync with an additional instrument
        rules_v2 = [
            _make_rule(1, "price", "NSE_EQ|A"),
            _make_rule(2, "price", "NSE_EQ|B"),
        ]
        await mgr.sync_rules(999, rules_v2)

        # Should have subscribed to the new instrument only
        mock_market_instance.subscribe.assert_awaited_once()
        new_keys = set(mock_market_instance.subscribe.call_args[0][0])
        assert new_keys == {"NSE_EQ|B"}

    @pytest.mark.asyncio
    @patch("monitor.user_manager.MarketDataStream")
    @patch("monitor.user_manager.PortfolioStream")
    async def test_removes_old_subscriptions(self, MockPortfolio, MockMarket):
        from monitor.user_manager import UserManager

        mock_market_instance = AsyncMock()
        MockPortfolio.return_value = AsyncMock()
        MockMarket.return_value = mock_market_instance

        mgr = UserManager(on_tick=AsyncMock(), on_portfolio_event=AsyncMock())

        # Start with two instruments
        rules_v1 = [
            _make_rule(1, "price", "NSE_EQ|A"),
            _make_rule(2, "price", "NSE_EQ|B"),
        ]
        await mgr.start_user(999, "test-token", rules_v1)
        mock_market_instance.unsubscribe.reset_mock()

        # Sync with only one instrument (removed B)
        rules_v2 = [_make_rule(1, "price", "NSE_EQ|A")]
        await mgr.sync_rules(999, rules_v2)

        mock_market_instance.unsubscribe.assert_awaited_once()
        removed_keys = set(mock_market_instance.unsubscribe.call_args[0][0])
        assert removed_keys == {"NSE_EQ|B"}

    @pytest.mark.asyncio
    @patch("monitor.user_manager.MarketDataStream")
    @patch("monitor.user_manager.PortfolioStream")
    async def test_creates_candle_buffers_for_indicator_rules(self, MockPortfolio, MockMarket):
        from monitor.user_manager import UserManager

        MockPortfolio.return_value = AsyncMock()
        MockMarket.return_value = AsyncMock()

        mgr = UserManager(on_tick=AsyncMock(), on_portfolio_event=AsyncMock())

        rules = [
            _make_rule(1, "indicator", "NSE_EQ|A", trigger_config={
                "indicator": "rsi", "timeframe": "5m",
                "condition": "lte", "value": 30.0, "params": {},
            }),
        ]
        await mgr.start_user(999, "test-token", rules)

        session = mgr.get_session(999)
        assert "NSE_EQ|A_5m" in session.candle_buffers

    @pytest.mark.asyncio
    @patch("monitor.user_manager.MarketDataStream")
    @patch("monitor.user_manager.PortfolioStream")
    async def test_removes_unused_candle_buffers(self, MockPortfolio, MockMarket):
        from monitor.user_manager import UserManager

        MockPortfolio.return_value = AsyncMock()
        MockMarket.return_value = AsyncMock()

        mgr = UserManager(on_tick=AsyncMock(), on_portfolio_event=AsyncMock())

        rules_v1 = [
            _make_rule(1, "indicator", "NSE_EQ|A", trigger_config={
                "indicator": "rsi", "timeframe": "5m",
                "condition": "lte", "value": 30.0, "params": {},
            }),
        ]
        await mgr.start_user(999, "test-token", rules_v1)
        assert "NSE_EQ|A_5m" in mgr.get_session(999).candle_buffers

        # Sync rules: remove indicator rule, add a price rule
        rules_v2 = [_make_rule(2, "price", "NSE_EQ|A")]
        await mgr.sync_rules(999, rules_v2)

        assert "NSE_EQ|A_5m" not in mgr.get_session(999).candle_buffers


# ── Test: market tick handling ───────────────────────────────────────


class TestMarketTickHandling:

    @pytest.mark.asyncio
    @patch("monitor.user_manager.MarketDataStream")
    @patch("monitor.user_manager.PortfolioStream")
    async def test_updates_prev_prices(self, MockPortfolio, MockMarket):
        from monitor.user_manager import UserManager

        mock_market_instance = AsyncMock()
        MockPortfolio.return_value = AsyncMock()
        MockMarket.return_value = mock_market_instance

        on_tick = AsyncMock()
        mgr = UserManager(on_tick=on_tick, on_portfolio_event=AsyncMock())

        rules = [_make_rule(1, "price", "NSE_EQ|A")]
        await mgr.start_user(999, "test-token", rules)

        session = mgr.get_session(999)

        # Simulate a market tick via the internal callback
        tick_data = {
            "NSE_EQ|A": {"instrument_key": "NSE_EQ|A", "ltp": 150.0, "close": 145.0},
        }
        await mgr._on_market_tick(999, tick_data)

        assert session.prev_prices.get("NSE_EQ|A") == 150.0

    @pytest.mark.asyncio
    @patch("monitor.user_manager.MarketDataStream")
    @patch("monitor.user_manager.PortfolioStream")
    async def test_feeds_candle_buffer(self, MockPortfolio, MockMarket):
        from monitor.user_manager import UserManager

        MockPortfolio.return_value = AsyncMock()
        MockMarket.return_value = AsyncMock()

        mgr = UserManager(on_tick=AsyncMock(), on_portfolio_event=AsyncMock())

        rules = [
            _make_rule(1, "indicator", "NSE_EQ|A", trigger_config={
                "indicator": "rsi", "timeframe": "5m",
                "condition": "lte", "value": 30.0, "params": {},
            }),
        ]
        await mgr.start_user(999, "test-token", rules)

        session = mgr.get_session(999)
        buf = session.candle_buffers["NSE_EQ|A_5m"]
        assert len(buf.get_candles()) == 0

        tick_data = {
            "NSE_EQ|A": {"instrument_key": "NSE_EQ|A", "ltp": 150.0, "close": 145.0},
        }
        await mgr._on_market_tick(999, tick_data)

        assert len(buf.get_candles()) == 1
        assert buf.get_candles()[0]["close"] == 150.0

    @pytest.mark.asyncio
    @patch("monitor.user_manager.compute_indicator")
    @patch("monitor.user_manager.MarketDataStream")
    @patch("monitor.user_manager.PortfolioStream")
    async def test_recomputes_indicators_on_candle_complete(
        self, MockPortfolio, MockMarket, mock_compute
    ):
        from monitor.user_manager import UserManager

        MockPortfolio.return_value = AsyncMock()
        MockMarket.return_value = AsyncMock()
        mock_compute.return_value = 42.5

        mgr = UserManager(on_tick=AsyncMock(), on_portfolio_event=AsyncMock())

        rules = [
            _make_rule(1, "indicator", "NSE_EQ|A", trigger_config={
                "indicator": "rsi", "timeframe": "1m",
                "condition": "lte", "value": 30.0, "params": {"period": 14},
            }),
        ]
        await mgr.start_user(999, "test-token", rules)
        session = mgr.get_session(999)

        # First tick at 10:00:30 -- creates first candle
        tick1 = {
            "NSE_EQ|A": {"instrument_key": "NSE_EQ|A", "ltp": 100.0, "close": 99.0},
        }
        await mgr._on_market_tick(
            999, tick1, timestamp=datetime(2026, 2, 16, 10, 0, 30)
        )

        # Second tick at 10:01:05 -- new window, first candle completes
        tick2 = {
            "NSE_EQ|A": {"instrument_key": "NSE_EQ|A", "ltp": 102.0, "close": 99.0},
        }
        await mgr._on_market_tick(
            999, tick2, timestamp=datetime(2026, 2, 16, 10, 1, 5)
        )

        # Indicator should have been recomputed because a new candle started
        mock_compute.assert_called()
        assert session.indicator_values.get("rsi_1m") == 42.5

    @pytest.mark.asyncio
    @patch("monitor.user_manager.MarketDataStream")
    @patch("monitor.user_manager.PortfolioStream")
    async def test_tick_forwards_to_external_callback(self, MockPortfolio, MockMarket):
        from monitor.user_manager import UserManager

        MockPortfolio.return_value = AsyncMock()
        MockMarket.return_value = AsyncMock()

        on_tick = AsyncMock()
        mgr = UserManager(on_tick=on_tick, on_portfolio_event=AsyncMock())

        rules = [_make_rule(1, "price", "NSE_EQ|A")]
        await mgr.start_user(999, "test-token", rules)

        tick_data = {
            "NSE_EQ|A": {"instrument_key": "NSE_EQ|A", "ltp": 150.0, "close": 145.0},
        }
        await mgr._on_market_tick(999, tick_data)

        on_tick.assert_awaited_once()
        call_args = on_tick.call_args
        assert call_args[0][0] == 999  # user_id
        assert call_args[0][1] == "NSE_EQ|A"  # instrument_token
        assert call_args[0][2]["ltp"] == 150.0  # market_data


# ── Test: portfolio event handling ───────────────────────────────────


class TestPortfolioEventHandling:

    @pytest.mark.asyncio
    @patch("monitor.user_manager.MarketDataStream")
    @patch("monitor.user_manager.PortfolioStream")
    async def test_portfolio_event_forwarded(self, MockPortfolio, MockMarket):
        from monitor.user_manager import UserManager

        MockPortfolio.return_value = AsyncMock()
        MockMarket.return_value = AsyncMock()

        on_portfolio = AsyncMock()
        mgr = UserManager(on_tick=AsyncMock(), on_portfolio_event=on_portfolio)

        rules = [_make_rule(1, "price", "NSE_EQ|A")]
        await mgr.start_user(999, "test-token", rules)

        event = {"order_id": "ORD-123", "status": "complete"}
        await mgr._on_portfolio_event(999, event)

        on_portfolio.assert_awaited_once_with(999, event)


# ── Test: stop_all ───────────────────────────────────────────────────


class TestStopAll:

    @pytest.mark.asyncio
    @patch("monitor.user_manager.MarketDataStream")
    @patch("monitor.user_manager.PortfolioStream")
    async def test_stops_all_sessions(self, MockPortfolio, MockMarket):
        from monitor.user_manager import UserManager

        mock_p1, mock_m1 = AsyncMock(), AsyncMock()
        mock_p2, mock_m2 = AsyncMock(), AsyncMock()

        call_count = [0]

        def make_portfolio(*a, **kw):
            call_count[0] += 1
            return mock_p1 if call_count[0] == 1 else mock_p2

        portfolio_call = [0]
        market_call = [0]

        def make_portfolio_fn(*a, **kw):
            portfolio_call[0] += 1
            return mock_p1 if portfolio_call[0] == 1 else mock_p2

        def make_market_fn(*a, **kw):
            market_call[0] += 1
            return mock_m1 if market_call[0] == 1 else mock_m2

        MockPortfolio.side_effect = make_portfolio_fn
        MockMarket.side_effect = make_market_fn

        mgr = UserManager(on_tick=AsyncMock(), on_portfolio_event=AsyncMock())
        await mgr.start_user(1, "token-1", [_make_rule(1, "price", "NSE_EQ|A")])
        await mgr.start_user(2, "token-2", [_make_rule(2, "price", "NSE_EQ|B")])

        assert mgr.get_session(1) is not None
        assert mgr.get_session(2) is not None

        await mgr.stop_all()

        mock_p1.stop.assert_awaited_once()
        mock_m1.stop.assert_awaited_once()
        mock_p2.stop.assert_awaited_once()
        mock_m2.stop.assert_awaited_once()

        assert mgr.get_session(1) is None
        assert mgr.get_session(2) is None


def test_trailing_stop_extracts_instrument():
    """trailing_stop rules should extract instrument tokens for subscription."""
    from monitor.user_manager import extract_instruments_from_rules
    from monitor.models import MonitorRule

    rule = MonitorRule(
        id=1,
        user_id=999,
        name="trailing test",
        trigger_type="trailing_stop",
        trigger_config={
            "trail_percent": 15.0,
            "initial_price": 100.0,
            "highest_price": 100.0,
        },
        action_type="place_order",
        action_config={
            "symbol": "X",
            "transaction_type": "SELL",
            "quantity": 1,
            "order_type": "MARKET",
            "product": "I",
            "price": None,
        },
        instrument_token="NSE_EQ|TEST123",
    )
    instruments = extract_instruments_from_rules([rule])
    assert "NSE_EQ|TEST123" in instruments
