"""Regression test for the intraday-merge in UpstoxClient.get_historical_data.

Upstox's historical candle endpoint EXCLUDES the current day; today's candles
only come from the intraday endpoint. The multi-day (days > 1) minute path was
therefore silently T-1 stale until we patched it to also call the intraday
endpoint and append today's candles (dedup by timestamp). See
services/upstox_client.py and the project memory note.

These tests mock the Upstox SDK's HistoryV3Api so no network/token is needed.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.upstox_client import UpstoxClient

# SDK candle shape: [timestamp, open, high, low, close, volume, oi]
HIST_CANDLES = [
    ["2026-05-26T09:15:00+05:30", 100, 102, 99, 101, 1000, 0],
    ["2026-05-26T09:30:00+05:30", 101, 103, 100, 102, 1200, 0],
]
INTRA_CANDLES = [
    # duplicate of the last historical candle — must be deduped, not double-counted
    ["2026-05-26T09:30:00+05:30", 101, 103, 100, 102, 1200, 0],
    ["2026-05-27T09:15:00+05:30", 102, 105, 101, 104, 1500, 0],
    ["2026-05-27T09:30:00+05:30", 104, 106, 103, 105, 1700, 0],
]


def _resp(candles):
    return SimpleNamespace(data=SimpleNamespace(candles=list(candles)))


def _mock_history_api(intra_candles=INTRA_CANDLES):
    api = MagicMock()
    api.get_historical_candle_data1.return_value = _resp(HIST_CANDLES)
    api.get_intra_day_candle_data.return_value = _resp(intra_candles)
    return api


async def _run(client, **kwargs):
    history_api = _mock_history_api(kwargs.pop("intra_candles", INTRA_CANDLES))
    with patch("services.upstox_client.upstox_client.ApiClient", MagicMock()), \
         patch("services.upstox_client.upstox_client.HistoryV3Api", return_value=history_api), \
         patch.object(client, "_ensure_valid_token", new=AsyncMock(return_value=None)):
        result = await client.get_historical_data(
            "TEST", interval="15minute", days=10,
            instrument_key="NSE_EQ|TEST", **kwargs,
        )
    return result, history_api


@pytest.mark.asyncio
async def test_today_candles_appended():
    client = UpstoxClient(access_token="x", user_id=1, paper_trading=False)
    candles, api = await _run(client)
    dates = {c.timestamp[:10] for c in candles}
    assert "2026-05-27" in dates, "today's session must be merged in from intraday"
    assert "2026-05-26" in dates
    # the intraday endpoint must actually be called on the multi-day path
    api.get_intra_day_candle_data.assert_called_once()


@pytest.mark.asyncio
async def test_duplicate_timestamp_deduped():
    client = UpstoxClient(access_token="x", user_id=1, paper_trading=False)
    candles, _ = await _run(client)
    # 2 historical + 3 intraday, but one intraday dupes a historical ts → 4 unique
    timestamps = [c.timestamp for c in candles]
    assert len(timestamps) == len(set(timestamps)), "no duplicate timestamps"
    assert len(candles) == 4


@pytest.mark.asyncio
async def test_candles_sorted_ascending():
    client = UpstoxClient(access_token="x", user_id=1, paper_trading=False)
    candles, _ = await _run(client)
    timestamps = [c.timestamp for c in candles]
    assert timestamps == sorted(timestamps)
    assert candles[-1].timestamp.startswith("2026-05-27")


@pytest.mark.asyncio
async def test_intraday_failure_falls_back_to_historical():
    """If the intraday append throws, we keep the historical candles, not crash."""
    client = UpstoxClient(access_token="x", user_id=1, paper_trading=False)
    history_api = _mock_history_api()
    history_api.get_intra_day_candle_data.side_effect = RuntimeError("boom")
    with patch("services.upstox_client.upstox_client.ApiClient", MagicMock()), \
         patch("services.upstox_client.upstox_client.HistoryV3Api", return_value=history_api), \
         patch.object(client, "_ensure_valid_token", new=AsyncMock(return_value=None)):
        candles = await client.get_historical_data(
            "TEST", interval="15minute", days=10, instrument_key="NSE_EQ|TEST",
        )
    assert len(candles) == 2  # historical only, no crash
    assert all(c.timestamp.startswith("2026-05-26") for c in candles)


@pytest.mark.asyncio
async def test_daily_interval_does_not_call_intraday():
    """Daily-interval (unit='days') must NOT append intraday candles."""
    client = UpstoxClient(access_token="x", user_id=1, paper_trading=False)
    history_api = _mock_history_api()
    with patch("services.upstox_client.upstox_client.ApiClient", MagicMock()), \
         patch("services.upstox_client.upstox_client.HistoryV3Api", return_value=history_api), \
         patch.object(client, "_ensure_valid_token", new=AsyncMock(return_value=None)):
        await client.get_historical_data(
            "TEST", interval="day", days=100, instrument_key="NSE_EQ|TEST",
        )
    history_api.get_intra_day_candle_data.assert_not_called()
