"""
HITL (Human-in-the-Loop) event streaming infrastructure.

Provides a global event queue for HITL approval events that can be consumed
by the AG-UI wrapper and forwarded as SSE events to the frontend.
"""

import asyncio
import logging
from typing import Dict, Optional
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class HITLEvent:
    """Event emitted during HITL approval workflow"""
    thread_id: str
    event_type: str  # 'approval_request', 'approved', 'rejected', 'timeout'
    approval_id: str
    timestamp: datetime
    tool_name: Optional[str] = None
    tool_args: Optional[dict] = None
    explanation: Optional[str] = None
    reason: Optional[str] = None


class HITLEventStreamer:
    """
    Global singleton for streaming HITL events.

    The HITLManager emits events to this streamer, and the AG-UI wrapper
    consumes and forwards them as SSE events to the frontend.
    """

    def __init__(self):
        self._queues: Dict[str, asyncio.Queue] = {}
        self._lock = asyncio.Lock()

    async def create_stream(self, thread_id: str) -> None:
        """Create a new event stream for a conversation thread"""
        async with self._lock:
            if thread_id not in self._queues:
                self._queues[thread_id] = asyncio.Queue()
                logger.info(f"[HITL_STREAM] Created event stream for thread {thread_id}")

    async def emit(self, event: HITLEvent) -> None:
        """Emit a HITL event"""
        async with self._lock:
            if event.thread_id in self._queues:
                await self._queues[event.thread_id].put(event)
                logger.debug(f"[HITL_STREAM] Emitted {event.event_type} event for thread {event.thread_id}")
            else:
                logger.warning(f"[HITL_STREAM] No queue found for thread {event.thread_id}, creating one")
                self._queues[event.thread_id] = asyncio.Queue()
                await self._queues[event.thread_id].put(event)

    def try_get_event(self, thread_id: str) -> Optional[HITLEvent]:
        """
        Try to get a HITL event without blocking.

        Returns:
            HITLEvent if one is available, None otherwise
        """
        if thread_id in self._queues:
            queue = self._queues[thread_id]
            if not queue.empty():
                try:
                    return queue.get_nowait()
                except asyncio.QueueEmpty:
                    return None
        return None

    async def cleanup(self, thread_id: str) -> None:
        """Clean up the event queue for a thread"""
        async with self._lock:
            if thread_id in self._queues:
                del self._queues[thread_id]
                logger.info(f"[HITL_STREAM] Cleaned up event stream for thread {thread_id}")


# Global singleton instance
hitl_streamer = HITLEventStreamer()
