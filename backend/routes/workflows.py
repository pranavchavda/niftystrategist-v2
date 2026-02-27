"""
Workflow API routes for managing automated workflows

Provides endpoints for:
- Running workflows manually (one-click)
- Configuring workflow settings
- Viewing workflow history
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from utils.datetime_utils import utc_now_naive

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload

from auth import User, get_current_user, get_current_user_optional
from database.session import AsyncSessionLocal
from database.models import WorkflowConfig, WorkflowRun, WorkflowDefinition, User as DBUser
from services.workflow_engine import WorkflowEngine, WorkflowType, WorkflowStatus
from services.scheduler import get_scheduler

logger = logging.getLogger(__name__)

router = APIRouter()


# ========================================
# Pydantic Models
# ========================================

class WorkflowConfigResponse(BaseModel):
    """Workflow configuration response"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    workflow_type: str
    enabled: bool
    frequency: str
    config: Dict[str, Any]
    last_run_at: Optional[datetime]
    next_run_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class WorkflowConfigUpdate(BaseModel):
    """Update workflow configuration"""
    enabled: Optional[bool] = None
    frequency: Optional[str] = None
    config: Optional[Dict[str, Any]] = None


class WorkflowRunResponse(BaseModel):
    """Workflow run history response"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    workflow_type: str
    status: str
    trigger_type: str
    started_at: datetime
    completed_at: Optional[datetime]
    duration_ms: Optional[int]
    result: Optional[Dict[str, Any]]
    error_message: Optional[str]


class WorkflowRunRequest(BaseModel):
    """Request to run a workflow manually"""
    config_override: Optional[Dict[str, Any]] = None


class WorkflowRunResult(BaseModel):
    """Result of running a workflow"""
    success: bool
    run_id: int
    data: Dict[str, Any]
    error: Optional[str] = None
    duration_ms: Optional[int] = None


class WorkflowTypeInfo(BaseModel):
    """Information about a workflow type"""
    type: str
    name: str
    description: str
    default_config: Dict[str, Any]
    config_schema: Dict[str, Any]


# ========================================
# Custom Workflow Pydantic Models
# ========================================

class CustomWorkflowCreate(BaseModel):
    """Create a new custom workflow"""
    name: str
    description: Optional[str] = None
    icon: str = "🤖"
    prompt: str
    agent_hint: Optional[str] = None
    enabled: bool = False
    frequency: str = "daily"  # 'hourly', '6hours', 'daily', 'weekly', 'once', 'manual'
    cron_expression: Optional[str] = None
    scheduled_at: Optional[datetime] = None  # For one-time runs (frequency='once')
    timeout_seconds: int = 600
    notify_on_complete: bool = True  # Default to true - users want success notifications
    notify_on_failure: bool = True


class CustomWorkflowUpdate(BaseModel):
    """Update a custom workflow"""
    name: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    prompt: Optional[str] = None
    agent_hint: Optional[str] = None
    enabled: Optional[bool] = None
    frequency: Optional[str] = None
    cron_expression: Optional[str] = None
    scheduled_at: Optional[datetime] = None  # For one-time runs (frequency='once')
    timeout_seconds: Optional[int] = None
    notify_on_complete: Optional[bool] = None
    notify_on_failure: Optional[bool] = None


class CustomWorkflowResponse(BaseModel):
    """Custom workflow response"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: Optional[str]
    icon: str
    prompt: str
    agent_hint: Optional[str]
    enabled: bool
    frequency: str
    cron_expression: Optional[str]
    scheduled_at: Optional[datetime]  # For one-time runs (frequency='once')
    timeout_seconds: int
    notify_on_complete: bool
    notify_on_failure: bool
    last_run_at: Optional[datetime]
    next_run_at: Optional[datetime]
    run_count: int
    created_at: datetime
    updated_at: datetime


class CustomWorkflowRunResult(BaseModel):
    """Result of running a custom workflow"""
    success: bool
    run_id: int
    output: str
    error: Optional[str] = None
    duration_ms: Optional[int] = None


# ========================================
# Workflow Type Definitions
# ========================================

WORKFLOW_TYPES = {
    "email_autolabel": WorkflowTypeInfo(
        type="email_autolabel",
        name="Email Auto-Labeler",
        description="Automatically categorize and label incoming emails using AI-powered classification",
        default_config={
            "email_count": 50,
            "skip_labeled": True,
            "max_age_days": 7
        },
        config_schema={
            "email_count": {"type": "select", "options": [25, 50, 100], "label": "Emails to process"},
            "skip_labeled": {"type": "boolean", "label": "Skip already labeled"},
            "max_age_days": {"type": "select", "options": [1, 3, 7, 14, 30], "label": "Max email age (days)"}
        }
    ),
    # Future workflow types will be added here
    # Or users can create custom prompt-based workflows via the UI
}


# ========================================
# Helper Functions
# ========================================

async def get_db_user(user: User) -> DBUser:
    """Get database user from auth user"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(DBUser).where(DBUser.email == user.email)
        )
        db_user = result.scalar_one_or_none()

        if not db_user:
            raise HTTPException(status_code=404, detail="User not found in database")

        return db_user


# ========================================
# Workflow Type Endpoints
# ========================================

@router.get("/api/workflows/types", response_model=List[WorkflowTypeInfo])
async def list_workflow_types(user: User = Depends(get_current_user)):
    """List all available workflow types"""
    return list(WORKFLOW_TYPES.values())


@router.get("/api/workflows/types/{workflow_type}", response_model=WorkflowTypeInfo)
async def get_workflow_type(
    workflow_type: str,
    user: User = Depends(get_current_user)
):
    """Get details about a specific workflow type"""
    if workflow_type not in WORKFLOW_TYPES:
        raise HTTPException(status_code=404, detail=f"Unknown workflow type: {workflow_type}")

    return WORKFLOW_TYPES[workflow_type]


# ========================================
# Configuration Endpoints
# ========================================

@router.get("/api/workflows/configs", response_model=List[WorkflowConfigResponse])
async def list_workflow_configs(user: User = Depends(get_current_user)):
    """List all workflow configurations for the current user"""
    async with AsyncSessionLocal() as session:
        # Get DB user
        result = await session.execute(
            select(DBUser).where(DBUser.email == user.email)
        )
        db_user = result.scalar_one_or_none()

        if not db_user:
            return []

        # Get all configs for user
        result = await session.execute(
            select(WorkflowConfig).where(WorkflowConfig.user_id == db_user.id)
        )
        configs = result.scalars().all()

        # Also include workflow types that don't have configs yet
        existing_types = {c.workflow_type for c in configs}
        response = list(configs)

        # For types without configs, return default
        for wf_type, info in WORKFLOW_TYPES.items():
            if wf_type not in existing_types:
                # Create a virtual config for display
                response.append(WorkflowConfig(
                    id=0,
                    workflow_type=wf_type,
                    enabled=False,
                    frequency="daily",
                    config=info.default_config,
                    last_run_at=None,
                    next_run_at=None,
                    created_at=utc_now_naive(),
                    updated_at=utc_now_naive()
                ))

        return response


@router.get("/api/workflows/{workflow_type}/config", response_model=WorkflowConfigResponse)
async def get_workflow_config(
    workflow_type: str,
    user: User = Depends(get_current_user)
):
    """Get configuration for a specific workflow"""
    if workflow_type not in WORKFLOW_TYPES:
        raise HTTPException(status_code=404, detail=f"Unknown workflow type: {workflow_type}")

    async with AsyncSessionLocal() as session:
        # Get DB user
        result = await session.execute(
            select(DBUser).where(DBUser.email == user.email)
        )
        db_user = result.scalar_one_or_none()

        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")

        # Get config
        result = await session.execute(
            select(WorkflowConfig).where(
                WorkflowConfig.user_id == db_user.id,
                WorkflowConfig.workflow_type == workflow_type
            )
        )
        config = result.scalar_one_or_none()

        if not config:
            # Return default config
            info = WORKFLOW_TYPES[workflow_type]
            return WorkflowConfigResponse(
                id=0,
                workflow_type=workflow_type,
                enabled=False,
                frequency="daily",
                config=info.default_config,
                last_run_at=None,
                next_run_at=None,
                created_at=utc_now_naive(),
                updated_at=utc_now_naive()
            )

        return config


@router.put("/api/workflows/{workflow_type}/config", response_model=WorkflowConfigResponse)
async def update_workflow_config(
    workflow_type: str,
    update: WorkflowConfigUpdate,
    user: User = Depends(get_current_user)
):
    """Update configuration for a workflow"""
    if workflow_type not in WORKFLOW_TYPES:
        raise HTTPException(status_code=404, detail=f"Unknown workflow type: {workflow_type}")

    async with AsyncSessionLocal() as session:
        # Get DB user
        result = await session.execute(
            select(DBUser).where(DBUser.email == user.email)
        )
        db_user = result.scalar_one_or_none()

        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")

        # Get or create config
        result = await session.execute(
            select(WorkflowConfig).where(
                WorkflowConfig.user_id == db_user.id,
                WorkflowConfig.workflow_type == workflow_type
            )
        )
        config = result.scalar_one_or_none()

        if not config:
            # Create new config
            info = WORKFLOW_TYPES[workflow_type]
            config = WorkflowConfig(
                user_id=db_user.id,
                workflow_type=workflow_type,
                enabled=update.enabled if update.enabled is not None else False,
                frequency=update.frequency or "daily",
                config=update.config or info.default_config
            )
            session.add(config)
        else:
            # Update existing config
            if update.enabled is not None:
                config.enabled = update.enabled
            if update.frequency is not None:
                config.frequency = update.frequency
            if update.config is not None:
                config.config = {**(config.config or {}), **update.config}

        await session.commit()
        await session.refresh(config)

        # Update scheduler
        scheduler = get_scheduler()
        if scheduler:
            await scheduler.add_or_update_workflow(config)

        return config


# ========================================
# Execution Endpoints
# ========================================

@router.post("/api/workflows/{workflow_type}/run", response_model=WorkflowRunResult)
async def run_workflow(
    workflow_type: str,
    request: WorkflowRunRequest = None,
    user: User = Depends(get_current_user)
):
    """
    Run a workflow manually (one-click execution).

    This is the "Run Now" button functionality.
    """
    if workflow_type not in WORKFLOW_TYPES:
        raise HTTPException(status_code=404, detail=f"Unknown workflow type: {workflow_type}")

    async with AsyncSessionLocal() as session:
        # Get DB user
        result = await session.execute(
            select(DBUser).where(DBUser.email == user.email)
        )
        db_user = result.scalar_one_or_none()

        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")

        # Check for Google credentials if needed
        if workflow_type == "email_autolabel" and not db_user.google_access_token:
            raise HTTPException(
                status_code=400,
                detail="Google authentication required. Please re-authenticate with Google in Settings."
            )

        # Execute workflow
        engine = WorkflowEngine(session)
        result = await engine.execute_workflow(
            user_id=db_user.id,
            workflow_type=workflow_type,
            trigger_type="manual",
            config_override=request.config_override if request else None
        )

        # Get the run ID from the latest run
        run_result = await session.execute(
            select(WorkflowRun)
            .where(
                WorkflowRun.user_id == db_user.id,
                WorkflowRun.workflow_type == workflow_type
            )
            .order_by(desc(WorkflowRun.id))
            .limit(1)
        )
        run = run_result.scalar_one_or_none()

        return WorkflowRunResult(
            success=result.success,
            run_id=run.id if run else 0,
            data=result.data,
            error=result.error,
            duration_ms=result.duration_ms
        )


# ========================================
# History Endpoints
# ========================================

@router.get("/api/workflows/{workflow_type}/history", response_model=List[WorkflowRunResponse])
async def get_workflow_history(
    workflow_type: str,
    limit: int = 10,
    user: User = Depends(get_current_user)
):
    """Get recent run history for a workflow"""
    if workflow_type not in WORKFLOW_TYPES:
        raise HTTPException(status_code=404, detail=f"Unknown workflow type: {workflow_type}")

    async with AsyncSessionLocal() as session:
        # Get DB user
        result = await session.execute(
            select(DBUser).where(DBUser.email == user.email)
        )
        db_user = result.scalar_one_or_none()

        if not db_user:
            return []

        # Get runs
        result = await session.execute(
            select(WorkflowRun)
            .where(
                WorkflowRun.user_id == db_user.id,
                WorkflowRun.workflow_type == workflow_type
            )
            .order_by(desc(WorkflowRun.started_at))
            .limit(limit)
        )
        runs = result.scalars().all()

        return runs


# ========================================
# Thread Awakening: Activate Endpoint
# ========================================

@router.post("/api/workflows/followup/activate/{workflow_id}")
async def activate_followup(
    workflow_id: int,
    request: Request,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Register a thread-bound follow-up workflow with the scheduler.

    Called by schedule_followup.py immediately after DB insertion.
    Localhost calls are allowed without authentication (CLI tool usage).
    """
    client_host = request.client.host if request.client else ""
    is_localhost = client_host in ("127.0.0.1", "::1", "localhost")

    if not current_user and not is_localhost:
        raise HTTPException(status_code=401, detail="Authentication required")

    async with AsyncSessionLocal() as session:
        q = select(WorkflowDefinition).where(WorkflowDefinition.id == workflow_id)
        if current_user:
            user_result = await session.execute(
                select(DBUser).where(DBUser.email == current_user.email)
            )
            db_user = user_result.scalar_one_or_none()
            if db_user:
                q = q.where(WorkflowDefinition.user_id == db_user.id)

        result = await session.execute(q)
        workflow_def = result.scalar_one_or_none()

        if not workflow_def:
            raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")

        scheduler = get_scheduler()
        if scheduler:
            await scheduler.add_or_update_custom_workflow(workflow_def)
            logger.info(f"Activated follow-up workflow {workflow_id} in scheduler")

        return {
            "status": "scheduled",
            "workflow_id": workflow_id,
            "name": workflow_def.name,
            "scheduled_at": workflow_def.scheduled_at.isoformat() if workflow_def.scheduled_at else None,
            "thread_id": workflow_def.thread_id,
        }


@router.get("/api/workflows/history", response_model=List[WorkflowRunResponse])
async def get_all_workflow_history(
    limit: int = 20,
    user: User = Depends(get_current_user)
):
    """Get recent run history for all workflows"""
    async with AsyncSessionLocal() as session:
        # Get DB user
        result = await session.execute(
            select(DBUser).where(DBUser.email == user.email)
        )
        db_user = result.scalar_one_or_none()

        if not db_user:
            return []

        # Get runs
        result = await session.execute(
            select(WorkflowRun)
            .where(WorkflowRun.user_id == db_user.id)
            .order_by(desc(WorkflowRun.started_at))
            .limit(limit)
        )
        runs = result.scalars().all()

        return runs


# ========================================
# Scheduler Status Endpoints
# ========================================

@router.get("/api/workflows/scheduler/status")
async def get_scheduler_status(user: User = Depends(get_current_user)):
    """Get current scheduler status (for debugging)"""
    scheduler = get_scheduler()

    if not scheduler:
        return {"status": "not_initialized", "jobs": []}

    return {
        "status": "running" if scheduler._started else "stopped",
        "jobs": scheduler.get_scheduled_jobs()
    }


# ========================================
# Custom Workflow CRUD Endpoints
# ========================================

@router.get("/api/workflows/custom", response_model=List[CustomWorkflowResponse])
async def list_custom_workflows(user: User = Depends(get_current_user)):
    """List all custom workflows for the current user"""
    async with AsyncSessionLocal() as session:
        # Get DB user
        result = await session.execute(
            select(DBUser).where(DBUser.email == user.email)
        )
        db_user = result.scalar_one_or_none()

        if not db_user:
            return []

        # Get all custom workflows for user
        result = await session.execute(
            select(WorkflowDefinition)
            .where(WorkflowDefinition.user_id == db_user.id)
            .order_by(desc(WorkflowDefinition.created_at))
        )
        workflows = result.scalars().all()

        return workflows


@router.post("/api/workflows/custom", response_model=CustomWorkflowResponse)
async def create_custom_workflow(
    workflow: CustomWorkflowCreate,
    user: User = Depends(get_current_user)
):
    """Create a new custom workflow"""
    async with AsyncSessionLocal() as session:
        # Get DB user
        result = await session.execute(
            select(DBUser).where(DBUser.email == user.email)
        )
        db_user = result.scalar_one_or_none()

        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")

        # Check for duplicate name
        result = await session.execute(
            select(WorkflowDefinition).where(
                WorkflowDefinition.user_id == db_user.id,
                WorkflowDefinition.name == workflow.name
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Workflow with name '{workflow.name}' already exists"
            )

        # For one-time runs, set next_run_at to scheduled_at
        next_run = None
        if workflow.frequency == 'once' and workflow.scheduled_at:
            next_run = workflow.scheduled_at

        # Create workflow
        new_workflow = WorkflowDefinition(
            user_id=db_user.id,
            name=workflow.name,
            description=workflow.description,
            icon=workflow.icon,
            prompt=workflow.prompt,
            agent_hint=workflow.agent_hint,
            enabled=workflow.enabled,
            frequency=workflow.frequency,
            cron_expression=workflow.cron_expression,
            scheduled_at=workflow.scheduled_at,
            next_run_at=next_run,
            timeout_seconds=workflow.timeout_seconds,
            notify_on_complete=workflow.notify_on_complete,
            notify_on_failure=workflow.notify_on_failure
        )
        session.add(new_workflow)
        await session.commit()
        await session.refresh(new_workflow)

        # Schedule if enabled
        if new_workflow.enabled:
            scheduler = get_scheduler()
            if scheduler:
                await scheduler.add_or_update_custom_workflow(new_workflow)

        return new_workflow


@router.get("/api/workflows/custom/{workflow_id}", response_model=CustomWorkflowResponse)
async def get_custom_workflow(
    workflow_id: int,
    user: User = Depends(get_current_user)
):
    """Get a specific custom workflow"""
    async with AsyncSessionLocal() as session:
        # Get DB user
        result = await session.execute(
            select(DBUser).where(DBUser.email == user.email)
        )
        db_user = result.scalar_one_or_none()

        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")

        # Get workflow
        result = await session.execute(
            select(WorkflowDefinition).where(
                WorkflowDefinition.id == workflow_id,
                WorkflowDefinition.user_id == db_user.id
            )
        )
        workflow = result.scalar_one_or_none()

        if not workflow:
            raise HTTPException(status_code=404, detail="Workflow not found")

        return workflow


@router.put("/api/workflows/custom/{workflow_id}", response_model=CustomWorkflowResponse)
async def update_custom_workflow(
    workflow_id: int,
    update: CustomWorkflowUpdate,
    user: User = Depends(get_current_user)
):
    """Update a custom workflow"""
    async with AsyncSessionLocal() as session:
        # Get DB user
        result = await session.execute(
            select(DBUser).where(DBUser.email == user.email)
        )
        db_user = result.scalar_one_or_none()

        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")

        # Get workflow
        result = await session.execute(
            select(WorkflowDefinition).where(
                WorkflowDefinition.id == workflow_id,
                WorkflowDefinition.user_id == db_user.id
            )
        )
        workflow = result.scalar_one_or_none()

        if not workflow:
            raise HTTPException(status_code=404, detail="Workflow not found")

        # Check for duplicate name if changing
        if update.name and update.name != workflow.name:
            result = await session.execute(
                select(WorkflowDefinition).where(
                    WorkflowDefinition.user_id == db_user.id,
                    WorkflowDefinition.name == update.name
                )
            )
            existing = result.scalar_one_or_none()
            if existing:
                raise HTTPException(
                    status_code=400,
                    detail=f"Workflow with name '{update.name}' already exists"
                )

        # Update fields
        if update.name is not None:
            workflow.name = update.name
        if update.description is not None:
            workflow.description = update.description
        if update.icon is not None:
            workflow.icon = update.icon
        if update.prompt is not None:
            workflow.prompt = update.prompt
        if update.agent_hint is not None:
            workflow.agent_hint = update.agent_hint
        if update.enabled is not None:
            workflow.enabled = update.enabled
        if update.frequency is not None:
            workflow.frequency = update.frequency
        if update.cron_expression is not None:
            workflow.cron_expression = update.cron_expression
        if update.timeout_seconds is not None:
            workflow.timeout_seconds = update.timeout_seconds
        if update.notify_on_complete is not None:
            workflow.notify_on_complete = update.notify_on_complete
        if update.notify_on_failure is not None:
            workflow.notify_on_failure = update.notify_on_failure
        if update.scheduled_at is not None:
            workflow.scheduled_at = update.scheduled_at
            # For one-time runs, also update next_run_at
            if workflow.frequency == 'once':
                workflow.next_run_at = update.scheduled_at

        await session.commit()
        await session.refresh(workflow)

        # Update scheduler
        scheduler = get_scheduler()
        if scheduler:
            if workflow.enabled:
                await scheduler.add_or_update_custom_workflow(workflow)
            else:
                await scheduler.remove_custom_workflow(workflow.id)

        return workflow


@router.delete("/api/workflows/custom/{workflow_id}")
async def delete_custom_workflow(
    workflow_id: int,
    user: User = Depends(get_current_user)
):
    """Delete a custom workflow"""
    async with AsyncSessionLocal() as session:
        # Get DB user
        result = await session.execute(
            select(DBUser).where(DBUser.email == user.email)
        )
        db_user = result.scalar_one_or_none()

        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")

        # Get workflow
        result = await session.execute(
            select(WorkflowDefinition).where(
                WorkflowDefinition.id == workflow_id,
                WorkflowDefinition.user_id == db_user.id
            )
        )
        workflow = result.scalar_one_or_none()

        if not workflow:
            raise HTTPException(status_code=404, detail="Workflow not found")

        # Remove from scheduler
        scheduler = get_scheduler()
        if scheduler:
            await scheduler.remove_custom_workflow(workflow_id)

        # Delete workflow
        await session.delete(workflow)
        await session.commit()

        return {"message": "Workflow deleted successfully"}


@router.post("/api/workflows/custom/{workflow_id}/run", response_model=CustomWorkflowRunResult)
async def run_custom_workflow(
    workflow_id: int,
    user: User = Depends(get_current_user)
):
    """Run a custom workflow manually"""
    async with AsyncSessionLocal() as session:
        # Get DB user
        result = await session.execute(
            select(DBUser).where(DBUser.email == user.email)
        )
        db_user = result.scalar_one_or_none()

        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")

        # Get workflow
        result = await session.execute(
            select(WorkflowDefinition).where(
                WorkflowDefinition.id == workflow_id,
                WorkflowDefinition.user_id == db_user.id
            )
        )
        workflow = result.scalar_one_or_none()

        if not workflow:
            raise HTTPException(status_code=404, detail="Workflow not found")

        # Execute workflow
        engine = WorkflowEngine(session)
        result = await engine.execute_custom_workflow(
            user_id=db_user.id,
            workflow_def_id=workflow_id,
            trigger_type="manual"
        )

        # Get the run ID from the latest run
        run_result = await session.execute(
            select(WorkflowRun)
            .where(
                WorkflowRun.user_id == db_user.id,
                WorkflowRun.workflow_type == f"custom_{workflow_id}"
            )
            .order_by(desc(WorkflowRun.id))
            .limit(1)
        )
        run = run_result.scalar_one_or_none()

        return CustomWorkflowRunResult(
            success=result.success,
            run_id=run.id if run else 0,
            output=result.data.get("output", "") if result.data else "",
            error=result.error,
            duration_ms=result.duration_ms
        )


@router.get("/api/workflows/custom/{workflow_id}/history", response_model=List[WorkflowRunResponse])
async def get_custom_workflow_history(
    workflow_id: int,
    limit: int = 10,
    user: User = Depends(get_current_user)
):
    """Get run history for a custom workflow"""
    async with AsyncSessionLocal() as session:
        # Get DB user
        result = await session.execute(
            select(DBUser).where(DBUser.email == user.email)
        )
        db_user = result.scalar_one_or_none()

        if not db_user:
            return []

        # Get runs for this custom workflow
        result = await session.execute(
            select(WorkflowRun)
            .where(
                WorkflowRun.user_id == db_user.id,
                WorkflowRun.workflow_type == f"custom_{workflow_id}"
            )
            .order_by(desc(WorkflowRun.started_at))
            .limit(limit)
        )
        runs = result.scalars().all()

        return runs
