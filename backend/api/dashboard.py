"""
Dashboard API for Nifty Strategist - Trading focused analytics
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from database.session import get_db
from database.models import Conversation, Message, User
from auth import get_current_user, User as AuthUser
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


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


@router.get("/trading-summary")
async def get_trading_summary(
    current_user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get trading summary for the current user.
    TODO: Implement when trades table is populated
    """
    return {
        "total_trades": 0,
        "winning_trades": 0,
        "losing_trades": 0,
        "total_pnl": 0.0,
        "win_rate": 0.0,
        "paper_trading": True,
        "message": "Trading summary will be available after executing trades"
    }
