"""Tests for MarketDataStream silence watchdog.

Catches the failure mode observed live on 2026-05-07 for user 5:
WebSocket stays connected and "subscribed" but Upstox delivers no
ticks for hours. The watchdog detects silence and forces a reconnect.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from monitor.streams.market_data import MarketDataStream, _in_market_hours


def _make_stream(silence_threshold: float = 0.05) -> MarketDataStream:
    return MarketDataStream(
        access_token="test-token",
        on_message=AsyncMock(),
        mode="full",
        silence_threshold=silence_threshold,
        watchdog_interval=0.01,
    )


class TestMarketHoursHelper:
    def test_weekday_in_window(self):
        # Mon 2026-05-04 04:00 UTC = 09:30 IST (in market)
        assert _in_market_hours(datetime(2026, 5, 4, 4, 0))

    def test_weekday_before_open(self):
        # Mon 03:30 UTC = 09:00 IST (pre-open)
        assert not _in_market_hours(datetime(2026, 5, 4, 3, 30))

    def test_weekday_after_close(self):
        # Mon 10:30 UTC = 16:00 IST (post-close)
        assert not _in_market_hours(datetime(2026, 5, 4, 10, 30))

    def test_saturday_excluded(self):
        # Sat in market window — still excluded
        assert not _in_market_hours(datetime(2026, 5, 9, 5, 0))


class TestSilenceWatchdog:
    @pytest.mark.asyncio
    async def test_tick_resets_timer(self):
        stream = _make_stream()
        # Wrapped on_message bumps _last_tick_at.
        await stream._on_message({"foo": "bar"})  # type: ignore[attr-defined]
        assert stream._last_tick_at is not None
        # User callback was forwarded.
        stream._user_on_message.assert_awaited_once_with({"foo": "bar"})

    @pytest.mark.asyncio
    async def test_silence_triggers_close_when_subscribed_and_market_open(self):
        stream = _make_stream(silence_threshold=0.05)
        stream._running = True
        stream._subscribed_keys = {"NSE_INDEX|Nifty 50"}
        stream._last_tick_at = datetime.utcnow() - timedelta(seconds=120)
        ws = AsyncMock()
        stream._ws = ws

        with patch(
            "monitor.streams.market_data._in_market_hours", return_value=True
        ):
            task = asyncio.create_task(stream._watchdog_loop())
            # Give the loop time for one iteration.
            await asyncio.sleep(0.05)
            stream._running = False
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        ws.close.assert_awaited()
        # Reset so next-connect grace window starts fresh.
        assert stream._last_tick_at is None

    @pytest.mark.asyncio
    async def test_silence_does_not_trigger_outside_market_hours(self):
        stream = _make_stream(silence_threshold=0.05)
        stream._running = True
        stream._subscribed_keys = {"NSE_INDEX|Nifty 50"}
        stream._last_tick_at = datetime.utcnow() - timedelta(seconds=120)
        ws = AsyncMock()
        stream._ws = ws

        with patch(
            "monitor.streams.market_data._in_market_hours", return_value=False
        ):
            task = asyncio.create_task(stream._watchdog_loop())
            await asyncio.sleep(0.05)
            stream._running = False
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        ws.close.assert_not_called()

    @pytest.mark.asyncio
    async def test_silence_does_not_trigger_with_no_subscriptions(self):
        stream = _make_stream(silence_threshold=0.05)
        stream._running = True
        stream._subscribed_keys = set()
        stream._last_tick_at = datetime.utcnow() - timedelta(seconds=120)
        ws = AsyncMock()
        stream._ws = ws

        with patch(
            "monitor.streams.market_data._in_market_hours", return_value=True
        ):
            task = asyncio.create_task(stream._watchdog_loop())
            await asyncio.sleep(0.05)
            stream._running = False
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        ws.close.assert_not_called()

    @pytest.mark.asyncio
    async def test_recent_tick_does_not_trigger(self):
        stream = _make_stream(silence_threshold=60.0)
        stream._running = True
        stream._subscribed_keys = {"NSE_INDEX|Nifty 50"}
        stream._last_tick_at = datetime.utcnow()  # just now
        ws = AsyncMock()
        stream._ws = ws

        with patch(
            "monitor.streams.market_data._in_market_hours", return_value=True
        ):
            task = asyncio.create_task(stream._watchdog_loop())
            await asyncio.sleep(0.05)
            stream._running = False
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        ws.close.assert_not_called()

    @pytest.mark.asyncio
    async def test_pre_connect_no_clock_no_trigger(self):
        """Before the first _on_connected, _last_tick_at is None — skip."""
        stream = _make_stream(silence_threshold=0.05)
        stream._running = True
        stream._subscribed_keys = {"NSE_INDEX|Nifty 50"}
        stream._last_tick_at = None
        ws = AsyncMock()
        stream._ws = ws

        with patch(
            "monitor.streams.market_data._in_market_hours", return_value=True
        ):
            task = asyncio.create_task(stream._watchdog_loop())
            await asyncio.sleep(0.05)
            stream._running = False
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        ws.close.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_connected_seeds_tick_clock(self):
        """A stream that connects but never gets its first tick still
        trips the watchdog after the threshold — guaranteed by seeding
        _last_tick_at on connect."""
        stream = _make_stream()
        stream._subscribed_keys = {"NSE_INDEX|Nifty 50"}
        before = datetime.utcnow()
        ws = AsyncMock()
        await stream._on_connected(ws)
        assert stream._last_tick_at is not None
        assert stream._last_tick_at >= before
