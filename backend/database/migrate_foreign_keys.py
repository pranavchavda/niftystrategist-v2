"""
Migration script to add CASCADE/SET NULL to foreign key constraints.

This fixes the conversation deletion error by allowing messages to be
automatically deleted when a conversation is deleted.
"""

import asyncio
import os
from sqlalchemy import text
from dotenv import load_dotenv

# Load environment
load_dotenv()

async def migrate():
    """Apply foreign key constraint migrations"""
    import sys
    from pathlib import Path

    # Add backend directory to path
    backend_dir = Path(__file__).parent.parent
    sys.path.insert(0, str(backend_dir))

    from database.models import DatabaseManager

    database_url = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/espressobot')
    db_manager = DatabaseManager(database_url)

    print("🔧 Applying foreign key migrations...")

    async with db_manager.engine.begin() as conn:
        # Step 1: Drop existing foreign key constraints
        print("  → Dropping old foreign key constraints...")

        # Drop message foreign key
        await conn.execute(text("""
            ALTER TABLE messages
            DROP CONSTRAINT IF EXISTS messages_conversation_id_fkey;
        """))

        # Drop memory foreign key
        await conn.execute(text("""
            ALTER TABLE memories
            DROP CONSTRAINT IF EXISTS memories_conversation_id_fkey;
        """))

        print("  ✓ Old constraints dropped")

        # Step 2: Add new foreign key constraints with proper ON DELETE behavior
        print("  → Adding new foreign key constraints...")

        # Add message foreign key with CASCADE
        await conn.execute(text("""
            ALTER TABLE messages
            ADD CONSTRAINT messages_conversation_id_fkey
            FOREIGN KEY (conversation_id)
            REFERENCES conversations(id)
            ON DELETE CASCADE;
        """))

        # Add memory foreign key with SET NULL
        await conn.execute(text("""
            ALTER TABLE memories
            ADD CONSTRAINT memories_conversation_id_fkey
            FOREIGN KEY (conversation_id)
            REFERENCES conversations(id)
            ON DELETE SET NULL;
        """))

        print("  ✓ New constraints added")

    print("✅ Migration complete!")
    print()
    print("Changes applied:")
    print("  • messages.conversation_id → ON DELETE CASCADE")
    print("  • memories.conversation_id → ON DELETE SET NULL")
    print()
    print("Conversation deletion should now work correctly.")

    await db_manager.close()

if __name__ == "__main__":
    asyncio.run(migrate())
