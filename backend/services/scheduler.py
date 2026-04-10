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

        # Clean up orphaned "running" workflow runs from previous process
        await self._cleanup_orphaned_runs()

        # Load all enabled workflows
        await self._load_enabled_workflows()

        # Add proactive TOTP token refresh job (3:35 AM IST = 22:05 UTC)
        self._add_totp_refresh_job()

        # Add pre-market forecast batch job (08:30 IST = 03:00 UTC, weekdays)
        self._add_forecast_batch_job()

        # Add thread embedding processor (cross-thread search)
        self._add_thread_embedding_job()

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

    async def _cleanup_orphaned_runs(self):
        """Mark any 'running' workflow runs as failed on startup.

        If the service was restarted (deploy, crash, etc.) while a workflow
        was executing, its DB status stays 'running' forever. This catches
        those orphans and marks them as failed so the UI doesn't show them
        as perpetually running.
        """
        from sqlalchemy import update, text
        from database.models import WorkflowRun

        try:
            async for session in self.get_db_session():
                stmt = (
                    update(WorkflowRun)
                    .where(WorkflowRun.status == "running")
                    .values(
                        status="failed",
                        completed_at=datetime.utcnow(),
                        error_message="Service restarted while workflow was running",
                    )
                    .returning(WorkflowRun.id)
                )
                result = await session.execute(stmt)
                orphaned_ids = [row[0] for row in result.fetchall()]
                await session.commit()
                if orphaned_ids:
                    logger.warning(
                        "Cleaned up %d orphaned 'running' workflow runs on startup: %s",
                        len(orphaned_ids), orphaned_ids,
                    )
                break
        except Exception as e:
            logger.error("Failed to clean up orphaned workflow runs: %s", e)

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

    # Max auto-retries for failed one-time awakenings (total attempts = MAX_AWAKENING_RETRIES + 1)
    MAX_AWAKENING_RETRIES = 2
    AWAKENING_RETRY_DELAY_SECONDS = 90

    async def _execute_custom_workflow_job(
        self,
        workflow_def_id: int,
        user_id: int,
        retry_count: int = 0
    ):
        """
        Execute a scheduled custom workflow job.

        This is called by APScheduler when a custom workflow job fires.
        For one-time awakenings that fail, auto-retries up to MAX_AWAKENING_RETRIES
        times with a 90-second delay between attempts.
        """
        from services.workflow_engine import WorkflowEngine

        attempt = retry_count + 1
        attempt_label = f" (attempt {attempt}/{self.MAX_AWAKENING_RETRIES + 1})" if retry_count > 0 else ""
        logger.info(f"Executing scheduled custom workflow {workflow_def_id} for user {user_id}{attempt_label}")

        failed = False
        error_msg = None
        is_one_time = False

        try:
            async for session in self.get_db_session():
                engine = WorkflowEngine(session)

                # Check if this is a one-time workflow (for retry logic)
                from database.models import WorkflowDefinition
                wf = await session.get(WorkflowDefinition, workflow_def_id)
                is_one_time = wf and wf.frequency == "once" and wf.thread_id is not None

                result = await engine.execute_custom_workflow(
                    user_id=user_id,
                    workflow_def_id=workflow_def_id,
                    trigger_type="scheduled"
                )

                if result.success:
                    logger.info(f"Custom workflow {workflow_def_id} completed successfully{attempt_label}")
                else:
                    logger.error(f"Custom workflow {workflow_def_id} failed: {result.error}{attempt_label}")
                    failed = True
                    error_msg = result.error

                break  # Only need one iteration

        except Exception as e:
            logger.exception(f"Failed to execute custom workflow {workflow_def_id}: {e}")
            failed = True
            error_msg = str(e)

        # Auto-retry failed one-time awakenings
        if failed and is_one_time and retry_count < self.MAX_AWAKENING_RETRIES:
            retry_at = datetime.now() + timedelta(seconds=self.AWAKENING_RETRY_DELAY_SECONDS)
            next_attempt = retry_count + 1
            job_id = f"custom_workflow_{workflow_def_id}_retry{next_attempt}"
            logger.warning(
                f"Scheduling retry {next_attempt}/{self.MAX_AWAKENING_RETRIES} for awakening "
                f"{workflow_def_id} at {retry_at} (failed: {error_msg})"
            )
            self.scheduler.add_job(
                func=self._execute_custom_workflow_job,
                trigger=DateTrigger(run_date=retry_at),
                id=job_id,
                args=[workflow_def_id, user_id, next_attempt],
                name=f"Retry {next_attempt}: workflow {workflow_def_id} for user {user_id}",
                replace_existing=True
            )
        elif failed and is_one_time and retry_count >= self.MAX_AWAKENING_RETRIES:
            logger.error(
                f"Awakening {workflow_def_id} exhausted all {self.MAX_AWAKENING_RETRIES} retries. Giving up."
            )

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

    def _add_totp_refresh_job(self):
        """Add a daily job to proactively refresh Upstox tokens via TOTP.

        Runs at 22:05 UTC (3:35 AM IST) — shortly after Upstox tokens
        expire at ~22:00 UTC (3:30 AM IST). This ensures tokens are
        refreshed even if no user request or daemon poll triggers it.
        """
        job_id = "totp_token_refresh"

        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)

        self.scheduler.add_job(
            func=self._refresh_all_totp_tokens,
            trigger=CronTrigger(hour=22, minute=5),  # 22:05 UTC = 3:35 AM IST
            id=job_id,
            name="Proactive TOTP token refresh (3:35 AM IST)",
            replace_existing=True,
        )
        logger.info("Scheduled proactive TOTP token refresh at 22:05 UTC (3:35 AM IST)")

    async def _refresh_all_totp_tokens(self):
        """Refresh Upstox tokens for all users with TOTP credentials."""
        from database.models import User as DBUser
        from database.session import get_db_session

        logger.info("Proactive TOTP refresh: starting for all eligible users")

        try:
            async with get_db_session() as session:
                result = await session.execute(
                    select(DBUser.id).where(
                        DBUser.upstox_mobile.isnot(None),
                        DBUser.upstox_totp_secret.isnot(None),
                    )
                )
                user_ids = [row[0] for row in result.all()]

            if not user_ids:
                logger.info("Proactive TOTP refresh: no users with TOTP credentials")
                return

            logger.info("Proactive TOTP refresh: found %d eligible users", len(user_ids))

            from api.upstox_oauth import auto_refresh_upstox_token

            for uid in user_ids:
                try:
                    token = await auto_refresh_upstox_token(uid)
                    if token:
                        logger.info("Proactive TOTP refresh: SUCCESS for user %d", uid)
                    else:
                        logger.warning("Proactive TOTP refresh: FAILED for user %d (returned None)", uid)
                except Exception as e:
                    logger.error("Proactive TOTP refresh: exception for user %d: %s", uid, e)

        except Exception as e:
            logger.exception("Proactive TOTP refresh: fatal error: %s", e)

    def _add_forecast_batch_job(self):
        """Add a pre-market batch forecast job for all users' watchlist symbols.

        Runs at 03:00 UTC (08:30 IST) on weekdays, before market open.
        Stores results in price_forecasts table so morning awakenings
        can read cached forecasts instantly via nf-forecast --latest.

        Skips gracefully if TimesFM is not installed or no watchlists exist.
        """
        job_id = "premarket_forecast_batch"

        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)

        self.scheduler.add_job(
            func=self._run_forecast_batch,
            trigger=CronTrigger(hour=3, minute=0, day_of_week="mon-fri"),
            id=job_id,
            name="Pre-market TimesFM batch forecast (08:30 IST)",
            replace_existing=True,
        )
        logger.info("Scheduled pre-market forecast batch at 03:00 UTC (08:30 IST) weekdays")

    async def _run_forecast_batch(self):
        """Run TimesFM forecasts for all users' watchlist symbols."""
        from database.models import User as DBUser, WatchlistItem
        from database.session import get_db_session

        # Check if TimesFM is available
        try:
            from services.timesfm_forecaster import TimesFMForecaster, TIMESFM_AVAILABLE
            if not TIMESFM_AVAILABLE:
                logger.info("Forecast batch: TimesFM not installed, skipping")
                return
        except ImportError:
            logger.info("Forecast batch: timesfm_forecaster not available, skipping")
            return

        logger.info("Forecast batch: starting pre-market forecasts")

        try:
            async with get_db_session() as session:
                # Get all users with watchlist items
                result = await session.execute(
                    select(DBUser.id).join(
                        WatchlistItem, DBUser.id == WatchlistItem.user_id
                    ).distinct()
                )
                user_ids = [row[0] for row in result.all()]

            if not user_ids:
                logger.info("Forecast batch: no users with watchlist items, skipping")
                return

            logger.info("Forecast batch: found %d users with watchlists", len(user_ids))

            for uid in user_ids:
                await self._forecast_user_watchlist(uid)

        except Exception as e:
            logger.exception("Forecast batch: fatal error: %s", e)

    async def _forecast_user_watchlist(self, user_id: int):
        """Run forecasts for a single user's watchlist."""
        import asyncio

        from api.upstox_oauth import get_user_upstox_token
        from database.models import PriceForecast, WatchlistItem
        from database.session import get_db_session
        from services.timesfm_forecaster import TimesFMForecaster
        from services.upstox_client import UpstoxClient

        try:
            # Get user's Upstox token
            token = await get_user_upstox_token(user_id)
            if not token:
                logger.warning("Forecast batch: no valid token for user %d, skipping", user_id)
                return

            # Get watchlist symbols
            async with get_db_session() as session:
                result = await session.execute(
                    select(WatchlistItem.symbol).where(WatchlistItem.user_id == user_id)
                )
                symbols = [row[0] for row in result.all()]

            if not symbols:
                return

            logger.info("Forecast batch: user %d — %d symbols", user_id, len(symbols))

            client = UpstoxClient(access_token=token, user_id=user_id)
            forecaster = TimesFMForecaster()

            for sym in symbols:
                try:
                    candles = await client.get_historical_data(sym, interval="day", days=365)
                    if not candles:
                        continue

                    close_prices = [c.close for c in candles]
                    current_price = close_prices[-1]

                    result = forecaster.forecast_single(
                        symbol=sym,
                        close_prices=close_prices,
                        current_price=current_price,
                        horizon=5,
                    )

                    # Store in DB
                    async with get_db_session() as session:
                        forecast = PriceForecast(
                            user_id=user_id,
                            symbol=sym,
                            horizon_days=result.forecast_horizon,
                            current_price=result.current_price,
                            data_points_used=result.data_points_used,
                            signal=result.signal,
                            confidence=result.confidence,
                            predicted_change_pct=result.predicted_change_pct,
                            predictions=[p.__dict__ for p in result.predictions],
                            model_version=result.model,
                            inference_time_ms=result.inference_time_ms,
                        )
                        session.add(forecast)
                        await session.commit()

                    logger.info("Forecast batch: user %d — %s: %s (%.1f%%)",
                                user_id, sym, result.signal, result.predicted_change_pct)

                except Exception as e:
                    logger.warning("Forecast batch: user %d — %s failed: %s", user_id, sym, e)

                # Brief pause between symbols to avoid hammering Upstox
                await asyncio.sleep(0.5)

        except Exception as e:
            logger.error("Forecast batch: user %d failed: %s", user_id, e)

    def _add_thread_embedding_job(self):
        """Add periodic thread embedding processor for cross-thread search.

        Runs every 60 seconds, processes threads that have been idle for 2+ minutes
        with new unembedded content. Lightweight — skips quickly if nothing to do.
        """
        job_id = "thread_embedding_processor"

        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)

        self.scheduler.add_job(
            func=self._run_thread_embeddings,
            trigger=IntervalTrigger(seconds=60),
            id=job_id,
            name="Thread Embedding Processor (60s)",
            replace_existing=True,
        )
        logger.info("Scheduled thread embedding processor (every 60s)")

    async def _run_thread_embeddings(self):
        """Process dirty threads — called every 60s by scheduler."""
        try:
            from services.thread_embedder import process_dirty_threads
            await process_dirty_threads()
        except Exception as e:
            logger.error("Thread embedding processor failed: %s", e)

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
