"""
Bash command streaming infrastructure for real-time terminal output.

This module provides a global event emitter that allows the execute_bash tool
to stream output in real-time while the command is running, similar to Claude Code.
"""

import asyncio
import logging
from typing import Dict, Optional, AsyncIterator
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class BashOutputEvent:
    """Event emitted during bash command execution"""
    thread_id: str
    tool_call_id: str
    event_type: str  # 'command', 'output', 'complete', 'error'
    content: str
    timestamp: datetime
    exit_code: Optional[int] = None


class BashOutputStreamer:
    """
    Global singleton for streaming bash output events.

    Tools can emit events to this streamer, and the AG-UI wrapper
    will consume and forward them as SSE events to the frontend.
    """

    def __init__(self):
        self._queues: Dict[str, asyncio.Queue] = {}
        self._lock = asyncio.Lock()

    async def create_stream(self, thread_id: str) -> None:
        """Create a new output stream for a conversation thread"""
        async with self._lock:
            if thread_id not in self._queues:
                self._queues[thread_id] = asyncio.Queue()
                logger.info(f"[BASH_STREAM] Created output stream for thread {thread_id}")

    async def emit(self, event: BashOutputEvent) -> None:
        """Emit a bash output event"""
        async with self._lock:
            if event.thread_id in self._queues:
                await self._queues[event.thread_id].put(event)
                logger.debug(f"[BASH_STREAM] Emitted {event.event_type} event for thread {event.thread_id}")
            else:
                logger.warning(f"[BASH_STREAM] No queue found for thread {event.thread_id}, creating one")
                self._queues[event.thread_id] = asyncio.Queue()
                await self._queues[event.thread_id].put(event)

    async def get_stream(self, thread_id: str) -> AsyncIterator[BashOutputEvent]:
        """
        Get an async iterator for bash events for a specific thread.

        This is used by the AG-UI wrapper to consume events and forward them.
        """
        await self.create_stream(thread_id)

        queue = self._queues[thread_id]

        while True:
            try:
                # Wait for events with timeout to allow checking if we should stop
                event = await asyncio.wait_for(queue.get(), timeout=0.1)
                yield event

                # If this was a complete or error event, we're done
                if event.event_type in ('complete', 'error'):
                    logger.info(f"[BASH_STREAM] Stream ended for thread {thread_id}")
                    break

            except asyncio.TimeoutError:
                # No event available, continue waiting
                continue
            except Exception as e:
                logger.error(f"[BASH_STREAM] Error in stream for thread {thread_id}: {e}")
                break

    async def cleanup_stream(self, thread_id: str) -> None:
        """Clean up the output stream for a conversation thread"""
        async with self._lock:
            if thread_id in self._queues:
                # Drain remaining events
                try:
                    while not self._queues[thread_id].empty():
                        self._queues[thread_id].get_nowait()
                except:
                    pass

                del self._queues[thread_id]
                logger.info(f"[BASH_STREAM] Cleaned up stream for thread {thread_id}")

    def has_active_stream(self, thread_id: str) -> bool:
        """Check if there's an active stream for a thread"""
        return thread_id in self._queues and not self._queues[thread_id].empty()


# Global singleton instance
bash_streamer = BashOutputStreamer()
