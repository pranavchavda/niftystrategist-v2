#!/usr/bin/env python3
"""
Migration: Add reasoning column to messages table

This migration adds a TEXT column to store extended thinking/reasoning from models like Claude.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
from sqlalchemy import text
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Add backend directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def migrate_add_reasoning(db_manager):
    """Add reasoning column to messages table"""
    async with db_manager.async_session() as session:
        try:
            # Check if column already exists
            check_sql = """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'messages'
                AND column_name = 'reasoning'
            """
            result = await session.execute(text(check_sql))
            existing = result.fetchone()

            if existing:
                logger.info("✓ Column 'reasoning' already exists in messages table")
                return

            # Add reasoning column
            logger.info("Adding 'reasoning' column to messages table...")
            alter_sql = """
                ALTER TABLE messages
                ADD COLUMN reasoning TEXT NULL
            """
            await session.execute(text(alter_sql))
            await session.commit()

            logger.info("✓ Successfully added 'reasoning' column to messages table")
            logger.info("  - Column type: TEXT")
            logger.info("  - Nullable: YES (existing rows will have NULL)")

        except Exception as e:
            logger.error(f"Migration failed: {e}")
            await session.rollback()
            raise


async def verify_migration(db_manager):
    """Verify the migration was successful"""
    async with db_manager.async_session() as session:
        try:
            # Check column exists and get its properties
            check_sql = """
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'messages'
                AND column_name = 'reasoning'
            """
            result = await session.execute(text(check_sql))
            column = result.fetchone()

            if column:
                logger.info("✓ Migration verification successful:")
                logger.info(f"  - Column: {column[0]}")
                logger.info(f"  - Type: {column[1]}")
                logger.info(f"  - Nullable: {column[2]}")
                return True
            else:
                logger.error("✗ Column 'reasoning' not found after migration")
                return False

        except Exception as e:
            logger.error(f"Verification failed: {e}")
            return False


async def main():
    """Run migration"""
    from database.models import DatabaseManager

    logger.info("=" * 60)
    logger.info("Migration: Add reasoning column to messages table")
    logger.info("=" * 60)

    database_url = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/espressobot')
    db_manager = DatabaseManager(database_url)

    try:
        await migrate_add_reasoning(db_manager)
        success = await verify_migration(db_manager)

        if success:
            logger.info("=" * 60)
            logger.info("✓ Migration completed successfully!")
            logger.info("=" * 60)
        else:
            logger.error("Migration verification failed")
            exit(1)

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        exit(1)


if __name__ == "__main__":
    asyncio.run(main())
