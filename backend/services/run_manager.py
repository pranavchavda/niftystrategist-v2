"""
Background Run Manager for async agent execution
Handles runs that persist after client disconnection
"""

import asyncio
import uuid
from datetime import datetime, timezone
from utils.datetime_utils import utc_now_naive
from typing import Dict, Optional, AsyncGenerator, Any
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from database.models import Run
from utils.interrupt_manager import InterruptManager


class RunManager:
    """
    Singleton manager for background agent runs

    Tracks active runs in memory and coordinates with database
    Ensures runs complete even after client disconnection
    """

    _instance: Optional['RunManager'] = None
    _lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self._active_runs: Dict[str, asyncio.Task] = {}
            self._run_results: Dict[str, Dict[str, Any]] = {}  # In-memory cache for completed runs
            self._run_generators: Dict[str, AsyncGenerator] = {}  # Active SSE generators
            self._initialized = True

    async def create_run(
        self,
        session: AsyncSession,
        thread_id: str,
        user_id: str,
        user_message: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create a new run record in pending state

        Args:
            session: Database session
            thread_id: Conversation thread ID
            user_id: User ID
            user_message: The user's message that triggered the run
            metadata: Optional metadata (model, etc.)

        Returns:
            run_id: UUID of the created run
        """
        run_id = str(uuid.uuid4())

        run = Run(
            id=run_id,
            thread_id=thread_id,
            user_id=user_id,
            user_message=user_message,
            status="pending",
            run_metadata=metadata or {}
        )

        session.add(run)
        await session.commit()

        return run_id

    async def start_run(
        self,
        run_id: str,
        session: AsyncSession,
        agent_task: asyncio.Task
    ):
        """
        Start a background run

        Args:
            run_id: Run ID
            session: Database session
            agent_task: The asyncio Task executing the agent
        """
        async with self._lock:
            self._active_runs[run_id] = agent_task

        # Update status to in_progress
        await session.execute(
            update(Run)
            .where(Run.id == run_id)
            .values(status="in_progress", started_at=utc_now_naive())
        )
        await session.commit()

    async def complete_run(
        self,
        run_id: str,
        session: AsyncSession,
        result: Dict[str, Any],
        error: Optional[str] = None
    ):
        """
        Mark a run as completed and store results

        Args:
            run_id: Run ID
            session: Database session
            result: Complete response data {text, tool_calls, reasoning, todos}
            error: Error message if run failed
        """
        status = "failed" if error else "completed"

        # Store result in database
        await session.execute(
            update(Run)
            .where(Run.id == run_id)
            .values(
                status=status,
                completed_at=utc_now_naive(),
                result=result,
                error=error
            )
        )
        await session.commit()

        # Cache result in memory for quick access
        async with self._lock:
            self._run_results[run_id] = {
                "status": status,
                "result": result,
                "error": error,
                "completed_at": utc_now_naive().isoformat()
            }

            # Remove from active runs
            if run_id in self._active_runs:
                del self._active_runs[run_id]

            # Remove generator if exists
            if run_id in self._run_generators:
                del self._run_generators[run_id]

    async def cancel_run(
        self,
        run_id: str,
        session: AsyncSession
    ):
        """
        Cancel an active run

        Args:
            run_id: Run ID
            session: Database session
        """
        async with self._lock:
            # Cancel the task if it's running
            if run_id in self._active_runs:
                task = self._active_runs[run_id]
                if not task.done():
                    task.cancel()
                del self._active_runs[run_id]

            # Signal interruption
            from utils.interrupt_manager import get_interrupt_manager
            interrupt_manager = get_interrupt_manager()
            interrupt_manager.interrupt(run_id, "Run cancelled by user")

        # Update status in database
        await session.execute(
            update(Run)
            .where(Run.id == run_id)
            .values(
                status="cancelled",
                completed_at=utc_now_naive(),
                error="Run cancelled by user"
            )
        )
        await session.commit()

    async def get_run_status(
        self,
        run_id: str,
        session: AsyncSession
    ) -> Optional[Dict[str, Any]]:
        """
        Get run status and results

        Args:
            run_id: Run ID
            session: Database session

        Returns:
            Dict with status, result, error, timestamps
        """
        # Check in-memory cache first
        async with self._lock:
            if run_id in self._run_results:
                return self._run_results[run_id]

        # Query database
        result = await session.execute(
            select(Run).where(Run.id == run_id)
        )
        run = result.scalar_one_or_none()

        if not run:
            return None

        return {
            "status": run.status,
            "result": run.result,
            "error": run.error,
            "created_at": run.created_at.isoformat() if run.created_at else None,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "metadata": run.run_metadata
        }

    def register_generator(self, run_id: str, generator: AsyncGenerator):
        """
        Register an SSE generator for a run

        This allows clients to reconnect to ongoing runs
        """
        self._run_generators[run_id] = generator

    def get_generator(self, run_id: str) -> Optional[AsyncGenerator]:
        """Get the active generator for a run"""
        return self._run_generators.get(run_id)

    def is_run_active(self, run_id: str) -> bool:
        """Check if a run is currently active"""
        return run_id in self._active_runs

    async def cleanup_completed_runs(self, max_age_hours: int = 24):
        """
        Clean up old completed runs from memory cache

        Args:
            max_age_hours: Maximum age in hours to keep in cache
        """
        current_time = utc_now_naive()

        async with self._lock:
            expired_ids = []
            for run_id, data in self._run_results.items():
                completed_at = datetime.fromisoformat(data["completed_at"])
                age_hours = (current_time - completed_at).total_seconds() / 3600

                if age_hours > max_age_hours:
                    expired_ids.append(run_id)

            for run_id in expired_ids:
                del self._run_results[run_id]

    async def get_active_runs_for_user(
        self,
        user_id: str,
        session: AsyncSession
    ) -> list[Dict[str, Any]]:
        """
        Get all active runs for a user

        Args:
            user_id: User ID
            session: Database session

        Returns:
            List of active run dictionaries
        """
        result = await session.execute(
            select(Run)
            .where(Run.user_id == user_id)
            .where(Run.status.in_(["pending", "in_progress"]))
            .order_by(Run.created_at.desc())
        )
        runs = result.scalars().all()

        return [
            {
                "id": run.id,
                "thread_id": run.thread_id,
                "status": run.status,
                "user_message": run.user_message,
                "created_at": run.created_at.isoformat() if run.created_at else None,
                "started_at": run.started_at.isoformat() if run.started_at else None,
                "metadata": run.run_metadata
            }
            for run in runs
        ]


# Singleton instance
run_manager = RunManager()
