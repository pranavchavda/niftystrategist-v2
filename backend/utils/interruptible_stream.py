"""
Interruptible stream wrapper for AG-UI responses.

Wraps SSE streams to enable graceful interruption.
"""

import json
import logging
import asyncio
from typing import AsyncIterator
from datetime import datetime

logger = logging.getLogger(__name__)


async def make_interruptible_stream(
    original_stream: AsyncIterator[bytes],
    thread_id: str,
    conversation_state=None
) -> AsyncIterator[bytes]:
    """
    Wrap a stream to make it interruptible.

    Periodically checks for interrupt signals and gracefully stops the stream.

    Args:
        original_stream: The original SSE stream
        thread_id: Thread ID for interrupt management
        conversation_state: ConversationState to save partial progress
    """
    from .interrupt_manager import get_interrupt_manager

    interrupt_mgr = get_interrupt_manager()

    # Get existing signal if already registered, otherwise create new one
    signal = interrupt_mgr.get_signal(thread_id)
    if signal is None:
        signal = interrupt_mgr.register_stream(thread_id)
        logger.info(f"[Interrupt] Registered new signal for {thread_id}")
    else:
        logger.info(f"[Interrupt] Using existing signal for {thread_id}")

    partial_response = ""

    try:
        async for chunk in original_stream:
            # Check for interruption before yielding
            if signal.is_set():
                logger.info(f"[Interrupt] Stream interrupted for {thread_id}: {signal.reason}")

                # Send interruption event to UI
                interrupt_event = {
                    "type": "INTERRUPTED",
                    "reason": signal.reason or "User requested stop",
                    "partial_response": partial_response
                }
                yield f"data: {json.dumps(interrupt_event)}\n\n".encode()

                # Save partial response to conversation state
                if conversation_state:
                    conversation_state.partial_response = partial_response
                    conversation_state.is_interrupted = True
                    conversation_state.interrupted_at = datetime.now()
                    conversation_state.interrupt_reason = signal.reason

                # Stop streaming
                break

            # Yield the chunk
            yield chunk

            # Try to extract text content for partial response tracking
            try:
                chunk_str = chunk.decode('utf-8') if isinstance(chunk, bytes) else chunk
                if chunk_str.startswith('data: '):
                    data_str = chunk_str[6:].strip()
                    if data_str and data_str != '[DONE]':
                        event = json.loads(data_str)
                        if event.get('type') == 'TEXT_MESSAGE_CONTENT':
                            content = event.get('content', '')
                            partial_response += content
            except:
                pass  # Ignore parsing errors for partial response tracking

    finally:
        # Always unregister when done
        interrupt_mgr.unregister_stream(thread_id)
        logger.info(f"[Interrupt] Stream finished for {thread_id}")
