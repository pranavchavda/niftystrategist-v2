"""
Daily Thread Manager — get-or-create a single trading thread per user per day.

All recurring awakenings for a given day write to the same daily thread.
This gives users ONE place to check "what happened today" and lets each
awakening see previous awakenings' results in the thread history.
"""

import asyncio
import logging
import sys
import uuid
from datetime import date, datetime
from pathlib import Path
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


async def _fetch_mood_briefing() -> Optional[str]:
    """Run financial_news_tracker.py to fetch a 24h market-mood briefing.

    Returns the captured stdout (markdown/text) or None on any failure.
    Bounded to 60s to prevent a runaway Perplexity call from blocking
    the scheduler. Failures are logged but never propagate.
    """
    backend_dir = Path(__file__).resolve().parent.parent
    cli_path = backend_dir / "cli-tools" / "financial_news_tracker.py"
    if not cli_path.exists():
        logger.warning("mood briefing: %s not found", cli_path)
        return None

    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, str(cli_path), "-t", "24h", "Nifty 500",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(backend_dir),
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
        except asyncio.TimeoutError:
            logger.warning("mood briefing timed out after 60s")
            proc.kill()
            await proc.wait()
            return None

        if proc.returncode != 0:
            logger.warning("mood briefing exit %d: %s", proc.returncode, stderr.decode()[:500])
            return None

        text = stdout.decode().strip()
        return text or None
    except Exception as e:
        logger.warning("mood briefing subprocess error: %s", e)
        return None


async def get_or_create_daily_thread(
    session: AsyncSession,
    user_id: int,
    user_email: str,
    mandate: Optional[dict] = None,
    include_mood_briefing: bool = False,
) -> str:
    """Get today's daily trading thread, or create it if it doesn't exist.

    Args:
        session: Active DB session
        user_id: User ID (integer)
        user_email: User email (used as conversation.user_id, which is a string)
        mandate: Optional trading mandate dict to include in the first message
        include_mood_briefing: If True and the thread is being created now,
            fetch a Perplexity-backed 24h market briefing and append it as
            a second system message. Only runs on fresh creation, never on
            get-existing. Failures are logged and ignored (non-fatal).

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

    if include_mood_briefing:
        briefing = await _fetch_mood_briefing()
        if briefing:
            mood_now = utc_now()
            mood_msg = Message(
                conversation_id=thread_id,
                message_id=f"daily_mood_{uuid.uuid4().hex}",
                role="system",
                content=(
                    "## Market Mood Briefing — last 24h\n\n"
                    "_Factual context from Perplexity web search. "
                    "No trade recommendations — interpret in light of your mandate._\n\n"
                    f"{briefing}"
                ),
                timestamp=mood_now,
                extra_metadata={"daily_thread_mood": True, "trading_date": today_str},
            )
            session.add(mood_msg)
            await session.commit()
            logger.info("Added mood briefing to daily thread %s (%d chars)", thread_id, len(briefing))

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
