"""Per-user session lifecycle for the trade monitor daemon.

Manages WebSocket connections (portfolio + market data), candle buffers,
and indicator engine computations for each active user.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Coroutine

from monitor.candle_buffer import CandleBuffer
from monitor.indicator_engine import compute_indicator
from monitor.models import MonitorRule
from monitor.streams.market_data import MarketDataStream
from monitor.streams.portfolio import PortfolioStream

logger = logging.getLogger(__name__)

# Mapping from string timeframe codes to minutes for CandleBuffer
_TIMEFRAME_MINUTES: dict[str, int] = {
    "1m": 1,
    "5m": 5,
    "15m": 15,
    "30m": 30,
    "1h": 60,
    "1d": 1440,
}


def extract_instruments_from_rules(rules: list[MonitorRule]) -> set[str]:
    """Extract the set of instrument tokens that need market data subscriptions.

    Price and indicator rules use their ``instrument_token`` directly.
    Compound rules use the parent rule's ``instrument_token``.
    Time and order-status rules do not require market data subscriptions.
    """
    instruments: set[str] = set()
    for rule in rules:
        if rule.trigger_type in ("price", "indicator", "compound", "trailing_stop"):
            if rule.instrument_token:
                instruments.add(rule.instrument_token)
    return instruments


def _extract_indicator_buffer_keys(rules: list[MonitorRule]) -> dict[str, dict]:
    """Extract unique (instrument_token, timeframe) pairs needing CandleBuffers.

    Returns a dict keyed by ``{instrument_token}_{timeframe}`` with value
    containing the timeframe string and instrument_token. Also scans
    compound rule sub-conditions for indicator conditions.
    """
    keys: dict[str, dict] = {}

    def _process_indicator_config(instrument_token: str | None, config: dict):
        if not instrument_token:
            return
        timeframe = config.get("timeframe", "5m")
        buf_key = f"{instrument_token}_{timeframe}"
        keys[buf_key] = {
            "instrument_token": instrument_token,
            "timeframe": timeframe,
            "indicator": config.get("indicator"),
            "params": config.get("params", {}),
        }

    for rule in rules:
        if rule.trigger_type == "indicator":
            _process_indicator_config(rule.instrument_token, rule.trigger_config)
        elif rule.trigger_type == "compound":
            conditions = rule.trigger_config.get("conditions", [])
            for cond in conditions:
                if cond.get("type") == "indicator":
                    _process_indicator_config(rule.instrument_token, cond)

    return keys


@dataclass
class UserSession:
    """Holds the per-user streaming state."""

    user_id: int
    access_token: str
    portfolio_stream: Any  # PortfolioStream (typed as Any for testability)
    market_stream: Any  # MarketDataStream
    rules: list[MonitorRule] = field(default_factory=list)
    candle_buffers: dict[str, CandleBuffer] = field(default_factory=dict)
    prev_prices: dict[str, float] = field(default_factory=dict)
    indicator_values: dict[str, float] = field(default_factory=dict)
    prev_indicator_values: dict[str, float] = field(default_factory=dict)
    # Tracks which instruments are currently subscribed
    subscribed_instruments: set[str] = field(default_factory=set)
    # Tracks indicator buffer metadata for recomputation
    indicator_buffer_meta: dict[str, dict] = field(default_factory=dict)


class UserManager:
    """Manages per-user WebSocket sessions for the trade monitor.

    For each active user, it creates and manages:
    - PortfolioStream (order/position/holding events)
    - MarketDataStream (live price ticks)
    - CandleBuffers (per instrument/timeframe for indicator rules)
    - Indicator value recomputation on candle completion

    Args:
        on_tick: Async callback ``(user_id, instrument_token, market_data)``
                 called for each market data tick.
        on_portfolio_event: Async callback ``(user_id, event)``
                            called for each portfolio event.
    """

    def __init__(
        self,
        on_tick: Callable[[int, str, dict], Coroutine[Any, Any, None]],
        on_portfolio_event: Callable[[int, dict], Coroutine[Any, Any, None]],
        on_auth_failure: Callable[[int], Coroutine[Any, Any, None]] | None = None,
    ):
        self._sessions: dict[int, UserSession] = {}
        self._on_tick = on_tick
        self._on_portfolio_event_cb = on_portfolio_event
        self._on_auth_failure = on_auth_failure

    def get_session(self, user_id: int) -> UserSession | None:
        """Get the session for a user, or None if not active."""
        return self._sessions.get(user_id)

    async def start_user(
        self,
        user_id: int,
        access_token: str,
        rules: list[MonitorRule],
    ):
        """Start streaming for a user.

        Creates portfolio and market data WebSocket connections, subscribes
        to the instruments needed by the user's rules, and sets up candle
        buffers for indicator-based rules.
        """
        # Stop existing session if any
        if user_id in self._sessions:
            await self.stop_user(user_id)

        # Create auth failure closure that binds user_id
        auth_failure_cb = None
        if self._on_auth_failure:
            async def auth_failure_cb():
                await self._on_auth_failure(user_id)

        # Create stream instances with closures that bind user_id
        portfolio_stream = PortfolioStream(
            access_token=access_token,
            on_message=lambda event: self._on_portfolio_event(user_id, event),
            on_auth_failure=auth_failure_cb,
        )
        market_stream = MarketDataStream(
            access_token=access_token,
            on_message=lambda tick_data: self._on_market_tick(user_id, tick_data),
            on_auth_failure=auth_failure_cb,
        )

        session = UserSession(
            user_id=user_id,
            access_token=access_token,
            portfolio_stream=portfolio_stream,
            market_stream=market_stream,
            rules=list(rules),
        )
        self._sessions[user_id] = session

        # Start both streams
        await portfolio_stream.start()
        await market_stream.start()

        # Subscribe to instruments from rules
        instruments = extract_instruments_from_rules(rules)
        if instruments:
            await market_stream.subscribe(list(instruments))
            session.subscribed_instruments = instruments

        # Set up candle buffers for indicator rules
        self._sync_candle_buffers(session, rules)

        logger.info(
            f"[UserManager] Started user {user_id}: "
            f"{len(instruments)} instruments, "
            f"{len(session.candle_buffers)} candle buffers"
        )

    async def stop_user(self, user_id: int):
        """Stop streaming for a user and remove the session."""
        session = self._sessions.get(user_id)
        if session is None:
            return

        await session.portfolio_stream.stop()
        await session.market_stream.stop()
        del self._sessions[user_id]

        logger.info(f"[UserManager] Stopped user {user_id}")

    async def sync_rules(self, user_id: int, rules: list[MonitorRule]):
        """Update the rules for a user and adjust subscriptions.

        Computes the diff of subscribed instruments — subscribes to new
        ones and unsubscribes from ones no longer needed. Also creates
        or removes CandleBuffers for indicator-based rules.
        """
        session = self._sessions.get(user_id)
        if session is None:
            logger.warning(
                f"[UserManager] sync_rules for unknown user {user_id}"
            )
            return

        old_instruments = session.subscribed_instruments
        new_instruments = extract_instruments_from_rules(rules)

        # Subscribe to new instruments
        to_add = new_instruments - old_instruments
        if to_add:
            await session.market_stream.subscribe(list(to_add))

        # Unsubscribe from removed instruments
        to_remove = old_instruments - new_instruments
        if to_remove:
            await session.market_stream.unsubscribe(list(to_remove))

        session.subscribed_instruments = new_instruments
        session.rules = list(rules)

        # Sync candle buffers
        self._sync_candle_buffers(session, rules)

        logger.info(
            f"[UserManager] Synced rules for user {user_id}: "
            f"+{len(to_add)} -{len(to_remove)} instruments, "
            f"{len(session.candle_buffers)} candle buffers"
        )

    async def stop_all(self):
        """Stop all active user sessions."""
        user_ids = list(self._sessions.keys())
        for user_id in user_ids:
            await self.stop_user(user_id)
        logger.info("[UserManager] All sessions stopped")

    # ── Internal callbacks ───────────────────────────────────────────

    async def _on_market_tick(
        self,
        user_id: int,
        tick_data: dict,
        timestamp: datetime | None = None,
    ):
        """Handle a market data tick from the MarketDataStream.

        For each instrument in the tick:
        1. Feed candle buffers
        2. Recompute indicators on candle completion
        3. Forward to external on_tick callback (prev_prices still has OLD value)
        4. Update prev_prices to current LTP (for next tick's crosses_above/below)
        """
        session = self._sessions.get(user_id)
        if session is None:
            return

        ts = timestamp or datetime.utcnow()

        for instrument_key, data in tick_data.items():
            ltp = data.get("ltp")
            if ltp is None:
                continue

            volume = data.get("volume", 0)

            # 1. Feed candle buffers and check for candle completion
            for buf_key, buf in session.candle_buffers.items():
                if not buf_key.startswith(f"{instrument_key}_"):
                    continue

                # Track candle count before tick to detect new candle
                candle_count_before = len(buf.get_candles())
                buf.add_tick(ltp, volume=volume, timestamp=ts)
                candle_count_after = len(buf.get_candles())

                # 2. New candle started => previous candle completed
                candle_completed = candle_count_after > candle_count_before
                if candle_completed:
                    self._recompute_indicators(session, buf_key, buf)

            # 3. Forward to external callback (prev_prices still has OLD value)
            await self._on_tick(user_id, instrument_key, data)

            # 4. Update prev_prices AFTER callback so crosses_above/below works
            session.prev_prices[instrument_key] = ltp

    async def _on_portfolio_event(self, user_id: int, event: dict):
        """Handle a portfolio event from the PortfolioStream."""
        await self._on_portfolio_event_cb(user_id, event)

    # ── Internal helpers ─────────────────────────────────────────────

    def _sync_candle_buffers(
        self, session: UserSession, rules: list[MonitorRule]
    ):
        """Create/remove candle buffers to match the current indicator rules."""
        needed = _extract_indicator_buffer_keys(rules)
        current_keys = set(session.candle_buffers.keys())
        needed_keys = set(needed.keys())

        # Create new buffers
        for key in needed_keys - current_keys:
            meta = needed[key]
            tf_str = meta["timeframe"]
            tf_minutes = _TIMEFRAME_MINUTES.get(tf_str, 5)
            session.candle_buffers[key] = CandleBuffer(
                timeframe_minutes=tf_minutes
            )

        # Remove unused buffers
        for key in current_keys - needed_keys:
            del session.candle_buffers[key]

        # Store metadata for recomputation
        session.indicator_buffer_meta = needed

    def _recompute_indicators(
        self, session: UserSession, buf_key: str, buf: CandleBuffer
    ):
        """Recompute indicator values after a candle completes.

        Looks up which indicators need this buffer and recomputes them.
        """
        meta = session.indicator_buffer_meta.get(buf_key)
        if meta is None:
            return

        indicator = meta["indicator"]
        timeframe = meta["timeframe"]
        params = meta.get("params", {})
        ind_key = f"{indicator}_{timeframe}"

        candles = buf.get_completed_candles()
        if not candles:
            return

        # Save previous value before recomputing
        old_val = session.indicator_values.get(ind_key)
        if old_val is not None:
            session.prev_indicator_values[ind_key] = old_val

        new_val = compute_indicator(indicator, candles, params)
        if new_val is not None:
            session.indicator_values[ind_key] = new_val
