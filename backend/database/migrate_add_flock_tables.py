#!/usr/bin/env python3
"""Migration script to add Flock integration tables.

This migration adds tables for Flock integration:
- flock_channels: Monitored channels/groups/DMs
- flock_messages: Raw messages for audit trail
- flock_actionables: Extracted actionable items
- flock_digests: Daily digest summaries
- flock_webhooks: Webhook configurations

Usage:
    python3 migrate_add_flock_tables.py
    python3 migrate_add_flock_tables.py rollback  # to rollback
"""

import asyncio
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from database.session import AsyncSessionLocal
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def migrate():
    """Run the migration."""
    async with AsyncSessionLocal() as session:
        try:
            logger.info("Starting migration: add Flock integration tables")

            # Check if tables already exist
            check_query = text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'flock_channels'
                );
            """)

            result = await session.execute(check_query)
            table_exists = result.scalar()

            if table_exists:
                logger.info("Flock tables already exist. Skipping migration.")
                return

            # Create flock_channels table
            logger.info("Creating flock_channels table...")
            await session.execute(text("""
                CREATE TABLE flock_channels (
                    id SERIAL PRIMARY KEY,
                    flock_id VARCHAR(255) UNIQUE NOT NULL,
                    name VARCHAR(255) NOT NULL,
                    type VARCHAR(50) NOT NULL CHECK (type IN ('group', 'channel', 'dm')),
                    is_monitored BOOLEAN DEFAULT TRUE,
                    include_in_digest BOOLEAN DEFAULT TRUE,
                    description TEXT,
                    member_count INTEGER,
                    last_synced_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """))

            await session.execute(text("""
                CREATE INDEX idx_flock_channel_monitored
                ON flock_channels(is_monitored, include_in_digest);
            """))

            await session.execute(text("""
                CREATE INDEX idx_flock_channel_flock_id
                ON flock_channels(flock_id);
            """))

            logger.info("✓ Created flock_channels table")

            # Create flock_messages table
            logger.info("Creating flock_messages table...")
            await session.execute(text("""
                CREATE TABLE flock_messages (
                    id SERIAL PRIMARY KEY,
                    flock_message_id VARCHAR(255) UNIQUE NOT NULL,
                    channel_id INTEGER NOT NULL REFERENCES flock_channels(id) ON DELETE CASCADE,
                    text TEXT,
                    sender_id VARCHAR(255) NOT NULL,
                    sender_name VARCHAR(255),
                    sent_at TIMESTAMP NOT NULL,
                    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    attachments JSONB,
                    mentions JSONB,
                    is_edited BOOLEAN DEFAULT FALSE,
                    is_deleted BOOLEAN DEFAULT FALSE,
                    is_analyzed BOOLEAN DEFAULT FALSE,
                    analyzed_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """))

            await session.execute(text("""
                CREATE INDEX idx_flock_message_sent_at ON flock_messages(sent_at);
            """))

            await session.execute(text("""
                CREATE INDEX idx_flock_message_sender ON flock_messages(sender_id, sent_at);
            """))

            await session.execute(text("""
                CREATE INDEX idx_flock_message_analyzed ON flock_messages(is_analyzed);
            """))

            await session.execute(text("""
                CREATE INDEX idx_flock_message_flock_id ON flock_messages(flock_message_id);
            """))

            logger.info("✓ Created flock_messages table")

            # Create flock_digests table
            logger.info("Creating flock_digests table...")
            await session.execute(text("""
                CREATE TABLE flock_digests (
                    id SERIAL PRIMARY KEY,
                    digest_date TIMESTAMP UNIQUE NOT NULL,
                    period_start TIMESTAMP NOT NULL,
                    period_end TIMESTAMP NOT NULL,
                    total_messages_analyzed INTEGER DEFAULT 0,
                    total_actionables_extracted INTEGER DEFAULT 0,
                    channels_monitored INTEGER DEFAULT 0,
                    tasks_count INTEGER DEFAULT 0,
                    decisions_count INTEGER DEFAULT 0,
                    questions_count INTEGER DEFAULT 0,
                    reminders_count INTEGER DEFAULT 0,
                    deadlines_count INTEGER DEFAULT 0,
                    summary TEXT,
                    highlights JSONB,
                    email_sent BOOLEAN DEFAULT FALSE,
                    email_sent_at TIMESTAMP,
                    email_recipients JSONB,
                    is_generated BOOLEAN DEFAULT FALSE,
                    generation_started_at TIMESTAMP,
                    generation_completed_at TIMESTAMP,
                    generation_error TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """))

            await session.execute(text("""
                CREATE INDEX idx_flock_digest_date ON flock_digests(digest_date);
            """))

            await session.execute(text("""
                CREATE INDEX idx_flock_digest_generated ON flock_digests(is_generated);
            """))

            logger.info("✓ Created flock_digests table")

            # Create flock_actionables table
            logger.info("Creating flock_actionables table...")
            await session.execute(text("""
                CREATE TABLE flock_actionables (
                    id SERIAL PRIMARY KEY,
                    message_id INTEGER NOT NULL REFERENCES flock_messages(id) ON DELETE CASCADE,
                    digest_id INTEGER REFERENCES flock_digests(id) ON DELETE SET NULL,
                    type VARCHAR(50) NOT NULL CHECK (type IN ('task', 'decision', 'question', 'reminder', 'deadline', 'followup', 'info')),
                    priority VARCHAR(20) DEFAULT 'medium' CHECK (priority IN ('low', 'medium', 'high', 'urgent')),
                    status VARCHAR(30) DEFAULT 'pending' CHECK (status IN ('pending', 'added_to_tasks', 'completed', 'dismissed')),
                    title VARCHAR(500) NOT NULL,
                    description TEXT,
                    context TEXT,
                    assigned_to VARCHAR(255),
                    assigned_to_name VARCHAR(255),
                    due_date TIMESTAMP,
                    confidence_score FLOAT,
                    extraction_model VARCHAR(100),
                    google_task_id VARCHAR(255),
                    google_task_created_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """))

            await session.execute(text("""
                CREATE INDEX idx_flock_actionable_status ON flock_actionables(status, priority);
            """))

            await session.execute(text("""
                CREATE INDEX idx_flock_actionable_assigned ON flock_actionables(assigned_to, status);
            """))

            await session.execute(text("""
                CREATE INDEX idx_flock_actionable_created ON flock_actionables(created_at);
            """))

            logger.info("✓ Created flock_actionables table")

            # Create flock_webhooks table
            logger.info("Creating flock_webhooks table...")
            await session.execute(text("""
                CREATE TABLE flock_webhooks (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    webhook_type VARCHAR(50) NOT NULL CHECK (webhook_type IN ('incoming', 'outgoing')),
                    webhook_url TEXT,
                    target_channel VARCHAR(255),
                    webhook_token VARCHAR(255),
                    source_channel VARCHAR(255),
                    is_active BOOLEAN DEFAULT TRUE,
                    use_case VARCHAR(100),
                    description TEXT,
                    created_by VARCHAR(255),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """))

            await session.execute(text("""
                CREATE INDEX idx_flock_webhook_active ON flock_webhooks(is_active, use_case);
            """))

            logger.info("✓ Created flock_webhooks table")

            await session.commit()
            logger.info("✓ Migration completed successfully - All Flock tables created")

        except Exception as e:
            await session.rollback()
            logger.error(f"✗ Migration failed: {e}")
            raise


async def rollback():
    """Rollback the migration."""
    async with AsyncSessionLocal() as session:
        try:
            logger.info("Rolling back migration: drop Flock tables")

            # Drop tables in reverse order (respecting foreign keys)
            await session.execute(text("DROP TABLE IF EXISTS flock_actionables CASCADE;"))
            await session.execute(text("DROP TABLE IF EXISTS flock_messages CASCADE;"))
            await session.execute(text("DROP TABLE IF EXISTS flock_digests CASCADE;"))
            await session.execute(text("DROP TABLE IF EXISTS flock_webhooks CASCADE;"))
            await session.execute(text("DROP TABLE IF EXISTS flock_channels CASCADE;"))

            await session.commit()
            logger.info("✓ Rollback completed successfully")

        except Exception as e:
            await session.rollback()
            logger.error(f"✗ Rollback failed: {e}")
            raise


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "rollback":
        asyncio.run(rollback())
    else:
        asyncio.run(migrate())
