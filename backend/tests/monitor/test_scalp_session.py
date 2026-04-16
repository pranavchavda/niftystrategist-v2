"""Tests for ScalpSessionManager — state machine, entry/exit, guards."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from monitor.scalp_models import ScalpSession, ScalpSessionConfig, ScalpSessionRuntime, ScalpState
from monitor.scalp_session import ScalpSessionManager


# ── Helpers ──────────────────────────────────────────────────────────


def _make_session(
    session_id: int = 1,
    user_id: int = 999,
    underlying: str = "NIFTY",
    state: ScalpState = ScalpState.IDLE,
    **runtime_overrides,
) -> ScalpSession:
    config = ScalpSessionConfig(
        id=session_id,
        user_id=user_id,
        name=f"test-session-{session_id}",
        underlying=underlying,
        underlying_instrument_token="NSE_INDEX|Nifty 50",
        expiry="2026-04-30",
        lots=1,
        indicator_timeframe="1m",
        utbot_period=5,
        utbot_sensitivity=0.5,
        sl_points=30.0,
        target_points=50.0,
        trail_percent=10.0,
        squareoff_time="15:15",
        max_trades=20,
        cooldown_seconds=60,
    )
    runtime = ScalpSessionRuntime(state=state, **runtime_overrides)
    return ScalpSession(config=config, runtime=runtime)


def _make_manager(**kwargs) -> ScalpSessionManager:
    mgr = ScalpSessionManager(
        get_client=AsyncMock(),
        get_order_node_url=AsyncMock(return_value=None),
        paper_mode=True,
    )
    mgr._user_manager = MagicMock()
    return mgr


# ── State machine: basic transitions ────────────────────────────────


class TestStateTransitions:
    @pytest.mark.asyncio
    async def test_idle_to_holding_ce_on_bullish_flip(self):
        mgr = _make_manager()
        session = _make_session()

        mgr._sessions = {999: [session]}
        mgr._underlying_map = {"999:NSE_INDEX|Nifty 50": [1]}

        with patch.object(mgr, '_enter_position', new_callable=AsyncMock) as mock_enter:
            # Simulate candle buffer with UT Bot flip
            from monitor.candle_buffer import CandleBuffer
            buf = CandleBuffer(1)
            mgr._candle_buffers["1"] = buf

            # Set previous UT Bot as bearish, current as bullish
            mgr._utbot_values["1"] = -1.0
            mgr._prev_utbot_values["1"] = -1.0

            # Directly test _process_underlying_tick with a bullish flip
            mgr._utbot_values["1"] = 1.0  # current = bullish
            mgr._prev_utbot_values["1"] = -1.0  # prev = bearish

            # Call _try_enter directly since candle close logic is hard to simulate
            await mgr._try_enter(session, "CE", 24350.0)

            mock_enter.assert_called_once_with(session, "CE", 24350.0)

    @pytest.mark.asyncio
    async def test_idle_to_holding_pe_on_bearish_flip(self):
        mgr = _make_manager()
        session = _make_session()

        with patch.object(mgr, '_enter_position', new_callable=AsyncMock) as mock_enter:
            await mgr._try_enter(session, "PE", 24350.0)
            mock_enter.assert_called_once_with(session, "PE", 24350.0)


# ── Mutual exclusion ────────────────────────────────────────────────


class TestMutualExclusion:
    @pytest.mark.asyncio
    async def test_cannot_enter_ce_while_holding_pe(self):
        mgr = _make_manager()
        session = _make_session(state=ScalpState.HOLDING_PE)

        with patch.object(mgr, '_enter_position', new_callable=AsyncMock) as mock_enter:
            await mgr._try_enter(session, "CE", 24350.0)
            mock_enter.assert_not_called()

    @pytest.mark.asyncio
    async def test_cannot_enter_pe_while_holding_ce(self):
        mgr = _make_manager()
        session = _make_session(state=ScalpState.HOLDING_CE)

        with patch.object(mgr, '_enter_position', new_callable=AsyncMock) as mock_enter:
            await mgr._try_enter(session, "PE", 24350.0)
            mock_enter.assert_not_called()


# ── Guards ───────────────────────────────────────────────────────────


class TestEntryGuards:
    @pytest.mark.asyncio
    async def test_max_trades_blocks_entry(self):
        mgr = _make_manager()
        session = _make_session(trade_count=20)
        session.config.max_trades = 20

        with patch.object(mgr, '_enter_position', new_callable=AsyncMock) as mock_enter:
            await mgr._try_enter(session, "CE", 24350.0)
            mock_enter.assert_not_called()

    @pytest.mark.asyncio
    async def test_cooldown_blocks_entry(self):
        mgr = _make_manager()
        session = _make_session(
            last_exit_time=datetime.utcnow() - timedelta(seconds=30),
        )
        session.config.cooldown_seconds = 60

        with patch.object(mgr, '_enter_position', new_callable=AsyncMock) as mock_enter:
            await mgr._try_enter(session, "CE", 24350.0)
            mock_enter.assert_not_called()

    @pytest.mark.asyncio
    async def test_cooldown_allows_after_expiry(self):
        mgr = _make_manager()
        session = _make_session(
            last_exit_time=datetime.utcnow() - timedelta(seconds=120),
        )
        session.config.cooldown_seconds = 60

        with patch.object(mgr, '_enter_position', new_callable=AsyncMock) as mock_enter:
            await mgr._try_enter(session, "CE", 24350.0)
            mock_enter.assert_called_once()


# ── Premium exit conditions ──────────────────────────────────────────


class TestPremiumExits:
    @pytest.mark.asyncio
    async def test_sl_exit(self):
        mgr = _make_manager()
        session = _make_session(
            state=ScalpState.HOLDING_CE,
            entry_price=200.0,
            highest_premium=210.0,
            current_instrument_token="NSE_FO|43885",
        )
        session.config.sl_points = 30.0

        with patch.object(mgr, '_exit_position', new_callable=AsyncMock) as mock_exit:
            await mgr._process_premium_tick(session, 165.0)  # 200 - 30 = 170, 165 < 170
            mock_exit.assert_called_once_with(session, "exit_sl", 165.0)

    @pytest.mark.asyncio
    async def test_target_exit(self):
        mgr = _make_manager()
        session = _make_session(
            state=ScalpState.HOLDING_CE,
            entry_price=200.0,
            highest_premium=240.0,
            current_instrument_token="NSE_FO|43885",
        )
        session.config.target_points = 50.0

        with patch.object(mgr, '_exit_position', new_callable=AsyncMock) as mock_exit:
            await mgr._process_premium_tick(session, 255.0)  # 200 + 50 = 250, 255 > 250
            mock_exit.assert_called_once_with(session, "exit_target", 255.0)

    @pytest.mark.asyncio
    async def test_trail_exit(self):
        mgr = _make_manager()
        session = _make_session(
            state=ScalpState.HOLDING_CE,
            entry_price=200.0,
            highest_premium=280.0,
            current_instrument_token="NSE_FO|43885",
        )
        session.config.trail_percent = 10.0
        session.config.sl_points = None
        session.config.target_points = None

        with patch.object(mgr, '_exit_position', new_callable=AsyncMock) as mock_exit:
            # Trail level = 280 * (1 - 10/100) = 252
            await mgr._process_premium_tick(session, 250.0)
            mock_exit.assert_called_once_with(session, "exit_trail", 250.0)

    @pytest.mark.asyncio
    async def test_no_exit_above_sl(self):
        mgr = _make_manager()
        session = _make_session(
            state=ScalpState.HOLDING_CE,
            entry_price=200.0,
            highest_premium=210.0,
            current_instrument_token="NSE_FO|43885",
        )
        session.config.sl_points = 30.0
        session.config.target_points = None
        session.config.trail_percent = None  # Disable trail so only SL is checked

        with patch.object(mgr, '_exit_position', new_callable=AsyncMock) as mock_exit:
            await mgr._process_premium_tick(session, 175.0)  # 200 - 30 = 170, 175 > 170
            mock_exit.assert_not_called()

    @pytest.mark.asyncio
    async def test_first_premium_tick_sets_entry_price(self):
        mgr = _make_manager()
        session = _make_session(
            state=ScalpState.HOLDING_CE,
            entry_price=None,
            current_instrument_token="NSE_FO|43885",
        )

        with patch.object(mgr, '_exit_position', new_callable=AsyncMock) as mock_exit:
            await mgr._process_premium_tick(session, 195.0)
            assert session.runtime.entry_price == 195.0
            assert session.runtime.highest_premium == 195.0
            mock_exit.assert_not_called()

    @pytest.mark.asyncio
    async def test_highest_premium_tracks_up(self):
        mgr = _make_manager()
        session = _make_session(
            state=ScalpState.HOLDING_CE,
            entry_price=200.0,
            highest_premium=210.0,
            current_instrument_token="NSE_FO|43885",
        )
        # Disable exits so we can test tracking
        session.config.sl_points = None
        session.config.target_points = None
        session.config.trail_percent = None

        await mgr._process_premium_tick(session, 220.0)
        assert session.runtime.highest_premium == 220.0

        await mgr._process_premium_tick(session, 215.0)
        assert session.runtime.highest_premium == 220.0  # Doesn't decrease


# ── Entry position flow ──────────────────────────────────────────────


class TestEntryPosition:
    @pytest.mark.asyncio
    async def test_entry_resolves_atm_and_places_order(self):
        mgr = _make_manager()
        session = _make_session()

        fake_inst = {"instrument_key": "NSE_FO|43885", "tradingsymbol": "NIFTY26APR24350CE"}

        with patch("strategies.fno_utils.resolve_option_instrument", return_value=fake_inst), \
             patch("strategies.fno_utils.list_strikes", return_value=[24300, 24350, 24400]), \
             patch("strategies.fno_utils.get_lot_size", return_value=25), \
             patch.object(mgr, '_place_order', new_callable=AsyncMock, return_value={"success": True, "order_id": "ORD-1"}), \
             patch.object(mgr, '_subscribe_instrument', new_callable=AsyncMock), \
             patch.object(mgr, '_log_event', new_callable=AsyncMock), \
             patch.object(mgr, '_persist_state', new_callable=AsyncMock):

            await mgr._enter_position(session, "CE", 24340.0)

            assert session.runtime.state == ScalpState.HOLDING_CE
            assert session.runtime.current_strike == 24350.0
            assert session.runtime.current_instrument_token == "NSE_FO|43885"
            assert session.runtime.current_option_type == "CE"
            assert session.runtime.entry_price is None  # Set on first premium tick

            mgr._place_order.assert_called_once()
            call_kwargs = mgr._place_order.call_args
            assert call_kwargs.kwargs.get("transaction_type") == "BUY" or call_kwargs[1].get("transaction_type") == "BUY"

    @pytest.mark.asyncio
    async def test_entry_failure_stays_idle(self):
        mgr = _make_manager()
        session = _make_session()

        fake_inst = {"instrument_key": "NSE_FO|43885", "tradingsymbol": "NIFTY26APR24350CE"}

        with patch("strategies.fno_utils.resolve_option_instrument", return_value=fake_inst), \
             patch("strategies.fno_utils.list_strikes", return_value=[24350]), \
             patch("strategies.fno_utils.get_lot_size", return_value=25), \
             patch.object(mgr, '_place_order', new_callable=AsyncMock, return_value={"success": False, "error": "rejected"}), \
             patch.object(mgr, '_log_event', new_callable=AsyncMock), \
             patch.object(mgr, '_persist_state', new_callable=AsyncMock):

            await mgr._enter_position(session, "CE", 24340.0)

            assert session.runtime.state == ScalpState.IDLE


# ── Exit position flow ───────────────────────────────────────────────


class TestExitPosition:
    @pytest.mark.asyncio
    async def test_exit_transitions_to_idle(self):
        mgr = _make_manager()
        session = _make_session(
            state=ScalpState.HOLDING_CE,
            entry_price=200.0,
            current_instrument_token="NSE_FO|43885",
            current_option_type="CE",
            current_strike=24350.0,
            current_tradingsymbol="NIFTY26APR24350CE",
            trade_count=2,
        )

        with patch("strategies.fno_utils.get_lot_size", return_value=25), \
             patch.object(mgr, '_place_order', new_callable=AsyncMock, return_value={"success": True, "order_id": "ORD-2"}), \
             patch.object(mgr, '_unsubscribe_instrument', new_callable=AsyncMock), \
             patch.object(mgr, '_log_event', new_callable=AsyncMock), \
             patch.object(mgr, '_persist_state', new_callable=AsyncMock):

            await mgr._exit_position(session, "exit_sl", 170.0)

            assert session.runtime.state == ScalpState.IDLE
            assert session.runtime.current_option_type is None
            assert session.runtime.entry_price is None
            assert session.runtime.trade_count == 3
            assert session.runtime.last_exit_time is not None

            # Verify P&L was calculated
            log_call = mgr._log_event.call_args
            assert log_call.kwargs.get("pnl_points") == -30.0  # 170 - 200
            assert log_call.kwargs.get("pnl_amount") == -750.0  # -30 * 25

    @pytest.mark.asyncio
    async def test_exit_failure_stays_holding(self):
        mgr = _make_manager()
        session = _make_session(
            state=ScalpState.HOLDING_CE,
            entry_price=200.0,
            current_instrument_token="NSE_FO|43885",
            current_option_type="CE",
        )

        with patch("strategies.fno_utils.get_lot_size", return_value=25), \
             patch.object(mgr, '_place_order', new_callable=AsyncMock, return_value={"success": False, "error": "rejected"}), \
             patch.object(mgr, '_log_event', new_callable=AsyncMock), \
             patch.object(mgr, '_persist_state', new_callable=AsyncMock):

            await mgr._exit_position(session, "exit_sl", 170.0)

            assert session.runtime.state == ScalpState.HOLDING_CE


# ── Tick routing ─────────────────────────────────────────────────────


class TestTickRouting:
    @pytest.mark.asyncio
    async def test_underlying_tick_routes_to_session(self):
        mgr = _make_manager()
        session = _make_session()
        mgr._sessions = {999: [session]}
        mgr._underlying_map = {"999:NSE_INDEX|Nifty 50": [1]}

        with patch.object(mgr, '_process_underlying_tick', new_callable=AsyncMock) as mock_proc:
            await mgr.on_tick(999, "NSE_INDEX|Nifty 50", {"ltp": 24350.0})
            mock_proc.assert_called_once_with(session, 24350.0)

    @pytest.mark.asyncio
    async def test_premium_tick_routes_to_holding_session(self):
        mgr = _make_manager()
        session = _make_session(
            state=ScalpState.HOLDING_CE,
            current_instrument_token="NSE_FO|43885",
        )
        mgr._sessions = {999: [session]}
        mgr._premium_map = {"999:NSE_FO|43885": 1}

        with patch.object(mgr, '_process_premium_tick', new_callable=AsyncMock) as mock_proc:
            await mgr.on_tick(999, "NSE_FO|43885", {"ltp": 210.0})
            mock_proc.assert_called_once_with(session, 210.0)

    @pytest.mark.asyncio
    async def test_unrelated_tick_is_noop(self):
        mgr = _make_manager()
        session = _make_session()
        mgr._sessions = {999: [session]}
        mgr._underlying_map = {"999:NSE_INDEX|Nifty 50": [1]}

        with patch.object(mgr, '_process_underlying_tick', new_callable=AsyncMock) as mock_under, \
             patch.object(mgr, '_process_premium_tick', new_callable=AsyncMock) as mock_prem:
            await mgr.on_tick(999, "NSE_EQ|RELIANCE", {"ltp": 1300.0})
            mock_under.assert_not_called()
            mock_prem.assert_not_called()


# ── Subscriptions ────────────────────────────────────────────────────


class TestSubscriptions:
    def test_get_subscribed_instruments_idle(self):
        mgr = _make_manager()
        session = _make_session()
        mgr._sessions = {999: [session]}

        instruments = mgr.get_subscribed_instruments(999)
        assert "NSE_INDEX|Nifty 50" in instruments
        assert len(instruments) == 1

    def test_get_subscribed_instruments_holding(self):
        mgr = _make_manager()
        session = _make_session(
            state=ScalpState.HOLDING_CE,
            current_instrument_token="NSE_FO|43885",
        )
        mgr._sessions = {999: [session]}

        instruments = mgr.get_subscribed_instruments(999)
        assert "NSE_INDEX|Nifty 50" in instruments
        assert "NSE_FO|43885" in instruments
        assert len(instruments) == 2
