"""
Database operations for conversation management
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta, timezone
from utils.datetime_utils import utc_now_naive
from sqlalchemy import select, update, delete, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .models import Conversation, Message, Memory, UserPreference, DocChunk

logger = logging.getLogger(__name__)


class ConversationOps:
    """Operations for managing conversations"""

    @staticmethod
    async def create_conversation(
        session: AsyncSession,
        thread_id: str,
        user_id: str,
        title: Optional[str] = None
    ) -> Conversation:
        """Create a new conversation"""
        conversation = Conversation(
            id=thread_id,
            user_id=user_id,
            title=title or "New Conversation"
        )
        session.add(conversation)
        await session.commit()
        await session.refresh(conversation)
        return conversation

    @staticmethod
    async def get_conversation(
        session: AsyncSession,
        thread_id: str,
        user_id: str,
        include_messages: bool = False
    ) -> Optional[Conversation]:
        """Get a conversation by ID"""
        query = select(Conversation).where(
            and_(
                Conversation.id == thread_id,
                Conversation.user_id == user_id
            )
        )

        if include_messages:
            query = query.options(selectinload(Conversation.messages))

        result = await session.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def list_conversations(
        session: AsyncSession,
        user_id: str,
        limit: int = 20,
        offset: int = 0,
        include_archived: bool = False
    ) -> List[Conversation]:
        """List user's conversations"""
        query = select(Conversation).where(
            Conversation.user_id == user_id
        )

        if not include_archived:
            query = query.where(Conversation.is_archived == False)

        query = query.order_by(Conversation.updated_at.desc())
        query = query.limit(limit).offset(offset)

        result = await session.execute(query)
        return result.scalars().all()

    @staticmethod
    async def update_conversation_title(
        session: AsyncSession,
        thread_id: str,
        user_id: str,
        title: str,
        update_timestamp: bool = True
    ) -> bool:
        """Update conversation title

        Args:
            update_timestamp: If False, don't update the updated_at timestamp.
                              Useful for background processes like memory extraction.
        """
        values = {"title": title}
        if update_timestamp:
            values["updated_at"] = utc_now_naive()

        query = update(Conversation).where(
            and_(
                Conversation.id == thread_id,
                Conversation.user_id == user_id
            )
        ).values(**values)

        result = await session.execute(query)
        await session.commit()
        return result.rowcount > 0

    @staticmethod
    async def star_conversation(
        session: AsyncSession,
        thread_id: str,
        user_id: str,
        starred: bool = True
    ) -> bool:
        """Star or unstar a conversation"""
        query = update(Conversation).where(
            and_(
                Conversation.id == thread_id,
                Conversation.user_id == user_id
            )
        ).values(is_starred=starred, updated_at=utc_now_naive())

        result = await session.execute(query)
        await session.commit()
        return result.rowcount > 0

    @staticmethod
    async def archive_conversation(
        session: AsyncSession,
        thread_id: str,
        user_id: str,
        archived: bool = True
    ) -> bool:
        """Archive or unarchive a conversation"""
        query = update(Conversation).where(
            and_(
                Conversation.id == thread_id,
                Conversation.user_id == user_id
            )
        ).values(is_archived=archived, updated_at=utc_now_naive())

        result = await session.execute(query)
        await session.commit()
        return result.rowcount > 0

    @staticmethod
    async def delete_conversation(
        session: AsyncSession,
        thread_id: str,
        user_id: str
    ) -> bool:
        """Delete a conversation and all its messages"""
        query = delete(Conversation).where(
            and_(
                Conversation.id == thread_id,
                Conversation.user_id == user_id
            )
        )

        result = await session.execute(query)
        await session.commit()
        return result.rowcount > 0

    @staticmethod
    async def search_conversations(
        session: AsyncSession,
        user_id: str,
        search_term: str,
        limit: int = 20
    ) -> List[Conversation]:
        """Search conversations by title or summary"""
        query = select(Conversation).where(
            and_(
                Conversation.user_id == user_id,
                or_(
                    Conversation.title.ilike(f"%{search_term}%"),
                    Conversation.summary.ilike(f"%{search_term}%")
                )
            )
        ).order_by(Conversation.updated_at.desc()).limit(limit)

        result = await session.execute(query)
        return result.scalars().all()

    @staticmethod
    async def fork_conversation(
        session: AsyncSession,
        source_thread_id: str,
        new_thread_id: str,
        user_id: str,
        fork_summary: str,
        new_title: Optional[str] = None
    ) -> Conversation:
        """
        Create a new conversation as a fork of an existing one.

        Args:
            source_thread_id: ID of the conversation being forked
            new_thread_id: ID for the new forked conversation
            user_id: User creating the fork
            fork_summary: Comprehensive summary of the parent conversation
            new_title: Optional custom title (defaults to "Fork of [parent title]")

        Returns:
            The newly created forked conversation
        """
        # Get parent conversation to derive title
        parent_query = select(Conversation).where(
            and_(
                Conversation.id == source_thread_id,
                Conversation.user_id == user_id
            )
        )
        parent_result = await session.execute(parent_query)
        parent_conv = parent_result.scalar_one_or_none()

        if not parent_conv:
            raise ValueError(f"Parent conversation {source_thread_id} not found for user {user_id}")

        # Create new conversation
        if not new_title:
            new_title = f"Fork of {parent_conv.title}"

        new_conversation = Conversation(
            id=new_thread_id,
            user_id=user_id,
            title=new_title,
            forked_from_id=source_thread_id,
            fork_summary=fork_summary,
            created_at=utc_now_naive(),
            updated_at=utc_now_naive()
        )

        session.add(new_conversation)
        await session.commit()
        await session.refresh(new_conversation)

        logger.info(f"Forked conversation {source_thread_id} -> {new_thread_id} for user {user_id}")
        return new_conversation


class MessageOps:
    """Operations for managing messages"""

    @staticmethod
    async def add_message(
        session: AsyncSession,
        conversation_id: str,
        message_id: str,
        role: str,
        content: str,
        attachments: Optional[List] = None,
        tool_calls: Optional[List] = None,
        metadata: Optional[Dict] = None
    ) -> Message:
        """Add a message to a conversation"""
        message = Message(
            conversation_id=conversation_id,
            message_id=message_id,
            role=role,
            content=content,
            attachments=attachments or [],
            tool_calls=tool_calls or [],
            metadata=metadata or {}
        )
        session.add(message)

        # Update conversation updated_at
        await session.execute(
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(updated_at=utc_now_naive())
        )

        await session.commit()
        await session.refresh(message)
        return message

    @staticmethod
    async def get_messages(
        session: AsyncSession,
        conversation_id: str,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[Message]:
        """Get messages for a conversation"""
        query = select(Message).where(
            Message.conversation_id == conversation_id
        ).order_by(Message.timestamp)

        if limit:
            query = query.limit(limit).offset(offset)

        result = await session.execute(query)
        return result.scalars().all()

    @staticmethod
    async def search_messages(
        session: AsyncSession,
        user_id: str,
        search_term: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Search messages across all user's conversations"""
        query = select(Message, Conversation).join(
            Conversation
        ).where(
            and_(
                Conversation.user_id == user_id,
                Message.content.ilike(f"%{search_term}%")
            )
        ).order_by(Message.timestamp.desc()).limit(limit)

        result = await session.execute(query)

        messages_with_conv = []
        for message, conversation in result:
            messages_with_conv.append({
                "message": message,
                "conversation": conversation
            })

        return messages_with_conv

    @staticmethod
    async def update_message(
        session: AsyncSession,
        conversation_id: str,
        message_id: str,
        new_content: str,
        checkpoint_mode: bool = False
    ) -> tuple[Optional[Message], int]:
        """
        Update the content of a message.

        Args:
            session: Database session
            conversation_id: Conversation ID (for verification)
            message_id: The unique message_id to update
            new_content: The new content for the message
            checkpoint_mode: If True, delete all messages after this one (like ChatGPT/Claude)

        Returns:
            Tuple of (updated Message or None, count of deleted subsequent messages)
        """
        # First, verify the message exists and belongs to the conversation
        query = select(Message).where(
            and_(
                Message.message_id == message_id,
                Message.conversation_id == conversation_id
            )
        )
        result = await session.execute(query)
        message = result.scalar_one_or_none()

        if not message:
            return None, 0

        deleted_count = 0

        # If checkpoint mode, delete all messages after this one
        if checkpoint_mode:
            # Delete all messages with timestamp > this message's timestamp
            delete_query = delete(Message).where(
                and_(
                    Message.conversation_id == conversation_id,
                    Message.timestamp > message.timestamp
                )
            )
            delete_result = await session.execute(delete_query)
            deleted_count = delete_result.rowcount
            logger.info(f"Checkpoint mode: deleted {deleted_count} messages after {message_id}")

        # Update the message
        message.content = new_content
        message.edited_at = utc_now_naive()

        # Update conversation's updated_at
        await session.execute(
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(updated_at=utc_now_naive())
        )

        await session.commit()
        await session.refresh(message)

        logger.info(f"Updated message {message_id} in conversation {conversation_id}")
        return message, deleted_count

    @staticmethod
    async def delete_message(
        session: AsyncSession,
        conversation_id: str,
        message_id: str
    ) -> tuple[bool, int]:
        """
        Delete a message and all subsequent messages from a conversation.
        Works like a checkpoint - removing a message removes everything after it too.

        Args:
            session: Database session
            conversation_id: Conversation ID (for verification)
            message_id: The unique message_id to delete

        Returns:
            Tuple of (True if message was deleted, count of total messages deleted including subsequent)
        """
        # First, get the message to find its timestamp
        query = select(Message).where(
            and_(
                Message.message_id == message_id,
                Message.conversation_id == conversation_id
            )
        )
        result = await session.execute(query)
        message = result.scalar_one_or_none()

        if not message:
            return False, 0

        # Delete this message AND all messages after it (checkpoint behavior)
        delete_query = delete(Message).where(
            and_(
                Message.conversation_id == conversation_id,
                Message.timestamp >= message.timestamp
            )
        )
        delete_result = await session.execute(delete_query)
        deleted_count = delete_result.rowcount

        # Update conversation's updated_at
        await session.execute(
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(updated_at=utc_now_naive())
        )

        await session.commit()

        logger.info(f"Deleted message {message_id} and {deleted_count - 1} subsequent messages from conversation {conversation_id}")
        return True, deleted_count

    @staticmethod
    async def get_message_by_id(
        session: AsyncSession,
        conversation_id: str,
        message_id: str
    ) -> Optional[Message]:
        """
        Get a single message by its message_id.

        Args:
            session: Database session
            conversation_id: Conversation ID (for verification)
            message_id: The unique message_id

        Returns:
            The Message or None if not found
        """
        query = select(Message).where(
            and_(
                Message.message_id == message_id,
                Message.conversation_id == conversation_id
            )
        )
        result = await session.execute(query)
        return result.scalar_one_or_none()


class MemoryOps:
    """Operations for managing memories"""

    @staticmethod
    async def add_memory_with_judge(
        session: AsyncSession,
        conversation_id: str,
        user_id: str,
        fact: str,
        category: Optional[str] = None,
        confidence: float = 1.0,
        embedding: Optional[List[float]] = None,
        user_context: str = ""
    ) -> tuple[Optional[Memory], str, str]:
        """
        Add a memory with quality judgment and deduplication.

        This is the NEW preferred way to add memories. It runs the memory through:
        1. Quality scoring (durability, specificity, actionability, novelty)
        2. Semantic similarity check with existing memories
        3. LLM judge decision (INSERT, UPDATE, CONSOLIDATE, REJECT)

        Args:
            session: Database session
            conversation_id: Conversation ID (can be None for manual memories)
            user_id: User ID
            fact: Memory content
            category: Memory category
            confidence: Confidence score
            embedding: Memory embedding vector (REQUIRED for judge)
            user_context: Additional context about user for quality scoring

        Returns:
            Tuple of (Memory or None, action_taken, reasoning)
            - Memory: The stored/updated memory (None if rejected)
            - action_taken: "INSERT", "UPDATE", "CONSOLIDATE", "REJECT"
            - reasoning: Judge's explanation
        """
        from database.memory_quality_judge import evaluate_memory

        if not embedding:
            # Fall back to old method if no embedding
            logger.warning("No embedding provided, skipping quality judge")
            memory, _ = await MemoryOps.add_memory(
                session, conversation_id, user_id, fact,
                category, confidence, embedding, skip_duplicate_check=False
            )
            return (memory, "INSERT_NO_JUDGE", "No embedding for quality judgment")

        # Get existing memories for similarity check
        existing_memories_objs = await MemoryOps.get_user_memories(
            session, user_id, limit=500  # Get recent memories for comparison
        )

        # Convert to dict format for judge
        existing_memories = [
            {
                "id": mem.id,
                "fact": mem.fact,
                "category": mem.category,
                "confidence": mem.confidence,
                "embedding": mem.embedding,
                "access_count": mem.access_count,
                "created_at": mem.created_at.isoformat() if mem.created_at else None
            }
            for mem in existing_memories_objs
        ]

        # Run through quality judge
        decision, quality_score = await evaluate_memory(
            candidate_fact=fact,
            candidate_category=category or "unknown",
            candidate_embedding=embedding,
            existing_memories=existing_memories,
            user_context=user_context
        )

        logger.info(
            f"[MemoryJudge] Decision: {decision.action} | "
            f"Quality: {quality_score.weighted_score:.2f}/10 | "
            f"Fact: '{fact[:60]}...'"
        )

        # Execute decision
        if decision.action == "REJECT":
            logger.info(f"[MemoryJudge] Rejected: {decision.reasoning}")
            return (None, "REJECT", decision.reasoning)

        elif decision.action == "INSERT":
            memory = Memory(
                conversation_id=conversation_id,
                user_id=user_id,
                fact=fact,
                category=category,
                confidence=confidence,
                embedding=embedding
            )
            session.add(memory)
            await session.commit()
            await session.refresh(memory)
            logger.info(f"[MemoryJudge] Inserted new memory: {memory.id}")
            return (memory, "INSERT", decision.reasoning)

        elif decision.action == "UPDATE" and decision.memory_id:
            # Replace existing memory
            await session.execute(
                update(Memory)
                .where(Memory.id == decision.memory_id)
                .values(
                    fact=fact,
                    category=category,
                    confidence=confidence,
                    embedding=embedding,
                    conversation_id=conversation_id,
                    last_accessed=utc_now_naive(),
                    access_count=Memory.access_count + 1
                )
            )
            await session.commit()

            # Fetch updated memory
            result = await session.execute(
                select(Memory).where(Memory.id == decision.memory_id)
            )
            memory = result.scalar_one()
            logger.info(f"[MemoryJudge] Updated memory {memory.id}: {decision.reasoning}")
            return (memory, "UPDATE", decision.reasoning)

        elif decision.action == "CONSOLIDATE" and decision.memory_id and decision.consolidated_fact:
            # Merge with existing memory
            await session.execute(
                update(Memory)
                .where(Memory.id == decision.memory_id)
                .values(
                    fact=decision.consolidated_fact,
                    confidence=max(confidence, 1.0),  # Boost confidence on consolidation
                    embedding=embedding,  # Use newer embedding
                    last_accessed=utc_now_naive(),
                    access_count=Memory.access_count + 1
                )
            )
            await session.commit()

            # Fetch consolidated memory
            result = await session.execute(
                select(Memory).where(Memory.id == decision.memory_id)
            )
            memory = result.scalar_one()
            logger.info(f"[MemoryJudge] Consolidated into memory {memory.id}: {decision.reasoning}")
            return (memory, "CONSOLIDATE", decision.reasoning)

        else:
            # Unknown action or missing data - reject
            logger.warning(f"[MemoryJudge] Unknown action or missing data: {decision.action}")
            return (None, "REJECT", "Invalid judge decision")

    @staticmethod
    async def find_duplicate_memory(
        session: AsyncSession,
        user_id: str,
        embedding: List[float],
        similarity_threshold: float = 0.92
    ) -> Optional[tuple[Memory, float]]:
        """
        Find duplicate memory using semantic similarity.

        Args:
            session: Database session
            user_id: User ID to search within
            embedding: Embedding of the new memory to check
            similarity_threshold: Minimum similarity to consider duplicate (0.92 = 92%)

        Returns:
            Tuple of (Memory, similarity_score) if duplicate found, None otherwise
        """
        import json

        # Convert embedding to JSON string for SQL
        embedding_json = json.dumps(embedding)

        # Use same cosine similarity query as semantic search
        # But with very high threshold (0.95+) to only catch near-duplicates
        conn = await session.connection()
        raw_conn = await conn.get_raw_connection()

        query_sql = """
            WITH query_embedding AS (
                SELECT $1::json AS emb
            ),
            similarities AS (
                SELECT
                    m.*,
                    (
                        -- Calculate dot product
                        (SELECT SUM((qe.value::float) * (me.value::float))
                         FROM json_array_elements_text((SELECT emb FROM query_embedding)) WITH ORDINALITY qe(value, idx)
                         JOIN json_array_elements_text(m.embedding) WITH ORDINALITY me(value, idx2) ON qe.idx = me.idx2
                        )
                        /
                        -- Divide by norms
                        (
                            SQRT((SELECT SUM(POWER(value::float, 2)) FROM json_array_elements_text((SELECT emb FROM query_embedding))))
                            *
                            SQRT((SELECT SUM(POWER(value::float, 2)) FROM json_array_elements_text(m.embedding)))
                        )
                    ) AS similarity
                FROM memories m
                WHERE m.user_id = $2
                  AND m.embedding IS NOT NULL
            )
            SELECT *
            FROM similarities
            WHERE similarity >= $3
            ORDER BY similarity DESC
            LIMIT 1
        """

        rows = await raw_conn.driver_connection.fetch(
            query_sql,
            embedding_json,
            user_id,
            similarity_threshold
        )

        if not rows:
            return None

        row = rows[0]
        memory = Memory(
            id=row['id'],
            conversation_id=row['conversation_id'],
            user_id=row['user_id'],
            fact=row['fact'],
            category=row['category'],
            confidence=row['confidence'] or 1.0,
            embedding=row['embedding'] if isinstance(row['embedding'], list) else (json.loads(row['embedding']) if row['embedding'] else None),
            created_at=row['created_at'],
            last_accessed=row['last_accessed'],
            access_count=row['access_count'] or 0
        )
        similarity = float(row['similarity']) if row.get('similarity') is not None else 0.0

        return (memory, similarity)

    @staticmethod
    async def add_memory(
        session: AsyncSession,
        conversation_id: str,
        user_id: str,
        fact: str,
        category: Optional[str] = None,
        confidence: float = 1.0,
        embedding: Optional[List[float]] = None,
        skip_duplicate_check: bool = False
    ) -> tuple[Memory, bool]:
        """
        Add a memory from a conversation.

        Args:
            session: Database session
            conversation_id: Conversation ID (can be None for manual memories)
            user_id: User ID
            fact: Memory content
            category: Memory category
            confidence: Confidence score
            embedding: Memory embedding vector
            skip_duplicate_check: Skip deduplication check (for bulk imports)

        Returns:
            Tuple of (Memory, is_duplicate) where is_duplicate=True if duplicate was found
        """
        # Check for duplicates if embedding is provided
        if embedding and not skip_duplicate_check:
            duplicate = await MemoryOps.find_duplicate_memory(
                session,
                user_id,
                embedding,
                similarity_threshold=0.92
            )

            if duplicate:
                existing_memory, similarity = duplicate
                logger.info(
                    f"[Dedup] Skipping duplicate memory: '{fact[:60]}...' "
                    f"(similarity: {similarity:.3f} to existing: '{existing_memory.fact[:60]}...')"
                )
                return (existing_memory, True)

        memory = Memory(
            conversation_id=conversation_id,
            user_id=user_id,
            fact=fact,
            category=category,
            confidence=confidence,
            embedding=embedding
        )
        session.add(memory)
        await session.commit()
        await session.refresh(memory)
        return (memory, False)  # Not a duplicate

    @staticmethod
    async def get_user_memories_count(
        session: AsyncSession,
        user_id: str,
        category: Optional[str] = None
    ) -> int:
        """Get total count of user's memories"""
        query = select(func.count(Memory.id)).where(Memory.user_id == user_id)

        if category:
            query = query.where(Memory.category == category)

        result = await session.execute(query)
        return result.scalar_one()

    @staticmethod
    async def get_user_memories(
        session: AsyncSession,
        user_id: str,
        category: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Memory]:
        """Get user's memories with pagination support"""
        query = select(Memory).where(Memory.user_id == user_id)

        if category:
            query = query.where(Memory.category == category)

        query = query.order_by(Memory.last_accessed.desc()).limit(limit).offset(offset)

        result = await session.execute(query)
        memories = result.scalars().all()

        # Update access count and last accessed
        if memories:
            memory_ids = [m.id for m in memories]
            await session.execute(
                update(Memory)
                .where(Memory.id.in_(memory_ids))
                .values(
                    access_count=Memory.access_count + 1,
                    last_accessed=utc_now_naive()
                )
            )
            await session.commit()

        return memories

    @staticmethod
    async def search_memories_semantic(
        session: AsyncSession,
        user_id: str,
        embedding: List[float],
        limit: int = 10,
        similarity_threshold: float = 0.7
    ) -> List[tuple[Memory, float]]:
        """
        Search memories by semantic similarity using pgvector HNSW index.

        Returns list of tuples (Memory, similarity_score) ordered by similarity.
        """
        from sqlalchemy import text

        # Convert embedding to halfvec format string
        # halfvec expects: '[val1,val2,val3,...]'
        halfvec_str = '[' + ','.join(str(v) for v in embedding) + ']'

        # Use pgvector's cosine distance operator (<=>)
        # cosine_distance = 1 - cosine_similarity, so similarity = 1 - distance
        query_sql = text("""
            SELECT
                id,
                conversation_id,
                user_id,
                fact,
                category,
                confidence,
                created_at,
                last_accessed,
                access_count,
                (1 - (embedding_halfvec <=> CAST(:embedding AS halfvec(3072)))) AS similarity
            FROM memories
            WHERE user_id = :user_id
              AND embedding_halfvec IS NOT NULL
              AND (1 - (embedding_halfvec <=> CAST(:embedding AS halfvec(3072)))) >= :threshold
            ORDER BY embedding_halfvec <=> CAST(:embedding AS halfvec(3072))
            LIMIT :limit
        """)

        result = await session.execute(
            query_sql,
            {
                "embedding": halfvec_str,
                "user_id": user_id,
                "threshold": similarity_threshold,
                "limit": limit
            }
        )

        # Convert to Memory objects with similarity scores
        rows = result.fetchall()
        memories_with_scores = []

        for row in rows:
            memory = Memory(
                id=row[0],
                conversation_id=row[1],
                user_id=row[2],
                fact=row[3],
                category=row[4],
                confidence=row[5] or 1.0,
                created_at=row[6],
                last_accessed=row[7],
                access_count=row[8] or 0
            )
            similarity = float(row[9]) if row[9] is not None else 0.0
            memories_with_scores.append((memory, similarity))

        # Update access count for retrieved memories
        if memories_with_scores:
            memory_ids = [m[0].id for m in memories_with_scores]
            await session.execute(
                update(Memory)
                .where(Memory.id.in_(memory_ids))
                .values(
                    access_count=Memory.access_count + 1,
                    last_accessed=utc_now_naive()
                )
            )
            await session.commit()

        return memories_with_scores


class UserPreferenceOps:
    """Operations for managing user preferences"""

    @staticmethod
    async def get_or_create_preferences(
        session: AsyncSession,
        user_id: str
    ) -> UserPreference:
        """Get or create user preferences"""
        query = select(UserPreference).where(UserPreference.user_id == user_id)
        result = await session.execute(query)
        pref = result.scalar_one_or_none()

        if not pref:
            pref = UserPreference(user_id=user_id)
            session.add(pref)
            await session.commit()
            await session.refresh(pref)

        return pref

    @staticmethod
    async def update_preferences(
        session: AsyncSession,
        user_id: str,
        **kwargs
    ) -> UserPreference:
        """Update user preferences"""
        pref = await UserPreferenceOps.get_or_create_preferences(session, user_id)

        for key, value in kwargs.items():
            if hasattr(pref, key):
                setattr(pref, key, value)

        pref.updated_at = utc_now_naive()
        await session.commit()
        await session.refresh(pref)
        return pref


class DocsOps:
    """Operations for managing documentation chunks"""

    @staticmethod
    async def search_docs_semantic(
        session: AsyncSession,
        embedding: List[float],
        limit: int = 5,
        similarity_threshold: float = 0.35
    ) -> List[tuple[DocChunk, float]]:
        """
        Search documentation chunks by semantic similarity using pgvector cosine distance.

        Args:
            session: Database session
            embedding: Query embedding vector
            limit: Maximum number of results to return
            similarity_threshold: Minimum similarity score (0.0-1.0)

        Returns:
            List of tuples (DocChunk, similarity_score) ordered by similarity.
        """
        import json

        # Convert embedding to halfvec string format
        halfvec_str = '[' + ','.join(str(v) for v in embedding) + ']'

        # Use direct SQL with asyncpg's native connection
        conn = await session.connection()
        raw_conn = await conn.get_raw_connection()

        # pgvector query using <=> operator (cosine distance)
        # cosine_distance = 1 - cosine_similarity, so similarity = 1 - distance
        query_sql = """
            SELECT
                dc.*,
                (1 - (dc.embedding_halfvec <=> CAST($1 AS halfvec))) AS similarity
            FROM doc_chunks dc
            WHERE dc.embedding_halfvec IS NOT NULL
              AND (1 - (dc.embedding_halfvec <=> CAST($1 AS halfvec))) >= $2
            ORDER BY dc.embedding_halfvec <=> CAST($1 AS halfvec)
            LIMIT $3
        """

        rows = await raw_conn.driver_connection.fetch(
            query_sql,
            halfvec_str,
            similarity_threshold,
            limit
        )

        # Convert to DocChunk objects with similarity scores
        chunks_with_scores = []
        for row in rows:
            chunk = DocChunk(
                id=row['id'],
                file_path=row['file_path'],
                chunk_index=row['chunk_index'],
                chunk_text=row['chunk_text'],
                chunk_tokens=row['chunk_tokens'] or 0,
                heading_context=row['heading_context'],
                embedding=row['embedding'] if isinstance(row['embedding'], list) else (json.loads(row['embedding']) if row['embedding'] else None),
                created_at=row['created_at'],
                updated_at=row['updated_at']
            )
            similarity = float(row['similarity']) if row.get('similarity') is not None else 0.0
            chunks_with_scores.append((chunk, similarity))

        logger.info(f"Found {len(chunks_with_scores)} documentation chunks with similarity >= {similarity_threshold}")
        if chunks_with_scores:
            logger.debug(f"Top result: {chunks_with_scores[0][0].file_path} (similarity: {chunks_with_scores[0][1]:.3f})")

        return chunks_with_scores