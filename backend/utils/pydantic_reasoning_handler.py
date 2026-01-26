"""
Custom event stream handler for Pydantic AI that captures GPT-5 reasoning.
This works within Pydantic AI's framework to emit reasoning events.
"""

import logging
from typing import Optional, Any
from pydantic_ai import EventStreamHandler
from pydantic_ai.result import PartStartEvent, PartDeltaEvent, ThinkingPartDelta, TextPartDelta

logger = logging.getLogger(__name__)


class ReasoningEventHandler(EventStreamHandler):
    """
    Custom event handler that intercepts Pydantic AI events.
    Unfortunately, Pydantic AI doesn't expose raw API responses,
    so we can't directly access delta.reasoning from OpenRouter.

    This handler would need to be extended with a way to access
    the raw streaming response from OpenRouter.
    """

    def __init__(self):
        super().__init__()
        self.reasoning_buffer = []
        self.content_buffer = []

    async def on_part_start(self, event: PartStartEvent) -> None:
        """Called when a new part starts."""
        logger.debug(f"Part started: {event.part}")

    async def on_part_delta(self, event: PartDeltaEvent) -> None:
        """Called when a part receives a delta update."""

        # Check if it's a thinking part (reasoning)
        if isinstance(event.delta, ThinkingPartDelta):
            if event.delta.content_delta:
                self.reasoning_buffer.append(event.delta.content_delta)
                logger.info(f"Reasoning delta captured: {event.delta.content_delta[:50]}...")

        # Regular text content
        elif isinstance(event.delta, TextPartDelta):
            if event.delta.content_delta:
                self.content_buffer.append(event.delta.content_delta)

    def get_reasoning(self) -> str:
        """Get the accumulated reasoning."""
        return ''.join(self.reasoning_buffer)

    def get_content(self) -> str:
        """Get the accumulated content."""
        return ''.join(self.content_buffer)