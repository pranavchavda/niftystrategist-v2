from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from database.session import get_db
from database.models import Conversation, Message, User
from services.dashboard_analytics import get_dashboard_analytics_service
from services.price_monitor.dashboard import PriceMonitorDashboard
from auth import get_current_user, User as AuthUser
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize price monitor dashboard service
price_monitor_dashboard = PriceMonitorDashboard()

@router.get("/stats")
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db)
):
    """Get dashboard statistics"""
    
    total_users = await db.execute(select(func.count(User.id)))
    total_conversations = await db.execute(select(func.count(Conversation.id)))
    total_messages = await db.execute(select(func.count(Message.id)))
    
    today = datetime.now(timezone.utc).date()
    today_start = datetime.combine(today, datetime.min.time())
    
    today_conversations = await db.execute(
        select(func.count(Conversation.id))
        .where(Conversation.created_at >= today_start)
    )
    
    return {
        "total_users": total_users.scalar(),
        "total_conversations": total_conversations.scalar(),
        "total_messages": total_messages.scalar(),
        "today_conversations": today_conversations.scalar()
    }

@router.get("/activity")
async def get_activity(
    days: int = 7,
    db: AsyncSession = Depends(get_db)
):
    """Get activity data for the last N days"""
    
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=days)
    
    result = await db.execute(
        select(
            func.date(Message.created_at).label("date"),
            func.count(Message.id).label("count")
        )
        .where(Message.created_at >= start_date)
        .group_by(func.date(Message.created_at))
        .order_by(func.date(Message.created_at))
    )
    
    activity = result.all()
    
    return {
        "dates": [str(row.date) for row in activity],
        "message_counts": [row.count for row in activity]
    }


@router.get("/analytics")
async def get_dashboard_analytics(
    start_date: Optional[str] = Query(None, description="Start date in YYYY-MM-DD format"),
    end_date: Optional[str] = Query(None, description="End date in YYYY-MM-DD format"),
    db: AsyncSession = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user)
):
    """
    Fetch dashboard analytics data directly for dashboard UI
    Provides Shopify, GA4, and Google Workspace data
    """
    try:
        # Handle invalid date formats from frontend
        if start_date and ('[object' in start_date or start_date == 'undefined' or start_date == 'null'):
            logger.warning(f"[Dashboard Analytics] Invalid start_date received: {start_date}, using None")
            start_date = None

        if end_date and ('[object' in end_date or end_date == 'undefined' or end_date == 'null'):
            logger.warning(f"[Dashboard Analytics] Invalid end_date received: {end_date}, using None")
            end_date = None

        analytics_service = get_dashboard_analytics_service()

        dashboard_data = await analytics_service.get_dashboard_analytics(
            db=db,
            user_id=current_user.id,
            start_date=start_date,
            end_date=end_date
        )

        logger.info(f"[Dashboard Analytics] Successfully compiled dashboard data for user {current_user.id}")
        return dashboard_data

    except Exception as error:
        logger.error(f"[Dashboard Analytics] Error: {error}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Failed to fetch analytics data",
                "message": str(error),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )


@router.get("/summary")
async def get_dashboard_summary(
    date: Optional[str] = Query(None, description="Date in YYYY-MM-DD format"),
    db: AsyncSession = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user)
):
    """
    Provide a conversational summary of analytics data for agents
    """
    try:
        analytics_service = get_dashboard_analytics_service()

        summary = await analytics_service.get_dashboard_summary(
            db=db,
            user_id=current_user.id,
            date=date
        )
        
        logger.info("[Dashboard Summary] Successfully generated conversational summary")
        return summary
        
    except Exception as error:
        logger.error(f"[Dashboard Summary] Error: {error}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Failed to generate analytics summary",
                "message": str(error),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )


@router.get("/price-monitor")
async def get_price_monitor_stats(
    current_user: AuthUser = Depends(get_current_user)
):
    """
    Get price monitor statistics for the dashboard widget
    """
    try:
        # Get overview data (basic counts and recent activity)
        overview = await price_monitor_dashboard.get_overview()

        # Get detailed stats (violations, competitors, alerts)
        stats = await price_monitor_dashboard.get_stats()

        logger.info("[Price Monitor Dashboard] Successfully fetched price monitor stats")

        return {
            "overview": overview,
            "stats": stats.get('stats', {}),
            "competitor_status": stats.get('competitor_status', []),
            "recent_alerts": stats.get('recent_alerts', [])[:5],  # Limit to 5 for widget
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    except Exception as error:
        logger.error(f"[Price Monitor Dashboard] Error: {error}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Failed to fetch price monitor data",
                "message": str(error),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )