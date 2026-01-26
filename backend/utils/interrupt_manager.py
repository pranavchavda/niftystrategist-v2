"""
Interrupt Manager for handling mid-task conversation interruptions.

Allows users to stop agents mid-execution and redirect them to new tasks
while preserving partial progress and queuing additional messages.
"""

import asyncio
import logging
from typing import Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class InterruptSignal:
    """
    Signal for interrupting an active agent task.

    Uses asyncio.Event for graceful cancellation.
    """

    def __init__(self, thread_id: str):
        self.thread_id = thread_id
        self.event = asyncio.Event()
        self.created_at = datetime.now()
        self.reason: Optional[str] = None

    def set(self, reason: str = "User interrupt"):
        """Signal interruption"""
        self.reason = reason
        self.event.set()
        logger.info(f"[Interrupt] Signal set for {self.thread_id}: {reason}")

    async def wait(self, timeout: Optional[float] = None) -> bool:
        """
        Wait for interrupt signal.

        Returns True if interrupted, False if timeout.
        """
        try:
            if timeout:
                await asyncio.wait_for(self.event.wait(), timeout=timeout)
            else:
                await self.event.wait()
            return True
        except asyncio.TimeoutError:
            return False

    def is_set(self) -> bool:
        """Check if interrupted"""
        return self.event.is_set()

    def clear(self):
        """Clear interrupt signal"""
        self.event.clear()
        self.reason = None


class InterruptManager:
    """
    Global manager for tracking active streams and handling interrupts.

    Singleton pattern - use get_interrupt_manager() to access.
    """

    _instance: Optional['InterruptManager'] = None

    def __init__(self):
        # Track active interrupt signals per conversation
        self.active_signals: Dict[str, InterruptSignal] = {}

        # Track active tasks per conversation
        self.active_tasks: Dict[str, asyncio.Task] = {}

        logger.info("[InterruptManager] Initialized")

    @classmethod
    def get_instance(cls) -> 'InterruptManager':
        """Get or create singleton instance"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register_stream(self, thread_id: str) -> InterruptSignal:
        """
        Register a new active stream and return its interrupt signal.

        Call this when starting a new agent execution.
        """
        # Cancel any existing signal for this thread
        if thread_id in self.active_signals:
            logger.warning(f"[Interrupt] Replacing existing signal for {thread_id}")
            self.active_signals[thread_id].set("New request started")

        # Create new signal
        signal = InterruptSignal(thread_id)
        self.active_signals[thread_id] = signal

        logger.info(f"[Interrupt] Registered stream for {thread_id}")
        return signal

    def interrupt(self, thread_id: str, reason: str = "User interrupt") -> bool:
        """
        Interrupt an active stream.

        Returns True if stream was interrupted, False if no active stream.
        """
        if thread_id not in self.active_signals:
            logger.warning(f"[Interrupt] No active signal for {thread_id}")
            return False

        signal = self.active_signals[thread_id]
        signal.set(reason)

        logger.info(f"[Interrupt] Interrupted {thread_id}: {reason}")
        return True

    def unregister_stream(self, thread_id: str):
        """
        Unregister a stream when it completes or is interrupted.

        Call this in finally block of stream handler.
        """
        if thread_id in self.active_signals:
            del self.active_signals[thread_id]
            logger.info(f"[Interrupt] Unregistered stream for {thread_id}")

    def is_interrupted(self, thread_id: str) -> bool:
        """Check if a thread is interrupted"""
        if thread_id not in self.active_signals:
            return False
        return self.active_signals[thread_id].is_set()

    def get_signal(self, thread_id: str) -> Optional[InterruptSignal]:
        """Get interrupt signal for a thread"""
        return self.active_signals.get(thread_id)

    def get_active_streams(self) -> list[str]:
        """Get list of active thread IDs"""
        return list(self.active_signals.keys())


# Global singleton instance
def get_interrupt_manager() -> InterruptManager:
    """Get the global interrupt manager instance"""
    return InterruptManager.get_instance()
