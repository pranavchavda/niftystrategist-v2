"""
API endpoints for conversation management
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Body, Request as FastAPIRequest
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import uuid
import os

from database import (
    DatabaseManager,
    ConversationOps,
    MessageOps,
    MemoryOps
)
from auth import get_current_user, User
import logging

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/api/conversations", tags=["conversations"])

@router.get("/debug-db")
async def debug_db():
    """Debug endpoint to check database connection"""
    from database.operations import ConversationOps
    from database import Conversation
    from sqlalchemy import select

    db_manager = get_db_manager()
    result = {
        "db_manager_injected": _db_manager is not None,
        "db_manager_type": type(_db_manager).__name__ if _db_manager else None,
        "db_url": str(_db_manager.engine.url) if _db_manager else None
    }

    # Test direct database access
    async with db_manager.async_session() as session:
        # Test with ConversationOps
        conversations = await ConversationOps.list_conversations(
            session,
            user_id="dev@localhost",
            limit=10,
            offset=0,
            include_archived=False
        )
        result["conversations_ops_count"] = len(conversations)

        # Test with direct query
        query = select(Conversation)
        db_result = await session.execute(query)
        all_convs = db_result.scalars().all()
        result["total_in_db"] = len(all_convs)
        result["all_users"] = list(set(c.user_id for c in all_convs))

    return result


# Request/Response models
class ConversationResponse(BaseModel):
    """Conversation response model"""
    id: str
    user_id: str
    title: Optional[str]
    created_at: datetime
    updated_at: datetime
    is_starred: bool
    is_archived: bool
    summary: Optional[str]
    message_count: Optional[int] = 0


class MessageResponse(BaseModel):
    """Message response model"""
    id: int
    message_id: str
    role: str
    content: str
    timestamp: datetime
    attachments: List
    tool_calls: List
    reasoning: Optional[str] = None  # Include reasoning/thinking content
    edited_at: Optional[datetime] = None  # Timestamp when message was edited


class UpdateMessageRequest(BaseModel):
    """Request model for updating a message"""
    content: str
    checkpoint_mode: bool = True  # Delete subsequent messages (like ChatGPT/Claude)


class UpdateTimelineRequest(BaseModel):
    """Request model for updating message timeline (temporal order of events)"""
    timeline: List[dict]  # List of timeline entries: {type, id, content/data, timestamp}


class ConversationListResponse(BaseModel):
    """List of conversations"""
    conversations: List[ConversationResponse]
    total: int
    has_more: bool


class UpdateConversationRequest(BaseModel):
    """Update conversation request"""
    title: Optional[str] = None
    is_starred: Optional[bool] = None
    is_archived: Optional[bool] = None


class ForkConversationRequest(BaseModel):
    """Fork conversation request"""
    fork_from_message_id: Optional[str] = None  # If provided, fork only up to this message


@router.post("/debug-fork-request")
async def debug_fork_request(request: ForkConversationRequest):
    """Debug endpoint to test request body parsing"""
    return {
        "received": request.model_dump(),
        "fork_from_message_id": request.fork_from_message_id,
        "fork_from_message_id_is_none": request.fork_from_message_id is None
    }


class ForkConversationResponse(BaseModel):
    """Fork conversation response"""
    new_thread_id: str
    new_title: str
    fork_summary: str


# Database manager will be injected from main.py
_db_manager = None

def get_db_manager():
    """Get the database manager instance"""
    if _db_manager is None:
        # Fallback if not yet injected
        import os
        from database import DatabaseManager
        from dotenv import load_dotenv
        # Load .env file
        load_dotenv()
        DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://espressobot:localdev123@localhost:5432/espressobot_pydantic')
        logger.warning(f"Database manager not injected, creating new one with URL: {DATABASE_URL[:30]}...")
        return DatabaseManager(DATABASE_URL)
    logger.debug(f"Using injected database manager")
    return _db_manager

# Dependency to get database session
async def get_db():
    """Get database session"""
    db_manager = get_db_manager()
    async with db_manager.async_session() as session:
        yield session

@router.get("/test-simple")
async def test_simple(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Simple test endpoint"""
    conversations = await ConversationOps.list_conversations(
        db, user.email, 10, 0, False
    )
    return {"count": len(conversations), "user": user.email}


@router.get("/")
async def list_conversations(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    include_archived: bool = False
):
    """List user's conversations"""
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Listing conversations for user: {user.email}")

    conversations = await ConversationOps.list_conversations(
        db, user.email, limit, offset, include_archived
    )
    logger.info(f"Found {len(conversations)} conversations for {user.email}")

    # Get total count
    total = len(conversations)  # Would use COUNT query in production

    # Return plain dict for debugging
    return {
        "conversations": [
            {
                "id": conv.id,
                "user_id": conv.user_id,
                "title": conv.title,
                "created_at": conv.created_at.isoformat() + 'Z' if conv.created_at else None,
                "updated_at": conv.updated_at.isoformat() + 'Z' if conv.updated_at else None,
                "is_starred": conv.is_starred,
                "is_archived": conv.is_archived,
                "summary": conv.summary,
                "message_count": 0  # Simplified for now
            }
            for conv in conversations
        ],
        "total": total,
        "has_more": (offset + limit) < total
    }


@router.get("/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific conversation with messages (for frontend compatibility)"""
    conversation = await ConversationOps.get_conversation(
        db, conversation_id, user.email, include_messages=True
    )

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Format messages for frontend and calculate token usage
    messages = []
    total_input_tokens = 0
    total_output_tokens = 0
    if conversation.messages:
        for msg in conversation.messages:
            messages.append({
                "id": msg.message_id,  # Frontend expects string ID
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat() + 'Z' if msg.timestamp else None,
                "attachments": msg.attachments or [],
                "tool_calls": msg.tool_calls or [],
                "reasoning": msg.reasoning,  # Extended thinking
                "timeline": msg.timeline or [],  # Temporal order of events
                "input_tokens": msg.input_tokens,
                "output_tokens": msg.output_tokens
            })
            # Sum up tokens
            if msg.input_tokens:
                total_input_tokens += msg.input_tokens
            if msg.output_tokens:
                total_output_tokens += msg.output_tokens

    # Determine if user should consider forking
    warning_threshold = 100000
    should_fork = total_input_tokens >= warning_threshold
    warning_message = None
    if total_input_tokens >= warning_threshold:
        warning_message = f"This conversation has used {total_input_tokens:,} input tokens. Consider forking to a new conversation."
    elif total_input_tokens >= warning_threshold * 0.8:
        warning_message = f"Approaching {warning_threshold:,} input tokens ({total_input_tokens:,} used). Consider forking soon."

    # Return in the format the frontend expects
    return {
        "id": conversation.id,
        "user_id": conversation.user_id,
        "title": conversation.title,
        "created_at": conversation.created_at.isoformat() + 'Z' if conversation.created_at else None,
        "updated_at": conversation.updated_at.isoformat() + 'Z' if conversation.updated_at else None,
        "is_starred": conversation.is_starred,
        "is_archived": conversation.is_archived,
        "summary": conversation.summary,
        "messages": messages,
        "tasks": [],  # Placeholder for tasks
        "fetchedTaskMarkdown": None,  # Placeholder for task markdown
        # Token usage info
        "token_usage": {
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "total_tokens": total_input_tokens + total_output_tokens,
            "warning_threshold": warning_threshold,
            "should_fork": should_fork,
            "warning_message": warning_message
        }
    }


@router.get("/{conversation_id}/messages", response_model=List[MessageResponse])
async def get_messages(
    conversation_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: Optional[int] = Query(None, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """Get messages for a conversation"""
    # Verify conversation belongs to user
    conversation = await ConversationOps.get_conversation(
        db, conversation_id, user.email
    )

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = await MessageOps.get_messages(
        db, conversation_id, limit, offset
    )

    return [
        MessageResponse(
            id=msg.id,
            message_id=msg.message_id,
            role=msg.role,
            content=msg.content,
            timestamp=msg.timestamp,
            attachments=msg.attachments,
            tool_calls=msg.tool_calls,
            reasoning=msg.reasoning,  # Include reasoning if present
            edited_at=msg.edited_at  # Include edit timestamp
        )
        for msg in messages
    ]


@router.patch("/{conversation_id}/messages/{message_id}")
async def update_message(
    conversation_id: str,
    message_id: str,
    update_req: UpdateMessageRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update the content of a message.

    Only user messages can be edited. Assistant and system messages cannot be modified.
    """
    # Verify conversation belongs to user
    conversation = await ConversationOps.get_conversation(
        db, conversation_id, user.email
    )

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Get the message to verify it's a user message
    message = await MessageOps.get_message_by_id(db, conversation_id, message_id)

    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    if message.role != "user":
        raise HTTPException(
            status_code=400,
            detail="Only user messages can be edited"
        )

    # Validate content is not empty
    if not update_req.content.strip():
        raise HTTPException(status_code=400, detail="Message content cannot be empty")

    # Update the message (with checkpoint mode to delete subsequent messages)
    updated_message, deleted_count = await MessageOps.update_message(
        db, conversation_id, message_id, update_req.content.strip(),
        checkpoint_mode=update_req.checkpoint_mode
    )

    if not updated_message:
        raise HTTPException(status_code=404, detail="Message not found")

    logger.info(f"User {user.email} updated message {message_id} in conversation {conversation_id} (deleted {deleted_count} subsequent messages)")

    return {
        "status": "success",
        "checkpoint_mode": update_req.checkpoint_mode,
        "deleted_count": deleted_count,
        "message": {
            "id": updated_message.id,
            "message_id": updated_message.message_id,
            "content": updated_message.content,
            "edited_at": updated_message.edited_at.isoformat() + 'Z' if updated_message.edited_at else None
        }
    }


@router.patch("/{conversation_id}/messages/{message_id}/timeline")
async def update_message_timeline(
    conversation_id: str,
    message_id: str,
    update_req: UpdateTimelineRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update the timeline of a message (temporal order of events).

    This is used by the frontend to persist the temporal ordering of
    reasoning, tool calls, and text content as they occurred during streaming.
    Only assistant messages can have their timeline updated.
    """
    # Verify conversation belongs to user
    conversation = await ConversationOps.get_conversation(
        db, conversation_id, user.email
    )

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Get the message
    message = await MessageOps.get_message_by_id(db, conversation_id, message_id)

    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    if message.role != "assistant":
        raise HTTPException(
            status_code=400,
            detail="Only assistant messages can have timeline updated"
        )

    # Update the timeline
    message.timeline = update_req.timeline
    await db.commit()
    await db.refresh(message)

    logger.info(f"Updated timeline for message {message_id} with {len(update_req.timeline)} entries")

    return {
        "status": "success",
        "message_id": message_id,
        "timeline_entries": len(update_req.timeline)
    }


@router.delete("/{conversation_id}/messages/{message_id}")
async def delete_message(
    conversation_id: str,
    message_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a message from a conversation.

    Only user messages can be deleted. Assistant and system messages cannot be deleted
    to preserve conversation context and integrity.
    """
    # Verify conversation belongs to user
    conversation = await ConversationOps.get_conversation(
        db, conversation_id, user.email
    )

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Get the message to verify it's a user message
    message = await MessageOps.get_message_by_id(db, conversation_id, message_id)

    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    if message.role != "user":
        raise HTTPException(
            status_code=400,
            detail="Only user messages can be deleted"
        )

    # Delete the message and all subsequent messages (checkpoint behavior)
    deleted, deleted_count = await MessageOps.delete_message(db, conversation_id, message_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Message not found")

    logger.info(f"User {user.email} deleted message {message_id} and {deleted_count - 1} subsequent messages from conversation {conversation_id}")

    return {
        "status": "success",
        "message_id": message_id,
        "deleted_count": deleted_count  # Total messages deleted (including the target message)
    }


@router.patch("/{conversation_id}")
async def update_conversation(
    conversation_id: str,
    update_req: UpdateConversationRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update conversation metadata"""
    # Verify conversation exists
    conversation = await ConversationOps.get_conversation(
        db, conversation_id, user.email
    )

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Update fields
    if update_req.title is not None:
        await ConversationOps.update_conversation_title(
            db, conversation_id, user.email, update_req.title
        )

    if update_req.is_starred is not None:
        await ConversationOps.star_conversation(
            db, conversation_id, user.email, update_req.is_starred
        )

    if update_req.is_archived is not None:
        await ConversationOps.archive_conversation(
            db, conversation_id, user.email, update_req.is_archived
        )

    return {"status": "success"}


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a conversation"""
    deleted = await ConversationOps.delete_conversation(
        db, conversation_id, user.email
    )

    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return {"status": "success"}


@router.get("/search")
async def search_conversations(
    q: str = Query(..., min_length=1),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(20, ge=1, le=100)
):
    """Search conversations"""
    conversations = await ConversationOps.search_conversations(
        db, user.email, q, limit
    )

    return {
        "results": [
            ConversationResponse(
                id=conv.id,
                user_id=conv.user_id,
                title=conv.title,
                created_at=conv.created_at,
                updated_at=conv.updated_at,
                is_starred=conv.is_starred,
                is_archived=conv.is_archived,
                summary=conv.summary
            )
            for conv in conversations
        ],
        "query": q,
        "count": len(conversations)
    }


@router.post("/{conversation_id}/star")
async def star_conversation(
    conversation_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Star a conversation"""
    success = await ConversationOps.star_conversation(
        db, conversation_id, user.email, True
    )

    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return {"status": "success"}


@router.post("/{conversation_id}/unstar")
async def unstar_conversation(
    conversation_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Unstar a conversation"""
    success = await ConversationOps.star_conversation(
        db, conversation_id, user.email, False
    )

    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return {"status": "success"}


@router.get("/{conversation_id}/cache/stats")
async def get_cache_stats(
    conversation_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get tool call cache statistics for a conversation.

    Returns:
        - total_entries: Total cache entries (valid + invalid)
        - valid_entries: Currently valid cache entries
        - invalid_entries: Invalidated cache entries
        - total_tokens_saved: Estimated tokens saved by caching
        - total_time_saved_ms: Total execution time saved (milliseconds)
        - total_time_saved_seconds: Total execution time saved (seconds)
        - invalidation_count: Number of invalidation operations
    """
    # Verify conversation belongs to user
    conversation = await ConversationOps.get_conversation(
        db, conversation_id, user.email
    )

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Get cache statistics
    from tools.native.tool_cache import ToolCache
    cache = ToolCache(conversation_id)
    stats = cache.get_stats()

    return stats


@router.get("/{conversation_id}/cache/entries")
async def get_cache_entries(
    conversation_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    query: Optional[str] = Query(None, description="Search query to filter entries")
):
    """
    List cache entries for a conversation (summaries only, no full results).

    Args:
        query: Optional search term to filter entries by tool name, summary, or parameters

    Returns:
        List of cache entry summaries with metadata (excluding full result data)
    """
    # Verify conversation belongs to user
    conversation = await ConversationOps.get_conversation(
        db, conversation_id, user.email
    )

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Get cache entries
    from tools.native.tool_cache import ToolCache
    cache = ToolCache(conversation_id)
    entries = cache.lookup(query)

    return {
        "entries": entries,
        "count": len(entries),
        "query": query
    }


@router.delete("/{conversation_id}/cache")
async def clear_cache(
    conversation_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Clear all cache entries for a conversation.

    Use this to free up storage or force fresh data retrieval.
    """
    # Verify conversation belongs to user
    conversation = await ConversationOps.get_conversation(
        db, conversation_id, user.email
    )

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Clear cache
    from tools.native.tool_cache import ToolCache
    cache = ToolCache(conversation_id)
    cache.clear()

    return {"status": "success", "message": "Cache cleared"}


async def generate_conversation_summary(messages: List, conversation_title: str) -> str:
    """
    Generate a comprehensive summary of a conversation using an LLM.

    Args:
        messages: List of message objects from the conversation
        conversation_title: Title of the conversation being forked

    Returns:
        A markdown-formatted comprehensive summary with recent messages
    """
    # Format ALL messages for the summary prompt
    conversation_text = f"# Original Conversation: {conversation_title}\n\n"

    for msg in messages:
        role = msg.role.capitalize()
        content = msg.content
        conversation_text += f"**{role}:** {content}\n\n"

    # Get last 5 messages for verbatim inclusion
    last_messages = messages[-5:] if len(messages) > 5 else messages
    last_messages_text = "## Recent Messages (Last 5)\n\n"
    for msg in last_messages:
        role = msg.role.capitalize()
        content = msg.content
        last_messages_text += f"**{role}:** {content}\n\n"

    # Create summary prompt
    summary_prompt = f"""You are creating a comprehensive summary of a conversation that is being "forked" into a new conversation.

CRITICAL: This summary must capture ALL important context so the new conversation can continue seamlessly with full awareness of what happened.

Here is the FULL conversation to summarize:

{conversation_text}

Create a detailed summary with these sections:

1. **Overview**: What was this conversation about? What was the user trying to accomplish?
2. **Key Context**: Important background, constraints, requirements, or decisions
3. **Technical Details**: Specific implementations, file paths, commands, code snippets, configurations
4. **Current State**: What was completed? What remains? Where did we leave off?
5. **Important Facts**: Specific requirements, preferences, constraints to remember

Be thorough and specific - include file paths, command examples, specific decisions made. This summary is the ONLY context the new conversation will have.

Format in clear markdown. Be comprehensive."""

    try:
        # Use minimax/minimax-m2 for cost-effective, fast summarization
        import httpx

        openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
        if not openrouter_api_key:
            raise ValueError("OPENROUTER_API_KEY not found")

        logger.info(f"Generating fork summary with minimax-m2 for {len(messages)} messages")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {openrouter_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "minimax/minimax-m2",
                    "messages": [
                        {"role": "user", "content": summary_prompt}
                    ],
                    "max_tokens": 4000,
                    "temperature": 1,
                    "top_p": 0.95,
                    "reasoning": {"enabled": True}  # Reasoning is mandatory for paid tier
                },
                timeout=60.0
            )

            if response.status_code == 200:
                result = response.json()
                ai_summary = result["choices"][0]["message"]["content"]

                # Combine AI summary with last 5 messages verbatim
                full_summary = f"{ai_summary}\n\n---\n\n{last_messages_text}"

                logger.info(f"Generated conversation summary ({len(full_summary)} chars) using minimax-m2 (paid tier)")
                return full_summary
            else:
                error_text = response.text
                logger.error(f"OpenRouter API error: {response.status_code} - {error_text}")
                raise Exception(f"OpenRouter API error: {response.status_code}")

    except Exception as e:
        logger.error(f"Failed to generate summary with minimax-m2: {e}", exc_info=True)

        # Fallback: Create a basic summary with last messages
        fallback_summary = f"""# Forked from: {conversation_title}

This conversation is a continuation of the previous conversation.

**Message Count:** {len(messages)} messages

**Note:** Automated summary generation failed. See recent messages below for context.

---

{last_messages_text}"""

        return fallback_summary


@router.post("/{conversation_id}/fork", response_model=ForkConversationResponse)
async def fork_conversation(
    conversation_id: str,
    request: ForkConversationRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Fork a conversation into a new one with a comprehensive summary.

    Similar to Claude Code's /compact feature, this creates a fresh conversation
    while preserving all important context from the original through an AI-generated summary.

    If fork_from_message_id is provided, only messages up to and including that message
    will be included in the fork (message-level forking).

    The summary becomes the first system-like message in the new conversation,
    providing complete context for continuing the discussion.

    Returns:
        new_thread_id: ID of the newly created conversation
        new_title: Title of the new conversation
        fork_summary: The generated summary text
    """
    logger.info(f"Forking conversation {conversation_id} for user {user.email}")
    logger.info(f"Fork request: {request}")
    if request:
        logger.info(f"Fork from message ID: {request.fork_from_message_id}")
    else:
        logger.info("No request body received - will fork entire conversation")

    # Get the source conversation with all messages
    source_conversation = await ConversationOps.get_conversation(
        db, conversation_id, user.email, include_messages=True
    )

    if not source_conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if not source_conversation.messages or len(source_conversation.messages) == 0:
        raise HTTPException(status_code=400, detail="Cannot fork an empty conversation")

    # Filter messages if fork_from_message_id is provided
    messages_to_fork = source_conversation.messages
    if request and request.fork_from_message_id:
        # Find the index of the target message
        fork_index = None
        for idx, msg in enumerate(source_conversation.messages):
            if msg.message_id == request.fork_from_message_id:
                fork_index = idx
                break

        if fork_index is None:
            raise HTTPException(
                status_code=400,
                detail=f"Message {request.fork_from_message_id} not found in conversation"
            )

        # Include messages up to and including the target message
        messages_to_fork = source_conversation.messages[:fork_index + 1]
        logger.info(f"Forking from message {request.fork_from_message_id}: using {len(messages_to_fork)}/{len(source_conversation.messages)} messages")

    # Generate hybrid LLM→JSON→TOON compressed context
    # Pipeline options:
    # 1. Default: Grok 4.1 Fast → JSON → TOON (fast, cheap)
    # 2. use_langextract=True: LangExtract + Gemini → Schema-enforced JSON → TOON (lossless)
    logger.info(f"Generating hybrid LLM→TOON context for {len(messages_to_fork)} messages")

    # Import hybrid TOON converter
    from utils.toon_converter import create_hybrid_fork_summary

    # Configuration: Choose extraction method
    # - False (default): Grok 4.1 Fast - single API call, ~2-5 seconds, reliable
    # - True: LangExtract - schema-enforced but unreliable (JSON parsing errors)
    USE_LANGEXTRACT = False  # Grok 4.1 Fast - reliable and fast

    # Create hybrid compressed summary
    fork_summary = await create_hybrid_fork_summary(
        messages_to_fork,
        source_conversation.title or "Untitled Conversation",
        fork_from_message_id=request.fork_from_message_id if request else None,
        use_gemini=False,  # Only used if use_langextract=False
        use_langextract=USE_LANGEXTRACT  # LangExtract for lossless, schema-enforced extraction
    )

    extraction_method = "LangExtract + Gemini 2.5 Flash (lossless)" if USE_LANGEXTRACT else "Grok 4.1 Fast"
    logger.info(f"Fork summary created with {extraction_method} → TOON encoding")

    # Generate new thread ID
    new_thread_id = f"thread_{uuid.uuid4().hex[:16]}"

    # Create the forked conversation
    new_conversation = await ConversationOps.fork_conversation(
        db,
        source_thread_id=conversation_id,
        new_thread_id=new_thread_id,
        user_id=user.email,
        fork_summary=fork_summary
    )

    # Add summary as the only message in the forked conversation
    # The summary already contains context from all messages including the last few
    await MessageOps.add_message(
        db,
        conversation_id=new_thread_id,
        message_id=f"msg_{uuid.uuid4().hex[:12]}",
        role="system",
        content=f"**Context from previous conversation:**\n\n{fork_summary}"
    )

    logger.info(f"Successfully forked conversation {conversation_id} -> {new_thread_id}: summarized all {len(messages_to_fork)} messages")

    return ForkConversationResponse(
        new_thread_id=new_thread_id,
        new_title=new_conversation.title,
        fork_summary=fork_summary
    )


# Response model for token usage
class TokenUsageResponse(BaseModel):
    """Token usage statistics for a conversation"""
    conversation_id: str
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int
    message_count: int
    warning_threshold: int = 100000  # Suggest fork when approaching this
    should_fork: bool = False
    warning_message: Optional[str] = None


@router.get("/{conversation_id}/token-usage")
async def get_conversation_token_usage(
    conversation_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get token usage statistics for a conversation.

    Returns the estimated context size (all messages that would be sent to the LLM)
    and whether the user should consider forking.

    Note: "input_tokens" here represents the cumulative context size, not per-message input.
    This is because each LLM call receives ALL previous messages as context.
    """
    from sqlalchemy import select, func
    from database.models import Message, Conversation

    # Token estimation using tiktoken
    try:
        import tiktoken
        encoding = tiktoken.get_encoding("cl100k_base")

        def estimate_tokens(text: str) -> int:
            if not text:
                return 0
            return len(encoding.encode(text))
    except ImportError:
        def estimate_tokens(text: str) -> int:
            if not text:
                return 0
            return len(text) // 4

    # Verify conversation belongs to user
    conv_result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user.email
        )
    )
    conversation = conv_result.scalar_one_or_none()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Get all messages to calculate cumulative context size
    messages_result = await db.execute(
        select(Message.role, Message.content, Message.reasoning)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.timestamp)
    )
    messages = messages_result.all()

    # Calculate cumulative context tokens (what would be sent to LLM on next call)
    # This is the sum of all message content - the actual context window usage
    total_context_tokens = 0
    user_tokens = 0
    assistant_tokens = 0

    for msg in messages:
        content_tokens = estimate_tokens(msg.content or "")
        reasoning_tokens = estimate_tokens(msg.reasoning or "")
        msg_tokens = content_tokens + reasoning_tokens

        total_context_tokens += msg_tokens

        if msg.role == "user":
            user_tokens += msg_tokens
        else:
            assistant_tokens += msg_tokens

    message_count = len(messages)

    # Add estimated system prompt tokens (rough estimate)
    # Most agents have ~2-4k tokens in system prompts + injected memories
    system_prompt_estimate = 3000
    total_context_tokens += system_prompt_estimate

    # Determine if user should fork based on context size
    warning_threshold = 100000  # 100k tokens - typical context window limit
    should_fork = total_context_tokens >= warning_threshold

    warning_message = None
    if total_context_tokens >= warning_threshold:
        warning_message = f"This conversation has ~{total_context_tokens:,} tokens in context. Consider forking to a new conversation for better performance and lower costs."
    elif total_context_tokens >= warning_threshold * 0.75:  # 75% warning
        warning_message = f"This conversation is approaching the context limit (~{total_context_tokens:,} / {warning_threshold:,} tokens). You may want to fork soon."

    return TokenUsageResponse(
        conversation_id=conversation_id,
        total_input_tokens=total_context_tokens,  # Context size (what gets sent to LLM)
        total_output_tokens=assistant_tokens,      # Just assistant responses for reference
        total_tokens=total_context_tokens,         # Primary metric is context size
        message_count=message_count,
        warning_threshold=warning_threshold,
        should_fork=should_fork,
        warning_message=warning_message
    )