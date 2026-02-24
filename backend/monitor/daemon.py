"""MonitorDaemon — main daemon loop for the trade monitor.

Polls DB for active rules, manages user sessions via UserManager,
routes market ticks/portfolio events/time checks to rule evaluation,
and dispatches fired rules to ActionExecutor.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Optional

from database.session import get_db_context
from monitor import crud
from monitor.action_executor import ActionExecutor
from monitor.models import MonitorRule
from monitor.rule_evaluator import EvalContext, RuleResult, evaluate_rule
from monitor.user_manager import UserManager
from services.upstox_client import UpstoxClient

logger = logging.getLogger(__name__)


class MonitorDaemon:
    """Main daemon that ties the trade monitor components together.

    Responsibilities:
    - Periodically polls DB for active rules (every ``poll_interval`` seconds)
    - Loads Upstox access tokens from the DB (encrypted, per-user)
    - Starts/stops/syncs per-user streaming sessions via UserManager
    - Routes market data ticks to price/indicator rule evaluation
    - Routes portfolio events to order-status rule evaluation
    - Periodically evaluates time-based rules
    - Dispatches fired rules to ActionExecutor

    Args:
        paper_mode: If True, ActionExecutor logs actions instead of executing.
        poll_interval: Seconds between DB polls and time-rule checks.
    """

    def __init__(
        self,
        paper_mode: bool = False,
        poll_interval: float = 30.0,
    ) -> None:
        self._paper_mode = paper_mode
        self._poll_interval = poll_interval
        self._running = False

        self._user_manager = UserManager(
            on_tick=self._on_tick,
            on_portfolio_event=self._on_portfolio_event,
        )
        self._action_executor = ActionExecutor(
            get_client=self._get_client,
            paper_mode=paper_mode,
        )

        self._rules_by_user: dict[int, list[MonitorRule]] = {}
        self._access_tokens: dict[int, str] = {}
        # Manual token overrides (for testing / CLI fallback).
        # These take precedence over DB-loaded tokens.
        self._manual_tokens: dict[int, str] = {}

    # ── Public API ────────────────────────────────────────────────────

    async def start(self) -> None:
        """Main daemon loop.

        Loads rules from DB, then loops: sleep -> poll rules -> check
        time triggers. Runs until ``stop()`` is called.
        """
        self._running = True
        logger.info("Monitor daemon starting (paper=%s)", self._paper_mode)

        # Initial rule load
        await self._poll_rules()

        # Main loop: poll rules + check time triggers periodically
        while self._running:
            await asyncio.sleep(self._poll_interval)
            await self._poll_rules()
            await self._check_time_rules()

    async def stop(self) -> None:
        """Graceful shutdown — stops all user sessions."""
        self._running = False
        await self._user_manager.stop_all()
        logger.info("Monitor daemon stopped")

    def set_access_token(self, user_id: int, token: str) -> None:
        """Manually set an access token (overrides DB lookup for this user).

        Primarily used for testing and CLI fallback. In production the
        daemon loads tokens from the DB automatically.
        """
        self._manual_tokens[user_id] = token
        self._access_tokens[user_id] = token

    # ── Token loading ────────────────────────────────────────────────

    async def _load_access_token(self, user_id: int) -> Optional[str]:
        """Load access token for a user.

        Manual overrides (via ``set_access_token``) take precedence.
        Otherwise loads from the DB via ``get_user_upstox_token`` which
        decrypts the token and checks expiry — returns None if expired.
        If the DB token is expired/missing and TOTP credentials are
        configured, attempts automatic token refresh via TOTP.
        """
        if user_id in self._manual_tokens:
            return self._manual_tokens[user_id]
        # Lazy import to avoid circular deps and keep tests lightweight
        from api.upstox_oauth import get_user_upstox_token

        # get_user_upstox_token handles expiry detection + TOTP auto-refresh
        return await get_user_upstox_token(user_id)

    # ── Rule polling ──────────────────────────────────────────────────

    async def _poll_rules(self) -> None:
        """Load active rules from DB, fetch tokens, and sync user sessions.

        Groups rules by user_id, loads access tokens from the DB for
        each user, then:
        - Starts sessions for new users (that have valid access tokens)
        - Stops sessions for users with no more active rules
        - Stops sessions for users whose tokens have expired
        - Syncs rules for users whose sessions already exist
        """
        async with get_db_context() as session:
            db_rules = await crud.get_active_rules_for_daemon(session)

        # Group by user_id
        rules_by_user: dict[int, list[MonitorRule]] = {}
        for db_rule in db_rules:
            schema = crud.db_rule_to_schema(db_rule)
            rules_by_user.setdefault(schema.user_id, []).append(schema)

        # Load access tokens from DB for all users with active rules
        for uid in rules_by_user:
            token = await self._load_access_token(uid)
            if token:
                self._access_tokens[uid] = token
            else:
                self._access_tokens.pop(uid, None)
                logger.debug("No valid Upstox token for user %d, skipping", uid)

        # Determine users to start/stop/sync
        old_users = set(self._rules_by_user.keys())
        new_users = set(rules_by_user.keys())

        # Stop users with no more rules
        for uid in old_users - new_users:
            await self._user_manager.stop_user(uid)

        # Start new users (only if we have an access token)
        for uid in new_users - old_users:
            token = self._access_tokens.get(uid)
            if token:
                await self._user_manager.start_user(uid, token, rules_by_user[uid])

        # Sync or restart existing users
        for uid in old_users & new_users:
            token = self._access_tokens.get(uid)
            if not token:
                # Token expired mid-session — stop the user
                await self._user_manager.stop_user(uid)
                logger.info(
                    "Stopped session for user %d (token expired)", uid
                )
                continue
            # Check if the token changed (e.g. TOTP refresh) — restart streams
            session = self._user_manager.get_session(uid)
            if session and session.access_token != token:
                logger.info("Token changed for user %d, restarting streams", uid)
                await self._user_manager.start_user(uid, token, rules_by_user[uid])
            else:
                await self._user_manager.sync_rules(uid, rules_by_user[uid])

        self._rules_by_user = rules_by_user

    # ── Tick routing ──────────────────────────────────────────────────

    async def _on_tick(
        self, user_id: int, instrument_token: str, market_data: dict
    ) -> None:
        """Called on every market data tick. Evaluate price/indicator/compound rules."""
        session_obj = self._user_manager.get_session(user_id)
        if session_obj is None:
            return

        for rule in session_obj.rules:
            if rule.trigger_type not in ("price", "indicator", "compound", "trailing_stop"):
                continue
            if rule.instrument_token != instrument_token:
                continue

            ctx = EvalContext(
                market_data=market_data,
                prev_prices=session_obj.prev_prices,
                now=datetime.utcnow(),
                indicator_values=session_obj.indicator_values,
                prev_indicator_values=session_obj.prev_indicator_values,
            )
            await self._evaluate_and_execute(rule, ctx)

    # ── Portfolio event routing ───────────────────────────────────────

    async def _on_portfolio_event(self, user_id: int, event: dict) -> None:
        """Called on portfolio events. Evaluate order_status rules."""
        rules = self._rules_by_user.get(user_id, [])
        for rule in rules:
            if rule.trigger_type != "order_status":
                continue
            ctx = EvalContext(order_event=event, now=datetime.utcnow())
            await self._evaluate_and_execute(rule, ctx)

    # ── Time rule checking ────────────────────────────────────────────

    async def _check_time_rules(self) -> None:
        """Evaluate all time-based rules (called every poll_interval)."""
        now = datetime.utcnow()
        for user_id, rules in self._rules_by_user.items():
            for rule in rules:
                if rule.trigger_type != "time":
                    continue
                ctx = EvalContext(now=now)
                await self._evaluate_and_execute(rule, ctx)

    # ── Evaluation + execution ────────────────────────────────────────

    async def _evaluate_and_execute(
        self, rule: MonitorRule, ctx: EvalContext
    ) -> None:
        """Evaluate a rule and execute its action if fired.

        Also persists trigger_config_update (used by trailing_stop to
        track highest_price) to DB and updates the in-memory rule.
        """
        result = evaluate_rule(rule, ctx)

        # Persist trigger_config_update if present (e.g. trailing stop highest_price)
        if result.trigger_config_update is not None:
            try:
                async with get_db_context() as db_session:
                    await crud.update_rule(
                        db_session, rule.id,
                        trigger_config=result.trigger_config_update,
                    )
                # Update in-memory rule so next tick uses new values
                rule.trigger_config = result.trigger_config_update
            except Exception as e:
                logger.error(
                    "Failed to persist trigger_config_update for rule %d: %s",
                    rule.id, e,
                )

        if not result.fired:
            return

        logger.info("Rule %d (%s) FIRED", rule.id, rule.name)

        trigger_snapshot = {
            "market_data": ctx.market_data,
            "now": str(ctx.now),
        }

        async with get_db_context() as db_session:
            await self._action_executor.execute(
                rule, result, trigger_snapshot, db_session
            )

    # ── Client factory ────────────────────────────────────────────────

    async def _get_client(self, user_id: int) -> UpstoxClient:
        """Get an UpstoxClient for a given user.

        Raises ValueError if no access token is available for the user.
        """
        token = self._access_tokens.get(user_id)
        if not token:
            raise ValueError(f"No access token for user {user_id}")
        return UpstoxClient(access_token=token, user_id=user_id)
