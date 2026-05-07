"""Tests for MarketStreamPool — shared market-data feed across users.

Background — 2026-05-07 silent-feed bug: per-user MarketDataStream
connections proved unreliable for index instruments. The pool routes
all users' market-data needs through one stream owned by a designated
feed-owner account. These tests cover:

- Reference-counted subscribe/unsubscribe (first-in subscribes, last-out
  unsubscribes).
- Tick fan-out to every interested user.
- Token rotation: stop the inner stream, rebuild with the new token,
  re-subscribe to the union of current interest.
- Auth-failure callback chains into rotate_token.
- Lifecycle: start raises if owner token is unavailable; stop clears
  the inner stream but preserves interest map.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from monitor.streams.market_stream_pool import MarketStreamPool


def _make_pool(
    owner_token: str | None = "owner-token",
    tick_handler: AsyncMock | None = None,
) -> tuple[MarketStreamPool, AsyncMock, AsyncMock]:
    get_token = AsyncMock(return_value=owner_token)
    handler = tick_handler or AsyncMock()
    pool = MarketStreamPool(
        get_owner_token=get_token,
        tick_handler=handler,
        mode="full",
    )
    return pool, get_token, handler


class TestInterestRefCount:
    @pytest.mark.asyncio
    async def test_set_interest_adds_first_user_calls_subscribe(self):
        pool, _, _ = _make_pool()
        # Inject a mock stream so set_interest's "subscribe to new" branch
        # has something to call.
        pool._stream = MagicMock()
        pool._stream.subscribe = AsyncMock()
        pool._stream.unsubscribe = AsyncMock()

        await pool.set_interest(1, {"NSE_INDEX|Nifty 50"})
        pool._stream.subscribe.assert_awaited_once()
        args = pool._stream.subscribe.call_args.args[0]
        assert "NSE_INDEX|Nifty 50" in args

    @pytest.mark.asyncio
    async def test_second_user_same_instrument_no_resubscribe(self):
        pool, _, _ = _make_pool()
        pool._stream = MagicMock()
        pool._stream.subscribe = AsyncMock()
        pool._stream.unsubscribe = AsyncMock()

        await pool.set_interest(1, {"NSE_INDEX|Nifty 50"})
        await pool.set_interest(2, {"NSE_INDEX|Nifty 50"})

        # Only the first user triggered a subscribe; second user reused.
        assert pool._stream.subscribe.await_count == 1
        assert pool._interest["NSE_INDEX|Nifty 50"] == {1, 2}

    @pytest.mark.asyncio
    async def test_last_user_drop_calls_unsubscribe(self):
        pool, _, _ = _make_pool()
        pool._stream = MagicMock()
        pool._stream.subscribe = AsyncMock()
        pool._stream.unsubscribe = AsyncMock()

        await pool.set_interest(1, {"NSE_INDEX|Nifty 50"})
        await pool.set_interest(2, {"NSE_INDEX|Nifty 50"})
        # First user drops — still one subscriber, no unsubscribe.
        await pool.set_interest(1, set())
        pool._stream.unsubscribe.assert_not_called()
        # Second user drops — interest empty, unsubscribe fires.
        await pool.set_interest(2, set())
        pool._stream.unsubscribe.assert_awaited_once()
        unsub_args = pool._stream.unsubscribe.call_args.args[0]
        assert "NSE_INDEX|Nifty 50" in unsub_args
        assert "NSE_INDEX|Nifty 50" not in pool._interest

    @pytest.mark.asyncio
    async def test_set_interest_diffs_correctly(self):
        pool, _, _ = _make_pool()
        pool._stream = MagicMock()
        pool._stream.subscribe = AsyncMock()
        pool._stream.unsubscribe = AsyncMock()

        await pool.set_interest(1, {"A", "B", "C"})
        # Now switch user 1's interest to {B, D}: drop A, C; add D
        await pool.set_interest(1, {"B", "D"})

        sub_calls = [c.args[0] for c in pool._stream.subscribe.call_args_list]
        all_subs = {x for batch in sub_calls for x in batch}
        assert all_subs == {"A", "B", "C", "D"}

        unsub_args = pool._stream.unsubscribe.call_args.args[0]
        assert set(unsub_args) == {"A", "C"}
        assert pool.interest_for(1) == {"B", "D"}

    @pytest.mark.asyncio
    async def test_drop_user_clears_all_interest(self):
        pool, _, _ = _make_pool()
        pool._stream = MagicMock()
        pool._stream.subscribe = AsyncMock()
        pool._stream.unsubscribe = AsyncMock()

        await pool.set_interest(1, {"A", "B"})
        await pool.drop_user(1)
        assert pool.interest_for(1) == set()
        assert pool._interest == {}


class TestTickFanout:
    @pytest.mark.asyncio
    async def test_tick_dispatched_only_to_interested_users(self):
        pool, _, handler = _make_pool()
        await pool.set_interest(1, {"NSE_INDEX|Nifty 50"})
        await pool.set_interest(2, {"NSE_EQ|RELIANCE"})

        await pool._on_pool_tick({
            "NSE_INDEX|Nifty 50": {"ltp": 24000.0},
            "NSE_EQ|RELIANCE": {"ltp": 1234.0},
        })

        # User 1 received only NIFTY; user 2 received only RELIANCE.
        calls = handler.await_args_list
        per_user: dict[int, set[str]] = {}
        for c in calls:
            uid, single = c.args
            per_user.setdefault(uid, set()).update(single.keys())
        assert per_user[1] == {"NSE_INDEX|Nifty 50"}
        assert per_user[2] == {"NSE_EQ|RELIANCE"}

    @pytest.mark.asyncio
    async def test_tick_dispatched_to_multiple_interested_users(self):
        pool, _, handler = _make_pool()
        await pool.set_interest(1, {"NSE_INDEX|Nifty 50"})
        await pool.set_interest(2, {"NSE_INDEX|Nifty 50"})

        await pool._on_pool_tick({"NSE_INDEX|Nifty 50": {"ltp": 24000.0}})

        uids = {c.args[0] for c in handler.await_args_list}
        assert uids == {1, 2}
        assert handler.await_count == 2

    @pytest.mark.asyncio
    async def test_tick_for_uninterested_instrument_silently_dropped(self):
        pool, _, handler = _make_pool()
        await pool.set_interest(1, {"NSE_INDEX|Nifty 50"})
        # No-one subscribed to BANKNIFTY.
        await pool._on_pool_tick({"NSE_INDEX|Bank Nifty": {"ltp": 50000.0}})
        handler.assert_not_called()

    @pytest.mark.asyncio
    async def test_handler_exception_does_not_break_fanout(self):
        bad_handler = AsyncMock(side_effect=RuntimeError("boom"))
        good_handler = AsyncMock()
        # Wrap two handlers: when bad raises, good must still get called
        # (or at least the loop continues).
        pool, _, _ = _make_pool(tick_handler=bad_handler)
        await pool.set_interest(1, {"A"})
        await pool.set_interest(2, {"A"})

        # Should not raise — exceptions are swallowed inside _on_pool_tick
        await pool._on_pool_tick({"A": {"ltp": 1.0}})
        # Both users were attempted.
        assert bad_handler.await_count == 2


class TestLifecycle:
    @pytest.mark.asyncio
    async def test_start_builds_stream_with_owner_token(self):
        pool, get_token, _ = _make_pool(owner_token="owner-A")
        with patch(
            "monitor.streams.market_stream_pool.MarketDataStream"
        ) as MdsMock:
            mds_inst = MagicMock()
            mds_inst.start = AsyncMock()
            MdsMock.return_value = mds_inst
            await pool.start()
        get_token.assert_awaited_once_with(False)
        MdsMock.assert_called_once()
        kwargs = MdsMock.call_args.kwargs
        assert kwargs["access_token"] == "owner-A"
        assert kwargs["mode"] == "full"
        mds_inst.start.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_start_raises_when_owner_token_missing(self):
        pool, _, _ = _make_pool(owner_token=None)
        with pytest.raises(RuntimeError, match="feed-owner token"):
            await pool.start()
        assert pool._stream is None

    @pytest.mark.asyncio
    async def test_start_idempotent(self):
        pool, _, _ = _make_pool()
        with patch(
            "monitor.streams.market_stream_pool.MarketDataStream"
        ) as MdsMock:
            mds_inst = MagicMock()
            mds_inst.start = AsyncMock()
            MdsMock.return_value = mds_inst
            await pool.start()
            await pool.start()
        assert MdsMock.call_count == 1

    @pytest.mark.asyncio
    async def test_stop_clears_stream_preserves_interest(self):
        pool, _, _ = _make_pool()
        pool._stream = MagicMock()
        pool._stream.subscribe = AsyncMock()
        pool._stream.unsubscribe = AsyncMock()
        pool._stream.stop = AsyncMock()
        await pool.set_interest(1, {"A"})
        await pool.stop()
        assert pool._stream is None
        # Interest map must survive — re-start would resubscribe from it.
        assert pool.interest_for(1) == {"A"}


class TestTokenRotation:
    @pytest.mark.asyncio
    async def test_rotate_token_rebuilds_stream_and_resubscribes(self):
        pool, get_token, _ = _make_pool()

        # Pre-load some interest so we verify resubscribe.
        pool._interest = {
            "A": {1, 2},
            "B": {1},
        }

        # First call returns "old", second (force) returns "new"
        get_token.side_effect = ["old", "new"]
        with patch(
            "monitor.streams.market_stream_pool.MarketDataStream"
        ) as MdsMock:
            old_inst = MagicMock()
            old_inst.start = AsyncMock()
            old_inst.stop = AsyncMock()
            old_inst.subscribe = AsyncMock()
            new_inst = MagicMock()
            new_inst.start = AsyncMock()
            new_inst.stop = AsyncMock()
            new_inst.subscribe = AsyncMock()
            MdsMock.side_effect = [old_inst, new_inst]

            await pool.start()
            await pool.rotate_token()

        # Old stream stopped, new stream started + resubscribed
        old_inst.stop.assert_awaited()
        new_inst.start.assert_awaited()
        new_inst.subscribe.assert_awaited_once()
        sub_keys = set(new_inst.subscribe.call_args.args[0])
        assert sub_keys == {"A", "B"}
        # get_owner_token called with force_refresh=True at rotate time
        assert get_token.await_args_list[-1].args == (True,)

    @pytest.mark.asyncio
    async def test_auth_failure_chains_into_rotate(self):
        pool, get_token, _ = _make_pool()
        get_token.side_effect = ["t1", "t2"]
        with patch(
            "monitor.streams.market_stream_pool.MarketDataStream"
        ) as MdsMock:
            inst1 = MagicMock()
            inst1.start = AsyncMock()
            inst1.stop = AsyncMock()
            inst2 = MagicMock()
            inst2.start = AsyncMock()
            inst2.stop = AsyncMock()
            inst2.subscribe = AsyncMock()
            MdsMock.side_effect = [inst1, inst2]

            await pool.start()
            await pool._on_pool_auth_failure()

        # Should have rebuilt
        assert MdsMock.call_count == 2

    @pytest.mark.asyncio
    async def test_rotate_with_no_token_leaves_stream_stopped(self):
        pool, get_token, _ = _make_pool(owner_token="t1")
        get_token.side_effect = ["t1", None]  # second call (force) fails
        with patch(
            "monitor.streams.market_stream_pool.MarketDataStream"
        ) as MdsMock:
            inst1 = MagicMock()
            inst1.start = AsyncMock()
            inst1.stop = AsyncMock()
            MdsMock.return_value = inst1

            await pool.start()
            await pool.rotate_token()

        inst1.stop.assert_awaited()
        assert pool._stream is None
