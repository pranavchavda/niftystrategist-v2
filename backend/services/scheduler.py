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


def _crontrigger_equiv(a, b) -> bool:
    """Return True if two CronTriggers fire on the same schedule.

    APScheduler doesn't override ``__eq__``, and field internals are private,
    so we compare the stringified expression + timezone. Used by the awakening
    reconcile loop to skip remove+re-add when the DB row hasn't changed,
    avoiding 60s churn that briefly empties the job store every minute.
    """
    if type(a) is not type(b):
        return False
    try:
        if str(getattr(a, "timezone", None)) != str(getattr(b, "timezone", None)):
            return False
        return [str(f) for f in a.fields] == [str(f) for f in b.fields]
    except Exception:
        return False


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

        # Refresh NSE ETF list once a week (Sunday 02:00 UTC = 07:30 IST)
        self._add_etf_refresh_job()

        # Daily memory maintenance — fade (importance recompute + archive) then
        # consolidate near-duplicates (20:30 UTC = 2:00 AM IST)
        self._add_memory_maintenance_job()

        # Pre-market daily learnings summarizer (02:45 UTC = 08:15 IST, weekdays)
        self._add_learnings_summary_job()

        # Candidate-scan cache refresh every 3 min during market hours. Runs the
        # scan as an isolated subprocess (memory freed each cycle — prod swaps).
        self._add_scan_cache_job()

        # Sector-flow sensor: the snapshot is now computed by a LIVE streaming
        # consumer inside the monitor daemon (monitor/sector_flow_streamer.py)
        # off the shared market feed — no historical-fetch cron. The old
        # subprocess writer was retired 2026-06-29 after its full-universe REST
        # burst saturated Upstox's rate limit and hung prod.

        # Thread embedding is now event-driven (triggered on message save)
        # instead of polling every 60s. See thread_embedder.schedule_debounced_embed()

        # Load recurring awakening schedules
        await self._load_awakening_schedules()

        # Reconcile awakening jobs every 60s — catches schedules created /
        # modified / deleted directly in the DB (e.g. via nf-mandate CLI
        # subprocess) without an in-process notification path.
        from apscheduler.triggers.interval import IntervalTrigger
        self.scheduler.add_job(
            func=self._reconcile_awakening_schedules,
            trigger=IntervalTrigger(seconds=60),
            id="reconcile_awakening_schedules",
            name="Reconcile awakening schedules from DB",
            replace_existing=True,
        )

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

    def _add_memory_maintenance_job(self):
        """Daily memory maintenance: fade (recompute importance_score + archive
        stale, unused memories) then consolidate near-duplicate clusters. See
        jobs/memory_fade.py + jobs/memory_consolidation.py. Runs 20:30 UTC
        (2:00 AM IST).
        """
        job_id = "memory_maintenance"

        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)

        self.scheduler.add_job(
            func=self._run_memory_maintenance,
            trigger=CronTrigger(hour=20, minute=30),  # 20:30 UTC = 2:00 AM IST
            id=job_id,
            name="Memory maintenance — fade + consolidate (2:00 AM IST)",
            replace_existing=True,
        )
        logger.info("Scheduled memory maintenance at 20:30 UTC (2:00 AM IST)")

    async def _run_memory_maintenance(self):
        """Run fade (score + archive) then consolidation (cluster + merge)."""
        # Fade first so stale memories are archived and excluded from clustering.
        try:
            from jobs.memory_fade import run_memory_fade
            fade = await run_memory_fade(dry_run=False)
            logger.info(
                "memory_fade: scored=%d archived=%d users=%d",
                fade.get("scored", 0),
                len(fade.get("would_archive", [])),
                fade.get("users", 0),
            )
        except Exception:
            logger.exception("memory_fade job failed")

        try:
            from jobs.memory_consolidation import run_consolidation
            cons = await run_consolidation(dry_run=False)
            logger.info(
                "memory_consolidation: clusters=%d merged=%d users=%d",
                cons.get("clusters_found", 0),
                cons.get("memories_consolidated", 0),
                cons.get("users", 0),
            )
        except Exception:
            logger.exception("memory_consolidation job failed")

        # Profile synthesis last — it reads the now-faded + consolidated memory
        # set to build each user's curated, always-injected profile.
        try:
            from jobs.memory_profile import run_profile_synthesis
            prof = await run_profile_synthesis(dry_run=False)
            logger.info(
                "memory_profile: synthesized=%d users=%d",
                prof.get("synthesized", 0),
                prof.get("users", 0),
            )
        except Exception:
            logger.exception("memory_profile job failed")

    def _add_learnings_summary_job(self):
        """Pre-market job that distils each user's prior daily thread into
        carry-over learnings (services/daily_learnings.py). Runs 00:30 UTC
        (06:00 IST) on weekdays — after any evening discussion, and a couple
        hours before the earliest awakening (First Strike Analysis, 08:15 IST)
        creates the new daily thread that injects them. Must finish before
        that first awakening, hence the early slot.
        """
        job_id = "daily_learnings_summary"

        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)

        self.scheduler.add_job(
            func=self._run_learnings_summary,
            trigger=CronTrigger(hour=0, minute=30, day_of_week="mon-fri"),
            id=job_id,
            name="Daily learnings summarizer (06:00 IST weekdays)",
            replace_existing=True,
        )
        logger.info("Scheduled daily learnings summarizer at 00:30 UTC (06:00 IST) weekdays")

    async def _run_learnings_summary(self):
        """Summarize prior daily threads into carry-over learnings."""
        try:
            from services.daily_learnings import summarize_all_users
            stats = await summarize_all_users()
            logger.info("daily learnings summary job: %s", stats)
        except Exception as e:
            logger.exception("daily learnings summary job failed: %s", e)

    # Universe the cached candidate scan covers. nifty500 = full Hero Scanner.
    SCAN_CACHE_UNIVERSE = "nifty500"

    def _add_scan_cache_job(self):
        """Refresh the cached candidate scan every 3 min during market hours.

        The scan is the snapshot's slowest + most staleness-tolerant component,
        so it lives on its own clock. Runs as an isolated subprocess (clean
        memory each cycle on a swap-pressured box). Market-hours gating + the
        weekday/holiday skip live inside ``_run_scan_cache``.
        """
        job_id = "scan_cache_refresh"
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)
        self.scheduler.add_job(
            func=self._run_scan_cache,
            trigger=IntervalTrigger(minutes=3),
            id=job_id,
            name="Candidate scan cache refresh (3 min, market hours)",
            replace_existing=True,
        )
        logger.info("Scheduled candidate scan cache refresh every 3 min (market hours)")

    @staticmethod
    def _market_open_ist() -> bool:
        """True during NSE regular hours (Mon-Fri 09:15-15:30 IST).

        Time-window + weekday gate only — holidays aren't checked here (a
        holiday scan just caches closed-market quotes harmlessly, and the
        snapshot shows market status + scan age regardless).
        """
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo("Asia/Kolkata"))
        if now.weekday() >= 5:  # Sat/Sun
            return False
        hm = now.hour * 60 + now.minute
        return (9 * 60 + 15) <= hm <= (15 * 60 + 30)

    async def _run_scan_cache(self):
        """Spawn the scan-cache writer as an isolated subprocess (market hours only)."""
        if not self._market_open_ist():
            return
        import sys
        from pathlib import Path

        backend = Path(__file__).resolve().parent.parent
        script = backend / "scripts" / "scan_cache_writer.py"
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, str(script), self.SCAN_CACHE_UNIVERSE,
                cwd=str(backend),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            # Bound the wait so a hung scan can't pile up (max_instances=1 also guards).
            # The nifty500 scan is IO-bound at ~130s on the prod box, so 120s was
            # killing every cycle and leaving the cache permanently stale. 200s
            # gives comfortable margin; if a cycle still overruns, the request-path
            # snapshot is cache-only and degrades to "no candidates" (never a 524).
            out, err = await asyncio.wait_for(proc.communicate(), timeout=200)
            if proc.returncode != 0:
                logger.warning("scan cache writer exited %s: %s", proc.returncode,
                               (err or b"").decode()[-500:])
            else:
                logger.debug("scan cache refreshed: %s", (out or b"").decode().strip()[-200:])
        except asyncio.TimeoutError:
            # Kill the orphan — wait_for cancels our await but leaves the
            # subprocess running, and back-to-back timeouts would otherwise
            # pile up scans on a small box.
            logger.warning("scan cache writer timed out (>200s); killing orphan")
            try:
                proc.kill()
                await proc.wait()
            except Exception:
                pass
        except Exception as e:
            logger.error("scan cache refresh failed: %s", e)

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

    def _add_etf_refresh_job(self):
        """Refresh the NSE ETF list weekly (Sunday 02:00 UTC = 07:30 IST).

        NSE rate-limits the live ETF API and a bundled seed ships with the
        repo as a fallback. Refreshing once a week is plenty — NSE typically
        lists 3–8 new ETFs per month.
        """
        job_id = "nse_etf_refresh"

        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)

        self.scheduler.add_job(
            func=self._refresh_etf_list,
            trigger=CronTrigger(day_of_week="sun", hour=2, minute=0),
            id=job_id,
            name="Weekly NSE ETF list refresh (Sun 07:30 IST)",
            replace_existing=True,
        )
        logger.info("Scheduled weekly NSE ETF list refresh (Sun 02:00 UTC)")

    async def _refresh_etf_list(self):
        """Pull fresh ETF list from NSE and overwrite the disk cache."""
        from services.instruments_cache import refresh_etf_cache
        try:
            ok = refresh_etf_cache()
            logger.info("Weekly ETF refresh: %s", "OK" if ok else "FAILED (kept old cache)")
        except Exception as e:
            logger.exception("Weekly ETF refresh: fatal error: %s", e)

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

    # ========================================================================
    # Recurring Awakening Schedules
    # ========================================================================

    async def _load_awakening_schedules(self):
        """Load all enabled awakening schedules and create CronTrigger jobs.

        Idempotent — `_add_awakening_job` uses `replace_existing=True` and
        job_id is keyed on schedule.id, so repeated calls are safe. Used at
        startup and by the 60s reconcile job below.

        Returns the list of enabled schedule ids. 2026-05-11: prior version
        had `return [...]` inside `try` with `finally: break`. Python's
        `break` in a `finally` overrides the pending return, so the function
        always fell through to `return []`. The reconcile job then deleted
        every scheduled awakening as "stale" each minute — Morning Scan never
        fired today.
        """
        from database.models import UserAwakeningSchedule

        enabled_ids: list[int] = []
        async for session in self.get_db_session():
            try:
                result = await session.execute(
                    select(UserAwakeningSchedule).where(
                        UserAwakeningSchedule.enabled == True
                    )
                )
                schedules = result.scalars().all()

                for schedule in schedules:
                    self._add_awakening_job(schedule)

                enabled_ids = [s.id for s in schedules]
                logger.info("Loaded %d enabled awakening schedules", len(enabled_ids))
            except Exception as e:
                logger.error("Failed to load awakening schedules: %s", e)
            break
        return enabled_ids

    async def _reconcile_awakening_schedules(self):
        """Periodic reconcile: pick up DB-direct schedule changes.

        APScheduler's job table lives in memory; CLI tools that write
        directly to the DB (e.g. `nf-mandate schedules add`) don't notify
        the scheduler in-process and their schedules silently never fire.
        This method runs every 60s, re-loads enabled schedules (idempotent
        via replace_existing), and removes any jobs whose schedule was
        disabled/deleted in the DB.

        Origin: 2026-05-08 — agent-created Tier-2 Gap-Fades schedule never
        fired because nf-mandate's _notify_scheduler_update is a no-op
        from a subprocess.
        """
        try:
            enabled_ids = await self._load_awakening_schedules()
            enabled_set = set(enabled_ids)
            for job in self.scheduler.get_jobs():
                if not job.id.startswith("awakening_"):
                    continue
                try:
                    sid = int(job.id.split("_", 1)[1])
                except (IndexError, ValueError):
                    continue
                if sid not in enabled_set:
                    self.scheduler.remove_job(job.id)
                    logger.info("Removed stale awakening job %s (schedule disabled/deleted)", job.id)
        except Exception as e:
            logger.error("Awakening reconcile failed: %s", e)

    # Catch-up window: if the most-recent prior cron fire for an awakening
    # was within this many seconds of the first time we register the job in
    # this process, fire it once now instead of waiting for tomorrow.
    # 2026-05-11: a deploy restart at 04:14:50 UTC re-added awakening_36
    # at 04:15:00.754, just past its 04:15:00 (09:45 IST) fire instant.
    # APScheduler pushed next_run_time to tomorrow and the scan never ran.
    AWAKENING_CATCH_UP_WINDOW_SEC = 600

    def _add_awakening_job(self, schedule):
        """Add a CronTrigger job for an awakening schedule.

        Uses timezone='Asia/Kolkata' directly so the user's IST times fire
        correctly regardless of server timezone (dev=EDT, prod=UTC, etc.).

        Catch-up: when this is the first time we've registered the job in
        the current process (fresh boot or first add after disable), check
        whether the most recent cron fire occurred in the last
        AWAKENING_CATCH_UP_WINDOW_SEC and, if so, queue a one-shot fire at
        that past instant. APScheduler's misfire_grace_time then runs it
        immediately. Subsequent reconcile calls hit ``existed_before=True``
        so they don't re-trigger catch-up.
        """
        from zoneinfo import ZoneInfo
        from datetime import datetime, timedelta

        job_id = f"awakening_{schedule.id}"
        existing_job = self.scheduler.get_job(job_id)
        existed_before = existing_job is not None

        day_of_week = "mon-fri" if schedule.weekdays_only else "*"
        ist = ZoneInfo("Asia/Kolkata")

        trigger = CronTrigger(
            hour=schedule.cron_hour,
            minute=schedule.cron_minute,
            day_of_week=day_of_week,
            timezone=ist,
        )

        # No-op on reconcile when the trigger is unchanged. Otherwise the 60s
        # reconcile loop would remove + re-add every job every minute (no
        # catch-up runs on reconcile, so the rebuild is pure churn). 2026-05-12.
        if existed_before and _crontrigger_equiv(existing_job.trigger, trigger):
            return

        # Catch-up scan only on first registration this process.
        catch_up_kwargs: dict = {}
        if not existed_before:
            now_ist = datetime.now(ist)
            window = timedelta(seconds=self.AWAKENING_CATCH_UP_WINDOW_SEC)
            search_from = now_ist - window
            # Walk forward from the start of the window to find the most
            # recent fire ≤ now. CronTrigger.get_next_fire_time(prev, now)
            # returns the next fire strictly after ``prev`` (or after ``now``
            # when prev is None). Iterate until we step past the present.
            prior_fire = None
            candidate = trigger.get_next_fire_time(None, search_from)
            while candidate is not None and candidate <= now_ist:
                prior_fire = candidate
                candidate = trigger.get_next_fire_time(
                    prior_fire, prior_fire + timedelta(seconds=1)
                )
            if prior_fire is not None:
                age_sec = (now_ist - prior_fire).total_seconds()
                logger.warning(
                    "Awakening %d ('%s'): missed fire at %s (%.0fs ago) — scheduling catch-up",
                    schedule.id, schedule.name, prior_fire.isoformat(), age_sec,
                )
                catch_up_kwargs["next_run_time"] = prior_fire
                # Grace must cover the age + a small buffer for the scheduler
                # tick latency, otherwise APScheduler marks the run as misfired
                # and skips it.
                catch_up_kwargs["misfire_grace_time"] = (
                    self.AWAKENING_CATCH_UP_WINDOW_SEC + 60
                )
                catch_up_kwargs["coalesce"] = True

        self.scheduler.add_job(
            func=self._execute_awakening_job,
            trigger=trigger,
            id=job_id,
            args=[schedule.id, schedule.user_id],
            name=f"Awakening: {schedule.name} for user {schedule.user_id} ({schedule.cron_hour:02d}:{schedule.cron_minute:02d} IST)",
            replace_existing=True,
            **catch_up_kwargs,
        )

        logger.info(
            "Scheduled awakening '%s' (id=%d) at %02d:%02d IST for user %d",
            schedule.name, schedule.id,
            schedule.cron_hour, schedule.cron_minute,
            schedule.user_id,
        )

    async def _execute_awakening_job(self, schedule_id: int, user_id: int):
        """Execute a recurring awakening — called by APScheduler."""
        from services.awakening_scheduler import execute_awakening
        from database.models import UserAwakeningSchedule

        logger.info("Firing awakening schedule %d for user %d", schedule_id, user_id)

        try:
            async for session in self.get_db_session():
                schedule = await session.get(UserAwakeningSchedule, schedule_id)
                if not schedule:
                    logger.warning("Awakening schedule %d not found, removing job", schedule_id)
                    self._remove_awakening_job(schedule_id)
                    break

                if not schedule.enabled:
                    logger.info("Awakening schedule %d is disabled, skipping", schedule_id)
                    break

                result = await execute_awakening(session, schedule)

                if result.get("success"):
                    if result.get("skipped"):
                        logger.info("Awakening %d skipped: %s", schedule_id, result.get("reason"))
                    else:
                        logger.info(
                            "Awakening %d completed in %dms",
                            schedule_id, result.get("duration_ms", 0)
                        )
                else:
                    logger.error("Awakening %d failed: %s", schedule_id, result.get("error"))

                break
        except Exception as e:
            logger.exception("Failed to execute awakening %d: %s", schedule_id, e)

    def _remove_awakening_job(self, schedule_id: int):
        """Remove an awakening job from the scheduler."""
        job_id = f"awakening_{schedule_id}"
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)
            logger.info("Removed awakening job %s", job_id)

    async def add_or_update_awakening(self, schedule):
        """Add, update, or remove an awakening schedule job.

        Called by the API when a user creates/updates/enables/disables a schedule.
        """
        if schedule.enabled:
            self._add_awakening_job(schedule)
        else:
            self._remove_awakening_job(schedule.id)

    async def reload_awakening_schedules(self, user_id: int):
        """Reload all awakening jobs for a specific user.

        Called when the user changes multiple schedules at once.
        """
        from database.models import UserAwakeningSchedule

        # Remove all existing awakening jobs for this user
        for job in self.scheduler.get_jobs():
            if job.id.startswith("awakening_"):
                # Check if this job belongs to the user
                if len(job.args) >= 2 and job.args[1] == user_id:
                    self.scheduler.remove_job(job.id)

        # Reload from DB
        async for session in self.get_db_session():
            try:
                result = await session.execute(
                    select(UserAwakeningSchedule).where(
                        UserAwakeningSchedule.user_id == user_id,
                        UserAwakeningSchedule.enabled == True,
                    )
                )
                schedules = result.scalars().all()
                for schedule in schedules:
                    self._add_awakening_job(schedule)
                logger.info("Reloaded %d awakening schedules for user %d", len(schedules), user_id)
            except Exception as e:
                logger.error("Failed to reload awakening schedules for user %d: %s", user_id, e)
            finally:
                break

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
