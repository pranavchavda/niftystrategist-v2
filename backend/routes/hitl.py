"""
Human-in-the-Loop (HITL) API Routes

Endpoints for handling approval requests and responses
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
import logging

from utils.hitl_manager import get_hitl_manager
from auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/hitl", tags=["hitl"])


class ApprovalResponse(BaseModel):
    """Response to an approval request"""
    approval_id: str
    approved: bool
    reason: Optional[str] = None


@router.post("/respond")
async def respond_to_approval(
    response: ApprovalResponse,
    current_user: dict = Depends(get_current_user)
):
    """
    Respond to a pending approval request

    This endpoint is called by the frontend when the user approves or rejects
    a tool execution request.
    """
    logger.info(
        f"[HITL] User {current_user.email} responding to approval {response.approval_id}: "
        f"approved={response.approved}, reason={response.reason}"
    )

    hitl_manager = get_hitl_manager()

    success = await hitl_manager.respond_to_approval(
        approval_id=response.approval_id,
        approved=response.approved,
        reason=response.reason
    )

    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Approval request {response.approval_id} not found or already processed"
        )

    return {
        "success": True,
        "approval_id": response.approval_id,
        "approved": response.approved
    }


@router.post("/cancel/{approval_id}")
async def cancel_approval(
    approval_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Cancel a pending approval request"""
    logger.info(f"[HITL] User {current_user.get('email')} cancelling approval {approval_id}")

    hitl_manager = get_hitl_manager()
    success = await hitl_manager.cancel_approval(approval_id)

    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Approval request {approval_id} not found"
        )

    return {"success": True, "approval_id": approval_id}


@router.get("/pending")
async def get_pending_approvals(
    current_user: dict = Depends(get_current_user)
):
    """Get all pending approval requests (for debugging)"""
    hitl_manager = get_hitl_manager()
    pending = hitl_manager.get_pending_approvals()

    return {
        "pending_approvals": [
            {
                "approval_id": req.approval_id,
                "tool_name": req.tool_name,
                "tool_args": req.tool_args,
                "explanation": req.explanation,
                "created_at": req.created_at.isoformat()
            }
            for req in pending.values()
        ]
    }
