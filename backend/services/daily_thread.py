"""
Daily Thread Manager — get-or-create a single trading thread per user per day.

All recurring awakenings for a given day write to the same daily thread.
This gives users ONE place to check "what happened today" and lets each
awakening see previous awakenings' results in the thread history.
"""

import logging
import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Conversation, Message, User, utc_now

logger = logging.getLogger(__name__)

# IST offset from UTC (5 hours 30 minutes)
IST_OFFSET_HOURS = 5
IST_OFFSET_MINUTES = 30


def _get_ist_date() -> date:
    """Get current date in IST (trading day)."""
    from datetime import timedelta, timezone
    ist = timezone(timedelta(hours=IST_OFFSET_HOURS, minutes=IST_OFFSET_MINUTES))
    return datetime.now(ist).date()


def _format_thread_title(d: date) -> str:
    """Format daily thread title: 'Trading Day — Apr 11, 2026'"""
    return f"Trading Day — {d.strftime('%b %d, %Y')}"


async def get_or_create_daily_thread(
    session: AsyncSession,
    user_id: int,
    user_email: str,
    mandate: Optional[dict] = None,
) -> str:
    """Get today's daily trading thread, or create it if it doesn't exist.

    Args:
        session: Active DB session
        user_id: User ID (integer)
        user_email: User email (used as conversation.user_id, which is a string)
        mandate: Optional trading mandate dict to include in the first message

    Returns:
        thread_id (conversation.id)
    """
    today = _get_ist_date()
    today_str = today.isoformat()

    # Try to find existing daily thread
    result = await session.execute(
        select(Conversation).where(
            Conversation.user_id == user_email,
            Conversation.is_daily_thread == True,
            Conversation.daily_thread_date == today,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        return existing.id

    # Create new daily thread
    thread_id = f"daily_{user_id}_{today_str}_{uuid.uuid4().hex[:8]}"
    title = _format_thread_title(today)
    now = utc_now()

    conversation = Conversation(
        id=thread_id,
        user_id=user_email,
        title=title,
        created_at=now,
        updated_at=now,
        is_daily_thread=True,
        daily_thread_date=today,
        tags=["daily-thread", "auto"],
    )
    session.add(conversation)

    # Build first system message with date + mandate
    content_parts = [
        f"# {title}",
        f"**Date:** {today.strftime('%A, %B %d, %Y')}",
        "",
    ]

    if mandate:
        content_parts.extend([
            "## Standing Trading Mandate",
            f"- **Risk per trade:** {mandate.get('risk_per_trade', 'Not set')}",
            f"- **Daily loss cap:** {mandate.get('daily_loss_cap', 'Not set')}",
            f"- **Allowed instruments:** {mandate.get('allowed_instruments', 'Not set')}",
            f"- **Cutoff time:** {mandate.get('cutoff_time', 'Not set')}",
            f"- **Auto-squareoff:** {mandate.get('auto_squareoff_time', 'Not set')}",
            "",
            f"_Mandate approved: {mandate.get('approved_at', 'Unknown')}_",
            "",
            "All awakenings today operate within these bounds.",
            "",
        ])

        custom = mandate.get('custom_instructions')
        if custom:
            content_parts.extend([
                "## Custom Instructions",
                custom,
                "",
            ])

    content_parts.append(
        "---\n_This thread is auto-generated. "
        "All scheduled awakenings today will write to this thread._"
    )

    system_msg = Message(
        conversation_id=thread_id,
        message_id=f"daily_init_{uuid.uuid4().hex}",
        role="system",
        content="\n".join(content_parts),
        timestamp=now,
        extra_metadata={"daily_thread_init": True, "trading_date": today_str},
    )
    session.add(system_msg)
    await session.commit()

    logger.info("Created daily thread %s for user %d (%s)", thread_id, user_id, title)
    return thread_id


async def get_daily_thread_id(
    session: AsyncSession,
    user_id: int,
    target_date: Optional[date] = None,
    user_email: Optional[str] = None,
) -> Optional[str]:
    """Look up a daily thread by date.

    Args:
        session: Active DB session
        user_id: User ID (used to look up email if not provided)
        target_date: Date to look up (defaults to today IST)
        user_email: User email (conversation.user_id uses email)

    Returns:
        thread_id or None if not found
    """
    if user_email is None:
        user = await session.get(User, user_id)
        user_email = user.email if user else str(user_id)
    if target_date is None:
        target_date = _get_ist_date()

    result = await session.execute(
        select(Conversation.id).where(
            Conversation.user_id == user_email,
            Conversation.is_daily_thread == True,
            Conversation.daily_thread_date == target_date,
        )
    )
    row = result.scalar_one_or_none()
    return row
