"""
Migration: Add CASCADE DELETE to messages and memories foreign keys

This allows automatic deletion of messages and memories when their parent
conversation is deleted, matching the SQLAlchemy model configuration.
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
    """Add CASCADE DELETE to foreign key constraints"""
    # Convert to async URL if needed
    if DATABASE_URL.startswith("postgresql://"):
        async_url = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
    else:
        async_url = DATABASE_URL

    logger.info(f"Migrating database at {async_url}")

    # Create engine
    engine = create_async_engine(async_url, echo=True)

    async with engine.begin() as conn:
        # Fix messages foreign key
        logger.info("Updating messages foreign key to CASCADE DELETE...")
        await conn.execute(text("""
            ALTER TABLE messages
            DROP CONSTRAINT IF EXISTS messages_conversation_id_fkey
        """))

        await conn.execute(text("""
            ALTER TABLE messages
            ADD CONSTRAINT messages_conversation_id_fkey
            FOREIGN KEY (conversation_id)
            REFERENCES conversations(id)
            ON DELETE CASCADE
        """))

        # Fix memories foreign key (already nullable, just add CASCADE)
        logger.info("Updating memories foreign key to CASCADE DELETE...")
        await conn.execute(text("""
            ALTER TABLE memories
            DROP CONSTRAINT IF EXISTS memories_conversation_id_fkey
        """))

        await conn.execute(text("""
            ALTER TABLE memories
            ADD CONSTRAINT memories_conversation_id_fkey
            FOREIGN KEY (conversation_id)
            REFERENCES conversations(id)
            ON DELETE CASCADE
        """))

    logger.info("✓ Migration completed successfully")
    logger.info("  - messages will now CASCADE DELETE when conversation is deleted")
    logger.info("  - memories will now CASCADE DELETE when conversation is deleted")

    # Close the engine
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(migrate())
