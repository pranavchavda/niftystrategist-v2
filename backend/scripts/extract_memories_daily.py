#!/usr/bin/env python3
"""
Daily Memory Extraction Script

Runs memory extraction on all conversations from the previous day.
Designed to be run via cron, e.g.:
    0 2 * * * cd /opt/niftystrategist/backend && venv/bin/python scripts/extract_memories_daily.py

Usage:
    python scripts/extract_memories_daily.py                    # Process yesterday's conversations
    python scripts/extract_memories_daily.py --days-back 7      # Process last 7 days
    python scripts/extract_memories_daily.py --date 2026-01-20  # Process specific date
    python scripts/extract_memories_daily.py --dry-run           # Preview without extracting
    python scripts/extract_memories_daily.py --force             # Re-extract even if memories exist
    python scripts/extract_memories_daily.py --user user@email   # Process specific user only
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Optional

# Add backend to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import select, and_, text
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Conversation, Message, Memory
from database.operations import ConversationOps, MessageOps, MemoryOps
from database.session import get_db_context
from agents.memory_extractor import get_memory_extractor
from memory.embedding_service import get_embedding_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("/tmp/memory_extraction_cron.log"),
    ],
)
logger = logging.getLogger(__name__)


class DailyMemoryExtractor:
    """Handles daily batch memory extraction."""

    def __init__(self, dry_run: bool = False, force: bool = False):
        self.dry_run = dry_run
        self.force = force
        self.memory_extractor = get_memory_extractor()
        self.embedding_service = get_embedding_service()
        self.stats = {
            "conversations_processed": 0,
            "conversations_skipped": 0,
            "conversations_already_extracted": 0,
            "memories_extracted": 0,
            "memories_rejected": 0,
            "memories_updated": 0,
            "memories_consolidated": 0,
            "errors": 0,
        }

    async def get_conversations_in_range(
        self,
        session: AsyncSession,
        start_date: datetime,
        end_date: datetime,
        user_email: Optional[str] = None,
    ) -> list[tuple[Conversation, str]]:
        """Get conversations updated within the date range."""
        query = select(Conversation).where(
            and_(
                Conversation.updated_at >= start_date,
                Conversation.updated_at < end_date,
                Conversation.is_archived == False,  # noqa: E712
            )
        )
        if user_email:
            query = query.where(Conversation.user_id == user_email)
        query = query.order_by(Conversation.updated_at)

        result = await session.execute(query)
        conversations = result.scalars().all()
        return [(conv, conv.user_id) for conv in conversations]

    async def get_conversations_with_memories(
        self, session: AsyncSession, conversation_ids: list[str]
    ) -> set[str]:
        """Get conversation IDs that already have memories extracted."""
        if not conversation_ids:
            return set()
        query = (
            select(Memory.conversation_id)
            .where(Memory.conversation_id.in_(conversation_ids))
            .distinct()
        )
        result = await session.execute(query)
        return {row[0] for row in result.fetchall() if row[0]}

    async def get_recent_conversation_dates(
        self, session: AsyncSession, limit: int = 5
    ) -> list[tuple[str, int]]:
        """Get recent dates with conversations (for debugging empty runs)."""
        result = await session.execute(
            text(
                "SELECT DATE(updated_at) AS d, COUNT(*) AS cnt "
                "FROM conversations GROUP BY DATE(updated_at) "
                "ORDER BY d DESC LIMIT :limit"
            ),
            {"limit": limit},
        )
        return [(str(row[0]), row[1]) for row in result.fetchall()]

    async def extract_for_conversation(
        self,
        session: AsyncSession,
        conversation: Conversation,
        user_email: str,
    ) -> dict:
        """Extract memories from a single conversation."""
        result = {
            "conversation_id": conversation.id,
            "user_email": user_email,
            "title": conversation.title,
            "extracted": 0,
            "rejected": 0,
            "updated": 0,
            "consolidated": 0,
            "error": None,
        }

        try:
            messages = await MessageOps.get_messages(session, conversation.id, limit=None)

            if not messages or len(messages) < 2:
                logger.info(
                    "  Skipping %s: insufficient messages (%d)",
                    conversation.id,
                    len(messages) if messages else 0,
                )
                result["error"] = "insufficient_messages"
                return result

            conversation_history = [
                {"role": msg.role, "content": msg.content} for msg in messages
            ]

            if self.dry_run:
                logger.info(
                    "  [DRY RUN] Would extract from %s (%d messages)",
                    conversation.id,
                    len(messages),
                )
                return result

            # Extract via LLM
            extraction = await self.memory_extractor.extract_memories(
                conversation_history=conversation_history,
                conversation_id=conversation.id,
            )

            # Process each extracted memory through quality judge
            for mem in extraction.memories:
                if getattr(mem, "is_ephemeral", False):
                    continue

                embedding_result = await self.embedding_service.get_embedding(mem.fact)

                memory, action, reasoning = await MemoryOps.add_memory_with_judge(
                    session=session,
                    conversation_id=conversation.id,
                    user_id=user_email,
                    fact=mem.fact,
                    category=mem.category,
                    confidence=mem.confidence,
                    embedding=embedding_result.embedding,
                    user_context="NiftyStrategist trading assistant context",
                )

                if action == "REJECT":
                    result["rejected"] += 1
                elif action == "UPDATE":
                    result["updated"] += 1
                    result["extracted"] += 1
                elif action == "CONSOLIDATE":
                    result["consolidated"] += 1
                    result["extracted"] += 1
                else:  # INSERT
                    result["extracted"] += 1

            # Update conversation title if we got a good summary
            if extraction.summary and extraction.summary != "Error extracting memories":
                await ConversationOps.update_conversation_title(
                    session,
                    conversation.id,
                    user_email,
                    extraction.summary,
                    update_timestamp=False,
                )

            logger.info(
                "  Extracted from %s: %d stored, %d rejected, %d updated, %d consolidated",
                conversation.id,
                result["extracted"],
                result["rejected"],
                result["updated"],
                result["consolidated"],
            )

        except Exception as e:
            logger.error("  Error extracting from %s: %s", conversation.id, e)
            result["error"] = str(e)

        return result

    async def run(
        self,
        start_date: datetime,
        end_date: datetime,
        user_email: Optional[str] = None,
    ):
        """Run memory extraction for conversations in the date range."""
        logger.info("=" * 60)
        logger.info("Daily Memory Extraction Started")
        logger.info("Date range: %s to %s", start_date.date(), end_date.date())
        if user_email:
            logger.info("Filtering to user: %s", user_email)
        if self.dry_run:
            logger.info("*** DRY RUN MODE ***")
        if self.force:
            logger.info("*** FORCE MODE ***")
        logger.info("=" * 60)

        async with get_db_context() as session:
            conversations = await self.get_conversations_in_range(
                session, start_date, end_date, user_email
            )
            logger.info("Found %d conversations to process", len(conversations))

            if not conversations:
                recent = await self.get_recent_conversation_dates(session)
                if recent:
                    logger.info("Recent dates with conversations:")
                    for date_str, count in recent:
                        logger.info("  %s: %d conversations", date_str, count)
                return

            users_seen = {email for _, email in conversations}
            logger.info("Across %d users: %s", len(users_seen), ", ".join(users_seen))

            # Skip conversations that already have memories (unless --force)
            already_extracted: set[str] = set()
            if not self.force:
                conv_ids = [conv.id for conv, _ in conversations]
                already_extracted = await self.get_conversations_with_memories(
                    session, conv_ids
                )
                if already_extracted:
                    logger.info(
                        "Skipping %d conversations that already have memories",
                        len(already_extracted),
                    )

            for i, (conversation, email) in enumerate(conversations, 1):
                if conversation.id in already_extracted:
                    logger.info(
                        "[%d/%d] Skipping %s (already has memories)",
                        i,
                        len(conversations),
                        conversation.id,
                    )
                    self.stats["conversations_already_extracted"] += 1
                    continue

                logger.info(
                    "[%d/%d] Processing %s (user: %s)",
                    i,
                    len(conversations),
                    conversation.id,
                    email,
                )

                res = await self.extract_for_conversation(session, conversation, email)

                if res["error"]:
                    if res["error"] == "insufficient_messages":
                        self.stats["conversations_skipped"] += 1
                    else:
                        self.stats["errors"] += 1
                else:
                    self.stats["conversations_processed"] += 1
                    self.stats["memories_extracted"] += res["extracted"]
                    self.stats["memories_rejected"] += res["rejected"]
                    self.stats["memories_updated"] += res["updated"]
                    self.stats["memories_consolidated"] += res["consolidated"]

                # Rate limit
                if not self.dry_run and i < len(conversations):
                    await asyncio.sleep(0.5)

        logger.info("=" * 60)
        logger.info("Extraction Complete")
        logger.info("=" * 60)
        for key, val in self.stats.items():
            logger.info("  %-35s %d", key, val)
        logger.info("=" * 60)


def parse_args():
    parser = argparse.ArgumentParser(description="Daily memory extraction for NiftyStrategist")
    parser.add_argument("--days-back", type=int, default=1, help="Days to look back (default: 1)")
    parser.add_argument("--date", type=str, help="Specific date YYYY-MM-DD (overrides --days-back)")
    parser.add_argument("--dry-run", action="store_true", help="Preview only")
    parser.add_argument("--force", action="store_true", help="Re-extract even if memories exist")
    parser.add_argument("--user", type=str, help="Process only this user email")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")
    return parser.parse_args()


def get_date_range(args) -> tuple[datetime, datetime]:
    if args.date:
        target = datetime.strptime(args.date, "%Y-%m-%d")
        start = target.replace(hour=0, minute=0, second=0, microsecond=0)
        return start, start + timedelta(days=1)

    today = datetime.now(timezone.utc).replace(tzinfo=None)
    today_midnight = today.replace(hour=0, minute=0, second=0, microsecond=0)
    return today_midnight - timedelta(days=args.days_back), today_midnight


async def main():
    args = parse_args()
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if not os.getenv("DATABASE_URL"):
        logger.error("DATABASE_URL not set")
        sys.exit(1)
    if not os.getenv("OPENROUTER_API_KEY"):
        logger.error("OPENROUTER_API_KEY not set (needed for memory extraction)")
        sys.exit(1)
    if not os.getenv("OPENAI_API_KEY"):
        logger.error("OPENAI_API_KEY not set (needed for embeddings)")
        sys.exit(1)

    start_date, end_date = get_date_range(args)
    extractor = DailyMemoryExtractor(dry_run=args.dry_run, force=args.force)
    await extractor.run(start_date, end_date, user_email=args.user)


if __name__ == "__main__":
    asyncio.run(main())
