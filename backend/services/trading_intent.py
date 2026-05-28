"""Read/write helpers for the agent's self-authored trading intent.

Full-rewrite-each-turn semantics: ``set_intent`` always INSERTs a fresh row.
The snapshot reads only the latest row (newest wins); the accumulated rows are
the intra-day trail. See ``database.models.TradingIntent`` for the contract
(intent only — never live state).
"""
from __future__ import annotations

from sqlalchemy import select

from database.models import TradingIntent
from database.session import get_db_context


async def set_intent(user_id: int, thread_id: str, content: str) -> int:
    """Insert a new intent row (full rewrite). Returns the new row id."""
    async with get_db_context() as session:
        row = TradingIntent(user_id=user_id, thread_id=thread_id, content=content)
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return row.id


async def get_latest_intent(thread_id: str) -> TradingIntent | None:
    """Most recent intent for a daily thread (the one the snapshot injects)."""
    async with get_db_context() as session:
        stmt = (
            select(TradingIntent)
            .where(TradingIntent.thread_id == thread_id)
            .order_by(TradingIntent.created_at.desc(), TradingIntent.id.desc())
            .limit(1)
        )
        return (await session.execute(stmt)).scalar_one_or_none()


async def get_intent_log(thread_id: str, limit: int = 50) -> list[TradingIntent]:
    """The full intra-day trail, newest first."""
    async with get_db_context() as session:
        stmt = (
            select(TradingIntent)
            .where(TradingIntent.thread_id == thread_id)
            .order_by(TradingIntent.created_at.desc(), TradingIntent.id.desc())
            .limit(limit)
        )
        return list((await session.execute(stmt)).scalars().all())
