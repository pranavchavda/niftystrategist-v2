"""Thread Embedding Processor — event-driven with debounce.

Embeds conversation turns (user+assistant pairs) for cross-thread
semantic search. Triggered after each assistant message save with a
2-minute debounce (to avoid embedding active conversations).

Keeps max 20 embedded threads per user (auto-purges oldest).
"""

import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Conversation, Message, ThreadEmbedding, utc_now
from database.session import get_db_context

logger = logging.getLogger(__name__)

# Pending debounced embed tasks — keyed by conversation_id.
# When a new message arrives for a thread that already has a pending task,
# the old task is cancelled and a new one is scheduled.
_pending_embeds: dict[str, asyncio.Task] = {}

# Config
IDLE_THRESHOLD_SECONDS = 120  # 2 min debounce — don't embed active conversations

# Recency-weighted search: no hard purge, old threads decay in relevance instead
DEFAULT_MIN_SIMILARITY = 0.25   # Floor — don't return poor matches even if recent
RECENCY_WEIGHT = 0.15           # 15% recency, 85% semantic similarity
RECENCY_HALF_LIFE_DAYS = 14     # Recency boost halves every 14 days


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

        if processed:
            logger.info("Embedded %d thread(s)", processed)

    except Exception as e:
        logger.error("process_dirty_threads failed: %s", e)

    return processed


async def embed_thread_immediately(conversation_id: str) -> None:
    """Embed a thread right now, bypassing the debounce.

    Used by awakening write-back to make results searchable immediately.
    """
    # Cancel any pending debounced task for this thread
    _cancel_pending(conversation_id)

    try:
        async with get_db_context() as session:
            conv = await session.get(Conversation, conversation_id)
            if conv:
                await _embed_thread(conversation_id, conv.user_id)
                logger.info("Immediately embedded thread %s", conversation_id)
    except Exception as e:
        logger.error("Immediate embed failed for thread %s: %s", conversation_id, e)


def schedule_debounced_embed(conversation_id: str) -> None:
    """Schedule a thread embed after the idle debounce period.

    Called from save_assistant_message_to_db. If a previous embed is pending
    for this thread (user sent another message), cancels it and restarts
    the debounce timer. This replaces the 60s APScheduler polling job.
    """
    _cancel_pending(conversation_id)

    async def _delayed_embed():
        try:
            await asyncio.sleep(IDLE_THRESHOLD_SECONDS)
            async with get_db_context() as session:
                conv = await session.get(Conversation, conversation_id)
                if conv and conv.needs_processing_since:
                    await _embed_thread(conversation_id, conv.user_id)
                    logger.info("Debounced embed completed for thread %s", conversation_id)
        except asyncio.CancelledError:
            pass  # New message arrived, debounce restarted
        except Exception as e:
            logger.error("Debounced embed failed for thread %s: %s", conversation_id, e)
        finally:
            _pending_embeds.pop(conversation_id, None)

    _pending_embeds[conversation_id] = asyncio.create_task(_delayed_embed())


def _cancel_pending(conversation_id: str) -> None:
    """Cancel a pending debounced embed task if one exists."""
    task = _pending_embeds.pop(conversation_id, None)
    if task and not task.done():
        task.cancel()


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

            # Upsert via raw SQL (halfvec needs CAST, not :: which conflicts with SQLAlchemy bind syntax)
            for (idx, txt), emb_result in zip(new_turns, embeddings):
                vec_str = "[" + ",".join(f"{v:.6f}" for v in emb_result.embedding) + "]"
                await session.execute(text(
                    "INSERT INTO thread_embeddings (conversation_id, user_id, turn_index, content, embedding, created_at) "
                    "VALUES (:conv_id, :user_id, :turn_idx, :content, CAST(:embedding AS halfvec), NOW() AT TIME ZONE 'utc') "
                    "ON CONFLICT (conversation_id, turn_index) DO UPDATE SET "
                    "content = EXCLUDED.content, embedding = CAST(EXCLUDED.embedding AS halfvec)"
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


async def search_threads(
    user_id: str,
    query: str,
    limit: int = 5,
    min_similarity: float = DEFAULT_MIN_SIMILARITY,
) -> list[dict]:
    """Recency-weighted semantic search across embedded thread turns.

    Combines cosine similarity (85%) with exponential recency decay (15%).
    Old threads still surface if the semantic match is strong enough,
    but recent threads get a natural boost. No hard purging needed.

    Returns list of {conversation_id, title, turn_content, similarity, score} dicts.
    """
    from memory.pplx_embedding_service import get_pplx_embedding_service

    svc = get_pplx_embedding_service()
    query_emb = await svc.get_embedding(query)
    vec_str = "[" + ",".join(f"{v:.6f}" for v in query_emb.embedding) + "]"

    async with get_db_context() as session:
        result = await session.execute(text(
            "SELECT te.conversation_id, te.content, "
            "  1 - (te.embedding <=> CAST(:query_vec AS halfvec)) AS similarity, "
            "  c.title, "
            "  c.updated_at, "
            # Exponential recency decay: half-life of N days
            # 0.693 = ln(2), converts half-life to decay constant
            "  EXP(-0.693 * EXTRACT(EPOCH FROM (NOW() - c.updated_at)) / 86400.0 / :half_life) AS recency, "
            # Combined score: weighted blend of similarity + recency
            "  (1 - (te.embedding <=> CAST(:query_vec AS halfvec))) * (1 - :recency_w) + "
            "    EXP(-0.693 * EXTRACT(EPOCH FROM (NOW() - c.updated_at)) / 86400.0 / :half_life) * :recency_w AS score "
            "FROM thread_embeddings te "
            "JOIN conversations c ON c.id = te.conversation_id "
            "WHERE te.user_id = :user_id "
            "  AND 1 - (te.embedding <=> CAST(:query_vec AS halfvec)) >= :min_sim "
            "ORDER BY score DESC "
            "LIMIT :limit"
        ), {
            "user_id": user_id,
            "query_vec": vec_str,
            "limit": limit,
            "half_life": RECENCY_HALF_LIFE_DAYS,
            "recency_w": RECENCY_WEIGHT,
            "min_sim": min_similarity,
        })

        rows = result.fetchall()
        return [
            {
                "conversation_id": row[0],
                "turn_content": row[1][:500],
                "similarity": round(float(row[2]), 3),
                "title": row[3] or "(untitled)",
                "score": round(float(row[6]), 3),
            }
            for row in rows
        ]
