"""Shared MarketDataStream pool.

Background — 2026-05-07: Per-user Upstox MarketDataStream connections
proved unreliable for index instruments (NSE_INDEX|Nifty 50). Two
different users hit the same silent-feed bug on the same day: stream
TCP-alive, "subscribed", but Upstox delivers no ticks. Restart with the
instrument in the *initial* subscribe set works; diff-add via
``sync_rules`` does not.

Solution: one shared MarketDataStream owned by the daemon, authenticated
with a designated "feed owner" token (typically the app owner — Pranav's
account). Each user-session registers per-instrument interest with the
pool. When a tick arrives, the pool fans it out to every interested
user's tick handler.

PortfolioStream stays per-user — those events (orders, positions,
holdings) are account-bound and can't be shared.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Awaitable, Callable

from monitor.streams.market_data import MarketDataStream

logger = logging.getLogger(__name__)


# Type aliases
TickHandler = Callable[[int, dict], Awaitable[None]]
"""(user_id, tick_data_for_one_instrument) -> awaitable.

The ``tick_data`` passed into a handler is a single-instrument dict in
the same shape MarketDataStream produces, e.g.::

    {"NSE_INDEX|Nifty 50": {"ltp": 24345.0, "close": 24340.0, ...}}
"""


class MarketStreamPool:
    """Single MarketDataStream shared across all daemon users.

    Reference-counts per-instrument interest so a Subscribe/Unsubscribe
    only goes to Upstox at the boundaries (first user adds → subscribe,
    last user drops → unsubscribe). Token rotation is handled by
    ``rotate_token`` which tears down the stream and rebuilds with the
    current owner token + the union of every user's interest.
    """

    def __init__(
        self,
        get_owner_token: Callable[[bool], Awaitable[str | None]],
        tick_handler: TickHandler,
        mode: str = "full",
    ):
        """Init.

        Args:
            get_owner_token: Async callable taking ``force_refresh: bool``
                and returning the feed-owner's current Upstox access
                token (or None if unavailable). Typically a closure over
                the daemon's ``_load_access_token(owner_user_id, ...)``.
            tick_handler: Async callable invoked once per (interested
                user, tick) pair. Receives the user_id and a
                single-instrument tick dict.
            mode: Subscription mode for the underlying MarketDataStream.
                ``full`` is the safe choice; supports both equity and
                indices.
        """
        self._get_owner_token = get_owner_token
        self._tick_handler = tick_handler
        self._mode = mode

        # instrument_token -> set of interested user_ids (refcount)
        self._interest: dict[str, set[int]] = {}
        # Lock guards _interest mutations and stream-level subscribe diffs
        self._lock = asyncio.Lock()
        self._stream: MarketDataStream | None = None
        self._owner_token: str | None = None
        self._restart_lock = asyncio.Lock()

    # ── Lifecycle ─────────────────────────────────────────────────────

    async def start(self) -> None:
        """Build and start the shared stream from the owner's token.

        Idempotent: a no-op if the stream is already running. Raises if
        the owner token cannot be loaded.
        """
        if self._stream is not None:
            return
        token = await self._get_owner_token(False)
        if not token:
            raise RuntimeError(
                "MarketStreamPool: feed-owner token unavailable, "
                "cannot start shared market feed"
            )
        await self._build_stream(token)
        logger.info("[MarketStreamPool] Started shared market feed")

    async def stop(self) -> None:
        """Stop the shared stream. Interest map is preserved so a later
        ``start`` can re-subscribe to whatever was active."""
        if self._stream is not None:
            await self._stream.stop()
            self._stream = None
        logger.info("[MarketStreamPool] Stopped shared market feed")

    async def rotate_token(self) -> None:
        """Force the shared stream to rebuild using the current owner
        token (force-refreshing if necessary). Re-subscribes to the
        union of all current interest.

        Called when the owner's token rotates (TOTP refresh) or when an
        auth failure callback fires from the underlying stream.
        """
        async with self._restart_lock:
            new_token = await self._get_owner_token(True)
            if not new_token:
                logger.error(
                    "[MarketStreamPool] rotate_token: feed-owner token "
                    "unavailable, leaving stream stopped",
                )
                if self._stream is not None:
                    await self._stream.stop()
                    self._stream = None
                return
            if self._stream is not None:
                await self._stream.stop()
                self._stream = None
            await self._build_stream(new_token)
            # Re-subscribe to everything we still care about.
            all_keys = list(self._interest.keys())
            if all_keys:
                await self._stream.subscribe(all_keys)
            logger.info(
                "[MarketStreamPool] Rotated owner token, resubscribed to %d "
                "instruments", len(all_keys),
            )

    async def _build_stream(self, token: str) -> None:
        """Construct and start the inner MarketDataStream."""
        self._owner_token = token
        self._stream = MarketDataStream(
            access_token=token,
            on_message=self._on_pool_tick,
            mode=self._mode,
            on_auth_failure=self._on_pool_auth_failure,
        )
        await self._stream.start()

    async def _on_pool_auth_failure(self) -> None:
        """The owner's token went bad. Try one rotation; if still bad,
        the stream stays stopped and ``rotate_token`` logs accordingly.
        """
        logger.warning(
            "[MarketStreamPool] Owner-token auth failure — attempting rotate"
        )
        await self.rotate_token()

    # ── Tick fan-out ──────────────────────────────────────────────────

    async def _on_pool_tick(self, tick_data: dict) -> None:
        """Fan out an incoming tick to every interested user.

        ``tick_data`` is keyed by instrument_token. For each instrument
        in the tick, look up interested user_ids and dispatch one tick
        per (user, instrument) pair.
        """
        if not tick_data:
            return
        # Snapshot interest under the lock so concurrent set_interest
        # calls don't observe a half-mutated map.
        snapshot: dict[str, list[int]] = {}
        async with self._lock:
            for inst_key in tick_data.keys():
                users = self._interest.get(inst_key)
                if users:
                    snapshot[inst_key] = list(users)
        for inst_key, user_ids in snapshot.items():
            single = {inst_key: tick_data[inst_key]}
            for uid in user_ids:
                try:
                    await self._tick_handler(uid, single)
                except Exception as e:
                    logger.exception(
                        "[MarketStreamPool] tick_handler raised for user "
                        "%d on %s: %s", uid, inst_key, e,
                    )

    # ── Interest management ──────────────────────────────────────────

    async def set_interest(
        self, user_id: int, instruments: set[str]
    ) -> None:
        """Replace ``user_id``'s interest with ``instruments``.

        Diffs against the user's current interest. Subscribes any
        instruments that just gained their first interested user;
        unsubscribes any that just lost their last.
        """
        instruments = set(instruments)
        new_subs: list[str] = []
        drop_subs: list[str] = []
        async with self._lock:
            current = {
                inst for inst, users in self._interest.items()
                if user_id in users
            }
            to_add = instruments - current
            to_remove = current - instruments
            for inst in to_add:
                bucket = self._interest.setdefault(inst, set())
                if not bucket:
                    new_subs.append(inst)
                bucket.add(user_id)
            for inst in to_remove:
                bucket = self._interest.get(inst)
                if bucket is None:
                    continue
                bucket.discard(user_id)
                if not bucket:
                    drop_subs.append(inst)
                    del self._interest[inst]
        if self._stream is not None:
            if new_subs:
                await self._stream.subscribe(new_subs)
                # Upstox quirk (2026-05-07 incident): NSE_INDEX
                # instruments subscribed via diff-add after the initial
                # connect are silently never delivered. Subscribed via
                # the *initial* subscribe message (i.e. on connect),
                # they work. Force a reconnect when any new index key
                # joins so the next ``_on_connected`` resubscribes from
                # ``_subscribed_keys`` (which now includes the index)
                # — that path Upstox honours.
                index_added = any(
                    k.startswith(("NSE_INDEX|", "BSE_INDEX|")) for k in new_subs
                )
                if index_added and self._stream._ws is not None:
                    logger.info(
                        "[MarketStreamPool] index subscribed via diff "
                        "(%s) — forcing reconnect so Upstox honours it",
                        sorted(
                            k for k in new_subs
                            if k.startswith(("NSE_INDEX|", "BSE_INDEX|"))
                        ),
                    )
                    try:
                        await self._stream._ws.close()
                    except Exception as e:
                        logger.warning(
                            "[MarketStreamPool] reconnect ws.close failed: %s",
                            e,
                        )
            if drop_subs:
                await self._stream.unsubscribe(drop_subs)

    async def drop_user(self, user_id: int) -> None:
        """Remove all of ``user_id``'s interest. Convenience for
        stop_user / cleanup paths."""
        await self.set_interest(user_id, set())

    # ── Introspection ────────────────────────────────────────────────

    def interest_for(self, user_id: int) -> set[str]:
        """Return a fresh copy of the instruments ``user_id`` is
        currently interested in."""
        return {
            inst for inst, users in self._interest.items()
            if user_id in users
        }

    @property
    def stream(self) -> MarketDataStream | None:
        """Underlying MarketDataStream — None if not started."""
        return self._stream

    @property
    def total_subscriptions(self) -> int:
        """Number of distinct instruments currently subscribed."""
        return len(self._interest)
