"""
Migration: Keep memories when conversation is deleted

Memories are long-term knowledge and should persist even when the
conversation they were extracted from is deleted. This updates the
foreign key constraint to SET NULL instead of CASCADE DELETE.
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
    """Update memories foreign key to SET NULL on delete"""
    # Convert to async URL if needed
    if DATABASE_URL.startswith("postgresql://"):
        async_url = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
    else:
        async_url = DATABASE_URL

    logger.info(f"Migrating database at {async_url}")

    # Create engine
    engine = create_async_engine(async_url, echo=True)

    async with engine.begin() as conn:
        # Update memories foreign key to SET NULL instead of CASCADE
        logger.info("Updating memories foreign key to SET NULL on delete...")
        await conn.execute(text("""
            ALTER TABLE memories
            DROP CONSTRAINT IF EXISTS memories_conversation_id_fkey
        """))

        await conn.execute(text("""
            ALTER TABLE memories
            ADD CONSTRAINT memories_conversation_id_fkey
            FOREIGN KEY (conversation_id)
            REFERENCES conversations(id)
            ON DELETE SET NULL
        """))

    logger.info("✓ Migration completed successfully")
    logger.info("  - Memories will now persist when conversation is deleted")
    logger.info("  - conversation_id will be set to NULL for orphaned memories")

    # Close the engine
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(migrate())
