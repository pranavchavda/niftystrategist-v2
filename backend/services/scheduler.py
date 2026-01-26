"""
Workflow Scheduler - APScheduler integration for automated workflows

Manages scheduled execution of workflows based on user configuration.
Runs as a background service within the FastAPI application.
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.jobstores.memory import MemoryJobStore
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

logger = logging.getLogger(__name__)


class WorkflowScheduler:
    """
    Manages scheduled workflow executions using APScheduler.

    This scheduler:
    1. Loads enabled workflows from database on startup
    2. Creates APScheduler jobs for each enabled workflow
    3. Handles job updates when users change settings
    4. Executes workflows via WorkflowEngine
    """

    def __init__(self, get_db_session):
        """
        Initialize the scheduler.

        Args:
            get_db_session: Async function to get database session
        """
        self.get_db_session = get_db_session
        self.scheduler = AsyncIOScheduler(
            jobstores={'default': MemoryJobStore()},
            job_defaults={
                'coalesce': True,  # Combine missed runs into one
                'max_instances': 1,  # Only one instance per workflow
                'misfire_grace_time': 3600  # 1 hour grace period for missed jobs
            }
        )
        self._started = False

    async def start(self):
        """Start the scheduler and load all enabled workflows"""
        if self._started:
            logger.warning("Scheduler already started")
            return

        logger.info("Starting workflow scheduler...")

        # Load all enabled workflows
        await self._load_enabled_workflows()

        # Start the scheduler
        self.scheduler.start()
        self._started = True

        logger.info("Workflow scheduler started successfully")

    async def shutdown(self):
        """Gracefully shutdown the scheduler"""
        if not self._started:
            return

        logger.info("Shutting down workflow scheduler...")
        self.scheduler.shutdown(wait=False)
        self._started = False
        logger.info("Workflow scheduler stopped")

    async def _load_enabled_workflows(self):
        """Load all enabled workflows from database and create jobs"""
        from database.models import WorkflowConfig, WorkflowDefinition

        async for session in self.get_db_session():
            try:
                # Load built-in workflows
                result = await session.execute(
                    select(WorkflowConfig).where(WorkflowConfig.enabled == True)
                )
                configs = result.scalars().all()

                for config in configs:
                    self._add_job(config)

                logger.info(f"Loaded {len(configs)} enabled built-in workflows")

                # Load custom workflows
                result = await session.execute(
                    select(WorkflowDefinition).where(WorkflowDefinition.enabled == True)
                )
                custom_workflows = result.scalars().all()

                for workflow in custom_workflows:
                    self._add_custom_job(workflow)

                logger.info(f"Loaded {len(custom_workflows)} enabled custom workflows")

            except Exception as e:
                logger.error(f"Failed to load workflows: {e}")
            finally:
                break  # Only need one iteration

    def _add_job(self, config):
        """Add or update a scheduled job for a workflow config"""
        job_id = f"workflow_{config.id}"

        # Remove existing job if present
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)

        # Get trigger based on frequency
        trigger = self._get_trigger(config.frequency, config.cron_expression)

        if trigger is None:
            logger.debug(f"Workflow {config.id} has manual frequency, skipping schedule")
            return

        # Add job
        self.scheduler.add_job(
            func=self._execute_workflow_job,
            trigger=trigger,
            id=job_id,
            args=[config.id, config.user_id, config.workflow_type],
            name=f"{config.workflow_type} for user {config.user_id}",
            replace_existing=True
        )

        logger.info(f"Scheduled workflow {config.id} ({config.workflow_type}) with frequency {config.frequency}")

    def _add_custom_job(self, workflow):
        """Add or update a scheduled job for a custom workflow definition"""
        job_id = f"custom_workflow_{workflow.id}"

        # Remove existing job if present
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)

        # Get trigger based on frequency (pass scheduled_at for one-time runs)
        trigger = self._get_trigger(workflow.frequency, workflow.cron_expression, workflow.scheduled_at)

        if trigger is None:
            logger.debug(f"Custom workflow {workflow.id} has manual frequency, skipping schedule")
            return

        # Add job
        self.scheduler.add_job(
            func=self._execute_custom_workflow_job,
            trigger=trigger,
            id=job_id,
            args=[workflow.id, workflow.user_id],
            name=f"Custom: {workflow.name} for user {workflow.user_id}",
            replace_existing=True
        )

        logger.info(f"Scheduled custom workflow {workflow.id} ({workflow.name}) with frequency {workflow.frequency}")

    def _get_trigger(self, frequency: str, cron_expression: Optional[str] = None, scheduled_at: Optional[datetime] = None):
        """
        Get APScheduler trigger based on frequency.

        Args:
            frequency: 'hourly', '6hours', 'daily', 'weekly', 'manual', 'once', or 'custom'
            cron_expression: Custom cron expression (only used if frequency is 'custom')
            scheduled_at: Specific datetime for one-time runs (only used if frequency is 'once')

        Returns:
            APScheduler trigger or None for manual
        """
        if frequency == "manual":
            return None

        # One-time scheduled run
        if frequency == "once":
            if scheduled_at is None:
                logger.warning("One-time workflow has no scheduled_at, skipping")
                return None
            # If scheduled time is in the past, skip
            now = datetime.now()
            if scheduled_at < now:
                logger.warning(f"One-time workflow scheduled_at {scheduled_at} is in the past, skipping")
                return None
            return DateTrigger(run_date=scheduled_at)

        if frequency == "custom" and cron_expression:
            try:
                return CronTrigger.from_crontab(cron_expression)
            except Exception as e:
                logger.error(f"Invalid cron expression '{cron_expression}': {e}")
                return None

        # Predefined frequencies
        triggers = {
            "hourly": CronTrigger(minute=0),  # Every hour at :00
            "6hours": CronTrigger(hour='0,6,12,18', minute=0),  # Every 6 hours
            "daily": CronTrigger(hour=8, minute=0),  # Daily at 8:00 AM
            "weekly": CronTrigger(day_of_week='mon', hour=8, minute=0),  # Monday 8:00 AM
        }

        return triggers.get(frequency)

    async def _execute_workflow_job(
        self,
        config_id: int,
        user_id: int,
        workflow_type: str
    ):
        """
        Execute a scheduled workflow job.

        This is called by APScheduler when a job fires.
        """
        from services.workflow_engine import WorkflowEngine

        logger.info(f"Executing scheduled workflow {workflow_type} for user {user_id}")

        try:
            async for session in self.get_db_session():
                engine = WorkflowEngine(session)
                result = await engine.execute_workflow(
                    user_id=user_id,
                    workflow_type=workflow_type,
                    trigger_type="scheduled"
                )

                if result.success:
                    logger.info(f"Workflow {workflow_type} completed: {result.data}")
                else:
                    logger.error(f"Workflow {workflow_type} failed: {result.error}")

                break  # Only need one iteration

        except Exception as e:
            logger.exception(f"Failed to execute workflow {workflow_type}: {e}")

    async def _execute_custom_workflow_job(
        self,
        workflow_def_id: int,
        user_id: int
    ):
        """
        Execute a scheduled custom workflow job.

        This is called by APScheduler when a custom workflow job fires.
        """
        from services.workflow_engine import WorkflowEngine

        logger.info(f"Executing scheduled custom workflow {workflow_def_id} for user {user_id}")

        try:
            async for session in self.get_db_session():
                engine = WorkflowEngine(session)
                result = await engine.execute_custom_workflow(
                    user_id=user_id,
                    workflow_def_id=workflow_def_id,
                    trigger_type="scheduled"
                )

                if result.success:
                    logger.info(f"Custom workflow {workflow_def_id} completed successfully")
                else:
                    logger.error(f"Custom workflow {workflow_def_id} failed: {result.error}")

                break  # Only need one iteration

        except Exception as e:
            logger.exception(f"Failed to execute custom workflow {workflow_def_id}: {e}")

    async def add_or_update_workflow(self, config):
        """
        Add or update a workflow schedule.

        Called when user enables a workflow or changes settings.
        """
        if config.enabled:
            self._add_job(config)
        else:
            self.remove_workflow(config.id)

    def remove_workflow(self, config_id: int):
        """Remove a workflow from the scheduler"""
        job_id = f"workflow_{config_id}"

        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)
            logger.info(f"Removed scheduled workflow {config_id}")

    async def add_or_update_custom_workflow(self, workflow):
        """
        Add or update a custom workflow schedule.

        Called when user enables a custom workflow or changes settings.
        """
        if workflow.enabled:
            self._add_custom_job(workflow)
        else:
            await self.remove_custom_workflow(workflow.id)

    async def remove_custom_workflow(self, workflow_id: int):
        """Remove a custom workflow from the scheduler"""
        job_id = f"custom_workflow_{workflow_id}"

        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)
            logger.info(f"Removed scheduled custom workflow {workflow_id}")

    def get_next_run_time(self, config_id: int) -> Optional[datetime]:
        """Get the next scheduled run time for a workflow"""
        job_id = f"workflow_{config_id}"
        job = self.scheduler.get_job(job_id)

        if job:
            return job.next_run_time

        return None

    def get_scheduled_jobs(self) -> list:
        """Get all scheduled jobs for debugging/monitoring"""
        return [
            {
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger)
            }
            for job in self.scheduler.get_jobs()
        ]


# Global scheduler instance
_scheduler: Optional[WorkflowScheduler] = None


def get_scheduler() -> Optional[WorkflowScheduler]:
    """Get the global scheduler instance"""
    return _scheduler


def init_scheduler(get_db_session) -> WorkflowScheduler:
    """Initialize the global scheduler instance"""
    global _scheduler
    _scheduler = WorkflowScheduler(get_db_session)
    return _scheduler
