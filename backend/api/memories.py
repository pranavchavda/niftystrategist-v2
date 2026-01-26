"""
API endpoints for memory management
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from database import DatabaseManager, MemoryOps, MessageOps, ConversationOps
from memory.embedding_service import get_embedding_service
from agents.memory_extractor import get_memory_extractor
from agents.memory_extractor_langextract import get_langextract_memory_extractor
from auth import get_current_user, User
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["memories"])


# Request/Response Models
class MemoryResponse(BaseModel):
    """Memory response model"""
    id: int
    content: str
    category: str
    tags: List[str] = []
    created_at: datetime
    updated_at: datetime
    confidence: float


class MemoriesListResponse(BaseModel):
    """List of memories"""
    memories: List[MemoryResponse]
    total: int


class CreateMemoryRequest(BaseModel):
    """Create memory request"""
    content: str
    category: str
    tags: List[str] = []


class UpdateMemoryRequest(BaseModel):
    """Update memory request"""
    content: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None


class ExtractMemoriesResponse(BaseModel):
    """Response from memory extraction"""
    extracted_count: int
    summary: str
    memories: List[MemoryResponse]


# Database manager (injected from main.py)
_db_manager = None

def get_db_manager():
    """Get the database manager instance"""
    if _db_manager is None:
        import os
        from database import DatabaseManager
        DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://espressobot:localdev123@localhost:5432/espressobot_pydantic')
        logger.warning(f"Database manager not injected, creating new one")
        return DatabaseManager(DATABASE_URL)
    return _db_manager


async def get_db():
    """Get database session"""
    db_manager = get_db_manager()
    async with db_manager.async_session() as session:
        yield session


@router.get("/memories")
@router.get("/memory/all")  # Legacy alias for backward compatibility
async def list_memories(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    category: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0)
):
    """List user's memories with pagination"""
    logger.info(f"Listing memories for user: {user.email}, category: {category}, limit: {limit}, offset: {offset}")

    # Get total count (before limit/offset)
    total_count = await MemoryOps.get_user_memories_count(
        db, user.email, category=category
    )

    # Get memories with pagination
    memories = await MemoryOps.get_user_memories(
        db, user.email, category=category, limit=limit, offset=offset
    )

    return {
        "memories": [
            {
                "id": mem.id,
                "content": mem.fact,
                "category": mem.category or "fact",
                "tags": [],  # TODO: Add tags support
                "created_at": mem.created_at.isoformat() if mem.created_at else None,
                "updated_at": mem.last_accessed.isoformat() if mem.last_accessed else None,
                "confidence": mem.confidence or 1.0
            }
            for mem in memories
        ],
        "total": total_count,  # Actual total count in database
        "showing": len(memories),  # How many we're returning
        "limit": limit,
        "offset": offset
    }


@router.post("/memories")
async def create_memory(
    request: CreateMemoryRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new memory manually"""
    logger.info(f"Creating manual memory for user: {user.email}")

    # Generate embedding
    embedding_service = get_embedding_service()
    embedding_result = await embedding_service.get_embedding(request.content)

    # Create memory (with deduplication check)
    memory, is_duplicate = await MemoryOps.add_memory(
        session=db,
        conversation_id=None,  # No specific conversation for manual memories
        user_id=user.email,
        fact=request.content,
        category=request.category,
        confidence=1.0,  # Manual memories have full confidence
        embedding=embedding_result.embedding
    )

    response = {
        "id": memory.id,
        "content": memory.fact,
        "category": memory.category,
        "tags": request.tags,
        "created_at": memory.created_at.isoformat(),
        "updated_at": memory.last_accessed.isoformat(),
        "confidence": memory.confidence
    }

    if is_duplicate:
        response["is_duplicate"] = True
        response["message"] = "This memory already exists (duplicate detected)"

    return response


@router.patch("/memories/{memory_id}")
async def update_memory(
    memory_id: int,
    request: UpdateMemoryRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update an existing memory"""
    logger.info(f"Updating memory {memory_id} for user: {user.email}")

    # TODO: Implement update logic
    # For now, return success
    return {"status": "success", "message": "Memory update not yet implemented"}


@router.delete("/memories/{memory_id}")
async def delete_memory(
    memory_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a memory"""
    from database.models import Memory
    from sqlalchemy import select, delete

    logger.info(f"Deleting memory {memory_id} for user: {user.email}")

    # Verify memory belongs to user
    query = select(Memory).where(
        Memory.id == memory_id,
        Memory.user_id == user.email
    )
    result = await db.execute(query)
    memory = result.scalar_one_or_none()

    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")

    # Delete memory
    await db.execute(
        delete(Memory).where(Memory.id == memory_id)
    )
    await db.commit()

    return {"status": "success"}


class BulkDeleteRequest(BaseModel):
    """Bulk delete request"""
    memory_ids: List[int]


class SimilarMemoryResponse(BaseModel):
    """Similar memory with similarity score"""
    id: int
    content: str
    category: str
    similarity: float
    created_at: datetime
    updated_at: datetime
    confidence: float


class SimilarMemoriesResponse(BaseModel):
    """Response for similar memories search"""
    original_memory_id: int
    similar_memories: List[SimilarMemoryResponse]


@router.post("/memories/bulk-delete")
async def bulk_delete_memories(
    request: BulkDeleteRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete multiple memories at once"""
    from database.models import Memory
    from sqlalchemy import select, delete

    logger.info(f"Bulk deleting {len(request.memory_ids)} memories for user: {user.email}")

    if not request.memory_ids:
        raise HTTPException(status_code=400, detail="No memory IDs provided")

    # Verify all memories belong to user
    query = select(Memory.id).where(
        Memory.id.in_(request.memory_ids),
        Memory.user_id == user.email
    )
    result = await db.execute(query)
    valid_ids = [row[0] for row in result.fetchall()]

    if len(valid_ids) != len(request.memory_ids):
        raise HTTPException(
            status_code=403,
            detail=f"Some memories not found or don't belong to user. Found {len(valid_ids)} of {len(request.memory_ids)}"
        )

    # Delete memories
    await db.execute(
        delete(Memory).where(Memory.id.in_(valid_ids))
    )
    await db.commit()

    logger.info(f"Successfully deleted {len(valid_ids)} memories")
    return {"status": "success", "deleted_count": len(valid_ids)}


@router.get("/memories/{memory_id}/similar")
async def find_similar_memories(
    memory_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(10, ge=1, le=50),
    threshold: float = Query(0.7, ge=0.0, le=1.0)
):
    """Find semantically similar memories to a given memory"""
    from database.models import Memory
    from sqlalchemy import select

    logger.info(f"Finding similar memories for memory {memory_id}, user: {user.email}")

    # Get the original memory
    query = select(Memory).where(
        Memory.id == memory_id,
        Memory.user_id == user.email
    )
    result = await db.execute(query)
    original_memory = result.scalar_one_or_none()

    if not original_memory:
        raise HTTPException(status_code=404, detail="Memory not found")

    if not original_memory.embedding:
        raise HTTPException(status_code=400, detail="Memory has no embedding for similarity search")

    # Search for similar memories
    similar_memories_with_scores = await MemoryOps.search_memories_semantic(
        session=db,
        user_id=user.email,
        embedding=original_memory.embedding,
        limit=limit + 1,  # +1 because we'll filter out the original
        similarity_threshold=threshold
    )

    # Filter out the original memory and format response
    similar_memories = [
        {
            "id": mem.id,
            "content": mem.fact,
            "category": mem.category or "fact",
            "similarity": round(score, 4),
            "created_at": mem.created_at.isoformat() if mem.created_at else None,
            "updated_at": mem.last_accessed.isoformat() if mem.last_accessed else None,
            "confidence": mem.confidence or 1.0
        }
        for mem, score in similar_memories_with_scores
        if mem.id != memory_id  # Exclude the original memory
    ][:limit]  # Ensure we only return requested limit

    logger.info(f"Found {len(similar_memories)} similar memories")

    return {
        "original_memory_id": memory_id,
        "similar_memories": similar_memories
    }


@router.post("/conversations/{conversation_id}/extract-memories")
async def extract_memories(
    conversation_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Extract memories from a conversation"""
    logger.info(f"Extracting memories from conversation {conversation_id}")

    # Verify conversation belongs to user
    conversation = await ConversationOps.get_conversation(
        db, conversation_id, user.email
    )

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Get conversation messages
    messages = await MessageOps.get_messages(db, conversation_id, limit=None)

    if not messages:
        raise HTTPException(status_code=400, detail="No messages in conversation")

    # Format messages for extraction
    conversation_history = [
        {
            "role": msg.role,
            "content": msg.content
        }
        for msg in messages
    ]

    # Extract memories - using Grok 4 Fast (langextract has too many issues)
    import os
    use_langextract = False  # Disabled - use Grok 4 Fast instead
    model_id = os.getenv("MEMORY_EXTRACTION_MODEL", "gpt-4.1-mini")  # Good balance of speed and quality

    if use_langextract:
        logger.info(f"Using langextract with model: {model_id}")
        memory_extractor = get_langextract_memory_extractor(model_id=model_id)

        # Format conversation for langextract (plain text)
        conversation_text = "\n".join([
            f"{msg['role'].capitalize()}: {msg['content']}"
            for msg in conversation_history
        ])

        extraction_result = await memory_extractor.extract_memories(
            conversation_text=conversation_text,
            user_id=user.email
        )
    else:
        logger.info("Using Grok 4 Fast extractor (legacy)")
        memory_extractor = get_memory_extractor()
        extraction_result = await memory_extractor.extract_memories(
            conversation_history=conversation_history,
            conversation_id=conversation_id
        )

    # Get embedding service
    embedding_service = get_embedding_service()

    # Store extracted memories with quality judgment
    stored_memories = []
    rejected_count = 0
    updated_count = 0
    consolidated_count = 0

    for extracted_mem in extraction_result.memories:
        # Skip ephemeral memories
        if getattr(extracted_mem, 'is_ephemeral', False):
            logger.info(f"[Filtered] Skipped ephemeral: {extracted_mem.fact[:60]}...")
            continue

        # Generate embedding
        embedding_result = await embedding_service.get_embedding(extracted_mem.fact)

        # Store in database with quality judge
        memory, action, reasoning = await MemoryOps.add_memory_with_judge(
            session=db,
            conversation_id=conversation_id,
            user_id=user.email,
            fact=extracted_mem.fact,
            category=extracted_mem.category,
            confidence=extracted_mem.confidence,
            embedding=embedding_result.embedding,
            user_context=f"iDrinkCoffee.com business context"  # Could be enhanced
        )

        if action == "REJECT":
            rejected_count += 1
            logger.info(f"[Judge] Rejected: {extracted_mem.fact[:60]}... | Reason: {reasoning}")
            continue

        if action == "UPDATE":
            updated_count += 1
            logger.info(f"[Judge] Updated memory {memory.id}: {reasoning}")
        elif action == "CONSOLIDATE":
            consolidated_count += 1
            logger.info(f"[Judge] Consolidated into memory {memory.id}: {reasoning}")
        else:  # INSERT
            logger.info(f"[Judge] Inserted new memory {memory.id}: {reasoning}")

        stored_memories.append({
            "id": memory.id,
            "content": memory.fact,
            "category": memory.category,
            "tags": [],
            "created_at": memory.created_at.isoformat(),
            "updated_at": memory.last_accessed.isoformat(),
            "confidence": memory.confidence,
            "action": action  # Include action for transparency
        })

        logger.info(
            f"[Memory] {action}: {memory.fact[:50]}... "
            f"(category: {memory.category}, confidence: {memory.confidence})"
        )

    logger.info(
        f"[Memory] Extraction complete: {len(stored_memories)} stored "
        f"(rejected: {rejected_count}, updated: {updated_count}, consolidated: {consolidated_count})"
    )

    # Update conversation title with emoji + topic summary (don't update timestamp)
    if extraction_result.summary:
        await ConversationOps.update_conversation_title(
            db, conversation_id, user.email, extraction_result.summary,
            update_timestamp=False  # Don't change updated_at for memory extraction
        )
        logger.info(f"[Memory] Updated conversation title: {extraction_result.summary}")

    return {
        "extracted_count": len(stored_memories),
        "rejected_count": rejected_count,
        "updated_count": updated_count,
        "consolidated_count": consolidated_count,
        "summary": extraction_result.summary,
        "memories": stored_memories
    }
