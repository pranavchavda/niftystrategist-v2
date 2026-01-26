"""
Flock Integration API Routes

Provides REST endpoints for:
- Viewing digests
- Managing actionables
- Creating Google Tasks
- Manual sync triggers
- Statistics
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from database import (
    FlockDigest, FlockActionable, FlockMessage, FlockChannel,
    ActionableStatus, ActionableType, ActionablePriority, FlockChannelType
)
from database.session import get_db
from auth import get_current_user, User
from services.flock import (
    FlockMessageFetcher,
    ActionableExtractor,
    DigestGenerator,
    GoogleTasksIntegration
)
from services.flock.digest_generator import generate_daily_digest
from services.flock.message_fetcher import fetch_daily_messages
from services.flock.actionable_extractor import extract_actionables_from_recent_messages
from typing import Optional, List
from datetime import datetime, timedelta, timezone
from utils.datetime_utils import utc_now_naive
from pydantic import BaseModel
import logging
import os

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/flock", tags=["flock"])


# ===============================
# Helper Functions
# ===============================

async def _store_outgoing_webhook_message(webhook_data: dict):
    """
    Store a message from Flock outgoing webhook

    Outgoing webhook format:
    {
        'id': 'd_1761369836270_510va9xc',
        'to': 'g:73184cf22f5c40eba6df3ec853817c56',  // Channel ID
        'from': 'u:gz5z25iz5z2ojozj',  // User ID
        'text': 'Message text',
        'timestamp': '2025-10-25T05:23:56.374Z',
        'timestampInMillis': 1761369836374,
        'uid': '1761369836374-dvY-m202',
        ...
    }

    Args:
        webhook_data: The webhook payload from Flock
    """
    try:
        # Extract data
        message_uid = webhook_data.get('uid')
        from_user = webhook_data.get('from')
        to_channel = webhook_data.get('to')
        text = webhook_data.get('text', '')
        timestamp_str = webhook_data.get('timestamp')

        if not message_uid or not from_user or not to_channel:
            logger.warning(f"Incomplete outgoing webhook data: {webhook_data}")
            return

        # Parse timestamp (ISO 8601 format) and convert to naive UTC
        from dateutil import parser as date_parser
        from datetime import timezone
        if timestamp_str:
            sent_at = date_parser.parse(timestamp_str).replace(tzinfo=None)  # Strip timezone
        else:
            sent_at = utc_now_naive()

        # Get database session
        from database.session import AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            # Determine channel type (g: = group, u: = user DM)
            channel_type = FlockChannelType.GROUP if to_channel.startswith('g:') else FlockChannelType.DM

            # Check if channel exists
            channel_stmt = select(FlockChannel).where(FlockChannel.flock_id == to_channel)
            result = await session.execute(channel_stmt)
            channel = result.scalar_one_or_none()

            if not channel:
                # Create new channel
                channel = FlockChannel(
                    flock_id=to_channel,
                    name=f"Channel {to_channel[:10]}...",  # Placeholder name
                    type=channel_type,
                    is_monitored=True,
                    include_in_digest=True
                )
                session.add(channel)
                await session.flush()
                logger.info(f"Created new Flock channel: {to_channel}")

            # Check if message already exists (avoid duplicates)
            existing_msg_stmt = select(FlockMessage).where(
                FlockMessage.flock_message_id == message_uid
            )
            result = await session.execute(existing_msg_stmt)
            existing_msg = result.scalar_one_or_none()

            if existing_msg:
                logger.debug(f"Message {message_uid} already stored, skipping")
                return

            # Create new message record
            new_message = FlockMessage(
                flock_message_id=message_uid,
                channel_id=channel.id,
                text=text,
                sender_id=from_user,
                sender_name='Unknown',  # Outgoing webhooks don't include sender name
                sent_at=sent_at,
                fetched_at=utc_now_naive(),
                attachments=None,
                mentions=None,
                is_edited=False
            )

            session.add(new_message)
            await session.commit()

            logger.info(f"✓ Stored outgoing webhook message {message_uid} from {from_user} in channel {to_channel}")

    except Exception as e:
        logger.error(f"Error storing outgoing webhook message: {e}", exc_info=True)
        # Don't raise - we still want to return 200 OK to Flock


async def _store_received_message(event_data: dict, request: Request):
    """
    Store a message received from chat.receiveMessage event

    Args:
        event_data: The event data from Flock
        request: FastAPI request object (to get db session)
    """
    try:
        # Extract message data
        message = event_data.get('message', {})
        user_id = event_data.get('userId')

        if not message:
            logger.warning("chat.receiveMessage event has no message data")
            return

        # Extract message fields
        message_id = message.get('uid')
        from_user = message.get('from')
        to_chat = message.get('to')  # Can be user ID or channel ID
        text = message.get('text', '')
        sent_at_ts = message.get('timestamp')

        if not message_id or not from_user or not to_chat:
            logger.warning(f"Incomplete message data: {message}")
            return

        # Parse timestamp (Flock uses milliseconds since epoch) - convert to naive UTC
        if sent_at_ts:
            sent_at = datetime.utcfromtimestamp(sent_at_ts / 1000.0)
        else:
            sent_at = utc_now_naive()

        # Get database session
        from database.session import AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            # Find or create channel
            # If 'to' starts with 'g:' it's a group, 'u:' is a user (DM)
            channel_type = FlockChannelType.GROUP if to_chat.startswith('g:') else FlockChannelType.DM

            # Check if channel exists
            channel_stmt = select(FlockChannel).where(FlockChannel.flock_id == to_chat)
            result = await session.execute(channel_stmt)
            channel = result.scalar_one_or_none()

            if not channel:
                # Create new channel
                channel = FlockChannel(
                    flock_id=to_chat,
                    name=f"Channel {to_chat[:10]}...",  # Placeholder name
                    type=channel_type,
                    is_monitored=True,
                    include_in_digest=True
                )
                session.add(channel)
                await session.flush()  # Get the channel ID
                logger.info(f"Created new Flock channel: {to_chat}")

            # Check if message already exists (avoid duplicates)
            existing_msg_stmt = select(FlockMessage).where(
                FlockMessage.flock_message_id == message_id
            )
            result = await session.execute(existing_msg_stmt)
            existing_msg = result.scalar_one_or_none()

            if existing_msg:
                logger.debug(f"Message {message_id} already stored, skipping")
                return

            # Create new message record
            new_message = FlockMessage(
                flock_message_id=message_id,
                channel_id=channel.id,
                text=text,
                sender_id=from_user,
                sender_name=message.get('senderName', 'Unknown'),  # May not be in event
                sent_at=sent_at,
                fetched_at=utc_now_naive(),
                attachments=message.get('attachments'),
                mentions=message.get('mentions'),
                is_edited=False
            )

            session.add(new_message)
            await session.commit()

            logger.info(f"✓ Stored message {message_id} from {from_user} in channel {to_chat}")

    except Exception as e:
        logger.error(f"Error storing Flock message: {e}", exc_info=True)
        # Don't raise - we still want to return 200 OK to Flock


# =======================
# Event Listener Endpoint
# =======================

@router.get("/events", include_in_schema=True)
@router.post("/events", include_in_schema=True)
async def flock_event_listener(request: Request):
    """
    Flock Event Listener Endpoint

    This endpoint receives events from Flock and responds with 200 OK.
    Required for Flock app configuration.

    Supports both GET (for verification) and POST (for events).

    Events that may be received:
    - app.install - When app is installed to a workspace
    - app.uninstall - When app is removed
    - chat.receiveMessage - When bot receives a message
    - And other Flock events

    For now, we just acknowledge receipt with 200 OK.
    Future: Can process events to enable interactive bot features.
    """
    try:
        # Handle GET request (Flock verification)
        if request.method == "GET":
            logger.info("Flock verification GET request received")
            return JSONResponse(
                status_code=200,
                content={"status": "ok", "message": "Event listener active"}
            )

        # Handle POST request (actual events)
        try:
            event_data = await request.json()
        except Exception:
            # If no JSON body, still return 200 OK
            logger.info("Flock event received with no JSON body")
            return JSONResponse(
                status_code=200,
                content={"status": "ok", "message": "Event acknowledged"}
            )

        # Detect event type
        # Outgoing webhooks have no 'name' field, data is at top level
        # App events have 'name' field like 'chat.receiveMessage', 'app.install', etc.
        event_name = event_data.get('name')

        if event_name:
            # This is an app event (has 'name' field)
            logger.info(f"Received Flock app event: {event_name}")
            logger.debug(f"Event data: {event_data}")

            # Validate app token if present (for security)
            app_token = event_data.get('token')
            expected_token = os.getenv('FLOCK_APP_SECRET')

            if app_token and expected_token and app_token != expected_token:
                logger.warning(f"Invalid app token in Flock event: {event_name}")
                # Still return 200 to avoid blocking app installation
                return JSONResponse(
                    status_code=200,
                    content={"status": "ok", "message": "Event acknowledged"}
                )

            # Process specific app events
            if event_name == 'app.install':
                logger.info("Flock app installed to a workspace")

            elif event_name == 'app.uninstall':
                logger.info("Flock app uninstalled from a workspace")

            elif event_name == 'chat.receiveMessage':
                # Store the message in database for daily digest
                await _store_received_message(event_data, request)

        else:
            # This is an outgoing webhook (no 'name' field)
            # Message data is at top level: {id, to, from, text, timestamp, uid, ...}
            logger.info("Received Flock outgoing webhook message")
            logger.info(f"Message: {event_data.get('text', '')[:100]}...")

            # Store the outgoing webhook message
            await _store_outgoing_webhook_message(event_data)

        # Return 200 OK to acknowledge receipt
        return JSONResponse(
            status_code=200,
            content={"status": "ok", "message": "Event received"}
        )

    except Exception as e:
        logger.error(f"Error processing Flock event: {e}")
        # Still return 200 to avoid retries from Flock
        return JSONResponse(
            status_code=200,
            content={"status": "ok", "message": "Event acknowledged"}
        )


# Pydantic models for request/response
class ActionableFilterParams(BaseModel):
    status: Optional[str] = None
    type: Optional[str] = None
    priority: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    limit: int = 50
    offset: int = 0


class CreateTaskRequest(BaseModel):
    actionable_ids: List[int]


class CreateTaskResponse(BaseModel):
    success: int
    failed: int
    task_ids: List[str]


# Routes

@router.get("/digests")
async def list_digests(
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get list of all digests with pagination

    Returns:
        List of digests ordered by date (newest first)
    """
    try:
        # Get total count
        count_stmt = select(func.count(FlockDigest.id))
        result = await session.execute(count_stmt)
        total = result.scalar()

        # Get digests
        stmt = select(FlockDigest).order_by(
            desc(FlockDigest.digest_date)
        ).limit(limit).offset(offset)

        result = await session.execute(stmt)
        digests = result.scalars().all()

        return {
            "digests": [
                {
                    "id": d.id,
                    "digest_date": d.digest_date.isoformat(),
                    "total_actionables": d.total_actionables_extracted,
                    "total_messages": d.total_messages_analyzed,
                    "channels_monitored": d.channels_monitored,
                    "tasks_count": d.tasks_count,
                    "decisions_count": d.decisions_count,
                    "questions_count": d.questions_count,
                    "reminders_count": d.reminders_count,
                    "deadlines_count": d.deadlines_count,
                    "summary": d.summary,
                    "is_generated": d.is_generated,
                    "email_sent": d.email_sent
                }
                for d in digests
            ],
            "total": total,
            "limit": limit,
            "offset": offset
        }

    except Exception as e:
        logger.error(f"Error listing digests: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/digests/{digest_id}")
async def get_digest(
    digest_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific digest with its actionables

    Args:
        digest_id: ID of the digest

    Returns:
        Digest details with actionables
    """
    try:
        # Get digest
        stmt = select(FlockDigest).where(FlockDigest.id == digest_id)
        result = await session.execute(stmt)
        digest = result.scalar_one_or_none()

        if not digest:
            raise HTTPException(status_code=404, detail="Digest not found")

        # Get actionables for this digest
        actionables_stmt = select(FlockActionable).where(
            FlockActionable.digest_id == digest_id
        ).order_by(
            desc(FlockActionable.priority),
            desc(FlockActionable.created_at)
        )

        result = await session.execute(actionables_stmt)
        actionables = result.scalars().all()

        return {
            "digest": {
                "id": digest.id,
                "digest_date": digest.digest_date.isoformat(),
                "period_start": digest.period_start.isoformat(),
                "period_end": digest.period_end.isoformat(),
                "total_actionables": digest.total_actionables_extracted,
                "total_messages": digest.total_messages_analyzed,
                "channels_monitored": digest.channels_monitored,
                "summary": digest.summary,
                "highlights": digest.highlights,
                "stats": {
                    "tasks": digest.tasks_count,
                    "decisions": digest.decisions_count,
                    "questions": digest.questions_count,
                    "reminders": digest.reminders_count,
                    "deadlines": digest.deadlines_count
                }
            },
            "actionables": [
                {
                    "id": a.id,
                    "type": a.type.value,
                    "priority": a.priority.value,
                    "status": a.status.value,
                    "title": a.title,
                    "description": a.description,
                    "context": a.context,
                    "assigned_to": a.assigned_to,
                    "assigned_to_name": a.assigned_to_name,
                    "due_date": a.due_date.isoformat() if a.due_date else None,
                    "confidence_score": a.confidence_score,
                    "google_task_id": a.google_task_id,
                    "created_at": a.created_at.isoformat()
                }
                for a in actionables
            ]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting digest: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/actionables")
async def list_actionables(
    status: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get filtered list of actionables

    Query Parameters:
        - status: Filter by status (pending, added_to_tasks, completed, dismissed)
        - type: Filter by type (task, decision, question, etc.)
        - priority: Filter by priority (low, medium, high, urgent)
        - limit: Number of results (max 200)
        - offset: Pagination offset

    Returns:
        Filtered list of actionables
    """
    try:
        # Build query
        query = select(FlockActionable)

        if status:
            query = query.where(FlockActionable.status == ActionableStatus(status))

        if type:
            query = query.where(FlockActionable.type == ActionableType(type))

        if priority:
            query = query.where(FlockActionable.priority == ActionablePriority(priority))

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        result = await session.execute(count_query)
        total = result.scalar()

        # Order and paginate
        query = query.order_by(
            desc(FlockActionable.priority),
            desc(FlockActionable.created_at)
        ).limit(limit).offset(offset)

        result = await session.execute(query)
        actionables = result.scalars().all()

        return {
            "actionables": [
                {
                    "id": a.id,
                    "type": a.type.value,
                    "priority": a.priority.value,
                    "status": a.status.value,
                    "title": a.title,
                    "description": a.description,
                    "context": a.context,
                    "assigned_to": a.assigned_to,
                    "assigned_to_name": a.assigned_to_name,
                    "due_date": a.due_date.isoformat() if a.due_date else None,
                    "confidence_score": a.confidence_score,
                    "google_task_id": a.google_task_id,
                    "created_at": a.created_at.isoformat(),
                    "digest_id": a.digest_id
                }
                for a in actionables
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
            "filters": {
                "status": status,
                "type": type,
                "priority": priority
            }
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid filter value: {e}")
    except Exception as e:
        logger.error(f"Error listing actionables: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/actionables/create-tasks")
async def create_tasks_from_actionables(
    request: CreateTaskRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create Google Tasks from actionables

    Request Body:
        - actionable_ids: List of actionable IDs to convert

    Returns:
        Summary of task creation (success/failure counts)
    """
    try:
        integration = GoogleTasksIntegration()
        results = await integration.bulk_create_tasks(
            session,
            request.actionable_ids,
            current_user.email
        )

        return CreateTaskResponse(
            success=results['success'],
            failed=results['failed'],
            task_ids=results['task_ids']
        )

    except Exception as e:
        logger.error(f"Error creating tasks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync")
async def trigger_sync(
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Manually trigger Flock message sync and actionable extraction

    Returns:
        Statistics about the sync operation
    """
    try:
        logger.info("Manual sync triggered by user")

        # Fetch messages
        stats = await fetch_daily_messages()

        # Extract actionables
        extraction_stats = await extract_actionables_from_recent_messages()

        return {
            "success": True,
            "message": "Sync completed successfully",
            "stats": {
                "messages_fetched": stats.get('messages_fetched', 0),
                "messages_stored": stats.get('messages_stored', 0),
                "channels_processed": stats.get('channels_processed', 0),
                "actionables_extracted": extraction_stats.get('actionables_extracted', 0),
                "actionables_stored": extraction_stats.get('actionables_stored', 0)
            }
        }

    except Exception as e:
        logger.error(f"Error during manual sync: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_stats(
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get overall Flock integration statistics

    Returns:
        Statistics about messages, actionables, digests, etc.
    """
    try:
        # Total messages
        messages_count_stmt = select(func.count(FlockMessage.id))
        result = await session.execute(messages_count_stmt)
        total_messages = result.scalar() or 0

        # Total actionables
        actionables_count_stmt = select(func.count(FlockActionable.id))
        result = await session.execute(actionables_count_stmt)
        total_actionables = result.scalar() or 0

        # Pending actionables
        pending_stmt = select(func.count(FlockActionable.id)).where(
            FlockActionable.status == ActionableStatus.PENDING
        )
        result = await session.execute(pending_stmt)
        pending_actionables = result.scalar() or 0

        # Tasks created
        tasks_created_stmt = select(func.count(FlockActionable.id)).where(
            FlockActionable.google_task_id.isnot(None)
        )
        result = await session.execute(tasks_created_stmt)
        tasks_created = result.scalar() or 0

        # Total digests
        digests_count_stmt = select(func.count(FlockDigest.id))
        result = await session.execute(digests_count_stmt)
        total_digests = result.scalar() or 0

        # Monitored channels
        channels_count_stmt = select(func.count(FlockChannel.id)).where(
            FlockChannel.is_monitored == True
        )
        result = await session.execute(channels_count_stmt)
        monitored_channels = result.scalar() or 0

        # Last sync time
        last_message_stmt = select(FlockMessage.fetched_at).order_by(
            desc(FlockMessage.fetched_at)
        ).limit(1)
        result = await session.execute(last_message_stmt)
        last_sync = result.scalar()

        # Actionables by type
        type_counts = {}
        for atype in ActionableType:
            type_stmt = select(func.count(FlockActionable.id)).where(
                FlockActionable.type == atype
            )
            result = await session.execute(type_stmt)
            type_counts[atype.value] = result.scalar() or 0

        return {
            "overall": {
                "total_messages": total_messages,
                "total_actionables": total_actionables,
                "pending_actionables": pending_actionables,
                "tasks_created": tasks_created,
                "total_digests": total_digests,
                "monitored_channels": monitored_channels,
                "last_sync": last_sync.isoformat() if last_sync else None
            },
            "actionables_by_type": type_counts
        }

    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-digest")
async def generate_digest_manually(
    date: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Manually generate a digest for a specific date

    Query Parameters:
        - date: ISO format date (default: today)

    Returns:
        Generated digest information
    """
    try:
        if date:
            digest_date = datetime.fromisoformat(date)
        else:
            digest_date = utc_now_naive().replace(hour=6, minute=0, second=0, microsecond=0)

        digest = await generate_daily_digest(digest_date)

        return {
            "success": True,
            "message": "Digest generated successfully",
            "digest": {
                "id": digest.id,
                "date": digest.digest_date.isoformat(),
                "actionables": digest.total_actionables_extracted,
                "messages": digest.total_messages_analyzed
            }
        }

    except Exception as e:
        logger.error(f"Error generating digest: {e}")
        raise HTTPException(status_code=500, detail=str(e))
