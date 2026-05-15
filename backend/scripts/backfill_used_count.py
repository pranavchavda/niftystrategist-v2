#!/usr/bin/env python3
"""
Backfill used_count + last_used_at by re-running the extractor's "which
existing memories were used?" pass over recent conversations.

Run AFTER migration `038_add_memory_used_count.sql` has been applied and
BEFORE any importance/cleanup logic starts weighting used_count, otherwise
existing good memories will have used_count=0 and risk premature pruning.

Usage:
    venv/bin/python scripts/backfill_used_count.py --days-back 30
    venv/bin/python scripts/backfill_used_count.py --days-back 60 --user pranav@idrinkcoffee.com
    venv/bin/python scripts/backfill_used_count.py --days-back 30 --dry-run
"""

import os
import sys
import argparse
import asyncio
import logging
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import select, and_, text
from database.models import Conversation
from database.session import AsyncSessionLocal
from database.operations import MessageOps
from agents.memory_extractor import get_memory_extractor, reset_memory_extractor

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)


async def backfill(days_back: int, user_email: str | None, dry_run: bool, model_name: str | None):
    # Model override is plumbed via the env var the extractor reads, then the
    # singleton is reset so the new model takes effect.
    if model_name:
        os.environ["MEMORY_EXTRACTION_MODEL"] = model_name
        reset_memory_extractor()
    extractor = get_memory_extractor()

    end = datetime.now(timezone.utc).replace(tzinfo=None)
    start = end - timedelta(days=days_back)

    stats = {"convs_seen": 0, "convs_processed": 0, "memories_bumped": 0, "errors": 0}

    async with AsyncSessionLocal() as session:
        q = select(Conversation).where(
            and_(
                Conversation.updated_at >= start,
                Conversation.updated_at < end,
                Conversation.is_archived == False,  # noqa: E712
            )
        )
        if user_email:
            q = q.where(Conversation.user_id == user_email)
        q = q.order_by(Conversation.updated_at.asc())

        convs = (await session.execute(q)).scalars().all()
        logger.info(f"Found {len(convs)} conversations in [{start.date()}, {end.date()})")

        for conv in convs:
            stats["convs_seen"] += 1
            uid = conv.user_id
            if not uid:
                continue

            messages = await MessageOps.get_messages(session, conv.id, limit=None)
            if not messages or len(messages) < 2:
                continue

            history = [{"role": m.role, "content": m.content} for m in messages]

            # Only consider memories that existed at the time of the conversation.
            existing_rows = (await session.execute(
                text("""
                    SELECT id, fact, category
                    FROM memories
                    WHERE user_id = :uid
                      AND created_at <= :ts
                    ORDER BY COALESCE(last_used_at, last_accessed) DESC NULLS LAST,
                             access_count DESC
                    LIMIT 60
                """),
                {"uid": uid, "ts": conv.updated_at},
            )).fetchall()

            if not existing_rows:
                continue

            existing = [{"id": r[0], "fact": r[1], "category": r[2]} for r in existing_rows]
            try:
                result = await extractor.extract_memories(
                    conversation_history=history,
                    conversation_id=conv.id,
                    existing_memories=existing,
                )
            except Exception as e:
                logger.warning(f"Extraction failed for {conv.id}: {e}")
                stats["errors"] += 1
                continue

            stats["convs_processed"] += 1
            valid = {m["id"] for m in existing}
            used_ids = [mid for mid in result.used_memory_ids if mid in valid]
            if not used_ids:
                continue

            logger.info(f"  {conv.id} -> bumping {len(used_ids)} memories")
            if dry_run:
                continue

            await session.execute(
                text("""
                    UPDATE memories
                    SET used_count = used_count + 1,
                        last_used_at = GREATEST(COALESCE(last_used_at, :ts), :ts)
                    WHERE id = ANY(:ids)
                """),
                {"ids": used_ids, "ts": conv.updated_at},
            )
            await session.commit()
            stats["memories_bumped"] += len(used_ids)

    logger.info(f"Done: {stats}")


def main():
    p = argparse.ArgumentParser(description="Backfill memory used_count over recent conversations")
    p.add_argument("--days-back", type=int, default=30)
    p.add_argument("--user", default=None)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--model", default=None, help="OpenRouter model id override (e.g. openai/gpt-5-mini)")
    args = p.parse_args()
    asyncio.run(backfill(args.days_back, args.user, args.dry_run, args.model))


if __name__ == "__main__":
    main()
