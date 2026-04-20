"""ScalpSessionManager — stateful options scalping engine.

Runs alongside the rule evaluator in the monitor daemon.  Maintains a
position-aware state machine per session: IDLE → HOLDING_CE/PE → IDLE.
Signals come from UT Bot on the underlying index; exits come from
premium SL/target/trail or UT Bot reversal.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Callable, Awaitable

from monitor.candle_buffer import CandleBuffer
from monitor.indicator_engine import compute_indicator
from monitor.scalp_models import (
    ScalpSession,
    ScalpSessionConfig,
    ScalpSessionRuntime,
    ScalpState,
)

logger = logging.getLogger(__name__)


class ScalpSessionManager:
    """Manages all active scalp sessions across all users."""

    def __init__(
        self,
        get_client: Callable[[int], Awaitable[Any]],
        get_order_node_url: Callable[[int], Awaitable[str | None]] | None = None,
        paper_mode: bool = False,
    ) -> None:
        self._get_client = get_client
        self._get_order_node_url = get_order_node_url
        self._paper_mode = paper_mode

        # In-memory session state: user_id → list[ScalpSession]
        self._sessions: dict[int, list[ScalpSession]] = {}

        # Per-session candle buffers: "{session_id}" → CandleBuffer
        self._candle_buffers: dict[str, CandleBuffer] = {}

        # Per-session UT Bot values for edge detection
        self._utbot_values: dict[str, float | None] = {}      # session_id → current
        self._prev_utbot_values: dict[str, float | None] = {}  # session_id → previous

        # Lookup: underlying_instrument_token → list of session_ids for that user
        self._underlying_map: dict[str, list[int]] = {}  # instrument_token → [session.id, ...]
        # Lookup: option_instrument_token → session_id
        self._premium_map: dict[str, int] = {}  # instrument_token → session.id

    # ── Lifecycle ────────────────────────────────────────────────────

    async def load_sessions(self) -> None:
        """Load enabled sessions from DB into memory. Called each poll cycle.

        Preserves in-memory runtime state across reloads: DB provides config
        (possibly edited by user) but transient runtime fields like entry_price
        and highest_premium live in memory and are only persisted at state
        transitions. Wholesale replacement would reset them every 30s.

        Also handles two HOLDING-dropout cases before finalizing the refresh:

        1. ``pending_action`` set by the API (user clicked disable/delete
           while holding) — exit the position, then apply the action.
        2. Defensive: in-memory HOLDING session that disappeared from the
           enabled list (direct DB edit or legacy code path) — force exit
           so we don't leak a broker position the daemon stops watching.
        """
        from database.session import get_db_context
        from monitor.scalp_crud import get_enabled_sessions, db_to_session

        async with get_db_context() as db:
            rows = await get_enabled_sessions(db)

        # Index existing sessions by id so we can preserve their runtime.
        existing: dict[int, ScalpSession] = {}
        for sessions in self._sessions.values():
            for s in sessions:
                existing[s.id] = s

        new_sessions: dict[int, list[ScalpSession]] = {}
        new_underlying_map: dict[str, list[int]] = {}
        new_premium_map: dict[str, int] = {}
        pending_actions: list[tuple[ScalpSession, str]] = []

        for row in rows:
            session = db_to_session(row)
            prior = existing.get(row.id)
            if prior is not None:
                # Keep live runtime; config may have been edited via UI/API.
                session.runtime = prior.runtime
            uid = session.user_id
            new_sessions.setdefault(uid, []).append(session)

            # Index by underlying
            ukey = f"{uid}:{session.config.underlying_instrument_token}"
            new_underlying_map.setdefault(ukey, []).append(session.id)

            # Index by held option
            if session.runtime.current_instrument_token:
                pkey = f"{uid}:{session.runtime.current_instrument_token}"
                new_premium_map[pkey] = session.id

            # Create candle buffer if not exists
            buf_key = str(session.id)
            if buf_key not in self._candle_buffers:
                tf = session.config.indicator_timeframe
                minutes = _parse_timeframe(tf)
                self._candle_buffers[buf_key] = CandleBuffer(minutes)

            if session.config.pending_action:
                pending_actions.append((session, session.config.pending_action))

        # Defensive: in-memory HOLDING sessions that vanished from DB.
        new_ids = {row.id for row in rows}
        dropped_holding: list[ScalpSession] = [
            s for s in existing.values()
            if s.is_holding and s.id not in new_ids
        ]

        self._sessions = new_sessions
        self._underlying_map = new_underlying_map
        self._premium_map = new_premium_map

        total = sum(len(v) for v in new_sessions.values())
        if total:
            logger.info("Loaded %d scalp sessions for %d users", total, len(new_sessions))

        # Handle dropped holdings — exit so we don't leak the broker position.
        for s in dropped_holding:
            logger.warning(
                "Session %d: HOLDING but removed from enabled list — force-exiting",
                s.id,
            )
            await self._exit_position(s, "exit_disabled", s.runtime.last_premium_ltp)

        # Handle API-requested pending actions.
        for session, action in pending_actions:
            await self._handle_pending_action(session, action)

    async def _handle_pending_action(
        self, session: ScalpSession, action: str
    ) -> None:
        """Process an API-set pending_action. Exits the position if HOLDING,
        then applies the requested disable or delete and clears the flag."""
        from database.session import get_db_context
        from monitor.scalp_crud import (
            clear_pending_action,
            delete_session as crud_delete,
            update_session as crud_update,
        )

        if session.is_holding:
            logger.info(
                "Session %d: handling pending_action=%s (state=%s) — exiting",
                session.id, action, session.runtime.state.value,
            )
            await self._exit_position(
                session, "exit_disabled", session.runtime.last_premium_ltp
            )

        try:
            async with get_db_context() as db:
                if action == "exit_and_delete":
                    await crud_delete(db, session.id)
                    logger.info("Session %d: deleted after exit_disabled", session.id)
                else:
                    # exit_and_disable (and any unknown action defaults to disable)
                    await crud_update(db, session.id, enabled=False, pending_action=None)
                    logger.info("Session %d: disabled after exit_disabled", session.id)
                # Drop the session from in-memory maps so it stops receiving ticks.
                self._drop_session_from_memory(session)
        except Exception as e:
            logger.error(
                "Session %d: failed to finalize pending_action=%s: %s",
                session.id, action, e, exc_info=True,
            )
            # Best-effort flag clear so we don't loop on the same action.
            try:
                async with get_db_context() as db:
                    await clear_pending_action(db, session.id)
            except Exception:
                pass

    def _drop_session_from_memory(self, session: ScalpSession) -> None:
        """Remove a session from in-memory maps after it's disabled/deleted."""
        uid = session.user_id
        sessions = self._sessions.get(uid, [])
        self._sessions[uid] = [s for s in sessions if s.id != session.id]
        if not self._sessions[uid]:
            self._sessions.pop(uid, None)
        # Prune index maps for this session.
        ukey = f"{uid}:{session.config.underlying_instrument_token}"
        if ukey in self._underlying_map:
            self._underlying_map[ukey] = [
                sid for sid in self._underlying_map[ukey] if sid != session.id
            ]
            if not self._underlying_map[ukey]:
                self._underlying_map.pop(ukey, None)
        # Option instrument map was already cleaned in _exit_position if we held.

    def get_subscribed_instruments(self, user_id: int) -> set[str]:
        """Return instruments this manager needs subscribed for a user."""
        instruments: set[str] = set()
        for session in self._sessions.get(user_id, []):
            instruments.add(session.config.underlying_instrument_token)
            if session.runtime.current_instrument_token:
                instruments.add(session.runtime.current_instrument_token)
        return instruments

    def get_session_by_id(self, session_id: int) -> ScalpSession | None:
        """Find a session across all users."""
        for sessions in self._sessions.values():
            for s in sessions:
                if s.id == session_id:
                    return s
        return None

    # ── Tick processing ──────────────────────────────────────────────

    async def on_tick(
        self,
        user_id: int,
        instrument_token: str,
        market_data: dict,
    ) -> None:
        """Process a tick. Handles both underlying and premium instruments."""
        ltp = market_data.get("ltp")
        if ltp is None:
            return

        # Check underlying sessions
        ukey = f"{user_id}:{instrument_token}"
        session_ids = self._underlying_map.get(ukey)
        if session_ids:
            for sid in session_ids:
                session = self.get_session_by_id(sid)
                if session and session.config.enabled:
                    await self._process_underlying_tick(session, ltp)

        # Check premium sessions
        pkey = f"{user_id}:{instrument_token}"
        sid = self._premium_map.get(pkey)
        if sid:
            session = self.get_session_by_id(sid)
            if session and session.is_holding:
                await self._process_premium_tick(session, ltp)

    async def _process_underlying_tick(
        self, session: ScalpSession, ltp: float
    ) -> None:
        """Feed underlying tick to candle buffer, evaluate UT Bot on close."""
        buf_key = str(session.id)
        buf = self._candle_buffers.get(buf_key)
        if not buf:
            return

        prev_count = len(buf.get_completed_candles())
        buf.add_tick(ltp, 0, datetime.utcnow())
        new_count = len(buf.get_completed_candles())

        if new_count <= prev_count:
            return  # No new candle closed

        # Recompute UT Bot
        candles = buf.get_completed_candles()
        params = {
            "sensitivity": session.config.utbot_sensitivity,
            "period": session.config.utbot_period,
        }
        utbot_val = compute_indicator("utbot", candles, params)

        prev_val = self._utbot_values.get(buf_key)
        self._prev_utbot_values[buf_key] = prev_val
        self._utbot_values[buf_key] = utbot_val

        if utbot_val is None or prev_val is None:
            return

        # Detect direction flip
        bullish_flip = prev_val <= 0 and utbot_val > 0
        bearish_flip = prev_val >= 0 and utbot_val < 0

        rt = session.runtime

        if rt.state == ScalpState.IDLE:
            if bullish_flip:
                await self._try_enter(session, "CE", ltp)
            elif bearish_flip:
                await self._try_enter(session, "PE", ltp)
        elif rt.state == ScalpState.HOLDING_CE and bearish_flip:
            # UT Bot reversal while holding CE → exit.
            # Use last-seen premium LTP, NOT underlying `ltp` (unit mismatch
            # would corrupt P&L — e.g. 24205 underlying vs 159 premium entry
            # reported ₹15L phantom profit on 2026-04-17).
            await self._exit_position(session, "exit_reversal", rt.last_premium_ltp)
        elif rt.state == ScalpState.HOLDING_PE and bullish_flip:
            # UT Bot reversal while holding PE → exit.
            await self._exit_position(session, "exit_reversal", rt.last_premium_ltp)

    async def _process_premium_tick(
        self, session: ScalpSession, ltp: float
    ) -> None:
        """Check SL/target/trail on the held option premium."""
        rt = session.runtime
        cfg = session.config

        # Track last premium LTP so reversal exits (driven by underlying ticks)
        # can report/compute P&L in premium space.
        rt.last_premium_ltp = ltp

        # Set entry_price on first premium tick if not yet set.
        # Highest_premium and trail_armed remain at initial values so the
        # trail can arm on the next qualifying tick, not from a random
        # first-tick anchor.
        if rt.entry_price is None:
            rt.entry_price = ltp
            logger.info(
                "Session %d: entry_price set from first premium tick: %.2f",
                session.id, ltp,
            )
            # Patch the entry log row so historical P&L analysis has the pair.
            try:
                from database.session import get_db_context
                from monitor.scalp_crud import backfill_entry_price
                async with get_db_context() as db:
                    await backfill_entry_price(db, session.id, ltp)
            except Exception as e:
                logger.error("Session %d: entry_price backfill failed: %s", session.id, e)
            return

        # Check SL first — armed trail must not override SL.
        if cfg.sl_points is not None:
            sl_level = rt.entry_price - cfg.sl_points
            if ltp <= sl_level:
                await self._exit_position(session, "exit_sl", ltp)
                return

        # Check target.
        if cfg.target_points is not None:
            target_level = rt.entry_price + cfg.target_points
            if ltp >= target_level:
                await self._exit_position(session, "exit_target", ltp)
                return

        # Trail arming. trail_arm_points=None means arm immediately at
        # any uptick past entry (pre-027 behavior). trail_arm_points=N
        # waits until the position is +N points in profit.
        trail_configured = cfg.trail_points is not None or cfg.trail_percent is not None
        if trail_configured and not rt.trail_armed:
            arm_threshold = cfg.trail_arm_points or 0
            if ltp >= rt.entry_price + arm_threshold:
                rt.trail_armed = True
                rt.highest_premium = ltp
                logger.info(
                    "Session %d: trail armed @ %.2f (entry=%.2f, +%.2f pts)",
                    session.id, ltp, rt.entry_price, ltp - rt.entry_price,
                )

        # Track highest only after arming.
        if rt.trail_armed:
            if rt.highest_premium is None or ltp > rt.highest_premium:
                rt.highest_premium = ltp

        # Trail check — only fires when armed.
        if rt.trail_armed and rt.highest_premium is not None:
            trail_level: float | None = None
            if cfg.trail_points is not None:
                # Absolute points trail — preferred when both are set.
                trail_level = rt.highest_premium - cfg.trail_points
            elif cfg.trail_percent is not None:
                trail_level = rt.highest_premium * (1 - cfg.trail_percent / 100)
            if trail_level is not None and ltp <= trail_level:
                await self._exit_position(session, "exit_trail", ltp)
                return

    async def check_time_squareoff(self) -> None:
        """Check all HOLDING sessions for time-based squareoff."""
        from zoneinfo import ZoneInfo

        ist = ZoneInfo("Asia/Kolkata")
        now_ist = datetime.now(ist)
        # Skip weekends
        if now_ist.weekday() >= 5:
            return

        for sessions in self._sessions.values():
            for session in sessions:
                if not session.is_holding:
                    continue
                hour, minute = (int(p) for p in session.config.squareoff_time.split(":"))
                squareoff_time = now_ist.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if now_ist >= squareoff_time:
                    logger.info(
                        "Session %d: time squareoff at %s IST",
                        session.id, session.config.squareoff_time,
                    )
                    await self._exit_position(
                        session, "exit_squareoff", session.runtime.last_premium_ltp
                    )

    # ── Entry ────────────────────────────────────────────────────────

    async def _try_enter(
        self, session: ScalpSession, direction: str, underlying_price: float
    ) -> None:
        """Attempt to enter a position. Guards: cooldown, max_trades, mutual exclusion."""
        rt = session.runtime
        cfg = session.config

        # Mutual exclusion
        if rt.state != ScalpState.IDLE:
            return

        # Max trades guard
        if cfg.max_trades and rt.trade_count >= cfg.max_trades:
            logger.info("Session %d: max_trades reached (%d)", session.id, cfg.max_trades)
            return

        # Past squareoff_time guard — prevents the wasteful
        # enter→immediate-squareoff cycle observed 2026-04-17 15:15-15:32
        # where 4 back-to-back entries each got squared off the next poll.
        from zoneinfo import ZoneInfo
        ist_now = datetime.now(ZoneInfo("Asia/Kolkata"))
        try:
            hour, minute = (int(p) for p in cfg.squareoff_time.split(":"))
            squareoff_dt = ist_now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if ist_now >= squareoff_dt:
                logger.info(
                    "Session %d: past squareoff time (%s IST) — skip entry",
                    session.id, cfg.squareoff_time,
                )
                return
        except Exception:
            pass

        # Cooldown guard
        if rt.last_exit_time:
            elapsed = (datetime.utcnow() - rt.last_exit_time).total_seconds()
            if elapsed < cfg.cooldown_seconds:
                logger.debug(
                    "Session %d: cooldown (%.0fs < %ds)",
                    session.id, elapsed, cfg.cooldown_seconds,
                )
                return

        await self._enter_position(session, direction, underlying_price)

    async def _enter_position(
        self, session: ScalpSession, direction: str, underlying_price: float
    ) -> None:
        """IDLE → HOLDING_CE or HOLDING_PE."""
        from strategies.fno_utils import resolve_option_instrument, list_strikes, get_lot_size

        cfg = session.config
        rt = session.runtime
        option_type = direction  # "CE" or "PE"

        try:
            # Resolve ATM strike
            strikes = list_strikes(cfg.underlying, cfg.expiry, option_type)
            if not strikes:
                logger.error("Session %d: no strikes for %s %s %s", session.id, cfg.underlying, cfg.expiry, option_type)
                await self._log_event(session, "order_failed", underlying_price=underlying_price,
                                      trigger_snapshot={"error": "no strikes available"})
                return

            atm_strike = min(strikes, key=lambda s: abs(s - underlying_price))
            inst_info = resolve_option_instrument(cfg.underlying, cfg.expiry, atm_strike, option_type)
            instrument_key = inst_info["instrument_key"]
            tradingsymbol = inst_info.get("tradingsymbol", "")
            lot_size = get_lot_size(cfg.underlying)
            quantity = cfg.lots * lot_size

            # Cross-session mutex on instrument — prevents two sessions on the
            # same user from holding the same option contract. Observed on
            # 2026-04-17: sessions 3 and 5 both held 24300 CE; premium_map only
            # routes ticks to one, stranding the other with entry_price=NULL.
            pkey = f"{cfg.user_id}:{instrument_key}"
            existing_sid = self._premium_map.get(pkey)
            if existing_sid and existing_sid != session.id:
                other = self.get_session_by_id(existing_sid)
                if other and other.is_holding:
                    logger.warning(
                        "Session %d: skip entry — session %d already holds %s",
                        session.id, existing_sid, instrument_key,
                    )
                    await self._log_event(
                        session, "order_failed", option_type=option_type,
                        strike=atm_strike, instrument_token=instrument_key,
                        underlying_price=underlying_price,
                        trigger_snapshot={
                            "reason": "instrument_held_by_session",
                            "other_session_id": existing_sid,
                        },
                    )
                    return

            logger.info(
                "Session %d: ENTRY %s — ATM strike=%.0f inst=%s qty=%d (underlying=%.2f)",
                session.id, option_type, atm_strike, instrument_key, quantity, underlying_price,
            )

            # Place order
            order_result = await self._place_order(
                user_id=cfg.user_id,
                instrument_token=instrument_key,
                symbol=tradingsymbol,
                transaction_type="BUY",
                quantity=quantity,
                product=cfg.product,
            )

            if not order_result.get("success"):
                logger.error("Session %d: entry order failed: %s", session.id, order_result)
                await self._log_event(
                    session, "order_failed", option_type=option_type, strike=atm_strike,
                    instrument_token=instrument_key, underlying_price=underlying_price,
                    trigger_snapshot={"order_result": order_result},
                )
                return

            # Transition state
            rt.state = ScalpState.HOLDING_CE if direction == "CE" else ScalpState.HOLDING_PE
            rt.current_option_type = option_type
            rt.current_strike = atm_strike
            rt.current_instrument_token = instrument_key
            rt.current_tradingsymbol = tradingsymbol
            rt.entry_price = None  # Set on first premium tick
            rt.entry_time = datetime.utcnow()
            rt.highest_premium = None
            rt.trail_armed = False

            # Update premium map so ticks get routed
            pkey = f"{cfg.user_id}:{instrument_key}"
            self._premium_map[pkey] = session.id

            # Subscribe to option premium
            await self._subscribe_instrument(cfg.user_id, instrument_key)

            # Log and persist
            await self._log_event(
                session, f"entry_{option_type.lower()}", option_type=option_type,
                strike=atm_strike, instrument_token=instrument_key, quantity=quantity,
                underlying_price=underlying_price,
                order_id=order_result.get("order_id"),
            )
            await self._persist_state(session)

        except Exception as e:
            logger.error("Session %d: entry failed: %s", session.id, e, exc_info=True)
            await self._log_event(
                session, "error", underlying_price=underlying_price,
                trigger_snapshot={"error": str(e)},
            )

    # ── Exit ─────────────────────────────────────────────────────────

    async def _exit_position(
        self,
        session: ScalpSession,
        reason: str,
        exit_price: float | None = None,
    ) -> None:
        """HOLDING_CE/HOLDING_PE → IDLE."""
        rt = session.runtime
        cfg = session.config

        if not session.is_holding:
            return

        from strategies.fno_utils import get_lot_size
        lot_size = get_lot_size(cfg.underlying)
        quantity = cfg.lots * lot_size

        logger.info(
            "Session %d: EXIT %s — reason=%s exit_price=%s entry_price=%s",
            session.id, rt.current_option_type, reason,
            exit_price, rt.entry_price,
        )

        try:
            order_result = await self._place_order(
                user_id=cfg.user_id,
                instrument_token=rt.current_instrument_token,
                symbol=rt.current_tradingsymbol or "",
                transaction_type="SELL",
                quantity=quantity,
                product=cfg.product,
            )

            if not order_result.get("success"):
                logger.error("Session %d: exit order failed: %s", session.id, order_result)
                await self._log_event(
                    session, "order_failed", option_type=rt.current_option_type,
                    strike=rt.current_strike, instrument_token=rt.current_instrument_token,
                    trigger_snapshot={"reason": reason, "order_result": order_result},
                )
                return  # Stay HOLDING, retry on next qualifying tick

        except Exception as e:
            logger.error("Session %d: exit order failed: %s", session.id, e, exc_info=True)
            await self._log_event(session, "error", trigger_snapshot={"error": str(e)})
            return

        # Calculate P&L
        pnl_points = None
        pnl_amount = None
        if rt.entry_price is not None and exit_price is not None:
            pnl_points = exit_price - rt.entry_price
            pnl_amount = pnl_points * quantity

        # Unsubscribe from option premium
        if rt.current_instrument_token:
            pkey = f"{cfg.user_id}:{rt.current_instrument_token}"
            self._premium_map.pop(pkey, None)
            await self._unsubscribe_instrument(cfg.user_id, rt.current_instrument_token)

        # Log exit
        await self._log_event(
            session, reason,
            option_type=rt.current_option_type,
            strike=rt.current_strike,
            instrument_token=rt.current_instrument_token,
            entry_price=rt.entry_price,
            exit_price=exit_price,
            quantity=quantity,
            pnl_points=pnl_points,
            pnl_amount=pnl_amount,
            order_id=order_result.get("order_id"),
        )

        # Transition to IDLE
        rt.state = ScalpState.IDLE
        rt.current_option_type = None
        rt.current_strike = None
        rt.current_instrument_token = None
        rt.current_tradingsymbol = None
        rt.entry_price = None
        rt.entry_time = None
        rt.highest_premium = None
        rt.trail_armed = False
        rt.last_premium_ltp = None
        rt.trade_count += 1
        rt.last_exit_time = datetime.utcnow()

        await self._persist_state(session)

    # ── Reconciliation ───────────────────────────────────────────────

    async def reconcile_on_startup(self) -> None:
        """Check HOLDING sessions against actual broker positions on daemon start."""
        for sessions in self._sessions.values():
            for session in sessions:
                if not session.is_holding:
                    continue
                try:
                    client = await self._get_client(session.user_id)
                    positions = await client.get_positions()

                    # Check if the held option instrument appears in positions
                    found = False
                    for pos in positions:
                        inst_key = getattr(pos, "instrument_token", None)
                        qty = getattr(pos, "quantity", 0)
                        if inst_key == session.runtime.current_instrument_token and qty > 0:
                            found = True
                            break

                    if not found:
                        logger.warning(
                            "Session %d: HOLDING but position not found — reconciling to IDLE",
                            session.id,
                        )
                        await self._log_event(session, "reconcile", trigger_snapshot={
                            "expected_instrument": session.runtime.current_instrument_token,
                            "expected_state": session.runtime.state.value,
                        })
                        session.runtime.state = ScalpState.IDLE
                        session.runtime.current_option_type = None
                        session.runtime.current_strike = None
                        session.runtime.current_instrument_token = None
                        session.runtime.current_tradingsymbol = None
                        session.runtime.entry_price = None
                        session.runtime.entry_time = None
                        session.runtime.highest_premium = None
                        session.runtime.trail_armed = False
                        await self._persist_state(session)
                    else:
                        logger.info("Session %d: reconciled — position confirmed", session.id)
                        # Re-subscribe to option premium
                        await self._subscribe_instrument(
                            session.user_id, session.runtime.current_instrument_token
                        )

                except Exception as e:
                    logger.error(
                        "Session %d: reconciliation failed: %s", session.id, e, exc_info=True
                    )

    # ── Order Placement ──────────────────────────────────────────────

    async def _place_order(
        self,
        user_id: int,
        instrument_token: str,
        symbol: str,
        transaction_type: str,
        quantity: int,
        product: str = "I",
        order_type: str = "MARKET",
    ) -> dict:
        """Place an F&O order via Upstox SDK."""
        if self._paper_mode:
            logger.info(
                "[PAPER] Scalp order: %s %d of %s (%s)",
                transaction_type, quantity, symbol, instrument_token,
            )
            return {"success": True, "order_id": "PAPER-001", "message": "Paper order"}

        # Check for order node
        node_url = None
        if self._get_order_node_url:
            node_url = await self._get_order_node_url(user_id)

        if node_url:
            return await self._place_order_via_node(
                user_id, node_url, instrument_token, symbol,
                transaction_type, quantity, product, order_type,
            )

        return await self._place_order_direct(
            user_id, instrument_token, symbol,
            transaction_type, quantity, product, order_type,
        )

    async def _place_order_direct(
        self, user_id, instrument_token, symbol,
        transaction_type, quantity, product, order_type,
    ) -> dict:
        """Place order directly via Upstox SDK (F&O path)."""
        client = await self._get_client(user_id)
        try:
            import upstox_client
            api_client = upstox_client.ApiClient(client._configuration)
            order_api = upstox_client.OrderApiV3(api_client)

            is_amo = not client._is_market_open()
            body = upstox_client.PlaceOrderV3Request(
                quantity=quantity,
                product=product,
                validity="DAY",
                price=0,
                trigger_price=0,
                instrument_token=instrument_token,
                order_type=order_type,
                transaction_type=transaction_type,
                disclosed_quantity=0,
                is_amo=is_amo,
            )
            response = order_api.place_order(body)
            order_ids = response.data.order_ids if response.data else []
            order_id = order_ids[0] if order_ids else None
            return {"success": True, "order_id": order_id, "status": "PLACED"}
        except Exception as e:
            logger.error("Scalp order failed (user=%d): %s", user_id, e)
            return {"success": False, "error": str(e)}

    async def _place_order_via_node(
        self, user_id, node_url, instrument_token, symbol,
        transaction_type, quantity, product, order_type,
    ) -> dict:
        """Place order through user's order node proxy."""
        from services.order_node_proxy import OrderNodeProxy
        client = await self._get_client(user_id)
        token = client.access_token
        proxy = OrderNodeProxy(node_url, token)
        try:
            result = await proxy.place_order(
                symbol=symbol,
                instrument_token=instrument_token,
                transaction_type=transaction_type,
                quantity=quantity,
                order_type=order_type,
                price=0,
                product=product,
            )
            return {
                "success": result.success,
                "order_id": result.order_id,
                "message": result.message,
            }
        except Exception as e:
            logger.error("Scalp order via node failed (user=%d): %s", user_id, e)
            return {"success": False, "error": str(e)}

    # ── Subscription helpers ─────────────────────────────────────────

    async def _subscribe_instrument(self, user_id: int, instrument_token: str) -> None:
        """Subscribe to an instrument via user_manager's market stream."""
        try:
            from monitor.user_manager import UserManager
            # Access the daemon's user_manager through the module-level reference
            # set during daemon init. This avoids circular imports.
            if hasattr(self, '_user_manager') and self._user_manager:
                session_obj = self._user_manager.get_session(user_id)
                if session_obj and instrument_token not in session_obj.subscribed_instruments:
                    await session_obj.market_stream.subscribe([instrument_token])
                    session_obj.subscribed_instruments.add(instrument_token)
                    logger.info("Scalp: subscribed to %s for user %d", instrument_token, user_id)
        except Exception as e:
            logger.error("Failed to subscribe %s: %s", instrument_token, e)

    async def _unsubscribe_instrument(self, user_id: int, instrument_token: str) -> None:
        """Unsubscribe from an instrument."""
        try:
            if hasattr(self, '_user_manager') and self._user_manager:
                session_obj = self._user_manager.get_session(user_id)
                if session_obj and instrument_token in session_obj.subscribed_instruments:
                    await session_obj.market_stream.unsubscribe([instrument_token])
                    session_obj.subscribed_instruments.discard(instrument_token)
                    logger.info("Scalp: unsubscribed from %s for user %d", instrument_token, user_id)
        except Exception as e:
            logger.error("Failed to unsubscribe %s: %s", instrument_token, e)

    # ── Persistence helpers ──────────────────────────────────────────

    async def _persist_state(self, session: ScalpSession) -> None:
        """Persist session runtime state to DB (background-safe)."""
        try:
            from database.session import get_db_context
            from monitor.scalp_crud import persist_session_state
            async with get_db_context() as db:
                await persist_session_state(db, session.id, session.runtime)
        except Exception as e:
            logger.error("Session %d: persist state failed: %s", session.id, e)

    async def _log_event(self, session: ScalpSession, event_type: str, **kwargs) -> None:
        """Log an event to the session log table."""
        try:
            from database.session import get_db_context
            from monitor.scalp_crud import log_event
            async with get_db_context() as db:
                await log_event(db, session.id, session.user_id, event_type, **kwargs)
        except Exception as e:
            logger.error("Session %d: log event failed: %s", session.id, e)


# ── Utility ──────────────────────────────────────────────────────────


def _parse_timeframe(tf: str) -> int:
    """Parse timeframe string like '1m', '5m', '15m' to minutes."""
    tf = tf.strip().lower()
    if tf.endswith("m"):
        return int(tf[:-1])
    if tf.endswith("h"):
        return int(tf[:-1]) * 60
    return int(tf)
