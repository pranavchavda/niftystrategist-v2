"""Tests for Upstox TOTP auto-refresh functionality."""
from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── Helpers ──────────────────────────────────────────────────────────


def _make_db_user(**overrides) -> MagicMock:
    """Create a mock DBUser with TOTP fields."""
    user = MagicMock()
    user.id = overrides.get("id", 999)
    user.upstox_mobile = overrides.get("upstox_mobile", None)
    user.upstox_pin = overrides.get("upstox_pin", None)
    user.upstox_totp_secret = overrides.get("upstox_totp_secret", None)
    user.upstox_totp_last_failed_at = overrides.get("upstox_totp_last_failed_at", None)
    user.upstox_api_key = overrides.get("upstox_api_key", "enc-api-key")
    user.upstox_api_secret = overrides.get("upstox_api_secret", "enc-api-secret")
    user.upstox_access_token = overrides.get("upstox_access_token", None)
    user.upstox_token_expiry = overrides.get("upstox_token_expiry", None)
    user.upstox_user_id = overrides.get("upstox_user_id", None)
    return user


# ── Test: _totp_get_token success ────────────────────────────────────


def test_totp_get_token_success():
    """_totp_get_token returns access_token on success."""
    from api.upstox_oauth import _totp_get_token

    # Mock the response from get_access_token()
    mock_response = MagicMock()
    mock_response.success = True
    mock_response.data.access_token = "fresh-access-token"

    mock_app_token = MagicMock()
    mock_app_token.get_access_token.return_value = mock_response

    mock_client = MagicMock()
    mock_client.app_token = mock_app_token

    with patch("api.upstox_oauth._import_totp_login") as mock_import:
        mock_cls = MagicMock()
        mock_cls.return_value = mock_client
        mock_import.return_value = mock_cls

        result = _totp_get_token(
            mobile="9876543210",
            pin="1234",
            totp_secret="JBSWY3DPEHPK3PXP",
            api_key="my-api-key",
            api_secret="my-api-secret",
            redirect_uri="http://localhost:5173/auth/upstox/callback",
        )

    assert result == {"success": True, "access_token": "fresh-access-token"}
    mock_cls.assert_called_once_with(
        username="9876543210",
        password="1234",
        pin_code="1234",
        totp_secret="JBSWY3DPEHPK3PXP",
        client_id="my-api-key",
        client_secret="my-api-secret",
        redirect_uri="http://localhost:5173/auth/upstox/callback",
    )


# ── Test: _totp_get_token failure ────────────────────────────────────


def test_totp_get_token_failure():
    """_totp_get_token returns success=False when login raises."""
    from api.upstox_oauth import _totp_get_token

    with patch("api.upstox_oauth._import_totp_login") as mock_import:
        mock_cls = MagicMock()
        mock_cls.side_effect = Exception("TOTP login failed: invalid OTP")
        mock_import.return_value = mock_cls

        result = _totp_get_token(
            mobile="9876543210",
            pin="1234",
            totp_secret="BAD_SECRET",
            api_key="my-api-key",
            api_secret="my-api-secret",
            redirect_uri="http://localhost:5173/auth/upstox/callback",
        )

    assert result["success"] is False
    assert "error" in result


# ── Test: auto_refresh_success ────────────────────────────────────────


@pytest.mark.asyncio
async def test_auto_refresh_success():
    """auto_refresh_upstox_token stores new token and returns it."""
    from api.upstox_oauth import auto_refresh_upstox_token

    db_user = _make_db_user(
        upstox_mobile="enc-mobile",
        upstox_pin="enc-pin",
        upstox_totp_secret="enc-totp-secret",
    )

    mock_session = AsyncMock()

    # Mock select().where() to return our user
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = db_user
    mock_session.execute = AsyncMock(return_value=mock_result)

    with patch("api.upstox_oauth.get_db_session") as mock_get_db, \
         patch("api.upstox_oauth.decrypt_token", side_effect=lambda x: f"dec-{x}"), \
         patch("api.upstox_oauth.encrypt_token", side_effect=lambda x: f"enc-{x}"), \
         patch("api.upstox_oauth._totp_get_token", return_value={"success": True, "access_token": "new-token"}), \
         patch("api.upstox_oauth._get_user_upstox_credentials", new_callable=AsyncMock, return_value=("api-key", "api-secret")):

        mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_get_db.return_value.__aexit__ = AsyncMock(return_value=False)

        token = await auto_refresh_upstox_token(999)

    assert token == "new-token"
    # Token should be stored encrypted
    assert db_user.upstox_access_token == "enc-new-token"
    mock_session.commit.assert_awaited_once()


# ── Test: auto_refresh_no_totp_credentials ────────────────────────────


@pytest.mark.asyncio
async def test_auto_refresh_no_totp_credentials():
    """Returns None when TOTP credentials are not set."""
    from api.upstox_oauth import auto_refresh_upstox_token

    # User with no TOTP creds
    db_user = _make_db_user()

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = db_user
    mock_session.execute = AsyncMock(return_value=mock_result)

    with patch("api.upstox_oauth.get_db_session") as mock_get_db:
        mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_get_db.return_value.__aexit__ = AsyncMock(return_value=False)

        token = await auto_refresh_upstox_token(999)

    assert token is None


# ── Test: auto_refresh_cooldown_active ────────────────────────────────


@pytest.mark.asyncio
async def test_auto_refresh_cooldown_active():
    """Returns None when within 30-minute cooldown."""
    from api.upstox_oauth import auto_refresh_upstox_token
    from database.models import utc_now

    db_user = _make_db_user(
        upstox_mobile="enc-mobile",
        upstox_pin="enc-pin",
        upstox_totp_secret="enc-totp-secret",
        # Failed 5 minutes ago
        upstox_totp_last_failed_at=utc_now() - timedelta(minutes=5),
    )

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = db_user
    mock_session.execute = AsyncMock(return_value=mock_result)

    with patch("api.upstox_oauth.get_db_session") as mock_get_db:
        mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_get_db.return_value.__aexit__ = AsyncMock(return_value=False)

        token = await auto_refresh_upstox_token(999)

    assert token is None


# ── Test: auto_refresh_failure_sets_cooldown ──────────────────────────


@pytest.mark.asyncio
async def test_auto_refresh_failure_sets_cooldown():
    """On TOTP failure, records last_failed_at timestamp."""
    from api.upstox_oauth import auto_refresh_upstox_token

    db_user = _make_db_user(
        upstox_mobile="enc-mobile",
        upstox_pin="enc-pin",
        upstox_totp_secret="enc-totp-secret",
    )

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = db_user
    mock_session.execute = AsyncMock(return_value=mock_result)

    with patch("api.upstox_oauth.get_db_session") as mock_get_db, \
         patch("api.upstox_oauth.decrypt_token", side_effect=lambda x: f"dec-{x}"), \
         patch("api.upstox_oauth._totp_get_token", return_value={"success": False, "error": "bad OTP"}), \
         patch("api.upstox_oauth._get_user_upstox_credentials", new_callable=AsyncMock, return_value=("api-key", "api-secret")):

        mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_get_db.return_value.__aexit__ = AsyncMock(return_value=False)

        token = await auto_refresh_upstox_token(999)

    assert token is None
    assert db_user.upstox_totp_last_failed_at is not None
    mock_session.commit.assert_awaited_once()


# ── Test: auto_refresh_exception_sets_cooldown ────────────────────────


@pytest.mark.asyncio
async def test_auto_refresh_exception_sets_cooldown():
    """On exception during TOTP, records last_failed_at timestamp."""
    from api.upstox_oauth import auto_refresh_upstox_token

    db_user = _make_db_user(
        upstox_mobile="enc-mobile",
        upstox_pin="enc-pin",
        upstox_totp_secret="enc-totp-secret",
    )

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = db_user
    mock_session.execute = AsyncMock(return_value=mock_result)

    with patch("api.upstox_oauth.get_db_session") as mock_get_db, \
         patch("api.upstox_oauth.decrypt_token", side_effect=lambda x: f"dec-{x}"), \
         patch("api.upstox_oauth._totp_get_token", side_effect=RuntimeError("network error")), \
         patch("api.upstox_oauth._get_user_upstox_credentials", new_callable=AsyncMock, return_value=("api-key", "api-secret")):

        mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_get_db.return_value.__aexit__ = AsyncMock(return_value=False)

        token = await auto_refresh_upstox_token(999)

    assert token is None
    assert db_user.upstox_totp_last_failed_at is not None
    mock_session.commit.assert_awaited_once()
