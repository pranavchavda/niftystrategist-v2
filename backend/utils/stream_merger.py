"""
Stream merger utility for combining AG-UI stream with HITL events.

This module provides a clean way to merge two async generators:
1. The main Pydantic AI AG-UI stream
2. HITL approval events (which can arrive even when main stream is blocked)
"""

import asyncio
import logging
from typing import AsyncIterator, Tuple, Any

logger = logging.getLogger(__name__)


async def merge_streams(
    main_stream: AsyncIterator[bytes],
    event_poller: AsyncIterator[Tuple[str, Any]],
) -> AsyncIterator[bytes]:
    """
    Merge two async streams using a queue-based approach.

    Args:
        main_stream: Primary stream (AG-UI events from Pydantic AI)
        event_poller: Secondary stream (HITL events)

    Yields:
        bytes: SSE-encoded events from either stream
    """
    output_queue = asyncio.Queue()
    main_done = asyncio.Event()
    poller_done = asyncio.Event()

    # Task 1: Read from main stream
    async def read_main_stream():
        chunk_count = 0
        logger.info("[MERGE] Starting to read main stream...")
        try:
            async for chunk in main_stream:
                chunk_count += 1
                logger.info(f"[MERGE] Main stream chunk #{chunk_count}")
                await output_queue.put(('main', chunk))
        except Exception as e:
            # Log the error and put it in the queue so it can be handled by the wrapper
            logger.error(f"[MERGE] Main stream error: {e}", exc_info=True)
            await output_queue.put(('error', e))
        finally:
            main_done.set()
            logger.info(f"[MERGE] Main stream finished after {chunk_count} chunks")

    # Task 2: Read from event poller
    async def read_event_poller():
        try:
            async for event_type, event_data in event_poller:
                await output_queue.put((event_type, event_data))
        except Exception as e:
            logger.error(f"[MERGE] Event poller error: {e}")
        finally:
            poller_done.set()
            logger.debug("[MERGE] Event poller finished")

    # Start both tasks
    main_task = asyncio.create_task(read_main_stream())
    poller_task = asyncio.create_task(read_event_poller())

    try:
        # Consume from merged queue until main stream is done
        # Note: We don't wait for poller_done because the HITL poller runs indefinitely
        # It will be cancelled in the finally block when the main stream ends
        while not (main_done.is_set() and output_queue.empty()):
            try:
                # Wait for next item with timeout
                item_type, item_data = await asyncio.wait_for(
                    output_queue.get(),
                    timeout=0.2
                )

                # Yield the item (caller will handle encoding based on type)
                yield item_type, item_data

            except asyncio.TimeoutError:
                # No items available, loop will check if streams are done
                continue

    finally:
        # Cleanup: cancel any remaining tasks
        for task in [main_task, poller_task]:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
