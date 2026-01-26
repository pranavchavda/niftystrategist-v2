#!/usr/bin/env python3
"""Migration script to add rejected_matches table.

This migration adds a new table to track product pairs that have been
manually rejected to prevent future auto-matching.

Usage:
    python3 migrate_add_rejected_matches.py
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
            logger.info("Starting migration: add rejected_matches table")

            # Check if table already exists
            check_query = text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'rejected_matches'
                );
            """)

            result = await session.execute(check_query)
            table_exists = result.scalar()

            if table_exists:
                logger.info("Table 'rejected_matches' already exists. Skipping migration.")
                return

            # Create rejected_matches table
            create_table_query = text("""
                CREATE TABLE rejected_matches (
                    id VARCHAR PRIMARY KEY,
                    idc_product_id VARCHAR NOT NULL REFERENCES idc_products(id) ON DELETE CASCADE,
                    competitor_product_id VARCHAR NOT NULL REFERENCES competitor_products(id) ON DELETE CASCADE,
                    rejected_reason TEXT,
                    rejected_by VARCHAR,
                    rejected_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
            """)

            await session.execute(create_table_query)
            logger.info("Created table 'rejected_matches'")

            # Create indexes
            create_idx_pair = text("""
                CREATE UNIQUE INDEX idx_rejected_pair
                ON rejected_matches(idc_product_id, competitor_product_id);
            """)

            create_idx_idc = text("""
                CREATE INDEX idx_rejected_idc
                ON rejected_matches(idc_product_id);
            """)

            create_idx_comp = text("""
                CREATE INDEX idx_rejected_comp
                ON rejected_matches(competitor_product_id);
            """)

            await session.execute(create_idx_pair)
            await session.execute(create_idx_idc)
            await session.execute(create_idx_comp)

            logger.info("Created indexes on rejected_matches")

            await session.commit()
            logger.info("✓ Migration completed successfully")

        except Exception as e:
            await session.rollback()
            logger.error(f"✗ Migration failed: {e}")
            raise


async def rollback():
    """Rollback the migration."""
    async with AsyncSessionLocal() as session:
        try:
            logger.info("Rolling back migration: drop rejected_matches table")

            drop_table_query = text("DROP TABLE IF EXISTS rejected_matches CASCADE;")
            await session.execute(drop_table_query)
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
