"""
API endpoints for querying workflow action logs.

Provides visibility into what tools were called during scheduled events (awakenings, automations).
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import Optional

from database.session import get_db
from database.models import WorkflowActionLog, WorkflowRun
from auth import get_current_user

router = APIRouter(prefix="/api/workflows/actions", tags=["workflows"])


@router.get("/run/{workflow_run_id}")
async def get_workflow_actions(
    workflow_run_id: int,
    session: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """Get all tool calls logged for a specific workflow run"""
    # Verify workflow belongs to user
    stmt = select(WorkflowRun).where(
        (WorkflowRun.id == workflow_run_id) & (WorkflowRun.user_id == current_user.id)
    )
    workflow = (await session.execute(stmt)).scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow run not found")

    # Get all actions for this workflow
    stmt = select(WorkflowActionLog).where(
        WorkflowActionLog.workflow_run_id == workflow_run_id
    ).order_by(WorkflowActionLog.sequence_order)

    result = await session.execute(stmt)
    actions = result.scalars().all()

    return {
        "workflow_run_id": workflow_run_id,
        "action_count": len(actions),
        "actions": [
            {
                "id": a.id,
                "sequence": a.sequence_order,
                "tool": a.tool_name,
                "args": a.tool_args,
                "status": a.execution_status,
                "result": a.tool_result,
                "error": a.error_message,
                "duration_ms": a.duration_ms,
                "reasoning": a.agent_reasoning,
                "started_at": a.started_at.isoformat() if a.started_at else None,
                "completed_at": a.completed_at.isoformat() if a.completed_at else None,
            }
            for a in actions
        ],
    }


@router.get("/user/recent")
async def get_recent_workflow_actions(
    limit: int = 50,
    offset: int = 0,
    tool_name: Optional[str] = None,
    session: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """Get recent tool calls for all the user's workflows"""
    query = select(WorkflowActionLog).where(
        WorkflowActionLog.user_id == current_user.id
    ).order_by(desc(WorkflowActionLog.started_at))

    if tool_name:
        query = query.where(WorkflowActionLog.tool_name == tool_name)

    # Get total count
    count_stmt = select(WorkflowActionLog).where(
        WorkflowActionLog.user_id == current_user.id
    )
    if tool_name:
        count_stmt = count_stmt.where(WorkflowActionLog.tool_name == tool_name)

    total = len((await session.execute(count_stmt)).scalars().all())

    # Get paginated results
    query = query.limit(limit).offset(offset)
    result = await session.execute(query)
    actions = result.scalars().all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "actions": [
            {
                "id": a.id,
                "workflow_run_id": a.workflow_run_id,
                "tool": a.tool_name,
                "args": a.tool_args,
                "status": a.execution_status,
                "result": a.tool_result,
                "error": a.error_message,
                "reasoning": a.agent_reasoning,
                "started_at": a.started_at.isoformat() if a.started_at else None,
            }
            for a in actions
        ],
    }


@router.get("/symbol/{symbol}")
async def get_actions_for_symbol(
    symbol: str,
    limit: int = 50,
    session: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """Get all tool calls involving a specific symbol"""
    from sqlalchemy import or_, and_, cast, String

    # Search in tool_args and tool_result JSONB for the symbol
    stmt = select(WorkflowActionLog).where(
        and_(
            WorkflowActionLog.user_id == current_user.id,
            or_(
                cast(WorkflowActionLog.tool_args, String).ilike(f"%{symbol}%"),
                cast(WorkflowActionLog.tool_result, String).ilike(f"%{symbol}%"),
            ),
        )
    ).order_by(desc(WorkflowActionLog.started_at)).limit(limit)

    result = await session.execute(stmt)
    actions = result.scalars().all()

    return {
        "symbol": symbol,
        "action_count": len(actions),
        "actions": [
            {
                "id": a.id,
                "workflow_run_id": a.workflow_run_id,
                "tool": a.tool_name,
                "args": a.tool_args,
                "status": a.execution_status,
                "result": a.tool_result,
                "reasoning": a.agent_reasoning,
                "started_at": a.started_at.isoformat() if a.started_at else None,
            }
            for a in actions
        ],
    }
