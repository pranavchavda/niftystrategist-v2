"""
API Routes for Async Run Management
Handles background agent runs that persist after client disconnection
"""

import asyncio
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from auth import get_current_user, User
from database import DatabaseManager
from services.run_manager import run_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/runs", tags=["runs"])

# Module-level database manager (set by main.py)
_db_manager: DatabaseManager = None


def get_db_manager():
    """Dependency to get database manager"""
    if _db_manager is None:
        raise HTTPException(status_code=500, detail="Database manager not initialized")
    return _db_manager


# Pydantic models for request/response
class CreateRunRequest(BaseModel):
    """Request to create a new background run"""
    thread_id: str
    user_message: str
    metadata: Optional[Dict[str, Any]] = None


class RunStatusResponse(BaseModel):
    """Response with run status and results"""
    id: str
    thread_id: str
    status: str  # pending, in_progress, completed, failed, cancelled
    user_message: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ActiveRunResponse(BaseModel):
    """Response for active run (simplified)"""
    id: str
    thread_id: str
    status: str
    user_message: str
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@router.get("/active")
async def get_active_runs(
    user: User = Depends(get_current_user),
    db_manager: DatabaseManager = Depends(get_db_manager)
):
    """
    Get all active runs for the current user

    Returns list of runs with status 'pending' or 'in_progress'
    """
    try:
        async with db_manager.async_session() as session:
            runs = await run_manager.get_active_runs_for_user(str(user.id), session)

        return {
            "status": "success",
            "runs": runs,
            "count": len(runs)
        }

    except Exception as e:
        logger.error(f"Error getting active runs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{run_id}/status")
async def get_run_status(
    run_id: str,
    user: User = Depends(get_current_user),
    db_manager: DatabaseManager = Depends(get_db_manager)
):
    """
    Get status and results for a specific run

    Returns:
        - 200: Run details with current status
        - 404: Run not found
        - 403: User doesn't own this run
    """
    try:
        async with db_manager.async_session() as session:
            run_data = await run_manager.get_run_status(run_id, session)

        if not run_data:
            raise HTTPException(status_code=404, detail="Run not found")

        # Verify ownership (load run from DB to check user_id)
        from sqlalchemy import select
        from database.models import Run

        async with db_manager.async_session() as session:
            result = await session.execute(
                select(Run).where(Run.id == run_id)
            )
            run = result.scalar_one_or_none()

            if not run or run.user_id != str(user.id):
                raise HTTPException(status_code=403, detail="Access denied")

        return {
            "status": "success",
            "run": run_data
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting run status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{run_id}/stream")
async def stream_run(
    run_id: str,
    user: User = Depends(get_current_user),
    db_manager: DatabaseManager = Depends(get_db_manager)
):
    """
    Stream SSE events for an ongoing or completed run

    For ongoing runs: Connects to active stream
    For completed runs: Immediately sends results and closes
    For failed runs: Sends error event

    Returns:
        SSE stream with AG-UI protocol events
    """
    try:
        # Verify ownership
        from sqlalchemy import select
        from database.models import Run

        async with db_manager.async_session() as session:
            result = await session.execute(
                select(Run).where(Run.id == run_id)
            )
            run = result.scalar_one_or_none()

            if not run:
                raise HTTPException(status_code=404, detail="Run not found")

            if run.user_id != str(user.id):
                raise HTTPException(status_code=403, detail="Access denied")

        # Check if run has an active generator (still streaming)
        generator = run_manager.get_generator(run_id)

        if generator:
            # Stream is still active - connect to it
            logger.info(f"[Runs] Reconnecting to active stream for run {run_id}")

            async def reconnect_stream():
                """Reconnect to ongoing stream"""
                try:
                    async for chunk in generator:
                        yield chunk
                except Exception as e:
                    logger.error(f"[Runs] Error reconnecting to stream: {e}", exc_info=True)
                    import json
                    error_event = {
                        "type": "ERROR",
                        "error": f"Reconnection error: {str(e)}"
                    }
                    yield f"data: {json.dumps(error_event)}\n\n".encode()

            return StreamingResponse(
                reconnect_stream(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no"
                }
            )

        # No active generator - send results immediately based on status
        async with db_manager.async_session() as session:
            run_data = await run_manager.get_run_status(run_id, session)

        async def replay_results():
            """Replay completed run results as SSE events"""
            import json
            import uuid

            try:
                if run_data["status"] == "completed":
                    # Send completed run data
                    result = run_data.get("result", {})
                    text = result.get("text", "Run completed successfully")

                    message_id = f"msg_{uuid.uuid4().hex[:12]}"

                    # Send AG-UI protocol events
                    yield f"data: {json.dumps({'type': 'AGENT_ROUTING', 'agent': 'orchestrator'})}\n\n".encode()
                    yield f"data: {json.dumps({'type': 'TEXT_MESSAGE_START', 'messageId': message_id})}\n\n".encode()
                    yield f"data: {json.dumps({'type': 'TEXT_MESSAGE_CONTENT', 'messageId': message_id, 'delta': text})}\n\n".encode()
                    yield f"data: {json.dumps({'type': 'TEXT_MESSAGE_END', 'messageId': message_id})}\n\n".encode()

                    # Send tool calls if any
                    tool_calls = result.get("tool_calls", [])
                    if tool_calls:
                        for tool_call in tool_calls:
                            yield f"data: {json.dumps({'type': 'TOOL_CALL', 'data': tool_call})}\n\n".encode()

                    # Send TODO updates if any
                    todos = result.get("todos", [])
                    if todos:
                        yield f"data: {json.dumps({'type': 'TODO_UPDATE', 'todos': todos})}\n\n".encode()

                    yield f"data: {json.dumps({'type': 'RUN_FINISHED'})}\n\n".encode()

                elif run_data["status"] == "failed":
                    # Send error event
                    error_msg = run_data.get("error", "Run failed")
                    error_event = {
                        "type": "ERROR",
                        "error": error_msg
                    }
                    yield f"data: {json.dumps(error_event)}\n\n".encode()
                    yield f"data: {json.dumps({'type': 'RUN_FINISHED'})}\n\n".encode()

                elif run_data["status"] in ["pending", "in_progress"]:
                    # Run is still active but no generator (edge case)
                    # Wait briefly and poll
                    for _ in range(10):  # Poll for 10 seconds
                        await asyncio.sleep(1)
                        async with db_manager.async_session() as session:
                            updated_data = await run_manager.get_run_status(run_id, session)

                        if updated_data["status"] in ["completed", "failed", "cancelled"]:
                            # Recursively call replay with updated data
                            async for chunk in replay_results():
                                yield chunk
                            return

                    # Still pending/in_progress after 10 seconds - inform user
                    status_event = {
                        "type": "RUN_STATUS",
                        "status": run_data["status"],
                        "message": "Run is still processing. Please check status later."
                    }
                    yield f"data: {json.dumps(status_event)}\n\n".encode()

                else:  # cancelled
                    cancel_event = {
                        "type": "RUN_CANCELLED",
                        "message": "This run was cancelled"
                    }
                    yield f"data: {json.dumps(cancel_event)}\n\n".encode()
                    yield f"data: {json.dumps({'type': 'RUN_FINISHED'})}\n\n".encode()

            except Exception as e:
                logger.error(f"[Runs] Error replaying results: {e}", exc_info=True)
                error_event = {
                    "type": "ERROR",
                    "error": f"Error loading results: {str(e)}"
                }
                yield f"data: {json.dumps(error_event)}\n\n".encode()

        return StreamingResponse(
            replay_results(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error streaming run: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{run_id}/cancel")
async def cancel_run(
    run_id: str,
    user: User = Depends(get_current_user),
    db_manager: DatabaseManager = Depends(get_db_manager)
):
    """
    Cancel an active run

    Returns:
        - 200: Run cancelled successfully
        - 404: Run not found
        - 403: User doesn't own this run
        - 400: Run is not active (already completed/failed/cancelled)
    """
    try:
        # Verify ownership and check if active
        from sqlalchemy import select
        from database.models import Run

        async with db_manager.async_session() as session:
            result = await session.execute(
                select(Run).where(Run.id == run_id)
            )
            run = result.scalar_one_or_none()

            if not run:
                raise HTTPException(status_code=404, detail="Run not found")

            if run.user_id != str(user.id):
                raise HTTPException(status_code=403, detail="Access denied")

            if run.status not in ["pending", "in_progress"]:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot cancel run with status: {run.status}"
                )

        # Cancel the run
        async with db_manager.async_session() as session:
            await run_manager.cancel_run(run_id, session)

        logger.info(f"[Runs] Run {run_id} cancelled by user {user.email}")

        return {
            "status": "success",
            "message": "Run cancelled successfully",
            "run_id": run_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling run: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{run_id}/retry")
async def retry_run(
    run_id: str,
    user: User = Depends(get_current_user),
    db_manager: DatabaseManager = Depends(get_db_manager)
):
    """
    Retry a failed run

    Creates a new run with the same parameters as the failed run

    Returns:
        - 200: New run created
        - 404: Run not found
        - 403: User doesn't own this run
        - 400: Run is not failed
    """
    try:
        # Verify ownership and check if failed
        from sqlalchemy import select
        from database.models import Run

        async with db_manager.async_session() as session:
            result = await session.execute(
                select(Run).where(Run.id == run_id)
            )
            run = result.scalar_one_or_none()

            if not run:
                raise HTTPException(status_code=404, detail="Run not found")

            if run.user_id != str(user.id):
                raise HTTPException(status_code=403, detail="Access denied")

            if run.status != "failed":
                raise HTTPException(
                    status_code=400,
                    detail=f"Can only retry failed runs. Current status: {run.status}"
                )

            # Create new run with same parameters
            new_run_id = await run_manager.create_run(
                session,
                thread_id=run.thread_id,
                user_id=run.user_id,
                user_message=run.user_message,
                metadata={
                    **run.run_metadata,
                    "retry_of": run_id,
                    "retry_at": datetime.now(timezone.utc).isoformat()
                }
            )

        logger.info(f"[Runs] Created retry run {new_run_id} for failed run {run_id}")

        return {
            "status": "success",
            "message": "Retry run created",
            "original_run_id": run_id,
            "new_run_id": new_run_id,
            "thread_id": run.thread_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrying run: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
