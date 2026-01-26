"""
Migration: Make conversation_id nullable in memories table
This allows manual memories to be created without a conversation.
"""
import os
import asyncio
import logging
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/espressobot')

async def migrate():
    """Alter memories table to make conversation_id nullable"""
    # Convert to async URL if needed
    if DATABASE_URL.startswith("postgresql://"):
        async_url = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
    else:
        async_url = DATABASE_URL

    logger.info(f"Migrating database at {async_url}")

    # Create engine
    engine = create_async_engine(async_url, echo=True)

    async with engine.begin() as conn:
        # Drop the foreign key constraint
        logger.info("Dropping foreign key constraint...")
        await conn.execute(text("""
            ALTER TABLE memories
            DROP CONSTRAINT IF EXISTS memories_conversation_id_fkey
        """))

        # Make conversation_id nullable
        logger.info("Making conversation_id nullable...")
        await conn.execute(text("""
            ALTER TABLE memories
            ALTER COLUMN conversation_id DROP NOT NULL
        """))

        # Re-add the foreign key constraint (now allowing NULL)
        logger.info("Re-adding foreign key constraint...")
        await conn.execute(text("""
            ALTER TABLE memories
            ADD CONSTRAINT memories_conversation_id_fkey
            FOREIGN KEY (conversation_id)
            REFERENCES conversations(id)
        """))

    logger.info("✓ Migration completed successfully")

    # Close the engine
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(migrate())
