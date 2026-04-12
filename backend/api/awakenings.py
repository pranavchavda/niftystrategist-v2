"""Awakenings API — CRUD for recurring awakening schedules + mandate management."""

import logging
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from auth import get_current_user, User
from database.session import get_db_context

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic request/response models
# ---------------------------------------------------------------------------

class ScheduleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    cron_hour: int = Field(..., ge=0, le=23)
    cron_minute: int = Field(0, ge=0, le=59)
    prompt: str = Field(..., min_length=1)
    enabled: bool = True
    weekdays_only: bool = True
    timeout_seconds: int = Field(600, ge=60, le=1800)
    model_override: Optional[str] = None


class ScheduleUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    cron_hour: Optional[int] = Field(None, ge=0, le=23)
    cron_minute: Optional[int] = Field(None, ge=0, le=59)
    prompt: Optional[str] = Field(None, min_length=1)
    enabled: Optional[bool] = None
    weekdays_only: Optional[bool] = None
    timeout_seconds: Optional[int] = Field(None, ge=60, le=1800)
    model_override: Optional[str] = None


class MandateUpdate(BaseModel):
    risk_per_trade: Optional[str] = None
    daily_loss_cap: Optional[str] = None
    allowed_instruments: Optional[str] = None
    cutoff_time: Optional[str] = None
    auto_squareoff_time: Optional[str] = None
    custom_instructions: Optional[str] = None


def _schedule_to_dict(s) -> dict:
    """Convert a UserAwakeningSchedule ORM object to a JSON-safe dict."""
    return {
        "id": s.id,
        "user_id": s.user_id,
        "name": s.name,
        "enabled": s.enabled,
        "cron_hour": s.cron_hour,
        "cron_minute": s.cron_minute,
        "weekdays_only": s.weekdays_only,
        "prompt": s.prompt,
        "timeout_seconds": s.timeout_seconds,
        "model_override": s.model_override,
        "last_run_at": s.last_run_at.isoformat() if s.last_run_at else None,
        "last_error": s.last_error,
        "run_count": s.run_count,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }


# ---------------------------------------------------------------------------
# Schedule CRUD
# ---------------------------------------------------------------------------

@router.get("/schedules")
async def list_schedules(current_user: User = Depends(get_current_user)):
    """List all awakening schedules for the current user."""
    from services.awakening_scheduler import list_schedules as _list

    async with get_db_context() as session:
        schedules = await _list(session, current_user.id)
        return {"schedules": [_schedule_to_dict(s) for s in schedules]}


@router.post("/schedules")
async def create_schedule(
    body: ScheduleCreate,
    current_user: User = Depends(get_current_user),
):
    """Create a new awakening schedule."""
    from services.awakening_scheduler import create_schedule as _create

    async with get_db_context() as session:
        try:
            schedule = await _create(
                session,
                user_id=current_user.id,
                name=body.name,
                cron_hour=body.cron_hour,
                cron_minute=body.cron_minute,
                prompt=body.prompt,
                enabled=body.enabled,
                weekdays_only=body.weekdays_only,
                timeout_seconds=body.timeout_seconds,
                model_override=body.model_override,
            )
        except Exception as e:
            if "unique" in str(e).lower():
                raise HTTPException(400, f"Schedule with name '{body.name}' already exists")
            raise

        # Update scheduler
        try:
            from services.scheduler import get_scheduler
            sched = get_scheduler()
            if sched:
                await sched.add_or_update_awakening(schedule)
        except Exception as e:
            logger.warning("Failed to update scheduler for new awakening: %s", e)

        return {"schedule": _schedule_to_dict(schedule)}


@router.get("/schedules/{schedule_id}")
async def get_schedule(
    schedule_id: int,
    current_user: User = Depends(get_current_user),
):
    """Get a single awakening schedule."""
    from services.awakening_scheduler import get_schedule as _get

    async with get_db_context() as session:
        schedule = await _get(session, schedule_id, current_user.id)
        if not schedule:
            raise HTTPException(404, "Schedule not found")
        return {"schedule": _schedule_to_dict(schedule)}


@router.patch("/schedules/{schedule_id}")
async def update_schedule(
    schedule_id: int,
    body: ScheduleUpdate,
    current_user: User = Depends(get_current_user),
):
    """Update an awakening schedule."""
    from services.awakening_scheduler import update_schedule as _update

    async with get_db_context() as session:
        updates = body.model_dump(exclude_none=True)
        if not updates:
            raise HTTPException(400, "No fields to update")

        schedule = await _update(session, schedule_id, current_user.id, **updates)
        if not schedule:
            raise HTTPException(404, "Schedule not found")

        # Update scheduler
        try:
            from services.scheduler import get_scheduler
            sched = get_scheduler()
            if sched:
                await sched.add_or_update_awakening(schedule)
        except Exception as e:
            logger.warning("Failed to update scheduler for awakening %d: %s", schedule_id, e)

        return {"schedule": _schedule_to_dict(schedule)}


@router.delete("/schedules/{schedule_id}")
async def delete_schedule(
    schedule_id: int,
    current_user: User = Depends(get_current_user),
):
    """Delete an awakening schedule."""
    from services.awakening_scheduler import delete_schedule as _delete

    async with get_db_context() as session:
        deleted = await _delete(session, schedule_id, current_user.id)
        if not deleted:
            raise HTTPException(404, "Schedule not found")

        # Remove from scheduler
        try:
            from services.scheduler import get_scheduler
            sched = get_scheduler()
            if sched:
                sched._remove_awakening_job(schedule_id)
        except Exception as e:
            logger.warning("Failed to remove awakening job %d from scheduler: %s", schedule_id, e)

        return {"deleted": True}


@router.post("/schedules/{schedule_id}/run")
async def run_schedule_now(
    schedule_id: int,
    current_user: User = Depends(get_current_user),
):
    """Manually trigger an awakening schedule (runs immediately)."""
    from services.awakening_scheduler import get_schedule as _get, execute_awakening

    async with get_db_context() as session:
        schedule = await _get(session, schedule_id, current_user.id)
        if not schedule:
            raise HTTPException(404, "Schedule not found")

        result = await execute_awakening(session, schedule)
        return result


@router.post("/schedules/seed")
async def seed_defaults(current_user: User = Depends(get_current_user)):
    """Seed default awakening schedules (Morning Scan, Mid-Day Check, etc.)."""
    from services.awakening_scheduler import seed_default_schedules

    async with get_db_context() as session:
        created = await seed_default_schedules(session, current_user.id)
        return {
            "seeded": len(created),
            "schedules": [_schedule_to_dict(s) for s in created],
        }


# ---------------------------------------------------------------------------
# Daily Thread
# ---------------------------------------------------------------------------

@router.get("/daily-thread")
async def get_daily_thread(
    date: Optional[str] = None,
    current_user: User = Depends(get_current_user),
):
    """Get today's (or a specific date's) daily thread ID."""
    from services.daily_thread import get_daily_thread_id
    from datetime import date as date_type

    target = None
    if date:
        try:
            target = date_type.fromisoformat(date)
        except ValueError:
            raise HTTPException(400, "Invalid date format. Use YYYY-MM-DD.")

    async with get_db_context() as session:
        thread_id = await get_daily_thread_id(session, current_user.id, target, user_email=current_user.email)
        return {"thread_id": thread_id, "date": date or "today"}


# ---------------------------------------------------------------------------
# Trading Mandate
# ---------------------------------------------------------------------------

@router.get("/mandate")
async def get_mandate(current_user: User = Depends(get_current_user)):
    """Get the current user's trading mandate."""
    from database.models import User as DBUser

    async with get_db_context() as session:
        user = await session.get(DBUser, current_user.id)
        if not user:
            raise HTTPException(404, "User not found")
        return {"mandate": user.trading_mandate}


@router.put("/mandate")
async def update_mandate(
    body: MandateUpdate,
    current_user: User = Depends(get_current_user),
):
    """Update the current user's trading mandate."""
    from database.models import User as DBUser, utc_now

    async with get_db_context() as session:
        user = await session.get(DBUser, current_user.id)
        if not user:
            raise HTTPException(404, "User not found")

        mandate = body.model_dump(exclude_none=True)
        mandate["approved_at"] = utc_now().isoformat()
        user.trading_mandate = mandate
        await session.commit()

        return {"mandate": user.trading_mandate}


@router.delete("/mandate")
async def clear_mandate(current_user: User = Depends(get_current_user)):
    """Clear the current user's trading mandate."""
    from database.models import User as DBUser

    async with get_db_context() as session:
        user = await session.get(DBUser, current_user.id)
        if not user:
            raise HTTPException(404, "User not found")

        user.trading_mandate = None
        await session.commit()

        return {"mandate": None}
