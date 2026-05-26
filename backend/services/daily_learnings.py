"""
Daily Learnings — distill carry-over learnings from the daily trading thread.

Every daily thread ends with a reflection on how the day went and what was
learned — and crucially, the user often discusses those learnings with the
orchestrator post-close and reaches *different* conclusions than the agent's
own auto-reflection. This module runs a dedicated pre-market LLM pass over the
WHOLE daily thread (including that discussion), distils it into a headline +
markdown bullets, and stores it in the `daily_learnings` table.

The next morning, `daily_thread.get_or_create_daily_thread()` injects the most
recent row verbatim, plus the headlines of the prior 2 trading days, so the
agent starts the day with yesterday's hard-won conclusions in front of it.

This COMPLEMENTS the semantic memory pipeline (memories table /
extract_memories_daily.py): that is relevance-searched and injected by match;
this is deterministic and always present.

Scheduling: a job in services/scheduler.py fires this at 02:45 UTC (08:15 IST)
on weekdays — after any evening discussion, before the 09:20 Morning Scan
creates the new thread.
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional

from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Conversation, DailyLearning, Message, User, utc_now
from database.session import get_db_context

logger = logging.getLogger(__name__)

# Cheap, reliable JSON model — same default family as the memory extractor.
# Override with LEARNINGS_SUMMARY_MODEL.
DEFAULT_LEARNINGS_MODEL = "deepseek/deepseek-v4-flash"

# How far back to look for the most recent un-summarized daily thread, so a
# Friday → Monday weekend gap (or a missed run / holiday) still gets captured.
LOOKBACK_DAYS = 7

IST_OFFSET = timedelta(hours=5, minutes=30)


def _ist_today() -> date:
    return (datetime.now(timezone.utc) + IST_OFFSET).date()


def _is_crashed(msg: Message) -> bool:
    """Crash/partial-summary turns reflect half-finished state, not durable
    learnings — exclude them (tagged extra_metadata.crashed by awakening_scheduler).
    """
    meta = getattr(msg, "extra_metadata", None) or {}
    return bool(isinstance(meta, dict) and meta.get("crashed"))


def _extract_json(text: str) -> str:
    if not text:
        return text
    fence = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    return fence.group(1).strip() if fence else text.strip()


SYSTEM_PROMPT = (
    "You are a trading journal analyst. You are given the full transcript of a "
    "trader's daily trading thread — scheduled awakenings, the agent's own "
    "end-of-day reflection, AND any discussion the trader had with the assistant "
    "afterward. Your job is to distil the LEARNINGS that should carry into the "
    "next trading day.\n\n"
    "Rules:\n"
    "- When the trader's discussion reaches a different conclusion than the "
    "agent's auto-reflection, the TRADER's conclusion wins. Capture it.\n"
    "- Focus on durable, actionable lessons: what worked, what didn't, sizing/"
    "timing/instrument mistakes, behavioural patterns, things to do differently.\n"
    "- Ignore transient market chatter, raw quotes, and one-off mechanics.\n"
    "- If there is nothing meaningful to learn, return an empty bullets list.\n\n"
    "Respond with JSON only:\n"
    "{\n"
    '  "headline": "one concise sentence (<=140 chars) summarizing the day\'s key lesson",\n'
    '  "bullets": ["actionable learning", "..."]\n'
    "}"
)


class _Summarizer:
    def __init__(self) -> None:
        self.model = os.environ.get("LEARNINGS_SUMMARY_MODEL", DEFAULT_LEARNINGS_MODEL)
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise RuntimeError("OPENROUTER_API_KEY not set — cannot summarize learnings")
        self.client = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)

    async def summarize(self, transcript: str) -> Optional[dict]:
        """Return {'headline': str, 'learnings_text': str} or None if nothing learned."""
        completion = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": transcript},
            ],
            temperature=0.2,
            max_tokens=900,
        )
        raw = completion.choices[0].message.content or ""
        try:
            data = json.loads(_extract_json(raw))
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning("learnings summary: bad JSON from model: %s | raw=%.300s", e, raw)
            return None

        bullets = [b.strip() for b in (data.get("bullets") or []) if b and b.strip()]
        if not bullets:
            return None
        headline = (data.get("headline") or bullets[0]).strip()
        learnings_text = "\n".join(f"- {b}" for b in bullets)
        return {"headline": headline[:300], "learnings_text": learnings_text}


def _build_transcript(messages: List[Message]) -> str:
    """Flatten thread messages into a role-tagged transcript for the LLM."""
    parts: List[str] = []
    for m in messages:
        if _is_crashed(m):
            continue
        content = (m.content or "").strip()
        if not content:
            continue
        role = {"user": "TRADER", "assistant": "ASSISTANT", "system": "SYSTEM"}.get(m.role, m.role.upper())
        parts.append(f"[{role}]\n{content}")
    return "\n\n".join(parts)


async def summarize_thread(
    session: AsyncSession,
    user_id: int,
    user_email: str,
    trading_date: date,
    thread_id: str,
    summarizer: Optional[_Summarizer] = None,
    force: bool = False,
) -> dict:
    """Summarize one daily thread and upsert into daily_learnings.

    Idempotent: skips if a row already exists for (user_id, trading_date)
    unless force=True. Returns a small result dict for logging.
    """
    if not force:
        existing = await session.execute(
            select(DailyLearning.id).where(
                DailyLearning.user_id == user_id,
                DailyLearning.trading_date == trading_date,
            )
        )
        if existing.scalar_one_or_none() is not None:
            return {"thread_id": thread_id, "skipped": "already_summarized"}

    msgs = await session.execute(
        select(Message).where(Message.conversation_id == thread_id).order_by(Message.timestamp)
    )
    messages = list(msgs.scalars().all())
    # Need at least one substantive turn beyond the auto-init system message.
    substantive = [m for m in messages if m.role in ("user", "assistant") and (m.content or "").strip()]
    if len(substantive) < 1:
        return {"thread_id": thread_id, "skipped": "no_content"}

    transcript = _build_transcript(messages)
    if not transcript:
        return {"thread_id": thread_id, "skipped": "empty_transcript"}

    summarizer = summarizer or _Summarizer()
    summary = await summarizer.summarize(transcript)
    if summary is None:
        return {"thread_id": thread_id, "skipped": "nothing_learned"}

    now = utc_now()
    stmt = pg_insert(DailyLearning.__table__).values(
        user_id=user_id,
        trading_date=trading_date,
        headline=summary["headline"],
        learnings_text=summary["learnings_text"],
        source_thread_id=thread_id,
        created_at=now,
        updated_at=now,
    ).on_conflict_do_update(
        index_elements=["user_id", "trading_date"],
        set_={
            "headline": summary["headline"],
            "learnings_text": summary["learnings_text"],
            "source_thread_id": thread_id,
            "updated_at": now,
        },
    )
    await session.execute(stmt)
    await session.commit()
    logger.info(
        "daily learnings: stored for user %d (%s) date=%s thread=%s headline=%.80s",
        user_id, user_email, trading_date, thread_id, summary["headline"],
    )
    return {"thread_id": thread_id, "stored": True, "headline": summary["headline"]}


async def get_recent_learnings(
    session: AsyncSession,
    user_id: int,
    before_date: date,
    limit: int = 3,
) -> List[DailyLearning]:
    """Most recent learnings strictly before `before_date`, newest first."""
    result = await session.execute(
        select(DailyLearning)
        .where(
            DailyLearning.user_id == user_id,
            DailyLearning.trading_date < before_date,
        )
        .order_by(DailyLearning.trading_date.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


def render_learnings_block(learnings: List[DailyLearning]) -> Optional[str]:
    """Render carry-over learnings for injection into a new daily thread.

    Most recent day's learnings in full; prior days as a one-line headline trail.
    Returns None if there's nothing to show.
    """
    if not learnings:
        return None

    latest = learnings[0]
    lines = [
        "## Yesterday's Learnings",
        f"_Carried forward from {latest.trading_date.strftime('%A, %b %d')} "
        "(your end-of-day reflection + discussion). Let these shape today's decisions._",
        "",
        latest.learnings_text,
    ]

    trail = [l for l in learnings[1:] if l.headline]
    if trail:
        lines.extend(["", "**Recent days:**"])
        lines.extend(
            f"- _{l.trading_date.strftime('%a %b %d')}:_ {l.headline}" for l in trail
        )

    return "\n".join(lines)


async def summarize_all_users(force: bool = False) -> dict:
    """Cron entry: summarize the most recent un-summarized daily thread per user.

    Scans daily threads with daily_thread_date in [today_ist - LOOKBACK_DAYS,
    today_ist) and summarizes any that lack a daily_learnings row. This backfills
    weekend/holiday gaps and missed runs. Each user/thread is independent — one
    failure never blocks the rest.
    """
    today = _ist_today()
    window_start = today - timedelta(days=LOOKBACK_DAYS)
    stats = {"threads_seen": 0, "stored": 0, "skipped": 0, "errors": 0}

    try:
        summarizer = _Summarizer()
    except RuntimeError as e:
        logger.error("daily learnings cron: %s", e)
        return {"error": str(e)}

    async with get_db_context() as session:
        # Daily threads in the lookback window (conversation.user_id is email).
        result = await session.execute(
            select(Conversation)
            .where(
                Conversation.is_daily_thread == True,  # noqa: E712
                Conversation.daily_thread_date >= window_start,
                Conversation.daily_thread_date < today,
            )
            .order_by(Conversation.daily_thread_date.desc())
        )
        threads = list(result.scalars().all())
        stats["threads_seen"] = len(threads)

        # Resolve emails → integer user ids in one pass.
        emails = {t.user_id for t in threads if t.user_id}
        users = {}
        if emails:
            urows = await session.execute(select(User.id, User.email).where(User.email.in_(emails)))
            users = {email: uid for uid, email in urows.all()}

        for t in threads:
            uid = users.get(t.user_id)
            if uid is None:
                logger.warning("daily learnings: no user id for email %s (thread %s)", t.user_id, t.id)
                stats["errors"] += 1
                continue
            td = t.daily_thread_date.date() if isinstance(t.daily_thread_date, datetime) else t.daily_thread_date
            try:
                res = await summarize_thread(
                    session, uid, t.user_id, td, t.id, summarizer=summarizer, force=force,
                )
                if res.get("stored"):
                    stats["stored"] += 1
                else:
                    stats["skipped"] += 1
            except Exception as e:
                logger.exception("daily learnings: failed for thread %s: %s", t.id, e)
                await session.rollback()
                stats["errors"] += 1

    logger.info("daily learnings cron complete: %s", stats)
    return stats


if __name__ == "__main__":
    # Manual run / backfill:
    #   python -m services.daily_learnings            # summarize last 7 days' un-summarized threads
    #   python -m services.daily_learnings --force    # re-summarize even if rows exist
    import argparse
    import asyncio

    from dotenv import load_dotenv

    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    parser = argparse.ArgumentParser(description="Distil daily trading thread learnings")
    parser.add_argument("--force", action="store_true", help="Re-summarize even if a row exists")
    args = parser.parse_args()

    result = asyncio.run(summarize_all_users(force=args.force))
    print(json.dumps(result, indent=2, default=str))
