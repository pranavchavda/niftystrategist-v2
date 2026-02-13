"""Upstox OAuth API endpoints for connecting user's trading account."""

import os
import secrets
import logging
import hmac
import hashlib
import base64
import json
from datetime import datetime, timezone, timedelta
from typing import Optional
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import get_current_user, User
from database.session import get_db_session
from database.models import User as DBUser
from utils.encryption import encrypt_token, decrypt_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth/upstox", tags=["upstox-oauth"])

# Upstox OAuth configuration
UPSTOX_AUTH_URL = "https://api.upstox.com/v2/login/authorization/dialog"
UPSTOX_TOKEN_URL = "https://api.upstox.com/v2/login/authorization/token"
UPSTOX_PROFILE_URL = "https://api.upstox.com/v2/user/profile"


def _get_state_secret() -> bytes:
    """Get secret key for signing OAuth state."""
    secret = os.getenv("JWT_SECRET", "fallback-secret-for-dev")
    return secret.encode()


def _create_oauth_state(user_id: int) -> str:
    """
    Create a signed OAuth state that encodes user_id.
    This is stateless - no server-side storage needed.
    """
    # Create payload with user_id and timestamp
    payload = {
        "user_id": user_id,
        "ts": int(datetime.now(timezone.utc).timestamp()),
        "nonce": secrets.token_hex(8)
    }
    payload_json = json.dumps(payload, separators=(',', ':'))
    payload_b64 = base64.urlsafe_b64encode(payload_json.encode()).decode()

    # Sign the payload
    signature = hmac.new(
        _get_state_secret(),
        payload_b64.encode(),
        hashlib.sha256
    ).hexdigest()[:16]  # Use first 16 chars of signature

    return f"{payload_b64}.{signature}"


def _verify_oauth_state(state: str) -> Optional[int]:
    """
    Verify OAuth state and extract user_id.
    Returns user_id if valid, None if invalid/expired.
    """
    try:
        parts = state.split('.')
        if len(parts) != 2:
            return None

        payload_b64, signature = parts

        # Verify signature
        expected_sig = hmac.new(
            _get_state_secret(),
            payload_b64.encode(),
            hashlib.sha256
        ).hexdigest()[:16]

        if not hmac.compare_digest(signature, expected_sig):
            logger.warning("OAuth state signature mismatch")
            return None

        # Decode payload
        payload_json = base64.urlsafe_b64decode(payload_b64.encode()).decode()
        payload = json.loads(payload_json)

        # Check expiry (10 minutes)
        ts = payload.get("ts", 0)
        if datetime.now(timezone.utc).timestamp() - ts > 600:
            logger.warning("OAuth state expired")
            return None

        return payload.get("user_id")

    except Exception as e:
        logger.error(f"OAuth state verification failed: {e}")
        return None


class TradingModeRequest(BaseModel):
    """Request to change trading mode."""
    mode: str  # 'paper' or 'live'


class UpstoxStatusResponse(BaseModel):
    """Response for Upstox connection status."""
    connected: bool
    upstox_user_id: Optional[str] = None
    token_expiry: Optional[str] = None
    trading_mode: str = "paper"


class TradingModeResponse(BaseModel):
    """Response for trading mode."""
    trading_mode: str
    upstox_connected: bool


def _build_upstox_auth_url(user_id: int) -> str:
    """Build Upstox OAuth URL with state for given user."""
    api_key = os.getenv("UPSTOX_API_KEY")
    redirect_uri = os.getenv("UPSTOX_REDIRECT_URI", "http://localhost:5173/auth/upstox/callback")

    if not api_key:
        raise HTTPException(status_code=500, detail="Upstox API key not configured")

    # Generate signed state token (stateless - encodes user_id)
    state = _create_oauth_state(user_id)

    # Build Upstox OAuth URL
    params = {
        "client_id": api_key,
        "redirect_uri": redirect_uri,
        "state": state,
        "response_type": "code",
    }

    return f"{UPSTOX_AUTH_URL}?{urlencode(params)}"


@router.get("/authorize")
async def authorize_upstox(
    request: Request,
    user: User = Depends(get_current_user)
):
    """
    Initiate Upstox OAuth flow.
    Redirects user to Upstox login page.
    """
    auth_url = _build_upstox_auth_url(user.id)
    logger.info(f"Redirecting user {user.id} to Upstox OAuth")
    return RedirectResponse(url=auth_url)


@router.get("/authorize-url")
async def get_authorize_url(user: User = Depends(get_current_user)):
    """
    Get Upstox OAuth URL without redirecting.
    Used by frontend to initiate OAuth flow via fetch + redirect.
    """
    auth_url = _build_upstox_auth_url(user.id)
    logger.info(f"Generated Upstox OAuth URL for user {user.id}")
    return {"url": auth_url}


@router.get("/callback")
async def oauth_callback(
    code: str,
    state: str,
):
    """
    Handle Upstox OAuth callback.
    Exchanges authorization code for access token.
    """
    # Verify and decode state (stateless verification)
    user_id = _verify_oauth_state(state)
    if user_id is None:
        raise HTTPException(status_code=400, detail="Invalid or expired state parameter")

    api_key = os.getenv("UPSTOX_API_KEY")
    api_secret = os.getenv("UPSTOX_API_SECRET")
    redirect_uri = os.getenv("UPSTOX_REDIRECT_URI", "http://localhost:5173/auth/upstox/callback")

    if not api_key or not api_secret:
        raise HTTPException(status_code=500, detail="Upstox credentials not configured")

    # Exchange code for tokens
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            logger.info(f"Exchanging code for tokens with Upstox for user {user_id}")
            response = await client.post(
                UPSTOX_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": api_key,
                    "client_secret": api_secret,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

            logger.info(f"Upstox token response status: {response.status_code}")

            if response.status_code != 200:
                logger.error(f"Upstox token exchange failed: {response.text}")
                error_detail = "Unknown error"
                try:
                    error_detail = response.json().get('message', response.text[:200])
                except Exception:
                    error_detail = response.text[:200] if response.text else "Unknown error"
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to exchange code: {error_detail}"
                )

            token_data = response.json()

    except httpx.RequestError as e:
        logger.error(f"Upstox API request failed: type={type(e).__name__}, error={e}, request={e.request if hasattr(e, 'request') else 'N/A'}")
        raise HTTPException(status_code=500, detail=f"Failed to connect to Upstox: {type(e).__name__}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during token exchange: type={type(e).__name__}, error={e}")
        raise HTTPException(status_code=500, detail=f"Token exchange error: {str(e)}")

    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token", "")

    if not access_token:
        raise HTTPException(status_code=400, detail="No access token in response")

    # Get user profile from Upstox
    upstox_user_id = None
    try:
        async with httpx.AsyncClient() as client:
            profile_response = await client.get(
                UPSTOX_PROFILE_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if profile_response.status_code == 200:
                profile_data = profile_response.json()
                upstox_user_id = profile_data.get("data", {}).get("user_id")
    except Exception as e:
        logger.warning(f"Failed to get Upstox profile: {e}")

    # Calculate token expiry (Upstox tokens typically expire at end of day)
    # Upstox returns expires_in in seconds, but let's default to end of day if not provided
    expires_in = token_data.get("expires_in", 86400)  # Default 24 hours
    # Use naive datetime (no timezone) for database compatibility
    token_expiry = datetime.utcnow() + timedelta(seconds=expires_in)

    # Encrypt and store tokens
    logger.info(f"Looking up user {user_id} to store tokens")
    async with get_db_session() as session:
        result = await session.execute(
            select(DBUser).where(DBUser.id == user_id)
        )
        db_user = result.scalar_one_or_none()

        if not db_user:
            logger.error(f"User not found with id {user_id}")
            raise HTTPException(status_code=404, detail="User not found")

        db_user.upstox_access_token = encrypt_token(access_token)
        db_user.upstox_refresh_token = encrypt_token(refresh_token) if refresh_token else None
        db_user.upstox_token_expiry = token_expiry
        db_user.upstox_user_id = upstox_user_id

        await session.commit()

    logger.info(f"Upstox OAuth successful for user {user_id}")

    # Redirect to frontend settings page with success status
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=f"{frontend_url}/settings?upstox=connected")


@router.post("/disconnect")
async def disconnect_upstox(user: User = Depends(get_current_user)):
    """
    Disconnect user's Upstox account.
    Removes stored tokens and resets to paper trading.
    """
    async with get_db_session() as session:
        result = await session.execute(
            select(DBUser).where(DBUser.id == user.id)
        )
        db_user = result.scalar_one_or_none()

        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")

        db_user.upstox_access_token = None
        db_user.upstox_refresh_token = None
        db_user.upstox_token_expiry = None
        db_user.upstox_user_id = None
        db_user.trading_mode = "paper"  # Reset to paper trading

        await session.commit()

    logger.info(f"Upstox disconnected for user {user.id}")
    return {"status": "success", "message": "Upstox account disconnected"}


@router.get("/status", response_model=UpstoxStatusResponse)
async def get_upstox_status(user: User = Depends(get_current_user)):
    """
    Check if user has a valid Upstox connection.
    Validates token against Upstox API if DB thinks it's still valid.
    """
    async with get_db_session() as session:
        result = await session.execute(
            select(DBUser).where(DBUser.id == user.id)
        )
        db_user = result.scalar_one_or_none()

        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")

        connected = bool(db_user.upstox_access_token)
        token_expiry = None

        if connected and db_user.upstox_token_expiry:
            # Check if token is expired (use naive datetime for DB compatibility)
            if db_user.upstox_token_expiry < datetime.utcnow():
                connected = False  # Token expired per DB
            else:
                token_expiry = db_user.upstox_token_expiry.isoformat()

        # If DB thinks token is valid, verify against Upstox API
        # (Upstox tokens expire at end of trading day regardless of expires_in)
        if connected and db_user.upstox_access_token:
            try:
                real_token = decrypt_token(db_user.upstox_access_token)
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.get(
                        UPSTOX_PROFILE_URL,
                        headers={"Authorization": f"Bearer {real_token}"},
                    )
                    if resp.status_code != 200:
                        logger.info(f"Upstox token invalid for user {user.id} (API returned {resp.status_code})")
                        connected = False
                        token_expiry = None
            except Exception as e:
                logger.warning(f"Upstox token validation failed for user {user.id}: {e}")
                # On network error, trust DB expiry rather than marking disconnected
                pass

        return UpstoxStatusResponse(
            connected=connected,
            upstox_user_id=db_user.upstox_user_id if connected else None,
            token_expiry=token_expiry,
            trading_mode=db_user.trading_mode or "paper",
        )


# Trading mode endpoints
@router.get("/trading-mode", response_model=TradingModeResponse)
async def get_trading_mode(user: User = Depends(get_current_user)):
    """Get user's current trading mode."""
    async with get_db_session() as session:
        result = await session.execute(
            select(DBUser).where(DBUser.id == user.id)
        )
        db_user = result.scalar_one_or_none()

        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")

        upstox_connected = bool(
            db_user.upstox_access_token and
            db_user.upstox_token_expiry and
            db_user.upstox_token_expiry > datetime.utcnow()
        )

        return TradingModeResponse(
            trading_mode=db_user.trading_mode or "paper",
            upstox_connected=upstox_connected,
        )


@router.post("/trading-mode", response_model=TradingModeResponse)
async def set_trading_mode(
    request: TradingModeRequest,
    user: User = Depends(get_current_user)
):
    """
    Set user's trading mode.
    Requires Upstox connection for live trading.
    """
    if request.mode not in ("paper", "live"):
        raise HTTPException(status_code=400, detail="Mode must be 'paper' or 'live'")

    async with get_db_session() as session:
        result = await session.execute(
            select(DBUser).where(DBUser.id == user.id)
        )
        db_user = result.scalar_one_or_none()

        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")

        upstox_connected = bool(
            db_user.upstox_access_token and
            db_user.upstox_token_expiry and
            db_user.upstox_token_expiry > datetime.utcnow()
        )

        # Can only enable live trading if Upstox is connected
        if request.mode == "live" and not upstox_connected:
            raise HTTPException(
                status_code=400,
                detail="Connect your Upstox account before enabling live trading"
            )

        db_user.trading_mode = request.mode
        await session.commit()

        logger.info(f"User {user.id} switched to {request.mode} trading mode")

        return TradingModeResponse(
            trading_mode=request.mode,
            upstox_connected=upstox_connected,
        )


async def get_user_upstox_token(user_id: int) -> Optional[str]:
    """
    Get decrypted Upstox access token for a user.
    Returns None if not connected or token expired.

    This is used by UpstoxClient for live trading.
    """
    async with get_db_session() as session:
        result = await session.execute(
            select(DBUser).where(DBUser.id == user_id)
        )
        db_user = result.scalar_one_or_none()

        if not db_user or not db_user.upstox_access_token:
            return None

        # Check expiry (use naive datetime for DB compatibility)
        if db_user.upstox_token_expiry and db_user.upstox_token_expiry < datetime.utcnow():
            logger.warning(f"Upstox token expired for user {user_id}")
            return None

        return decrypt_token(db_user.upstox_access_token)


async def get_user_trading_mode(user_id: int) -> str:
    """Get user's trading mode (paper or live)."""
    async with get_db_session() as session:
        result = await session.execute(
            select(DBUser.trading_mode).where(DBUser.id == user_id)
        )
        mode = result.scalar_one_or_none()
        return mode or "paper"
