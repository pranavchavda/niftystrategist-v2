"""Tests for UpstoxClient 401 → TOTP refresh + retry helper.

Verifies the contract added 2026-05-11 after a Post-Close awakening hit
UDAPI100050 (Invalid token) and didn't recover. The helper must:
  - on 401: force a TOTP refresh, retry once
  - on success during retry: return the response
  - if refresh fails: re-raise the original 401
  - if max_refreshes=0: don't retry, re-raise immediately
  - on non-401 ApiException: re-raise unchanged
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from upstox_client.rest import ApiException

from services.upstox_client import UpstoxClient


def _api_401() -> ApiException:
    e = ApiException(status=401, reason="Unauthorized")
    return e


def _api_500() -> ApiException:
    e = ApiException(status=500, reason="Server Error")
    return e


@pytest.mark.asyncio
async def test_retry_succeeds_after_refresh():
    client = UpstoxClient(access_token="stale", user_id=1, paper_trading=False)

    call_count = {"n": 0}

    def fn():
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise _api_401()
        return {"ok": True}

    with patch.object(client, "_refresh_token_force", new=AsyncMock(return_value=True)) as mock_refresh:
        result = await client._call_with_token_retry(fn)

    assert result == {"ok": True}
    assert call_count["n"] == 2
    mock_refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_retry_reraises_when_refresh_fails():
    client = UpstoxClient(access_token="stale", user_id=1, paper_trading=False)

    def fn():
        raise _api_401()

    with patch.object(client, "_refresh_token_force", new=AsyncMock(return_value=False)):
        with pytest.raises(ApiException) as exc_info:
            await client._call_with_token_retry(fn)
    assert exc_info.value.status == 401


@pytest.mark.asyncio
async def test_max_refreshes_zero_does_not_retry():
    client = UpstoxClient(access_token="stale", user_id=1, paper_trading=False)
    call_count = {"n": 0}

    def fn():
        call_count["n"] += 1
        raise _api_401()

    with patch.object(client, "_refresh_token_force", new=AsyncMock(return_value=True)) as mock_refresh:
        with pytest.raises(ApiException):
            await client._call_with_token_retry(fn, max_refreshes=0)

    assert call_count["n"] == 1
    mock_refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_non_401_passes_through_unchanged():
    client = UpstoxClient(access_token="stale", user_id=1, paper_trading=False)

    def fn():
        raise _api_500()

    with patch.object(client, "_refresh_token_force", new=AsyncMock(return_value=True)) as mock_refresh:
        with pytest.raises(ApiException) as exc_info:
            await client._call_with_token_retry(fn)

    assert exc_info.value.status == 500
    mock_refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_two_401s_only_one_refresh_then_reraise():
    """If retry also returns 401 (refresh succeeded but token still bad),
    re-raise — we don't keep hammering TOTP."""
    client = UpstoxClient(access_token="stale", user_id=1, paper_trading=False)
    call_count = {"n": 0}

    def fn():
        call_count["n"] += 1
        raise _api_401()

    with patch.object(client, "_refresh_token_force", new=AsyncMock(return_value=True)) as mock_refresh:
        with pytest.raises(ApiException):
            await client._call_with_token_retry(fn, max_refreshes=1)

    assert call_count["n"] == 2  # original + 1 retry
    assert mock_refresh.await_count == 1


@pytest.mark.asyncio
async def test_works_with_async_callable():
    client = UpstoxClient(access_token="stale", user_id=1, paper_trading=False)
    call_count = {"n": 0}

    async def fn():
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise _api_401()
        return "ok"

    with patch.object(client, "_refresh_token_force", new=AsyncMock(return_value=True)):
        result = await client._call_with_token_retry(fn)

    assert result == "ok"
    assert call_count["n"] == 2


@pytest.mark.asyncio
async def test_refresh_force_skips_when_no_user_id():
    """Shared/global clients without a user_id can't TOTP-refresh."""
    client = UpstoxClient(access_token="stale", user_id=0, paper_trading=False)
    ok = await client._refresh_token_force()
    assert ok is False
