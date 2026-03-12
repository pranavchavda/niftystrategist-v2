"""
DB-backed scratchpad service replacing file-based tools/native/scratchpad.py.

Stores entries in PostgreSQL via async DB sessions.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from database.session import get_db_context

logger = logging.getLogger(__name__)


class ScratchpadDB:
    """Async DB-backed scratchpad, thread-specific."""

    def __init__(self, thread_id: str):
        if not thread_id:
            raise ValueError("A thread_id is required to initialize the scratchpad.")
        self.thread_id = thread_id

    async def add_entry(
        self,
        content: str,
        author: str = "agent",
        entry_type: str = "note",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Add a new entry. Returns the created entry dict with id."""
        async with get_db_context() as session:
            result = await session.execute(
                text("""
                    INSERT INTO scratchpad_entries (thread_id, author, content, entry_type, metadata)
                    VALUES (:thread_id, :author, :content, :entry_type, :metadata)
                    RETURNING id, thread_id, author, content, entry_type, metadata, created_at, updated_at
                """),
                {
                    "thread_id": self.thread_id,
                    "author": author,
                    "content": content,
                    "entry_type": entry_type,
                    "metadata": _serialize_metadata(metadata),
                },
            )
            row = result.fetchone()
            await session.commit()
            return _row_to_dict(row)

    async def get_entries(
        self, entry_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Get all entries for this thread, optionally filtered by type."""
        async with get_db_context() as session:
            if entry_types:
                result = await session.execute(
                    text("""
                        SELECT id, thread_id, author, content, entry_type, metadata, created_at, updated_at
                        FROM scratchpad_entries
                        WHERE thread_id = :thread_id AND entry_type = ANY(:entry_types)
                        ORDER BY created_at ASC
                    """),
                    {"thread_id": self.thread_id, "entry_types": entry_types},
                )
            else:
                result = await session.execute(
                    text("""
                        SELECT id, thread_id, author, content, entry_type, metadata, created_at, updated_at
                        FROM scratchpad_entries
                        WHERE thread_id = :thread_id
                        ORDER BY created_at ASC
                    """),
                    {"thread_id": self.thread_id},
                )
            rows = result.fetchall()
            return [_row_to_dict(row) for row in rows]

    async def update_entry(self, entry_id: int, content: str) -> Dict[str, Any]:
        """Update an entry by id. Returns updated entry dict."""
        async with get_db_context() as session:
            result = await session.execute(
                text("""
                    UPDATE scratchpad_entries
                    SET content = :content, updated_at = NOW()
                    WHERE id = :id AND thread_id = :thread_id
                    RETURNING id, thread_id, author, content, entry_type, metadata, created_at, updated_at
                """),
                {"id": entry_id, "content": content, "thread_id": self.thread_id},
            )
            row = result.fetchone()
            await session.commit()
            if not row:
                raise ValueError(f"Entry {entry_id} not found in thread {self.thread_id}")
            return _row_to_dict(row)

    async def delete_entry(self, entry_id: int) -> bool:
        """Delete an entry by id. Returns True if deleted."""
        async with get_db_context() as session:
            result = await session.execute(
                text("""
                    DELETE FROM scratchpad_entries
                    WHERE id = :id AND thread_id = :thread_id
                    RETURNING id
                """),
                {"id": entry_id, "thread_id": self.thread_id},
            )
            deleted = result.fetchone()
            await session.commit()
            if not deleted:
                raise ValueError(f"Entry {entry_id} not found in thread {self.thread_id}")
            return True

    async def clear_entries(self) -> int:
        """Delete all entries for this thread. Returns count deleted."""
        async with get_db_context() as session:
            result = await session.execute(
                text("""
                    DELETE FROM scratchpad_entries
                    WHERE thread_id = :thread_id
                """),
                {"thread_id": self.thread_id},
            )
            await session.commit()
            return result.rowcount


def _serialize_metadata(metadata: Optional[Dict[str, Any]]) -> str:
    if metadata is None:
        return "{}"
    return json.dumps(metadata)


def _row_to_dict(row) -> Dict[str, Any]:
    metadata = row[5]
    if isinstance(metadata, str):
        metadata = json.loads(metadata)
    elif metadata is None:
        metadata = {}

    created_at = row[6]
    updated_at = row[7]

    return {
        "id": row[0],
        "thread_id": row[1],
        "author": row[2],
        "content": row[3],
        "entry_type": row[4],
        "metadata": metadata,
        "timestamp": created_at.isoformat() if created_at else None,
        "created_at": created_at.isoformat() if created_at else None,
        "updated_at": updated_at.isoformat() if updated_at else None,
    }
