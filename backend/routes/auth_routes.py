"""
Authentication routes for user info and preferences
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from auth import User, get_current_user
from database.models import UserPreference
from sqlalchemy import select
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

# Will be set by main.py
_db_manager = None


@router.get("/api/auth/me")
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """
    Get current user info from JWT token.
    Returns user data including permissions.
    """
    return {
        "id": current_user.id,
        "email": current_user.email,
        "name": current_user.name,
        "picture": current_user.picture,
        "bio": current_user.bio,
        "permissions": current_user.permissions
    }


class HITLPreferenceUpdate(BaseModel):
    """Update HITL preference"""
    enabled: bool


@router.get("/api/auth/preferences")
async def get_user_preferences(current_user: User = Depends(get_current_user)):
    """Get user preferences including HITL settings"""
    if not _db_manager:
        raise HTTPException(status_code=500, detail="Database not configured")

    try:
        async with _db_manager.async_session() as session:
            # Query user preferences
            stmt = select(UserPreference).where(UserPreference.user_id == str(current_user.id))
            result = await session.execute(stmt)
            prefs = result.scalar_one_or_none()

            if not prefs:
                # Create default preferences if they don't exist
                prefs = UserPreference(
                    user_id=str(current_user.id),
                    hitl_enabled=False,
                    theme="light",
                    sidebar_collapsed=False
                )
                session.add(prefs)
                await session.commit()

            return {
                "hitl_enabled": prefs.hitl_enabled,
                "theme": prefs.theme,
                "sidebar_collapsed": prefs.sidebar_collapsed,
                "default_model": prefs.default_model,
                "temperature": prefs.temperature
            }

    except Exception as e:
        logger.error(f"Error fetching user preferences: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/api/auth/preferences/hitl")
async def update_hitl_preference(
    update: HITLPreferenceUpdate,
    current_user: User = Depends(get_current_user)
):
    """Update HITL (Human-in-the-Loop) preference"""
    if not _db_manager:
        raise HTTPException(status_code=500, detail="Database not configured")

    try:
        async with _db_manager.async_session() as session:
            # Get or create user preferences
            stmt = select(UserPreference).where(UserPreference.user_id == str(current_user.id))
            result = await session.execute(stmt)
            prefs = result.scalar_one_or_none()

            if not prefs:
                # Create new preferences
                prefs = UserPreference(
                    user_id=str(current_user.id),
                    hitl_enabled=update.enabled
                )
                session.add(prefs)
            else:
                # Update existing
                prefs.hitl_enabled = update.enabled

            await session.commit()

            logger.info(f"[HITL] User {current_user.email} set HITL to {update.enabled}")

            return {
                "success": True,
                "hitl_enabled": update.enabled
            }

    except Exception as e:
        logger.error(f"Error updating HITL preference: {e}")
        raise HTTPException(status_code=500, detail=str(e))
