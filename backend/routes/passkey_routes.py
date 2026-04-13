"""
WebAuthn passkey authentication routes.

Provides passkey registration (for logged-in users) and passkey login.
Challenge state is stored in the Starlette session (SessionMiddleware
is added in main.py).
"""

import os
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import selectinload

import webauthn
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    ResidentKeyRequirement,
    UserVerificationRequirement,
    PublicKeyCredentialDescriptor,
    AuthenticatorTransport,
)
from webauthn.helpers import bytes_to_base64url, base64url_to_bytes

from auth import User, get_current_user, create_access_token
from database.models import User as DBUser, UserPasskey, Role
from database.session import AsyncSessionLocal

router = APIRouter()
logger = logging.getLogger(__name__)

# ── RP configuration ──────────────────────────────────────────────────────

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

def _get_rp_id() -> str:
    """Derive RP ID from FRONTEND_URL (just the hostname, no port)."""
    from urllib.parse import urlparse
    parsed = urlparse(FRONTEND_URL)
    return parsed.hostname or "localhost"

def _get_origin() -> str:
    """Expected origin for WebAuthn responses."""
    return FRONTEND_URL

RP_NAME = "Nifty Strategist"


# ── Pydantic request/response models ─────────────────────────────────────

class PasskeyRegisterVerifyRequest(BaseModel):
    credential: dict
    device_name: str | None = None

class PasskeyLoginVerifyRequest(BaseModel):
    credential: dict


# ── Helpers ───────────────────────────────────────────────────────────────

def _transport_str_to_enum(t: str) -> AuthenticatorTransport | None:
    try:
        return AuthenticatorTransport(t)
    except ValueError:
        return None


# ── Registration (requires auth) ─────────────────────────────────────────

@router.post("/api/auth/passkey/register/options")
async def passkey_register_options(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Generate WebAuthn registration options for the current user."""
    rp_id = _get_rp_id()

    async with AsyncSessionLocal() as db:
        stmt = select(UserPasskey).where(UserPasskey.user_id == current_user.id)
        result = await db.execute(stmt)
        existing = result.scalars().all()

    exclude_credentials = [
        PublicKeyCredentialDescriptor(
            id=pk.credential_id,
            transports=[
                t_enum
                for t in (pk.transports or [])
                if (t_enum := _transport_str_to_enum(t)) is not None
            ],
        )
        for pk in existing
    ]

    options = webauthn.generate_registration_options(
        rp_id=rp_id,
        rp_name=RP_NAME,
        user_id=str(current_user.id).encode(),
        user_name=current_user.email,
        user_display_name=current_user.name or current_user.email,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
        exclude_credentials=exclude_credentials,
    )

    request.session["passkey_register_challenge"] = bytes_to_base64url(options.challenge)

    options_json = webauthn.options_to_json(options)

    import json
    return {"options": json.loads(options_json)}


@router.post("/api/auth/passkey/register/verify")
async def passkey_register_verify(
    body: PasskeyRegisterVerifyRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Verify a WebAuthn registration response and store the credential."""
    challenge_b64 = request.session.pop("passkey_register_challenge", None)
    if not challenge_b64:
        raise HTTPException(status_code=400, detail="No registration challenge in session")

    expected_challenge = base64url_to_bytes(challenge_b64)
    rp_id = _get_rp_id()
    origin = _get_origin()

    import json
    credential_json = json.dumps(body.credential)

    try:
        verification = webauthn.verify_registration_response(
            credential=credential_json,
            expected_challenge=expected_challenge,
            expected_rp_id=rp_id,
            expected_origin=origin,
        )
    except Exception as e:
        logger.error(f"Passkey registration verification failed: {e}")
        raise HTTPException(status_code=400, detail=f"Verification failed: {e}")

    transports = body.credential.get("response", {}).get("transports", [])
    if not transports:
        transports = body.credential.get("transports", [])

    async with AsyncSessionLocal() as db:
        passkey = UserPasskey(
            user_id=current_user.id,
            credential_id=verification.credential_id,
            public_key=verification.credential_public_key,
            sign_count=verification.sign_count,
            device_name=body.device_name or "Passkey",
            transports=transports if transports else None,
        )
        db.add(passkey)
        await db.commit()

    logger.info(f"Passkey registered for user {current_user.email} (device: {body.device_name})")

    return {
        "success": True,
        "credential_id": bytes_to_base64url(verification.credential_id),
        "device_name": body.device_name or "Passkey",
    }


# ── Authentication (no auth required) ────────────────────────────────────

@router.post("/api/auth/passkey/login/options")
async def passkey_login_options(request: Request):
    """Generate WebAuthn authentication options (discoverable credentials)."""
    rp_id = _get_rp_id()

    options = webauthn.generate_authentication_options(
        rp_id=rp_id,
        user_verification=UserVerificationRequirement.PREFERRED,
    )

    request.session["passkey_login_challenge"] = bytes_to_base64url(options.challenge)

    options_json = webauthn.options_to_json(options)

    import json
    return {"options": json.loads(options_json)}


@router.post("/api/auth/passkey/login/verify")
async def passkey_login_verify(
    body: PasskeyLoginVerifyRequest,
    request: Request,
):
    """Verify a WebAuthn authentication response and return a JWT."""
    challenge_b64 = request.session.pop("passkey_login_challenge", None)
    if not challenge_b64:
        raise HTTPException(status_code=400, detail="No login challenge in session")

    expected_challenge = base64url_to_bytes(challenge_b64)
    rp_id = _get_rp_id()
    origin = _get_origin()

    raw_id = body.credential.get("rawId") or body.credential.get("id", "")
    try:
        credential_id_bytes = base64url_to_bytes(raw_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid credential ID")

    async with AsyncSessionLocal() as db:
        stmt = select(UserPasskey).where(UserPasskey.credential_id == credential_id_bytes)
        result = await db.execute(stmt)
        passkey = result.scalar_one_or_none()

        if not passkey:
            raise HTTPException(status_code=401, detail="Unknown passkey")

        import json
        credential_json = json.dumps(body.credential)

        try:
            verification = webauthn.verify_authentication_response(
                credential=credential_json,
                expected_challenge=expected_challenge,
                expected_rp_id=rp_id,
                expected_origin=origin,
                credential_public_key=passkey.public_key,
                credential_current_sign_count=passkey.sign_count,
            )
        except Exception as e:
            logger.error(f"Passkey login verification failed: {e}")
            raise HTTPException(status_code=401, detail=f"Authentication failed: {e}")

        passkey.sign_count = verification.new_sign_count
        passkey.last_used_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await db.commit()

        user_stmt = (
            select(DBUser)
            .where(DBUser.id == passkey.user_id)
            .options(selectinload(DBUser.roles).selectinload(Role.permissions))
        )
        user_result = await db.execute(user_stmt)
        db_user = user_result.scalar_one_or_none()

        if not db_user:
            raise HTTPException(status_code=401, detail="User not found")

        permissions = []
        for role in db_user.roles:
            for perm in role.permissions:
                if perm.name not in permissions:
                    permissions.append(perm.name)

        user_data = {
            "id": db_user.id,
            "email": db_user.email,
            "name": db_user.name or db_user.email.split("@")[0],
            "permissions": permissions,
        }
        token = create_access_token(user_data)

        logger.info(f"Passkey login successful for user: {db_user.email}")

        return {
            "access_token": token,
            "token_type": "bearer",
            "user": user_data,
        }


# ── Passkey management (requires auth) ───────────────────────────────────

@router.get("/api/auth/passkeys")
async def list_passkeys(current_user: User = Depends(get_current_user)):
    """List all passkeys for the current user."""
    async with AsyncSessionLocal() as db:
        stmt = select(UserPasskey).where(UserPasskey.user_id == current_user.id)
        result = await db.execute(stmt)
        passkeys = result.scalars().all()

    return {
        "passkeys": [
            {
                "id": pk.id,
                "credential_id": bytes_to_base64url(pk.credential_id),
                "device_name": pk.device_name,
                "created_at": pk.created_at.isoformat() if pk.created_at else None,
                "last_used_at": pk.last_used_at.isoformat() if pk.last_used_at else None,
            }
            for pk in passkeys
        ]
    }


@router.delete("/api/auth/passkeys/{passkey_id}")
async def delete_passkey(
    passkey_id: int,
    current_user: User = Depends(get_current_user),
):
    """Delete a passkey by ID (must belong to current user)."""
    async with AsyncSessionLocal() as db:
        stmt = select(UserPasskey).where(
            UserPasskey.id == passkey_id,
            UserPasskey.user_id == current_user.id,
        )
        result = await db.execute(stmt)
        passkey = result.scalar_one_or_none()

        if not passkey:
            raise HTTPException(status_code=404, detail="Passkey not found")

        await db.delete(passkey)
        await db.commit()

    logger.info(f"Passkey {passkey_id} deleted for user {current_user.email}")
    return {"success": True}
