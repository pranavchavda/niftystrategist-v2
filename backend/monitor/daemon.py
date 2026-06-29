"""MonitorDaemon — main daemon loop for the trade monitor.

Polls DB for active rules, manages user sessions via UserManager,
routes market ticks/portfolio events/time checks to rule evaluation,
and dispatches fired rules to ActionExecutor.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, time as dt_time, timedelta, timezone
from typing import Optional

# IST = UTC+5:30 — used for time-trigger evaluation because users specify
# trigger times in IST (Indian market hours).
_IST = timezone(timedelta(hours=5, minutes=30))

from database.session import get_db_context
from monitor import crud
from monitor.action_executor import ActionExecutor
from monitor.models import MonitorRule
from monitor.rule_evaluator import EvalContext, RuleResult, evaluate_rule
from monitor.scalp_session import ScalpSessionManager
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

        self._auth_refresh_locks: dict[int, asyncio.Lock] = {}
        # Per-user locks to serialize tick processing.
        # Without this, rapid WebSocket ticks can evaluate the same rule
        # concurrently before fire_count is incremented, causing duplicates.
        self._tick_locks: dict[int, asyncio.Lock] = {}

        # Shared market-data feed (opt-in via NF_SHARED_MARKET_FEED=1).
        # When enabled, ALL users' market-data needs are served by a
        # single MarketDataStream owned by the feed-owner user (default
        # user 1). Per-user MarketDataStream connections are skipped.
        # PortfolioStream stays per-user.
        #
        # Background — 2026-05-07 silent-feed bug: per-user streams
        # proved unreliable for NSE_INDEX|Nifty 50 ticks (Upstox accepts
        # the diff-add subscribe but never delivers data). The shared
        # feed sidesteps this by always putting the index in the
        # initial subscribe set.
        self._shared_feed_enabled = os.getenv(
            "NF_SHARED_MARKET_FEED", "0"
        ).lower() in ("1", "true", "yes")
        self._feed_owner_user_id = int(
            os.getenv("NF_FEED_OWNER_USER_ID", "1")
        )
        self._market_pool: MarketStreamPool | None = None
        # Sector-flow streamer (opt-in via NF_SECTOR_FLOW_FEED=1). Rides the
        # shared pool to accumulate nifty500 15-min candles off the live feed
        # and compute the sector-flow snapshot — replaces the old historical-
        # fetch cron that hung prod on 2026-06-29. None unless enabled below.
        self._sector_flow = None

        if self._shared_feed_enabled:
            from monitor.streams.market_stream_pool import MarketStreamPool

            async def _get_owner_token(force_refresh: bool) -> str | None:
                # Prefer the long-lived analytics token if configured —
                # it's read-only, 1-year validity, and isolated from
                # per-user OAuth churn (which has been the source of
                # today's silent-feed flakes). Falls back to the
                # feed-owner user's regular OAuth token.
                analytics = os.getenv("UPSTOX_ANALYTICS_TOKEN", "").strip()
                if analytics:
                    return analytics
                return await self._load_access_token(
                    self._feed_owner_user_id, force_refresh=force_refresh
                )

            async def _pool_tick_handler(user_id: int, tick_data: dict) -> None:
                # Sector-flow feed rides the same pool under a sentinel uid.
                # Branch BEFORE the per-user path so the money path (rule
                # evaluation / orders) is never touched by sector ticks.
                sf = self._sector_flow
                if sf is not None and user_id == sf.SENTINEL_UID:
                    await sf.on_tick(tick_data)
                    return
                # Hand the pool's fan-out tick to UserManager so candle
                # buffers and indicator engine still run per-user.
                await self._user_manager._on_market_tick(user_id, tick_data)

            # ltpc mode — lighter payload (LTP + close only), and the
            # mode that ChartMarketStream uses successfully for NSE_INDEX
            # delivery via the same analytics token. Empirical: 2026-05-07
            # silent-feed bug only manifested with mode="full" for index
            # instruments, never on the chart stream's ltpc path.
            self._market_pool = MarketStreamPool(
                get_owner_token=_get_owner_token,
                tick_handler=_pool_tick_handler,
                mode="ltpc",
            )

            # Opt-in sector-flow streamer on the shared pool. Off by default;
            # enabled in prod via NF_SECTOR_FLOW_FEED=1.
            if os.getenv("NF_SECTOR_FLOW_FEED", "0").lower() in ("1", "true", "yes"):
                from monitor.sector_flow_streamer import SectorFlowStreamer

                self._sector_flow = SectorFlowStreamer(self._market_pool)

        self._user_manager = UserManager(
            on_tick=self._on_tick,
            on_portfolio_event=self._on_portfolio_event,
            on_auth_failure=self._on_stream_auth_failure,
            get_client=self._get_client,
            market_pool=self._market_pool,
        )
        self._action_executor = ActionExecutor(
            get_client=self._get_client,
            get_order_node_url=self._get_order_node_url,
            paper_mode=paper_mode,
        )

        self._scalp_manager = ScalpSessionManager(
            get_client=self._get_client,
            get_order_node_url=self._get_order_node_url,
            paper_mode=paper_mode,
        )
        self._scalp_manager._user_manager = self._user_manager

        self._rules_by_user: dict[int, list[MonitorRule]] = {}
        self._access_tokens: dict[int, str] = {}
        self._order_node_urls: dict[int, str] = {}
        # Manual token overrides (for testing / CLI fallback).
        # These take precedence over DB-loaded tokens.
        self._manual_tokens: dict[int, str] = {}
        # Per-rule asyncio locks held while an order placement is in flight.
        # Prevents two concurrent ticks from both calling place_order for the
        # same rule while the first call is still pending at Upstox. Origin:
        # 2026-05-11 TATACONSUM incident — a 40s SDK call was repeatedly
        # interrupted by 30s polls, each firing place_order on the same rule.
        self._rule_inflight_locks: dict[int, asyncio.Lock] = {}

    # ── Public API ────────────────────────────────────────────────────

    async def start(self) -> None:
        """Main daemon loop.

        Loads rules from DB, then loops: sleep -> poll rules -> check
        time triggers. Runs until ``stop()`` is called.
        """
        self._running = True
        logger.info(
            "Monitor daemon starting (paper=%s, shared_feed=%s, owner_uid=%s)",
            self._paper_mode,
            self._shared_feed_enabled,
            self._feed_owner_user_id if self._shared_feed_enabled else None,
        )

        # If the shared market feed is enabled, start it before the
        # first poll so user sessions register interest with a running
        # pool from the start. If the owner token isn't loadable yet
        # (e.g. TOTP cooldown), the pool stays stopped and the next
        # rotate_token attempt picks it up.
        if self._market_pool is not None:
            try:
                await self._market_pool.start()
            except Exception as e:
                logger.error(
                    "Shared market feed failed to start at boot: %s. "
                    "Will retry on next owner-token rotation.", e,
                )

        # Start the sector-flow streamer (registers its 500-name interest with
        # the pool — even if the pool itself deferred its connection, the
        # interest is recorded and resubscribed on the pool's next start/rotate).
        if self._sector_flow is not None:
            try:
                await self._sector_flow.start()
            except Exception as e:
                logger.error("Sector-flow streamer failed to start: %s", e)

        # Initial rule load + scalp session load. Order matters:
        # _poll_rules must run first because it loads access tokens, which
        # load_sessions() needs to seed candle buffers. Scalp-only users
        # (no monitor rules) miss their order_node_url on this first cycle
        # but pick it up on the next poll 30s later — that delay is the
        # acceptable cost of preserving buffer seeding for everyone.
        await self._poll_rules()
        await self._scalp_manager.load_sessions()
        await self._scalp_manager.reconcile_on_startup()

        # Main loop: poll rules + scalp sessions + check time triggers
        while self._running:
            await asyncio.sleep(self._poll_interval)
            await self._poll_rules()
            await self._scalp_manager.load_sessions()
            await self._check_time_rules()
            await self._scalp_manager.check_time_squareoff()

    async def stop(self) -> None:
        """Graceful shutdown — stops all user sessions."""
        self._running = False
        if self._sector_flow is not None:
            await self._sector_flow.stop()
        await self._user_manager.stop_all()
        if self._market_pool is not None:
            await self._market_pool.stop()
        logger.info("Monitor daemon stopped")

    def set_access_token(self, user_id: int, token: str) -> None:
        """Manually set an access token (overrides DB lookup for this user).

        Primarily used for testing and CLI fallback. In production the
        daemon loads tokens from the DB automatically.
        """
        self._manual_tokens[user_id] = token
        self._access_tokens[user_id] = token

    async def _get_order_node_url(self, user_id: int) -> str | None:
        """Return the order node URL for a user (loaded during poll)."""
        return self._order_node_urls.get(user_id)

    # ── Token loading ────────────────────────────────────────────────

    async def _load_access_token(
        self, user_id: int, force_refresh: bool = False
    ) -> Optional[str]:
        """Load access token for a user.

        Manual overrides (via ``set_access_token``) take precedence.
        Otherwise loads from the DB via ``get_user_upstox_token`` which
        decrypts the token and checks expiry — returns None if expired.
        If the DB token is expired/missing and TOTP credentials are
        configured, attempts automatic token refresh via TOTP.

        Args:
            force_refresh: Bypass "recently refreshed" guard and force
                TOTP refresh. Use after 401 from Upstox (token invalidated
                server-side despite valid DB expiry).
        """
        if user_id in self._manual_tokens and not force_refresh:
            return self._manual_tokens[user_id]
        # Lazy import to avoid circular deps and keep tests lightweight
        from api.upstox_oauth import get_user_upstox_token

        # get_user_upstox_token handles expiry detection + TOTP auto-refresh
        return await get_user_upstox_token(user_id, force_refresh=force_refresh)

    async def _load_user_configs(self, user_ids) -> None:
        """Load access tokens and order_node_urls for all users with active rules."""
        from database.models import User
        from sqlalchemy import select

        # Load order_node_urls in one query
        async with get_db_context() as session:
            result = await session.execute(
                select(User.id, User.order_node_url).where(User.id.in_(list(user_ids)))
            )
            for uid, node_url in result:
                if node_url:
                    self._order_node_urls[uid] = node_url
                else:
                    self._order_node_urls.pop(uid, None)

        # Load access tokens (one at a time — each may trigger TOTP refresh)
        for uid in user_ids:
            token = await self._load_access_token(uid)
            if token:
                self._access_tokens[uid] = token
            else:
                self._access_tokens.pop(uid, None)
                logger.debug("No valid Upstox token for user %d, skipping", uid)

    # ── Stream auth failure handling ─────────────────────────────────

    async def _on_stream_auth_failure(self, user_id: int) -> None:
        """Handle authentication failure from a WebSocket stream.

        Called when a stream gets a 401/403 from Upstox. Both streams
        for the same user may fire concurrently, so we deduplicate via
        a per-user asyncio.Lock — if a refresh is already in progress,
        the second call is a no-op.

        On success (new token obtained): restarts streams for the user.
        On failure (same/no token): leaves user stopped for next poll cycle.
        """
        lock = self._auth_refresh_locks.setdefault(user_id, asyncio.Lock())

        # If already handling this user's auth failure, skip
        if lock.locked():
            logger.debug(
                "Auth failure for user %d already being handled, skipping",
                user_id,
            )
            return

        async with lock:
            stale_token = self._access_tokens.get(user_id)
            logger.warning(
                "Stream auth failure for user %d, attempting token refresh",
                user_id,
            )

            # Tear down both streams
            await self._user_manager.stop_user(user_id)

            # Attempt TOTP refresh — force=True bypasses "recently refreshed"
            # guard since Upstox invalidated the token server-side
            new_token = await self._load_access_token(
                user_id, force_refresh=True
            )

            if new_token and new_token != stale_token:
                # Fresh token — restart streams
                self._access_tokens[user_id] = new_token
                rules = self._rules_by_user.get(user_id, [])
                if rules:
                    await self._user_manager.start_user(
                        user_id, new_token, rules
                    )
                    logger.info(
                        "Refreshed token for user %d, streams restarted",
                        user_id,
                    )
                else:
                    logger.info(
                        "Refreshed token for user %d but no active rules",
                        user_id,
                    )
            else:
                # Refresh failed or returned same stale token
                self._access_tokens.pop(user_id, None)
                logger.warning(
                    "Token refresh failed for user %d, "
                    "streams stopped until next poll cycle",
                    user_id,
                )
                try:
                    from services.notifier import notify_user
                    await notify_user(
                        user_id=user_id,
                        category="monitor_failure",
                        text=(
                            "⚠️ Monitor daemon: Upstox WS auth failed and token "
                            "refresh did not produce a fresh credential. Streams "
                            "are down until the next poll cycle. Re-OAuth if this "
                            "persists."
                        ),
                    )
                except Exception:
                    logger.exception("Daemon telegram notify raised; ignoring")

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
        # ── Periodic cleanup: disable expired, delete stale ──
        try:
            async with get_db_context() as session:
                expired = await crud.auto_disable_expired_rules(session)
                if expired:
                    logger.info("Auto-disabled %d expired rules", expired)
                stale = await crud.cleanup_stale_rules(session)
                if stale:
                    logger.info("Cleaned up %d stale (max-fired+disabled >24h) rules", stale)
        except Exception as e:
            logger.error("Rule cleanup failed: %s", e)

        # ── Load active rules ──
        async with get_db_context() as session:
            db_rules = await crud.get_active_rules_for_daemon(session)

        # Group by user_id
        rules_by_user: dict[int, list[MonitorRule]] = {}
        for db_rule in db_rules:
            schema = crud.db_rule_to_schema(db_rule)
            rules_by_user.setdefault(schema.user_id, []).append(schema)

        # Load access tokens and order node URLs from DB for all users with
        # active rules OR active scalp sessions. Scalp-only users (no monitor
        # rules) still need their order_node_url loaded so scalp orders route
        # through the user's static-IP order node — otherwise Upstox rejects
        # with UDAPI1154 (IP mismatch).
        config_user_ids = set(rules_by_user.keys()) | set(
            self._scalp_manager._sessions.keys()
        )
        await self._load_user_configs(config_user_ids)

        # Determine users to start/stop/sync
        old_users = set(self._rules_by_user.keys())
        new_users = set(rules_by_user.keys())

        # Stop users with no more rules
        for uid in old_users - new_users:
            await self._user_manager.stop_user(uid)

        # Start new users (only if we have an access token). Scalp-owned
        # instruments are passed in so sync_rules() on later polls won't
        # treat them as orphans and unsubscribe them.
        for uid in new_users - old_users:
            token = self._access_tokens.get(uid)
            if token:
                scalp_instruments = self._scalp_manager.get_subscribed_instruments(uid)
                await self._user_manager.start_user(
                    uid, token, rules_by_user[uid],
                    extra_instruments=scalp_instruments or None,
                )

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
            scalp_instruments = self._scalp_manager.get_subscribed_instruments(uid)
            session = self._user_manager.get_session(uid)
            if session is None:
                # Session was destroyed (e.g. by auth failure handler)
                # but user still has rules and a valid token — re-create
                logger.info(
                    "Re-creating session for user %d (session lost, token valid)",
                    uid,
                )
                await self._user_manager.start_user(
                    uid, token, rules_by_user[uid],
                    extra_instruments=scalp_instruments or None,
                )
            elif session.access_token != token:
                # Token changed (e.g. TOTP refresh) — restart streams
                logger.info("Token changed for user %d, restarting streams", uid)
                await self._user_manager.start_user(
                    uid, token, rules_by_user[uid],
                    extra_instruments=scalp_instruments or None,
                )
                # If this user owns the shared market feed, the pool's
                # underlying token also needs to roll. ``rotate_token``
                # rebuilds the stream and re-subscribes to the union of
                # all current interest.
                if (
                    self._market_pool is not None
                    and uid == self._feed_owner_user_id
                ):
                    await self._market_pool.rotate_token()
            else:
                await self._user_manager.sync_rules(
                    uid, rules_by_user[uid],
                    extra_instruments=scalp_instruments or None,
                )

        self._rules_by_user = rules_by_user

        # Ensure scalp-only users (no rules but have sessions) get started.
        # Rule-based users already had scalp instruments merged into their
        # subscription set above via extra_instruments.
        for uid in self._scalp_manager._sessions:
            if uid not in new_users:
                token = self._access_tokens.get(uid)
                if not token:
                    # Try loading token for this scalp-only user
                    token = await self._load_access_token(uid)
                    if token:
                        self._access_tokens[uid] = token
                if token and not self._user_manager.get_session(uid):
                    scalp_instruments = self._scalp_manager.get_subscribed_instruments(uid)
                    await self._user_manager.start_user(
                        uid, token, [],
                        extra_instruments=scalp_instruments or None,
                    )

        # Periodic summary — helps confirm daemon is alive and processing
        total_rules = sum(len(r) for r in rules_by_user.values())
        total_sessions = sum(len(s) for s in self._scalp_manager._sessions.values())
        active_users = [uid for uid in rules_by_user if uid in self._access_tokens]
        logger.info(
            "Poll cycle: %d active rules, %d scalp sessions for %d users %s",
            total_rules, total_sessions, len(active_users), active_users,
        )

    # ── Tick routing ──────────────────────────────────────────────────

    async def _on_tick(
        self, user_id: int, instrument_token: str, market_data: dict
    ) -> None:
        """Called on every market data tick. Evaluate price/indicator/compound rules.

        Serialized per instrument+user via _tick_locks to prevent concurrent
        evaluation of the same rule from rapid WebSocket ticks. Per-instrument
        granularity allows NIFTY and BANKNIFTY (or any two instruments) to
        evaluate in parallel for the same user — safe because rules are
        filtered by instrument_token match (line below), so two instruments
        never touch the same rule.
        """
        ltp = market_data.get("ltp")
        logger.debug(
            "Tick user=%d inst=%s ltp=%s", user_id, instrument_token, ltp,
        )

        lock_key = f"{user_id}:{instrument_token}"
        lock = self._tick_locks.setdefault(lock_key, asyncio.Lock())
        async with lock:
            session_obj = self._user_manager.get_session(user_id)
            if session_obj is None:
                return

            # Evaluate entry rules first so they can disable opposite-direction
            # rules before those get a chance to fire on the same tick.
            matching = [
                r for r in session_obj.rules
                if r.trigger_type in ("price", "indicator", "compound", "trailing_stop")
                and r.instrument_token == instrument_token
            ]
            matching.sort(key=lambda r: (0 if "Entry" in r.name else 1, r.id))

            if matching:
                logger.debug(
                    "Evaluating %d rules for inst=%s ltp=%s: %s",
                    len(matching), instrument_token, ltp,
                    [(r.id, r.name, r.trigger_type) for r in matching],
                )

            for rule in matching:
                ctx = EvalContext(
                    market_data=market_data,
                    prev_prices=session_obj.prev_prices,
                    now=datetime.utcnow(),
                    indicator_values=session_obj.indicator_values,
                    prev_indicator_values=session_obj.prev_indicator_values,
                )
                await self._evaluate_and_execute(rule, ctx)

            # Consume indicator edges: after all rules on this tick have
            # evaluated, advance prev_indicator_values to match the current
            # indicator_values. Without this, crosses_above/below keeps
            # returning True on every tick between candle closes, because
            # _recompute_indicators only refreshes prev at the next close.
            #
            # Effect: crosses_* fires once on the first tick after a candle
            # close (when the indicator genuinely advances), then is silent
            # until the next close. This prevents the "meaningless exit"
            # replay bug — a cycling template that re-enables a disabled
            # entry mid-bar would otherwise see the same stale edge and
            # re-enter immediately, making the exit that just fired a no-op.
            # Observed live on utbot-scalp-options 2026-04-15: entry fired
            # at 05:07:00, LR-exit fired, entry re-enabled, and re-fired
            # 13s later on the exact same 5m UT Bot flip edge.
            for key, val in session_obj.indicator_values.items():
                session_obj.prev_indicator_values[key] = val

            # Route to scalp session manager (no-op if instrument doesn't
            # match any session — single dict lookup overhead).
            await self._scalp_manager.on_tick(user_id, instrument_token, market_data)

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
        """Evaluate all time-based rules (called every poll_interval).

        Time triggers use IST because users specify trigger times in IST
        (Indian market hours).  We convert UTC → IST here and pass a naive
        IST datetime so evaluate_time_trigger() can compare directly.
        """
        now_ist = datetime.now(_IST).replace(tzinfo=None)
        for user_id, rules in self._rules_by_user.items():
            for rule in rules:
                if rule.trigger_type != "time":
                    continue
                ctx = EvalContext(now=now_ist)
                try:
                    await self._evaluate_and_execute(rule, ctx)
                except Exception:
                    # A single malformed rule must never crash the daemon's
                    # poll loop — that silently kills every other rule.
                    logger.exception(
                        "Time rule %s (%s) raised during evaluation — skipping",
                        rule.id, rule.name,
                    )

    # ── Evaluation + execution ────────────────────────────────────────

    async def _evaluate_and_execute(
        self, rule: MonitorRule, ctx: EvalContext
    ) -> None:
        """Evaluate a rule and execute its action if fired.

        Two-phase design for scalping-speed execution:

        Phase 1 (under tick lock, ~1ms): Evaluate rule, update all in-memory
        state (fire_count, enabled, kill/activate chains). This is the only
        part that needs serialization to prevent double-fires.

        Phase 2 (background task, ~200-500ms): Order placement + DB writes.
        Launched via asyncio.create_task() so the tick lock is released
        immediately and the next tick can be processed.
        """
        result = evaluate_rule(rule, ctx)

        if result.skipped:
            logger.debug(
                "Rule %d (%s) SKIPPED (enabled=%s fire_count=%s/%s)",
                rule.id, rule.name, rule.enabled, rule.fire_count, rule.max_fires,
            )
        elif not result.fired:
            logger.debug(
                "Rule %d (%s) evaluated → not fired (ltp=%s)",
                rule.id, rule.name, ctx.market_data.get("ltp"),
            )

        # Persist trigger_config_update if present (e.g. trailing stop highest_price).
        # Update in-memory immediately; defer DB write to background.
        if result.trigger_config_update is not None:
            rule.trigger_config = result.trigger_config_update
            asyncio.create_task(
                self._persist_trigger_config(rule.id, result.trigger_config_update)
            )

        if not result.fired:
            return

        # ── Market hours guard ────────────────────────────────────────
        # Skip order placement outside NSE market hours (9:15–15:30 IST).
        # Don't waste max_fires on guaranteed-to-fail orders.
        # Time-based rules (auto-squareoff) and non-order actions pass through.
        if result.action_type == "place_order" and not self._is_nse_market_open():
            logger.warning(
                "Rule %d (%s) FIRED but market CLOSED — skipping order "
                "placement (not counted against max_fires=%s)",
                rule.id, rule.name, rule.max_fires,
            )
            return

        # ── Phase 1: In-memory state updates (synchronous, under lock) ──

        # Immediately increment in-memory fire_count so the next tick's
        # should_evaluate check sees the updated count.  Without this,
        # rules with max_fires=1 and level-triggered conditions (gte/lte)
        # fire on every tick until the next _poll_rules() DB reload.
        rule.fire_count += 1

        # Also stamp fired_at in-memory so cooldown checks in the next tick
        # see fresh values. The background task (sync_rule_fire_state) will
        # persist this to DB; we just can't wait for that round-trip.
        rule.fired_at = ctx.now

        # Also disable the rule in-memory if max_fires is reached, so even
        # concurrent ticks on other async tasks see it as disabled immediately.
        if rule.max_fires and rule.fire_count >= rule.max_fires:
            rule.enabled = False

        logger.info("Rule %d (%s) FIRED", rule.id, rule.name)

        # Sync in-memory state for kill chain (rules_to_cancel) and
        # activate chain (rules_to_enable) BEFORE releasing the lock,
        # so same-tick evaluation of other rules sees the changes.
        session_obj = self._user_manager.get_session(rule.user_id)
        if session_obj:
            if result.rules_to_cancel:
                for r in session_obj.rules:
                    if r.id in result.rules_to_cancel:
                        r.enabled = False
                logger.info(
                    "Rule %d kill chain: disabled %d rules in-memory: %s",
                    rule.id, len(result.rules_to_cancel), result.rules_to_cancel,
                )
            if result.rules_to_enable:
                for r in session_obj.rules:
                    if r.id in result.rules_to_enable:
                        r.enabled = True
                        # Reset fire_count so max_fires-gated rules can fire
                        # again in the next cycle.  Without this, a target
                        # rule with max_fires=1 would be permanently exhausted
                        # after the first cycle even when re-enabled by entry.
                        r.fire_count = 0
                logger.info(
                    "Rule %d activate chain: enabled %d rules in-memory (fire_count reset): %s",
                    rule.id, len(result.rules_to_enable), result.rules_to_enable,
                )

        # Persist kill/activate chain state changes to DB in background.
        # Without this, _poll_rules() would reload stale fire_count/enabled
        # values from DB, undoing the in-memory resets above.
        chain_affected: list[MonitorRule] = []
        if session_obj:
            affected_ids = set(result.rules_to_cancel) | set(result.rules_to_enable)
            if affected_ids:
                chain_affected = [r for r in session_obj.rules if r.id in affected_ids]

        # ── Phase 2: Fire-and-forget order + DB writes (background) ──

        trigger_snapshot = {
            "market_data": ctx.market_data,
            "now": str(ctx.now),
        }

        asyncio.create_task(
            self._execute_and_record(rule, result, trigger_snapshot, chain_affected)
        )

    async def _execute_and_record(
        self,
        rule: MonitorRule,
        result,
        trigger_snapshot: dict,
        chain_affected: list[MonitorRule] | None = None,
    ) -> None:
        """Background task: place order + persist fire to DB.

        Runs outside the tick lock so the daemon can process the next tick
        immediately. Errors are logged but don't crash the daemon.

        On failed place_order: revert the optimistic state changes that the
        in-memory tick handler applied (fire_count bump, max_fires-driven
        disable, kill/activate chain) — but ONLY for true rejections. SDK
        timeouts are ``ambiguous`` (action_executor flags them): the order
        may have reached Upstox and be filling, so reverting would let the
        rule fire again while orders are in flight (2026-05-11 TATACONSUM
        triple-fill). On ambiguous timeouts we keep fire_count incremented;
        manual re-enable is required if Upstox truly never got the order.

        Origin: 2026-05-08 FINCABLES — long trail rule's exit timed out;
        fire_count and also_cancel_rules ran anyway, leaving the position
        dangling. See project_exit_rule_stacking_bug.md.
        """
        # Per-rule in-flight lock: a second tick arriving while the first
        # tick's place_order is still pending at Upstox skips immediately
        # instead of submitting a parallel request. This is belt to the
        # action_executor's pre-fire idempotency scan suspenders — the lock
        # blocks duplicates on this same daemon process; the scan catches
        # duplicates that already reached the broker.
        lock = self._rule_inflight_locks.setdefault(rule.id, asyncio.Lock())
        if lock.locked():
            logger.warning(
                "Rule %d: prior place_order still in flight — skipping this tick",
                rule.id,
            )
            return
        async with lock:
            try:
                async with get_db_context() as db_session:
                    action_result = await self._action_executor.execute(
                        rule, result, trigger_snapshot, db_session
                    )

                    order_failed = (
                        result.action_type == "place_order"
                        and isinstance(action_result, dict)
                        and not action_result.get("success", False)
                    )
                    ambiguous = bool(
                        isinstance(action_result, dict)
                        and action_result.get("ambiguous")
                    )

                    if order_failed and not ambiguous:
                        await self._revert_failed_fire(
                            rule, result, chain_affected, db_session, action_result
                        )
                    elif order_failed and ambiguous:
                        # Don't revert — the order may have made it to Upstox
                        # and be filling right now. Log loudly so it's visible
                        # in incident review. Daemon's next poll will not
                        # re-fire this rule because fire_count stays put.
                        err_msg = (
                            action_result.get("error")
                            or action_result.get("message")
                            or ""
                        )[:200]
                        logger.error(
                            "Rule %d (%s) order AMBIGUOUS (timeout) — keeping "
                            "fire_count=%d, NOT rearming. err=%s",
                            rule.id, rule.name, rule.fire_count, err_msg,
                        )
                        # Persist chain state — even on ambiguous outcome the
                        # also_cancel_rules / also_enable_rules should stand,
                        # since the order may have filled.
                        if chain_affected:
                            for r in chain_affected:
                                try:
                                    await crud.sync_rule_fire_state(
                                        session=db_session,
                                        rule_id=r.id,
                                        fire_count=r.fire_count,
                                        enabled=r.enabled,
                                    )
                                except Exception as e:
                                    logger.error(
                                        "Failed to sync chain rule %d state: %s",
                                        r.id, e,
                                    )
                    else:
                        # Persist kill/activate chain state (enabled, fire_count)
                        # so DB stays in sync with in-memory daemon state.
                        if chain_affected:
                            for r in chain_affected:
                                try:
                                    await crud.sync_rule_fire_state(
                                        session=db_session,
                                        rule_id=r.id,
                                        fire_count=r.fire_count,
                                        enabled=r.enabled,
                                    )
                                except Exception as e:
                                    logger.error(
                                        "Failed to sync chain rule %d state: %s",
                                        r.id, e,
                                    )
            except Exception as e:
                logger.error(
                    "Background execute_and_record failed for rule %d: %s",
                    rule.id, e, exc_info=True,
                )

    async def _revert_failed_fire(
        self,
        rule: MonitorRule,
        result,
        chain_affected: list[MonitorRule] | None,
        db_session,
        action_result: dict,
    ) -> None:
        """Undo the optimistic state changes for a fired rule whose order failed.

        Reverts both the in-memory state (so the daemon's next tick sees the
        rule as still-armed and the protective rules as still-active) AND
        the DB writes that action_executor.execute() already committed
        inside the kill/activate chain. Idempotent: re-enabling an
        already-enabled rule is harmless.
        """
        err_msg = (action_result.get("error") or action_result.get("message") or "")[:200]

        # Revert the rule's own fire_count + max_fires-driven disable.
        if rule.fire_count > 0:
            rule.fire_count -= 1
        rule_was_disabled_now_re_armed = False
        if not rule.enabled and (not rule.max_fires or rule.fire_count < rule.max_fires):
            rule.enabled = True
            rule_was_disabled_now_re_armed = True

        # Revert kill chain (re-enable rules we just disabled) and activate
        # chain (re-disable rules we just enabled).
        session_obj = self._user_manager.get_session(rule.user_id)
        if session_obj:
            if result.rules_to_cancel:
                for r in session_obj.rules:
                    if r.id in result.rules_to_cancel:
                        r.enabled = True
            if result.rules_to_enable:
                for r in session_obj.rules:
                    if r.id in result.rules_to_enable:
                        r.enabled = False

        # Persist the revert to DB.
        try:
            await crud.sync_rule_fire_state(
                session=db_session,
                rule_id=rule.id,
                fire_count=rule.fire_count,
                enabled=rule.enabled,
            )
        except Exception as e:
            logger.error("Failed to sync revert for rule %d: %s", rule.id, e)

        if chain_affected:
            for r in chain_affected:
                try:
                    await crud.sync_rule_fire_state(
                        session=db_session,
                        rule_id=r.id,
                        fire_count=r.fire_count,
                        enabled=r.enabled,
                    )
                except Exception as e:
                    logger.error(
                        "Failed to sync revert for chain rule %d: %s", r.id, e
                    )

        logger.warning(
            "Rule %d (%s) order FAILED, reverted: fire_count=%d, "
            "re-armed=%s, restored %d cancelled rule(s), disabled %d activated rule(s). err=%s",
            rule.id, rule.name, rule.fire_count, rule_was_disabled_now_re_armed,
            len(result.rules_to_cancel) if result.rules_to_cancel else 0,
            len(result.rules_to_enable) if result.rules_to_enable else 0,
            err_msg,
        )

    async def _persist_trigger_config(
        self, rule_id: int, trigger_config: dict
    ) -> None:
        """Background task: persist trailing stop trigger_config to DB."""
        try:
            async with get_db_context() as db_session:
                await crud.update_rule(
                    db_session, rule_id, trigger_config=trigger_config,
                )
        except Exception as e:
            logger.error(
                "Failed to persist trigger_config for rule %d: %s",
                rule_id, e,
            )

    # ── Market hours ────────────────────────────────────────────────

    @staticmethod
    def _is_nse_market_open() -> bool:
        """Check if NSE is currently in trading hours (9:15–15:30 IST).

        Uses a simple time-of-day + weekday check.  Does not account for
        exchange holidays — the Upstox API will still reject orders on
        holidays with a 423 Locked, but the guard prevents burning
        max_fires on weekends and obvious off-hours.
        """
        now_ist = datetime.now(_IST)
        # Weekday: Mon=0 .. Fri=4, Sat=5, Sun=6
        if now_ist.weekday() >= 5:
            return False
        t = now_ist.time()
        return dt_time(9, 15) <= t <= dt_time(15, 30)

    # ── Client factory ────────────────────────────────────────────────

    async def _get_client(self, user_id: int) -> UpstoxClient:
        """Get an UpstoxClient for a given user.

        Raises ValueError if no access token is available for the user.
        """
        token = self._access_tokens.get(user_id)
        if not token:
            raise ValueError(f"No access token for user {user_id}")
        return UpstoxClient(
            access_token=token,
            user_id=user_id,
            paper_trading=self._paper_mode,
        )
