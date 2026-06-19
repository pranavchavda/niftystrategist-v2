"""Web Push subscription management API.

The PWA subscribes a device via the browser PushManager and posts the resulting
subscription here. Sending happens out-of-band via services.webpush_notifier
(usually behind services.notifier.notify_user).

VAPID public key is served to the frontend so it can subscribe without a
build-time env. Notification category prefs are shared with Telegram and managed
by `PUT /api/telegram/notification-prefs` — not duplicated here.

See docs/plans/2026-06-19-web-push-notifications.md.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, func, select

from auth import get_current_user, User
from database.session import get_db_session
from database.models import WebPushSubscription, User as DBUser, utc_now
from services.webpush_notifier import VAPID_PUBLIC_KEY

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/push", tags=["push"])


class SubscriptionKeys(BaseModel):
    p256dh: str
    auth: str


class SubscribeRequest(BaseModel):
    endpoint: str
    keys: SubscriptionKeys
    user_agent: Optional[str] = None


class UnsubscribeRequest(BaseModel):
    endpoint: str


class PushStatusResponse(BaseModel):
    enabled: bool
    device_count: int
    vapid_public_key: Optional[str] = None
    notification_prefs: dict = {}


@router.get("/vapid-public-key")
async def get_vapid_public_key():
    """Return the app VAPID public key the browser needs to subscribe."""
    if not VAPID_PUBLIC_KEY:
        raise HTTPException(status_code=503, detail="Web Push not configured")
    return {"key": VAPID_PUBLIC_KEY}


@router.post("/subscribe")
async def subscribe(
    request: SubscribeRequest,
    user: User = Depends(get_current_user),
):
    """Register (or refresh) a browser push subscription for this user/device.

    Upserts on (user_id, endpoint) so re-subscribing the same device — common
    after a key rotation or SW update — refreshes the keys instead of duplicating.
    """
    endpoint = request.endpoint.strip()
    if not endpoint or not request.keys.p256dh or not request.keys.auth:
        raise HTTPException(status_code=400, detail="Incomplete subscription")

    async with get_db_session() as session:
        existing = (
            await session.execute(
                select(WebPushSubscription).where(
                    WebPushSubscription.user_id == user.id,
                    WebPushSubscription.endpoint == endpoint,
                )
            )
        ).scalar_one_or_none()

        if existing:
            existing.p256dh = request.keys.p256dh
            existing.auth = request.keys.auth
            existing.user_agent = request.user_agent
            existing.last_used_at = utc_now()
        else:
            session.add(
                WebPushSubscription(
                    user_id=user.id,
                    endpoint=endpoint,
                    p256dh=request.keys.p256dh,
                    auth=request.keys.auth,
                    user_agent=request.user_agent,
                )
            )
        await session.commit()

    logger.info(f"Web Push subscription saved for user {user.id}")
    return {"status": "success"}


@router.delete("/subscribe")
async def unsubscribe(
    request: UnsubscribeRequest,
    user: User = Depends(get_current_user),
):
    """Remove a single device's push subscription."""
    async with get_db_session() as session:
        await session.execute(
            delete(WebPushSubscription).where(
                WebPushSubscription.user_id == user.id,
                WebPushSubscription.endpoint == request.endpoint.strip(),
            )
        )
        await session.commit()

    return {"status": "success"}


@router.get("/status", response_model=PushStatusResponse)
async def get_status(user: User = Depends(get_current_user)):
    """Whether this user has any push devices, plus shared notification prefs."""
    async with get_db_session() as session:
        count = (
            await session.execute(
                select(func.count(WebPushSubscription.id)).where(
                    WebPushSubscription.user_id == user.id
                )
            )
        ).scalar_one()

        prefs = (
            await session.execute(
                select(DBUser.notification_prefs).where(DBUser.id == user.id)
            )
        ).scalar_one_or_none()

    return PushStatusResponse(
        enabled=count > 0,
        device_count=count,
        vapid_public_key=VAPID_PUBLIC_KEY or None,
        notification_prefs=prefs or {},
    )
