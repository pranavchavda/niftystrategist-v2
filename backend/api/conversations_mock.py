"""
Mock conversation endpoints for testing without database
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
import logging
import json
import os
from pathlib import Path

from auth import get_current_user, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/conversations", tags=["conversations"])

# File-based storage for persistence across reloads
STORAGE_FILE = Path("/tmp/espressobot_conversations.json")

def load_storage() -> tuple[Dict[str, Dict[str, Any]], Dict[str, List[Dict[str, Any]]]]:
    """Load conversations from file"""
    if STORAGE_FILE.exists():
        try:
            with open(STORAGE_FILE, 'r') as f:
                data = json.load(f)
                # Convert datetime strings back to datetime objects
                for conv in data.get('conversations', {}).values():
                    conv['created_at'] = datetime.fromisoformat(conv['created_at'])
                    conv['updated_at'] = datetime.fromisoformat(conv['updated_at'])
                for msgs in data.get('messages', {}).values():
                    for msg in msgs:
                        msg['timestamp'] = datetime.fromisoformat(msg['timestamp'])
                return data.get('conversations', {}), data.get('messages', {})
        except Exception as e:
            logger.error(f"Error loading storage: {e}")
    return {}, {}

def save_storage(conversations: Dict[str, Dict[str, Any]], messages: Dict[str, List[Dict[str, Any]]]):
    """Save conversations to file"""
    try:
        # Convert datetime objects to strings for JSON serialization
        conv_copy = {}
        for k, v in conversations.items():
            conv_copy[k] = v.copy()
            conv_copy[k]['created_at'] = v['created_at'].isoformat()
            conv_copy[k]['updated_at'] = v['updated_at'].isoformat()

        msg_copy = {}
        for k, msgs in messages.items():
            msg_copy[k] = []
            for msg in msgs:
                msg_dict = msg.copy()
                msg_dict['timestamp'] = msg['timestamp'].isoformat()
                msg_copy[k].append(msg_dict)

        with open(STORAGE_FILE, 'w') as f:
            json.dump({'conversations': conv_copy, 'messages': msg_copy}, f)
    except Exception as e:
        logger.error(f"Error saving storage: {e}")

# Load existing data on module import
conversations_store, messages_store = load_storage()


class ConversationResponse(BaseModel):
    """Conversation response model"""
    id: str
    user_id: str
    title: Optional[str]
    created_at: datetime
    updated_at: datetime
    is_starred: bool = False
    is_archived: bool = False
    summary: Optional[str] = None
    message_count: int = 0


class ConversationListResponse(BaseModel):
    """List of conversations"""
    conversations: List[ConversationResponse]
    total: int
    has_more: bool


@router.get("/", response_model=ConversationListResponse)
async def list_conversations(
    user: User = Depends(get_current_user),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    include_archived: bool = False
):
    """List user's conversations"""
    # Simply use the user's email as their ID
    user_id = user.email

    logger.info(f"Listing conversations for user: {user_id}")
    logger.info(f"Current conversations in store: {list(conversations_store.keys())}")
    logger.info(f"Store contents: {conversations_store}")

    user_convs = [
        conv for conv in conversations_store.values()
        if conv['user_id'] == user_id and (include_archived or not conv.get('is_archived', False))
    ]

    logger.info(f"Found {len(user_convs)} conversations for user {user_id}")

    # Sort by updated_at
    user_convs.sort(key=lambda x: x['updated_at'], reverse=True)

    # Pagination
    paginated = user_convs[offset:offset + limit]

    return ConversationListResponse(
        conversations=[
            ConversationResponse(**conv)
            for conv in paginated
        ],
        total=len(user_convs),
        has_more=(offset + limit) < len(user_convs)
    )


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: str,
    user: User = Depends(get_current_user)
):
    """Get a specific conversation"""
    conv = conversations_store.get(conversation_id)

    if not conv or conv['user_id'] != user.email:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return ConversationResponse(**conv)


@router.post("/{conversation_id}/star")
async def star_conversation(
    conversation_id: str,
    user: User = Depends(get_current_user)
):
    """Star a conversation"""
    conv = conversations_store.get(conversation_id)

    if not conv or conv['user_id'] != user.email:
        raise HTTPException(status_code=404, detail="Conversation not found")

    conv['is_starred'] = True
    conv['updated_at'] = datetime.now(timezone.utc)
    save_storage(conversations_store, messages_store)

    return {"status": "success"}


@router.post("/{conversation_id}/unstar")
async def unstar_conversation(
    conversation_id: str,
    user: User = Depends(get_current_user)
):
    """Unstar a conversation"""
    conv = conversations_store.get(conversation_id)

    if not conv or conv['user_id'] != user.email:
        raise HTTPException(status_code=404, detail="Conversation not found")

    conv['is_starred'] = False
    conv['updated_at'] = datetime.now(timezone.utc)
    save_storage(conversations_store, messages_store)

    return {"status": "success"}


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    user: User = Depends(get_current_user)
):
    """Delete a conversation"""
    conv = conversations_store.get(conversation_id)

    if not conv or conv['user_id'] != user.email:
        raise HTTPException(status_code=404, detail="Conversation not found")

    del conversations_store[conversation_id]
    if conversation_id in messages_store:
        del messages_store[conversation_id]
    save_storage(conversations_store, messages_store)

    return {"status": "success"}


# Helper function to create/update conversation when messages are sent
def create_or_update_conversation(thread_id: str, user_email: str, message: str):
    """Create or update conversation record"""
    logger.info(f"Creating/updating conversation {thread_id} for user {user_email}")

    if thread_id not in conversations_store:
        # Extract title from first message (first 50 chars)
        title = message[:50] + "..." if len(message) > 50 else message

        conversations_store[thread_id] = {
            'id': thread_id,
            'user_id': user_email,
            'title': title,
            'created_at': datetime.now(timezone.utc),
            'updated_at': datetime.now(timezone.utc),
            'is_starred': False,
            'is_archived': False,
            'summary': None,
            'message_count': 1
        }
    else:
        conversations_store[thread_id]['updated_at'] = datetime.now(timezone.utc)
        conversations_store[thread_id]['message_count'] += 1

    # Store message
    if thread_id not in messages_store:
        messages_store[thread_id] = []

    messages_store[thread_id].append({
        'content': message,
        'timestamp': datetime.now(timezone.utc)
    })

    # Save to file
    save_storage(conversations_store, messages_store)
    logger.info(f"Saved conversation {thread_id} to storage")