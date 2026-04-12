"""
Awakening Scheduler — CRUD + execution engine for recurring awakenings.

Manages user awakening schedules and executes them by:
1. Getting or creating today's daily thread
2. Loading thread history (previous awakenings from today)
3. Running the orchestrator with the awakening prompt
4. Writing the result back to the daily thread
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import (
    UserAwakeningSchedule, User, Conversation, WorkflowRun, utc_now,
)

logger = logging.getLogger(__name__)

# IST is UTC+5:30
IST_UTC_OFFSET_HOURS = 5
IST_UTC_OFFSET_MINUTES = 30


def ist_to_utc(ist_hour: int, ist_minute: int) -> tuple[int, int]:
    """Convert IST hour:minute to UTC hour:minute.

    IST = UTC + 5:30, so UTC = IST - 5:30.
    """
    total_minutes = ist_hour * 60 + ist_minute - (IST_UTC_OFFSET_HOURS * 60 + IST_UTC_OFFSET_MINUTES)
    if total_minutes < 0:
        total_minutes += 24 * 60
    return total_minutes // 60, total_minutes % 60


# ============================================================================
# CRUD operations
# ============================================================================

async def list_schedules(session: AsyncSession, user_id: int) -> List[UserAwakeningSchedule]:
    """List all awakening schedules for a user."""
    result = await session.execute(
        select(UserAwakeningSchedule)
        .where(UserAwakeningSchedule.user_id == user_id)
        .order_by(UserAwakeningSchedule.cron_hour, UserAwakeningSchedule.cron_minute)
    )
    return list(result.scalars().all())


async def get_schedule(session: AsyncSession, schedule_id: int, user_id: int) -> Optional[UserAwakeningSchedule]:
    """Get a single schedule by ID, scoped to user."""
    result = await session.execute(
        select(UserAwakeningSchedule).where(
            UserAwakeningSchedule.id == schedule_id,
            UserAwakeningSchedule.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def create_schedule(
    session: AsyncSession,
    user_id: int,
    name: str,
    cron_hour: int,
    cron_minute: int,
    prompt: str,
    enabled: bool = True,
    weekdays_only: bool = True,
    timeout_seconds: int = 600,
    model_override: Optional[str] = None,
) -> UserAwakeningSchedule:
    """Create a new awakening schedule."""
    schedule = UserAwakeningSchedule(
        user_id=user_id,
        name=name,
        enabled=enabled,
        cron_hour=cron_hour,
        cron_minute=cron_minute,
        weekdays_only=weekdays_only,
        prompt=prompt,
        timeout_seconds=timeout_seconds,
        model_override=model_override,
    )
    session.add(schedule)
    await session.commit()
    await session.refresh(schedule)
    logger.info("Created awakening schedule '%s' (id=%d) for user %d at %02d:%02d IST",
                name, schedule.id, user_id, cron_hour, cron_minute)
    return schedule


async def update_schedule(
    session: AsyncSession,
    schedule_id: int,
    user_id: int,
    **kwargs,
) -> Optional[UserAwakeningSchedule]:
    """Update an existing schedule. Only provided kwargs are updated."""
    schedule = await get_schedule(session, schedule_id, user_id)
    if not schedule:
        return None

    allowed_fields = {
        'name', 'enabled', 'cron_hour', 'cron_minute', 'weekdays_only',
        'prompt', 'timeout_seconds', 'model_override',
    }
    for key, value in kwargs.items():
        if key in allowed_fields and value is not None:
            setattr(schedule, key, value)

    schedule.updated_at = utc_now()
    await session.commit()
    await session.refresh(schedule)
    logger.info("Updated awakening schedule %d for user %d", schedule_id, user_id)
    return schedule


async def delete_schedule(session: AsyncSession, schedule_id: int, user_id: int) -> bool:
    """Delete a schedule. Returns True if deleted."""
    result = await session.execute(
        delete(UserAwakeningSchedule).where(
            UserAwakeningSchedule.id == schedule_id,
            UserAwakeningSchedule.user_id == user_id,
        )
    )
    await session.commit()
    deleted = result.rowcount > 0
    if deleted:
        logger.info("Deleted awakening schedule %d for user %d", schedule_id, user_id)
    return deleted


async def seed_default_schedules(session: AsyncSession, user_id: int) -> List[UserAwakeningSchedule]:
    """Seed the 4 default awakening windows for a user.

    Only creates schedules that don't already exist (by name).
    All created as disabled — user must enable them.
    """
    defaults = [
        {
            "name": "Morning Scan",
            "cron_hour": 9,
            "cron_minute": 20,
            "prompt": (
                "Run morning scan: check nf-market-status, then nf-quote for watchlist symbols. "
                "For top movers, run nf-analyze. Report findings and identify high-conviction setups. "
                "If a setup matches the mandate, deploy the strategy."
            ),
        },
        {
            "name": "Mid-Day Check",
            "cron_hour": 11,
            "cron_minute": 30,
            "prompt": (
                "Check all open positions via nf-portfolio --json. For each position: "
                "is P&L positive? Are SL/target rules active? Is thesis still valid? "
                "Cut positions down >1% with invalid thesis. Trail stops on winners."
            ),
        },
        {
            "name": "Pre-Close Positioning",
            "cron_hour": 14,
            "cron_minute": 0,
            "prompt": (
                "Review positions for end-of-day. Trail stops tighter on winners. "
                "Ensure auto-squareoff rules set for 3:15 PM. Check options positions "
                "near expiry. Prepare for close."
            ),
        },
        {
            "name": "Post-Close Review",
            "cron_hour": 15,
            "cron_minute": 45,
            "prompt": (
                "Run nf-trades --json for today's trades. Calculate daily P&L. "
                "Review rule firing logs (nf-monitor logs). Clean up expired/disabled rules. "
                "Summarize the day: trades, P&L, what worked, what didn't."
            ),
        },
    ]

    created = []
    for d in defaults:
        # Check if already exists
        existing = await session.execute(
            select(UserAwakeningSchedule).where(
                UserAwakeningSchedule.user_id == user_id,
                UserAwakeningSchedule.name == d["name"],
            )
        )
        if existing.scalar_one_or_none():
            continue

        schedule = UserAwakeningSchedule(
            user_id=user_id,
            name=d["name"],
            enabled=False,  # User must enable
            cron_hour=d["cron_hour"],
            cron_minute=d["cron_minute"],
            weekdays_only=True,
            prompt=d["prompt"],
            timeout_seconds=600,
        )
        session.add(schedule)
        created.append(schedule)

    if created:
        await session.commit()
        for s in created:
            await session.refresh(s)
        logger.info("Seeded %d default awakening schedules for user %d", len(created), user_id)

    return created


# ============================================================================
# Executor — runs a single awakening
# ============================================================================

async def execute_awakening(
    session: AsyncSession,
    schedule: UserAwakeningSchedule,
) -> Dict[str, Any]:
    """Execute a single recurring awakening.

    1. Check market holiday
    2. Get or create daily thread
    3. Load thread history
    4. Run orchestrator with awakening prompt + thread context
    5. Write result to daily thread
    6. Update schedule tracking

    Returns dict with success, output, thread_id, duration_ms.
    """
    from services.daily_thread import get_or_create_daily_thread
    from services.workflow_engine import WorkflowEngine, utc_now_naive
    from database.models import WorkflowRun
    from agents.orchestrator import OrchestratorDeps
    from models.state import ConversationState
    from config.models import DEFAULT_MODEL_ID
    from main import get_orchestrator_for_model
    from api.upstox_oauth import get_user_upstox_token

    start_time = utc_now()
    user_id = schedule.user_id

    # Get user
    user = await session.get(User, user_id)
    if not user:
        logger.error("Awakening %d: user %d not found", schedule.id, user_id)
        return {"success": False, "error": f"User {user_id} not found"}

    # Check market holiday via Upstox API (best-effort)
    try:
        from services.upstox_client import UpstoxClient
        upstox_token = await get_user_upstox_token(user_id)
        if upstox_token:
            client = UpstoxClient(upstox_token, paper_trading=False)
            status = await asyncio.to_thread(client.get_market_status)
            if status and status.get("status") == "CLOSED" and schedule.name != "Post-Close Review":
                logger.info("Awakening %d: market closed (holiday?), skipping", schedule.id)
                return {"success": True, "skipped": True, "reason": "Market closed"}
    except Exception as e:
        logger.warning("Awakening %d: market status check failed (non-fatal): %s", schedule.id, e)

    # Get or create daily thread
    mandate = user.trading_mandate if hasattr(user, 'trading_mandate') else None
    thread_id = await get_or_create_daily_thread(
        session, user_id, user.email, mandate=mandate
    )

    # Create workflow run for audit trail
    run = WorkflowRun(
        workflow_config_id=None,
        user_id=user_id,
        workflow_type=f"awakening_{schedule.id}_{schedule.name.lower().replace(' ', '_')}",
        status="running",
        trigger_type="scheduled",
        started_at=start_time,
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)

    try:
        # Load thread history (previous awakenings from today)
        engine = WorkflowEngine(session)
        message_history = await engine._load_thread_messages(thread_id)
        logger.info(
            "Awakening '%s' (id=%d): loaded %d messages from daily thread %s",
            schedule.name, schedule.id, len(message_history), thread_id
        )

        # Build effective prompt
        from zoneinfo import ZoneInfo
        ist_now = datetime.now(ZoneInfo("UTC")).astimezone(ZoneInfo("Asia/Kolkata"))
        time_str = ist_now.strftime('%I:%M %p IST')

        effective_prompt = (
            f"[{time_str}] [RECURRING AWAKENING: {schedule.name}] [NO USER PRESENT]\n"
            "You are executing a recurring scheduled awakening in the daily trading thread. "
            "The user is NOT available to respond. Rules:\n"
            "- Execute the task described below completely\n"
            "- You have access to all CLI tools (nf-quote, nf-analyze, nf-portfolio, etc.)\n"
            "- Report your findings clearly\n"
            "- Do NOT ask questions or request clarification\n"
            "- Check the thread history above for context from earlier awakenings today\n"
            "- If a trading mandate exists in the thread, operate within its bounds\n"
            f"\nTask: {schedule.prompt}"
        )

        # Get orchestrator
        model_id = schedule.model_override or user.preferred_model or DEFAULT_MODEL_ID
        orchestrator = await get_orchestrator_for_model(model_id, user_id=user_id)

        # Resolve Upstox token
        upstox_token = await get_user_upstox_token(user_id)

        # Build deps
        state = ConversationState(user_id=user.email, thread_id=thread_id)

        from services.workflow_action_logger import WorkflowActionLogger
        action_logger = WorkflowActionLogger(session, run.id, user_id)

        deps = OrchestratorDeps(
            state=state,
            upstox_access_token=upstox_token,
            order_node_url=user.order_node_url,
            user_id=user_id,
            trading_mode=user.trading_mode or "live",
            is_awakening=True,
            action_logger=action_logger,
        )

        # Execute
        run_result = await asyncio.wait_for(
            orchestrator.agent.run(effective_prompt, deps=deps, message_history=message_history),
            timeout=schedule.timeout_seconds,
        )
        orchestrator_result = run_result.output if run_result.output else ""

        # Write result to daily thread
        if orchestrator_result:
            await engine._write_followup_to_thread(
                thread_id=thread_id,
                user_id=user_id,
                response_text=orchestrator_result,
            )

        # Update run record
        end_time = utc_now()
        duration_ms = int((end_time - start_time).total_seconds() * 1000)

        run.status = "COMPLETED"
        run.completed_at = end_time
        run.duration_ms = duration_ms
        run.result = {
            "schedule_name": schedule.name,
            "thread_id": thread_id,
            "response": orchestrator_result[:5000] if orchestrator_result else None,
        }

        # Update schedule tracking
        schedule.last_run_at = end_time
        schedule.last_error = None
        schedule.run_count = (schedule.run_count or 0) + 1

        await session.commit()

        logger.info(
            "Awakening '%s' (id=%d) completed in %dms, thread=%s",
            schedule.name, schedule.id, duration_ms, thread_id
        )

        return {
            "success": True,
            "output": orchestrator_result,
            "thread_id": thread_id,
            "duration_ms": duration_ms,
            "run_id": run.id,
        }

    except asyncio.TimeoutError:
        end_time = utc_now()
        duration_ms = int((end_time - start_time).total_seconds() * 1000)
        error_msg = f"Timed out after {schedule.timeout_seconds}s"

        run.status = "FAILED"
        run.completed_at = end_time
        run.duration_ms = duration_ms
        run.error_message = error_msg

        schedule.last_run_at = end_time
        schedule.last_error = error_msg
        await session.commit()

        logger.error("Awakening '%s' (id=%d) timed out after %ds", schedule.name, schedule.id, schedule.timeout_seconds)
        return {"success": False, "error": error_msg, "thread_id": thread_id}

    except Exception as e:
        end_time = utc_now()
        duration_ms = int((end_time - start_time).total_seconds() * 1000)
        error_msg = str(e)

        run.status = "FAILED"
        run.completed_at = end_time
        run.duration_ms = duration_ms
        run.error_message = error_msg

        schedule.last_run_at = end_time
        schedule.last_error = error_msg
        await session.commit()

        logger.exception("Awakening '%s' (id=%d) failed: %s", schedule.name, schedule.id, e)
        return {"success": False, "error": error_msg, "thread_id": thread_id}
