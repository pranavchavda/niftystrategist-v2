"""
Handler for GPT-5 reasoning stream integration with AG-UI protocol.
Captures and emits reasoning as special SSE events.
"""

import json
import asyncio
import logging
from typing import AsyncIterator, Optional, Dict, Any
from datetime import datetime
from .reasoning_stream import ReasoningStreamClient, StreamChunk
from .sse_events import SSEEventEmitter

logger = logging.getLogger(__name__)


class ReasoningEvent:
    """Format reasoning events for SSE"""

    @staticmethod
    def reasoning_start() -> str:
        """Event when reasoning begins"""
        return f"data: {json.dumps({'type': 'REASONING_START', 'timestamp': datetime.now().isoformat()})}\n\n"

    @staticmethod
    def reasoning_content(text: str) -> str:
        """Event with reasoning text chunk"""
        return f"data: {json.dumps({'type': 'REASONING_CONTENT', 'delta': text, 'timestamp': datetime.now().isoformat()})}\n\n"

    @staticmethod
    def reasoning_end(full_reasoning: str) -> str:
        """Event when reasoning completes"""
        return f"data: {json.dumps({'type': 'REASONING_END', 'fullReasoning': full_reasoning, 'timestamp': datetime.now().isoformat()})}\n\n"


class ReasoningAwareOrchestrator:
    """
    Wrapper for orchestrator that captures reasoning when using GPT-5.
    Falls back to regular orchestrator for other models.
    """

    def __init__(self, orchestrator, model_name: str = "gpt-5"):
        self.orchestrator = orchestrator
        self.model_name = model_name
        self.reasoning_client = ReasoningStreamClient() if model_name == "gpt-5" else None

    async def process_with_reasoning(
        self,
        messages: list[Dict[str, str]],
        system_prompt: str
    ) -> AsyncIterator[bytes]:
        """
        Process request with reasoning stream for GPT-5.
        Yields SSE events for both reasoning and content.
        """

        if not self.reasoning_client:
            # Fall back to regular orchestrator for non-GPT-5 models
            async for chunk in self.orchestrator.stream(messages):
                yield chunk
            return

        # Prepare messages with system prompt
        full_messages = [{"role": "system", "content": system_prompt}] + messages

        # Track reasoning and content
        reasoning_buffer = []
        content_buffer = []
        reasoning_started = False
        content_started = False

        try:
            # Stream from OpenRouter with reasoning capture
            async for chunk in self.reasoning_client.stream_completion(
                full_messages,
                model="openai/gpt-5",
                temperature=0.7
            ):

                if chunk.error:
                    logger.error(f"Reasoning stream error: {chunk.error}")
                    yield f"data: {json.dumps({'type': 'ERROR', 'message': chunk.error})}\n\n".encode()
                    break

                # Handle reasoning chunks
                if chunk.reasoning:
                    if not reasoning_started:
                        yield ReasoningEvent.reasoning_start().encode()
                        reasoning_started = True

                    reasoning_buffer.append(chunk.reasoning)

                    # Emit reasoning content in small chunks for real-time display
                    yield ReasoningEvent.reasoning_content(chunk.reasoning).encode()

                # Handle content chunks
                if chunk.content:
                    if not content_started:
                        # Reasoning is done, now content is starting
                        if reasoning_started and reasoning_buffer:
                            full_reasoning = ''.join(reasoning_buffer)
                            yield ReasoningEvent.reasoning_end(full_reasoning).encode()

                        # Start content streaming
                        yield f"data: {json.dumps({'type': 'TEXT_MESSAGE_START'})}\n\n".encode()
                        yield SSEEventEmitter.writing().encode()
                        content_started = True

                    content_buffer.append(chunk.content)

                    # Emit content as AG-UI event
                    yield f"data: {json.dumps({'type': 'TEXT_MESSAGE_CONTENT', 'delta': chunk.content})}\n\n".encode()

                # Handle completion
                if chunk.finished:
                    if content_started:
                        full_content = ''.join(content_buffer)
                        yield f"data: {json.dumps({'type': 'TEXT_MESSAGE_END', 'fullContent': full_content})}\n\n".encode()

                    yield f"data: {json.dumps({'type': 'RUN_FINISHED'})}\n\n".encode()
                    break

        except Exception as e:
            logger.error(f"Error in reasoning stream: {e}")
            yield f"data: {json.dumps({'type': 'ERROR', 'message': str(e)})}\n\n".encode()


async def inject_reasoning_events(
    original_stream: AsyncIterator[bytes],
    model_name: str = "gpt-5"
) -> AsyncIterator[bytes]:
    """
    Inject reasoning events into an existing AG-UI stream.
    This is a simpler approach that works with existing infrastructure.
    """

    # For now, pass through original stream
    # In a full implementation, we'd intercept LLM calls and add reasoning
    async for chunk in original_stream:
        yield chunk

    # TODO: Implement proper interception of Pydantic AI's OpenRouter calls
    # to capture reasoning in delta.reasoning field


def create_reasoning_aware_agent(base_agent, model_name: str = "gpt-5"):
    """
    Create a wrapper around an agent that captures reasoning.

    This modifies the agent's streaming behavior to include reasoning events.
    """

    # This would require modifying Pydantic AI's internals
    # For now, we'll use direct OpenRouter calls when reasoning is needed

    return base_agent  # Placeholder