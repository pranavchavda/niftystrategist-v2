"""Thread Embedding Processor — event-driven with debounce.

Embeds conversation turns (user+assistant pairs) for cross-thread
semantic search. Runs as a periodic APScheduler job (every 60s),
processing threads that have been idle for 2+ minutes.

Keeps max 20 embedded threads per user (auto-purges oldest).
"""

import logging
from datetime import datetime, timedelta

from sqlalchemy import select, delete, text, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Conversation, Message, ThreadEmbedding, utc_now
from database.session import get_db_context

logger = logging.getLogger(__name__)

# Config
IDLE_THRESHOLD_SECONDS = 120  # 2 min debounce — don't embed active conversations
MAX_THREADS_PER_USER = 20     # Auto-purge oldest beyond this


async def process_dirty_threads() -> int:
    """Find idle threads with new content and embed their turns.

    Returns number of threads processed.
    """
    processed = 0
    cutoff = utc_now() - timedelta(seconds=IDLE_THRESHOLD_SECONDS)

    try:
        async with get_db_context() as session:
            # Find dirty threads: has new content, idle for 2+ minutes
            stmt = (
                select(Conversation.id, Conversation.user_id)
                .where(Conversation.needs_processing_since.isnot(None))
                .where(Conversation.needs_processing_since < cutoff)
                .where(
                    (Conversation.last_embedded_at.is_(None))
                    | (Conversation.last_embedded_at < Conversation.needs_processing_since)
                )
                .limit(10)  # Process max 10 per cycle to avoid long-running jobs
            )
            result = await session.execute(stmt)
            dirty = result.fetchall()

        if not dirty:
            return 0

        for conv_id, user_id in dirty:
            try:
                await _embed_thread(conv_id, user_id)
                processed += 1
            except Exception as e:
                logger.error("Failed to embed thread %s: %s", conv_id, e)

        # Purge excess threads per user (run once per cycle)
        users_processed = {user_id for _, user_id in dirty}
        for user_id in users_processed:
            try:
                await _purge_excess_threads(user_id)
            except Exception as e:
                logger.error("Failed to purge excess threads for user %s: %s", user_id, e)

        if processed:
            logger.info("Embedded %d thread(s)", processed)

    except Exception as e:
        logger.error("process_dirty_threads failed: %s", e)

    return processed


async def embed_thread_immediately(conversation_id: str) -> None:
    """Embed a thread right now, bypassing the debounce.

    Used by awakening write-back to make results searchable immediately.
    """
    try:
        async with get_db_context() as session:
            conv = await session.get(Conversation, conversation_id)
            if conv:
                await _embed_thread(conversation_id, conv.user_id)
                logger.info("Immediately embedded thread %s", conversation_id)
    except Exception as e:
        logger.error("Immediate embed failed for thread %s: %s", conversation_id, e)


async def _embed_thread(conversation_id: str, user_id: str) -> None:
    """Load messages, chunk into turns, embed, and upsert."""
    from memory.pplx_embedding_service import get_pplx_embedding_service

    async with get_db_context() as session:
        # Load conversational messages only (user + assistant, skip system/tool)
        msg_stmt = (
            select(Message.role, Message.content, Message.timestamp)
            .where(Message.conversation_id == conversation_id)
            .where(Message.role.in_(["user", "assistant"]))
            .where(Message.content.isnot(None))
            .where(Message.content != "")
            .order_by(Message.timestamp.asc())
        )
        result = await session.execute(msg_stmt)
        messages = result.fetchall()

        if not messages:
            # Mark as processed even if empty
            await session.execute(
                update(Conversation)
                .where(Conversation.id == conversation_id)
                .values(last_embedded_at=utc_now(), needs_processing_since=None)
            )
            await session.commit()
            return

        # Chunk into turn pairs: user message + next assistant response
        turns: list[tuple[int, str]] = []  # (turn_index, content)
        turn_index = 0
        current_turn = []

        for role, content, _ in messages:
            current_turn.append(f"{role}: {content.strip()}")
            if role == "assistant":
                # Complete turn — combine user + assistant
                turn_text = "\n".join(current_turn)
                # Cap turn length to avoid huge embeddings (32K context, but be reasonable)
                if len(turn_text) > 4000:
                    turn_text = turn_text[:4000]
                turns.append((turn_index, turn_text))
                turn_index += 1
                current_turn = []

        # Include trailing user message without response (rare but possible)
        if current_turn:
            turn_text = "\n".join(current_turn)
            if len(turn_text) > 4000:
                turn_text = turn_text[:4000]
            turns.append((turn_index, turn_text))

        if not turns:
            await session.execute(
                update(Conversation)
                .where(Conversation.id == conversation_id)
                .values(last_embedded_at=utc_now(), needs_processing_since=None)
            )
            await session.commit()
            return

        # Check which turns already exist
        existing_stmt = (
            select(ThreadEmbedding.turn_index)
            .where(ThreadEmbedding.conversation_id == conversation_id)
        )
        existing = {row[0] for row in (await session.execute(existing_stmt)).fetchall()}

        # Filter to new turns only
        new_turns = [(idx, txt) for idx, txt in turns if idx not in existing]

        if new_turns:
            # Batch embed
            svc = get_pplx_embedding_service()
            texts = [txt for _, txt in new_turns]
            embeddings = await svc.get_embeddings_batch(texts)

            # Upsert via raw SQL (halfvec needs raw insert)
            for (idx, txt), emb_result in zip(new_turns, embeddings):
                vec_str = "[" + ",".join(f"{v:.6f}" for v in emb_result.embedding) + "]"
                await session.execute(text(
                    "INSERT INTO thread_embeddings (conversation_id, user_id, turn_index, content, embedding, created_at) "
                    "VALUES (:conv_id, :user_id, :turn_idx, :content, :embedding::halfvec, NOW() AT TIME ZONE 'utc') "
                    "ON CONFLICT (conversation_id, turn_index) DO UPDATE SET "
                    "content = EXCLUDED.content, embedding = EXCLUDED.embedding"
                ), {
                    "conv_id": conversation_id,
                    "user_id": user_id,
                    "turn_idx": idx,
                    "content": txt,
                    "embedding": vec_str,
                })

            logger.debug(
                "Embedded %d new turns for thread %s (total %d)",
                len(new_turns), conversation_id, len(turns),
            )

        # Mark as processed
        await session.execute(
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(last_embedded_at=utc_now(), needs_processing_since=None)
        )
        await session.commit()


async def _purge_excess_threads(user_id: str) -> None:
    """Keep only MAX_THREADS_PER_USER most recent embedded threads per user."""
    async with get_db_context() as session:
        # Get distinct conversation_ids with embeddings, ordered by newest
        stmt = text(
            "SELECT DISTINCT conversation_id, MAX(created_at) as latest "
            "FROM thread_embeddings WHERE user_id = :user_id "
            "GROUP BY conversation_id ORDER BY latest DESC"
        )
        result = await session.execute(stmt, {"user_id": user_id})
        all_convs = result.fetchall()

        if len(all_convs) <= MAX_THREADS_PER_USER:
            return

        # Delete embeddings for oldest threads beyond the limit
        to_purge = [row[0] for row in all_convs[MAX_THREADS_PER_USER:]]
        if to_purge:
            await session.execute(
                delete(ThreadEmbedding)
                .where(ThreadEmbedding.conversation_id.in_(to_purge))
            )
            await session.commit()
            logger.info(
                "Purged embeddings for %d old threads for user %s (keeping %d)",
                len(to_purge), user_id, MAX_THREADS_PER_USER,
            )


async def search_threads(
    user_id: str,
    query: str,
    limit: int = 5,
) -> list[dict]:
    """Semantic search across embedded thread turns.

    Returns list of {conversation_id, title, turn_content, similarity} dicts.
    """
    from memory.pplx_embedding_service import get_pplx_embedding_service

    svc = get_pplx_embedding_service()
    query_emb = await svc.get_embedding(query)
    vec_str = "[" + ",".join(f"{v:.6f}" for v in query_emb.embedding) + "]"

    async with get_db_context() as session:
        result = await session.execute(text(
            "SELECT te.conversation_id, te.content, "
            "1 - (te.embedding <=> :query_vec::halfvec) AS similarity, "
            "c.title "
            "FROM thread_embeddings te "
            "JOIN conversations c ON c.id = te.conversation_id "
            "WHERE te.user_id = :user_id "
            "ORDER BY te.embedding <=> :query_vec::halfvec "
            "LIMIT :limit"
        ), {"user_id": user_id, "query_vec": vec_str, "limit": limit})

        rows = result.fetchall()
        return [
            {
                "conversation_id": row[0],
                "turn_content": row[1][:500],  # Truncate for display
                "similarity": round(float(row[2]), 3),
                "title": row[3] or "(untitled)",
            }
            for row in rows
        ]
