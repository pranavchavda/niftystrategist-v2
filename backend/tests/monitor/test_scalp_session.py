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
        squareoff_time="23:59",
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

            # Set previous primary as bearish, current as bullish
            mgr._primary_values["1"] = -1.0
            mgr._prev_primary_values["1"] = -1.0

            # Directly test _process_underlying_tick with a bullish flip
            mgr._primary_values["1"] = 1.0  # current = bullish
            mgr._prev_primary_values["1"] = -1.0  # prev = bearish

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

    @pytest.mark.asyncio
    async def test_past_squareoff_time_blocks_entry(self):
        """New entries after squareoff_time waste brokerage (enter→immediate squareoff)."""
        from zoneinfo import ZoneInfo
        mgr = _make_manager()
        session = _make_session()
        ist_now = datetime.now(ZoneInfo("Asia/Kolkata"))
        past = ist_now.replace(second=0, microsecond=0) - timedelta(minutes=5)
        session.config.squareoff_time = f"{past.hour:02d}:{past.minute:02d}"

        with patch.object(mgr, '_enter_position', new_callable=AsyncMock) as mock_enter:
            await mgr._try_enter(session, "CE", 24350.0)
            mock_enter.assert_not_called()


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
            trail_armed=True,
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
            # Trail starts disarmed; highest_premium stays None until arm fires.
            assert session.runtime.highest_premium is None
            assert session.runtime.trail_armed is False
            mock_exit.assert_not_called()

    @pytest.mark.asyncio
    async def test_highest_premium_tracks_up_when_armed(self):
        mgr = _make_manager()
        session = _make_session(
            state=ScalpState.HOLDING_CE,
            entry_price=200.0,
            highest_premium=210.0,
            trail_armed=True,
            current_instrument_token="NSE_FO|43885",
        )
        session.config.sl_points = None
        session.config.target_points = None
        session.config.trail_percent = 50.0  # 50% trail → level = highest * 0.5, far below

        await mgr._process_premium_tick(session, 220.0)
        assert session.runtime.highest_premium == 220.0

        await mgr._process_premium_tick(session, 215.0)
        assert session.runtime.highest_premium == 220.0  # Doesn't decrease


# ── Armed trailing stop ─────────────────────────────────────────────


class TestArmedTrail:
    @pytest.mark.asyncio
    async def test_trail_does_not_fire_before_arm_threshold(self):
        """Trail is configured with arm=+20pts. Price rises +10 then dips — no exit."""
        mgr = _make_manager()
        session = _make_session(
            state=ScalpState.HOLDING_CE,
            entry_price=200.0,
            current_instrument_token="NSE_FO|43885",
        )
        session.config.sl_points = None
        session.config.target_points = None
        session.config.trail_points = 5.0
        session.config.trail_arm_points = 20.0

        with patch.object(mgr, '_exit_position', new_callable=AsyncMock) as mock_exit:
            # Rise to +10 (below +20 arm threshold), then pull back.
            await mgr._process_premium_tick(session, 210.0)
            await mgr._process_premium_tick(session, 205.0)
            assert session.runtime.trail_armed is False
            assert session.runtime.highest_premium is None
            mock_exit.assert_not_called()

    @pytest.mark.asyncio
    async def test_trail_arms_then_fires_on_pullback(self):
        """Once armed at +20pts, a trail_points=5 stop should fire on a 5pt pullback."""
        mgr = _make_manager()
        session = _make_session(
            state=ScalpState.HOLDING_CE,
            entry_price=200.0,
            current_instrument_token="NSE_FO|43885",
        )
        session.config.sl_points = None
        session.config.target_points = None
        session.config.trail_points = 5.0
        session.config.trail_arm_points = 20.0

        with patch.object(mgr, '_exit_position', new_callable=AsyncMock) as mock_exit:
            # Arm at +20.
            await mgr._process_premium_tick(session, 220.0)
            assert session.runtime.trail_armed is True
            assert session.runtime.highest_premium == 220.0
            mock_exit.assert_not_called()

            # Push higher.
            await mgr._process_premium_tick(session, 225.0)
            assert session.runtime.highest_premium == 225.0
            mock_exit.assert_not_called()

            # Pull back 5 pts from high (trail level = 225 - 5 = 220).
            await mgr._process_premium_tick(session, 219.0)
            mock_exit.assert_called_once_with(session, "exit_trail", 219.0)

    @pytest.mark.asyncio
    async def test_trail_points_takes_precedence_over_percent(self):
        """If both trail_points and trail_percent are set, use trail_points."""
        mgr = _make_manager()
        session = _make_session(
            state=ScalpState.HOLDING_CE,
            entry_price=100.0,
            highest_premium=110.0,
            trail_armed=True,
            current_instrument_token="NSE_FO|43885",
        )
        session.config.sl_points = None
        session.config.target_points = None
        session.config.trail_points = 2.0      # absolute: level = 110 - 2 = 108
        session.config.trail_percent = 20.0    # percent: level = 110 * 0.8 = 88

        with patch.object(mgr, '_exit_position', new_callable=AsyncMock) as mock_exit:
            # 107 < 108 (points trail) but >> 88 (percent trail). Exits → points wins.
            await mgr._process_premium_tick(session, 107.0)
            mock_exit.assert_called_once_with(session, "exit_trail", 107.0)

    @pytest.mark.asyncio
    async def test_arm_points_none_arms_immediately(self):
        """Back-compat: no arm_points → arm on first uptick past entry."""
        mgr = _make_manager()
        session = _make_session(
            state=ScalpState.HOLDING_CE,
            entry_price=100.0,
            current_instrument_token="NSE_FO|43885",
        )
        session.config.sl_points = None
        session.config.target_points = None
        session.config.trail_points = 3.0
        session.config.trail_arm_points = None

        with patch.object(mgr, '_exit_position', new_callable=AsyncMock) as mock_exit:
            await mgr._process_premium_tick(session, 101.0)
            assert session.runtime.trail_armed is True
            assert session.runtime.highest_premium == 101.0

    @pytest.mark.asyncio
    async def test_sl_still_fires_before_trail_arms(self):
        """Hard SL must fire even while trail is disarmed."""
        mgr = _make_manager()
        session = _make_session(
            state=ScalpState.HOLDING_CE,
            entry_price=200.0,
            current_instrument_token="NSE_FO|43885",
        )
        session.config.sl_points = 10.0
        session.config.target_points = None
        session.config.trail_points = 3.0
        session.config.trail_arm_points = 20.0  # high arm threshold

        with patch.object(mgr, '_exit_position', new_callable=AsyncMock) as mock_exit:
            await mgr._process_premium_tick(session, 189.0)  # below 190 SL
            mock_exit.assert_called_once_with(session, "exit_sl", 189.0)
            assert session.runtime.trail_armed is False


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
    async def test_cross_session_instrument_mutex(self):
        """Another session already holding the same instrument blocks entry."""
        mgr = _make_manager()
        holder = _make_session(
            session_id=1,
            state=ScalpState.HOLDING_CE,
            current_instrument_token="NSE_FO|43885",
        )
        new_session = _make_session(session_id=2)
        mgr._sessions = {999: [holder, new_session]}
        mgr._premium_map = {"999:NSE_FO|43885": holder.id}

        fake_inst = {"instrument_key": "NSE_FO|43885", "tradingsymbol": "NIFTY26APR24350CE"}
        with patch("strategies.fno_utils.resolve_option_instrument", return_value=fake_inst), \
             patch("strategies.fno_utils.list_strikes", return_value=[24350]), \
             patch("strategies.fno_utils.get_lot_size", return_value=25), \
             patch.object(mgr, '_place_order', new_callable=AsyncMock) as mock_order, \
             patch.object(mgr, '_log_event', new_callable=AsyncMock), \
             patch.object(mgr, '_persist_state', new_callable=AsyncMock):

            await mgr._enter_position(new_session, "CE", 24340.0)

            assert new_session.runtime.state == ScalpState.IDLE
            mock_order.assert_not_called()

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
    async def test_squareoff_uses_last_premium_ltp(self):
        """Time-based squareoff must pass premium LTP so P&L isn't null."""
        from zoneinfo import ZoneInfo
        mgr = _make_manager()
        ist_now = datetime.now(ZoneInfo("Asia/Kolkata"))
        past = ist_now.replace(second=0, microsecond=0) - timedelta(minutes=1)
        session = _make_session(
            state=ScalpState.HOLDING_CE,
            entry_price=200.0,
            current_instrument_token="NSE_FO|43885",
            current_option_type="CE",
            last_premium_ltp=185.0,
        )
        session.config.squareoff_time = f"{past.hour:02d}:{past.minute:02d}"
        mgr._sessions = {999: [session]}

        with patch.object(mgr, '_exit_position', new_callable=AsyncMock) as mock_exit:
            await mgr.check_time_squareoff()
            mock_exit.assert_called_once_with(session, "exit_squareoff", 185.0)

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


# ── Pending action handling (API→daemon disable/delete) ─────────────


class TestPendingAction:
    @pytest.mark.asyncio
    async def test_exit_and_disable_on_holding_session(self):
        """API set pending_action=exit_and_disable on a HOLDING session.
        Daemon should exit, then disable the row."""
        mgr = _make_manager()
        session = _make_session(
            state=ScalpState.HOLDING_CE,
            entry_price=200.0,
            current_instrument_token="NSE_FO|43885",
        )
        mgr._sessions = {999: [session]}
        mgr._underlying_map = {"999:NSE_INDEX|Nifty 50": [1]}

        with patch.object(mgr, '_exit_position', new_callable=AsyncMock) as mock_exit, \
             patch('monitor.scalp_crud.update_session', new_callable=AsyncMock) as mock_update, \
             patch('monitor.scalp_crud.delete_session', new_callable=AsyncMock) as mock_delete, \
             patch('monitor.scalp_crud.clear_pending_action', new_callable=AsyncMock), \
             patch('database.session.get_db_context') as mock_ctx:
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

            await mgr._handle_pending_action(session, "exit_and_disable")

            mock_exit.assert_called_once()
            assert mock_exit.call_args.args[1] == "exit_disabled"
            mock_update.assert_called_once()
            # kwargs contain enabled=False, pending_action=None
            kwargs = mock_update.call_args.kwargs
            assert kwargs.get("enabled") is False
            assert kwargs.get("pending_action") is None
            mock_delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_exit_and_delete_on_holding_session(self):
        mgr = _make_manager()
        session = _make_session(
            state=ScalpState.HOLDING_PE,
            entry_price=150.0,
            current_instrument_token="NSE_FO|43886",
        )
        mgr._sessions = {999: [session]}

        with patch.object(mgr, '_exit_position', new_callable=AsyncMock) as mock_exit, \
             patch('monitor.scalp_crud.update_session', new_callable=AsyncMock) as mock_update, \
             patch('monitor.scalp_crud.delete_session', new_callable=AsyncMock) as mock_delete, \
             patch('database.session.get_db_context') as mock_ctx:
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

            await mgr._handle_pending_action(session, "exit_and_delete")

            mock_exit.assert_called_once()
            mock_delete.assert_called_once()
            mock_update.assert_not_called()

    @pytest.mark.asyncio
    async def test_pending_action_on_idle_skips_exit(self):
        """IDLE session with pending_action just gets disabled, no SELL order."""
        mgr = _make_manager()
        session = _make_session(state=ScalpState.IDLE)
        mgr._sessions = {999: [session]}

        with patch.object(mgr, '_exit_position', new_callable=AsyncMock) as mock_exit, \
             patch('monitor.scalp_crud.update_session', new_callable=AsyncMock), \
             patch('monitor.scalp_crud.delete_session', new_callable=AsyncMock), \
             patch('database.session.get_db_context') as mock_ctx:
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

            await mgr._handle_pending_action(session, "exit_and_disable")
            mock_exit.assert_not_called()

    def test_drop_session_from_memory_prunes_maps(self):
        mgr = _make_manager()
        session = _make_session(session_id=1, user_id=999)
        other = _make_session(session_id=2, user_id=999)
        mgr._sessions = {999: [session, other]}
        mgr._underlying_map = {"999:NSE_INDEX|Nifty 50": [1, 2]}

        mgr._drop_session_from_memory(session)

        assert 999 in mgr._sessions
        assert len(mgr._sessions[999]) == 1
        assert mgr._sessions[999][0].id == 2
        assert mgr._underlying_map["999:NSE_INDEX|Nifty 50"] == [2]

    def test_drop_last_session_removes_user_key(self):
        mgr = _make_manager()
        session = _make_session(session_id=1, user_id=999)
        mgr._sessions = {999: [session]}
        mgr._underlying_map = {"999:NSE_INDEX|Nifty 50": [1]}

        mgr._drop_session_from_memory(session)

        assert 999 not in mgr._sessions
        assert "999:NSE_INDEX|Nifty 50" not in mgr._underlying_map


# ── Primary + confirm indicator plumbing ────────────────────────────


class TestPrimaryConfirmIndicators:
    @pytest.mark.asyncio
    async def test_primary_defaults_to_utbot_params_from_legacy_fields(self):
        """When primary_params is None and primary_indicator='utbot', the
        runtime falls back to the legacy utbot_period/utbot_sensitivity
        columns. Exercised via _process_underlying_tick's compute call."""
        mgr = _make_manager()
        session = _make_session()
        session.config.primary_indicator = "utbot"
        session.config.primary_params = None  # force legacy fallback path
        session.config.utbot_period = 7
        session.config.utbot_sensitivity = 1.5

        from monitor.candle_buffer import CandleBuffer
        buf = CandleBuffer(1)
        mgr._candle_buffers["1"] = buf

        called = {}
        def fake_compute(name, candles, params):
            called["name"] = name
            called["params"] = params
            return 1.0
        # Session manager uses the manager's internal maps first, so set
        # up a candle-close path by calling _process_underlying_tick with
        # pre-populated buf state. Easiest: stub compute_indicator and
        # pre-load candles into buf.
        # Build a fake completed-candle list via get_completed_candles mock.
        with patch("monitor.scalp_session.compute_indicator", side_effect=fake_compute):
            # Simulate two candle closes so prev_val is populated.
            from unittest.mock import patch as _p
            with _p.object(buf, "get_completed_candles",
                           side_effect=[[], [{"c": 1}], [{"c": 1}, {"c": 2}]]):
                # 1st tick — no candle closed yet (empty → [])... adjust.
                pass
        # Direct assertion path: config carries primary_params=None, so the
        # tick processor should build {"period":7,"sensitivity":1.5}. Verify
        # via a focused unit check on the config→crud fallback logic instead.
        from monitor.scalp_crud import db_to_session
        class FakeRow:
            id, user_id, name, enabled = 1, 999, "x", True
            session_mode = "options_scalp"
            underlying = "NIFTY"
            underlying_instrument_token = "NSE_INDEX|Nifty 50"
            expiry = "2026-04-30"
            lots, quantity, product = 1, None, "I"
            indicator_timeframe = "1m"
            utbot_period, utbot_sensitivity = 7, 1.5
            primary_indicator = "utbot"
            primary_params = None
            confirm_indicator = None
            confirm_params = None
            sl_points = target_points = trail_percent = trail_points = trail_arm_points = None
            squareoff_time = "15:15"
            max_trades = 20
            cooldown_seconds = 60
            pending_action = None
            state = "IDLE"
            current_option_type = current_strike = None
            current_instrument_token = current_tradingsymbol = None
            entry_price = entry_time = highest_premium = None
            trade_count = 0
            last_exit_time = None
        s = db_to_session(FakeRow())
        assert s.config.primary_params == {"period": 7, "sensitivity": 1.5}

    @pytest.mark.asyncio
    async def test_primary_indicator_is_called_with_config_name(self):
        """_process_underlying_tick must invoke compute_indicator with the
        config's primary_indicator name, not a hardcoded 'utbot'."""
        mgr = _make_manager()
        session = _make_session()
        session.config.primary_indicator = "ema_crossover"
        session.config.primary_params = {"fast": 9, "slow": 21}

        from monitor.candle_buffer import CandleBuffer
        buf = CandleBuffer(1)
        mgr._candle_buffers["1"] = buf
        mgr._sessions = {999: [session]}
        mgr._underlying_map = {"999:NSE_INDEX|Nifty 50": [1]}

        # Seed "prior" primary value to make flip detection work on the
        # closed candle that the mock returns on the second call.
        mgr._primary_values["1"] = -1.0

        calls = []
        def fake_compute(name, candles, params):
            calls.append((name, dict(params)))
            return 1.0  # flip bullish (prev was -1.0)

        completed = [[{"c": 1, "h": 1, "l": 1, "o": 1, "volume": 0, "timestamp": 0}]]
        with patch("monitor.scalp_session.compute_indicator", side_effect=fake_compute), \
             patch.object(buf, "get_completed_candles",
                          side_effect=[[], completed[0], completed[0]]), \
             patch.object(mgr, "_try_enter", new_callable=AsyncMock) as mock_enter:
            await mgr._process_underlying_tick(session, 24350.0)

        assert calls[0][0] == "ema_crossover"
        assert calls[0][1] == {"fast": 9, "slow": 21}
        mock_enter.assert_called_once_with(session, "CE", 24350.0)

    @pytest.mark.asyncio
    async def test_confirm_agrees_noop_when_unconfigured(self):
        mgr = _make_manager()
        session = _make_session()
        session.config.confirm_indicator = None
        # compute_indicator shouldn't be called at all.
        with patch("monitor.scalp_session.compute_indicator") as mock_compute:
            assert mgr._confirm_agrees(session, [], 1) is True
            mock_compute.assert_not_called()

    @pytest.mark.asyncio
    async def test_confirm_blocks_entry_when_disagrees(self):
        mgr = _make_manager()
        session = _make_session()
        session.config.confirm_indicator = "macd"
        session.config.confirm_params = {}

        with patch("monitor.scalp_session.compute_indicator", return_value=-0.5):
            # Primary bullish (direction=1) but confirm negative → blocks.
            assert mgr._confirm_agrees(session, [], 1) is False

    @pytest.mark.asyncio
    async def test_confirm_allows_entry_when_agrees(self):
        mgr = _make_manager()
        session = _make_session()
        session.config.confirm_indicator = "macd"
        session.config.confirm_params = {}

        with patch("monitor.scalp_session.compute_indicator", return_value=0.8):
            assert mgr._confirm_agrees(session, [], 1) is True

    @pytest.mark.asyncio
    async def test_confirm_blocks_when_not_ready(self):
        """Indicator returns None (warm-up) → don't enter."""
        mgr = _make_manager()
        session = _make_session()
        session.config.confirm_indicator = "macd"
        session.config.confirm_params = {}

        with patch("monitor.scalp_session.compute_indicator", return_value=None):
            assert mgr._confirm_agrees(session, [], 1) is False

    @pytest.mark.asyncio
    async def test_confirm_gate_does_not_block_exits(self):
        """Reversal exit should fire even when confirm disagrees — holding
        into adverse move waiting for two-indicator agreement is worse."""
        mgr = _make_manager()
        session = _make_session(
            state=ScalpState.HOLDING_CE,
            entry_price=200.0,
            current_instrument_token="NSE_FO|43885",
            last_premium_ltp=180.0,
        )
        session.config.primary_indicator = "utbot"
        session.config.primary_params = {"period": 5, "sensitivity": 0.5}
        session.config.confirm_indicator = "macd"
        session.config.confirm_params = {}

        from monitor.candle_buffer import CandleBuffer
        buf = CandleBuffer(1)
        mgr._candle_buffers["1"] = buf
        # Previous primary bullish, current bearish → exit should trigger.
        mgr._primary_values["1"] = 1.0

        completed = [{"c": 1, "h": 1, "l": 1, "o": 1, "volume": 0, "timestamp": 0}]

        # Only the primary gets called — confirm is not consulted on exits.
        with patch("monitor.scalp_session.compute_indicator", return_value=-1.0) as mock_c, \
             patch.object(buf, "get_completed_candles",
                          side_effect=[[], completed, completed]), \
             patch.object(mgr, "_exit_position", new_callable=AsyncMock) as mock_exit:
            await mgr._process_underlying_tick(session, 24350.0)

        mock_exit.assert_called_once_with(session, "exit_reversal", 180.0)
        # Primary was called once; confirm must not have been called at all.
        assert mock_c.call_count == 1


# ── Equity sessions (intraday + swing) ──────────────────────────────


def _make_equity_session(
    session_id: int = 100,
    user_id: int = 999,
    mode: str = "equity_intraday",
    state: ScalpState = ScalpState.IDLE,
    quantity: int = 10,
    **runtime_overrides,
) -> ScalpSession:
    config = ScalpSessionConfig(
        id=session_id,
        user_id=user_id,
        name=f"equity-{session_id}",
        session_mode=mode,
        underlying="RELIANCE",
        underlying_instrument_token="NSE_EQ|INE002A01018",
        expiry="",
        lots=1,
        quantity=quantity,
        product="D" if mode == "equity_swing" else "I",
        indicator_timeframe="5m",
        utbot_period=10,
        utbot_sensitivity=1.0,
        squareoff_time="15:15",
        max_trades=10,
        cooldown_seconds=60,
    )
    runtime = ScalpSessionRuntime(state=state, **runtime_overrides)
    return ScalpSession(config=config, runtime=runtime)


class TestEquityModeRouting:
    def test_bullish_direction_options(self):
        assert ScalpSessionManager._bullish_direction("options_scalp") == "CE"

    def test_bullish_direction_equity(self):
        assert ScalpSessionManager._bullish_direction("equity_intraday") == "LONG"
        assert ScalpSessionManager._bullish_direction("equity_swing") == "LONG"

    def test_bearish_direction_options(self):
        assert ScalpSessionManager._bearish_direction("options_scalp") == "PE"

    def test_bearish_direction_intraday_supports_short(self):
        assert ScalpSessionManager._bearish_direction("equity_intraday") == "SHORT"

    def test_bearish_direction_swing_blocks_short(self):
        """Delivery doesn't permit shorting (no SLBM here) → no entry direction."""
        assert ScalpSessionManager._bearish_direction("equity_swing") is None


class TestEquityEntry:
    @pytest.mark.asyncio
    async def test_equity_long_entry_places_buy(self):
        mgr = _make_manager()
        session = _make_equity_session(mode="equity_intraday")

        with patch.object(mgr, '_place_order', new_callable=AsyncMock,
                          return_value={"success": True, "order_id": "ORD-EQ-1"}) as mock_order, \
             patch.object(mgr, '_log_event', new_callable=AsyncMock), \
             patch.object(mgr, '_persist_state', new_callable=AsyncMock):

            await mgr._enter_equity(session, "LONG", 2500.0)

        assert session.runtime.state == ScalpState.HOLDING_LONG
        assert session.runtime.current_instrument_token == "NSE_EQ|INE002A01018"
        assert session.runtime.entry_price == 2500.0  # Set at entry, not deferred
        kwargs = mock_order.call_args.kwargs
        assert kwargs["transaction_type"] == "BUY"
        assert kwargs["quantity"] == 10
        assert kwargs["product"] == "I"

    @pytest.mark.asyncio
    async def test_equity_short_entry_places_sell(self):
        mgr = _make_manager()
        session = _make_equity_session(mode="equity_intraday")

        with patch.object(mgr, '_place_order', new_callable=AsyncMock,
                          return_value={"success": True, "order_id": "ORD-EQ-2"}) as mock_order, \
             patch.object(mgr, '_log_event', new_callable=AsyncMock), \
             patch.object(mgr, '_persist_state', new_callable=AsyncMock):

            await mgr._enter_equity(session, "SHORT", 2500.0)

        assert session.runtime.state == ScalpState.HOLDING_SHORT
        assert mock_order.call_args.kwargs["transaction_type"] == "SELL"

    @pytest.mark.asyncio
    async def test_equity_swing_uses_delivery_product(self):
        mgr = _make_manager()
        session = _make_equity_session(mode="equity_swing")

        with patch.object(mgr, '_place_order', new_callable=AsyncMock,
                          return_value={"success": True, "order_id": "ORD-D"}) as mock_order, \
             patch.object(mgr, '_log_event', new_callable=AsyncMock), \
             patch.object(mgr, '_persist_state', new_callable=AsyncMock):

            await mgr._enter_equity(session, "LONG", 2500.0)

        assert mock_order.call_args.kwargs["product"] == "D"

    @pytest.mark.asyncio
    async def test_equity_entry_requires_quantity(self):
        mgr = _make_manager()
        session = _make_equity_session(mode="equity_intraday", quantity=0)

        with patch.object(mgr, '_place_order', new_callable=AsyncMock) as mock_order, \
             patch.object(mgr, '_log_event', new_callable=AsyncMock):
            await mgr._enter_equity(session, "LONG", 2500.0)

        assert session.runtime.state == ScalpState.IDLE
        mock_order.assert_not_called()


class TestEquityExit:
    @pytest.mark.asyncio
    async def test_equity_long_exit_sells_and_pnl_positive(self):
        mgr = _make_manager()
        session = _make_equity_session(
            mode="equity_intraday",
            state=ScalpState.HOLDING_LONG,
            entry_price=2500.0,
            current_instrument_token="NSE_EQ|INE002A01018",
            current_tradingsymbol="RELIANCE",
        )

        with patch.object(mgr, '_place_order', new_callable=AsyncMock,
                          return_value={"success": True, "order_id": "EXIT-1"}) as mock_order, \
             patch.object(mgr, '_log_event', new_callable=AsyncMock) as mock_log, \
             patch.object(mgr, '_unsubscribe_instrument', new_callable=AsyncMock) as mock_unsub, \
             patch.object(mgr, '_persist_state', new_callable=AsyncMock):
            await mgr._exit_position(session, "exit_target", 2530.0)

        assert mock_order.call_args.kwargs["transaction_type"] == "SELL"
        # Equity LONG: P&L = (exit - entry) * qty = +30 * 10 = +300
        assert mock_log.call_args.kwargs["pnl_amount"] == 300.0
        # Equity must NOT unsubscribe — the underlying drives the signal too.
        mock_unsub.assert_not_called()
        assert session.runtime.state == ScalpState.IDLE

    @pytest.mark.asyncio
    async def test_equity_short_exit_buys_and_pnl_inverted(self):
        mgr = _make_manager()
        session = _make_equity_session(
            mode="equity_intraday",
            state=ScalpState.HOLDING_SHORT,
            entry_price=2500.0,
            current_instrument_token="NSE_EQ|INE002A01018",
            current_tradingsymbol="RELIANCE",
        )

        with patch.object(mgr, '_place_order', new_callable=AsyncMock,
                          return_value={"success": True, "order_id": "EXIT-2"}) as mock_order, \
             patch.object(mgr, '_log_event', new_callable=AsyncMock) as mock_log, \
             patch.object(mgr, '_persist_state', new_callable=AsyncMock):
            # Short profitable when price falls: entry 2500, exit 2470
            await mgr._exit_position(session, "exit_target", 2470.0)

        assert mock_order.call_args.kwargs["transaction_type"] == "BUY"
        # SHORT P&L: (entry - exit) * qty = +30 * 10 = +300
        assert mock_log.call_args.kwargs["pnl_amount"] == 300.0


class TestSwingExemptions:
    @pytest.mark.asyncio
    async def test_swing_skips_time_squareoff(self):
        """Swing mode holds across days — no daily squareoff."""
        from zoneinfo import ZoneInfo
        mgr = _make_manager()
        ist_now = datetime.now(ZoneInfo("Asia/Kolkata"))
        past_time = (ist_now - timedelta(minutes=5))
        session = _make_equity_session(
            mode="equity_swing",
            state=ScalpState.HOLDING_LONG,
            entry_price=2500.0,
            current_instrument_token="NSE_EQ|INE002A01018",
        )
        session.config.squareoff_time = f"{past_time.hour:02d}:{past_time.minute:02d}"
        mgr._sessions = {999: [session]}

        with patch.object(mgr, '_exit_position', new_callable=AsyncMock) as mock_exit:
            await mgr.check_time_squareoff()
            mock_exit.assert_not_called()

    @pytest.mark.asyncio
    async def test_swing_allows_entry_after_squareoff_time(self):
        """Swing mode can enter even after the daily squareoff window."""
        from zoneinfo import ZoneInfo
        mgr = _make_manager()
        ist_now = datetime.now(ZoneInfo("Asia/Kolkata"))
        past_time = (ist_now - timedelta(minutes=5))
        session = _make_equity_session(mode="equity_swing")
        session.config.squareoff_time = f"{past_time.hour:02d}:{past_time.minute:02d}"

        with patch.object(mgr, '_enter_position', new_callable=AsyncMock) as mock_enter:
            await mgr._try_enter(session, "LONG", 2500.0)
            mock_enter.assert_called_once()


def test_parse_timeframe_supports_daily():
    """Swing mode uses '1d' — _parse_timeframe must handle it."""
    from monitor.scalp_session import _parse_timeframe
    assert _parse_timeframe("1d") == 24 * 60
    assert _parse_timeframe("1h") == 60
    assert _parse_timeframe("5m") == 5
