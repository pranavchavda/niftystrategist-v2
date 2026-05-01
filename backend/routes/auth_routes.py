"""
Authentication routes for user info and preferences
"""

from fastapi import APIRouter, Depends, HTTPException
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


@router.get("/api/auth/preferences")
async def get_user_preferences(current_user: User = Depends(get_current_user)):
    """Get user preferences"""
    if not _db_manager:
        raise HTTPException(status_code=500, detail="Database not configured")

    try:
        async with _db_manager.async_session() as session:
            stmt = select(UserPreference).where(UserPreference.user_id == str(current_user.id))
            result = await session.execute(stmt)
            prefs = result.scalar_one_or_none()

            if not prefs:
                prefs = UserPreference(
                    user_id=str(current_user.id),
                    theme="light",
                    sidebar_collapsed=False
                )
                session.add(prefs)
                await session.commit()

            return {
                "theme": prefs.theme,
                "sidebar_collapsed": prefs.sidebar_collapsed,
                "default_model": prefs.default_model,
                "temperature": prefs.temperature
            }

    except Exception as e:
        logger.error(f"Error fetching user preferences: {e}")
        raise HTTPException(status_code=500, detail=str(e))
