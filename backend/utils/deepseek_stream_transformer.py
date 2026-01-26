"""
Stream transformer for DeepSeek models via OpenRouter.

DeepSeek V3.2 with reasoning sends content in the 'reasoning' field.
This module provides utilities to intercept SSE streams and emit
reasoning events for real-time UI display.
"""

import json
import logging
import asyncio
from typing import Optional, Callable, Awaitable, Any
import httpx

logger = logging.getLogger(__name__)


class ReasoningEventEmitter:
    """
    Collects reasoning events and provides them to an async consumer.

    Used to bridge the httpx transport layer with the AG-UI event stream.
    """

    def __init__(self):
        self.queue: asyncio.Queue = asyncio.Queue()
        self._reasoning_started = False
        self._reasoning_ended = False

    async def emit_reasoning(self, delta: str):
        """Emit a reasoning delta event."""
        if not self._reasoning_started:
            await self.queue.put({"type": "reasoning_start"})
            self._reasoning_started = True
        await self.queue.put({"type": "reasoning_delta", "delta": delta})

    async def end_reasoning(self):
        """Signal that reasoning has ended."""
        if self._reasoning_started and not self._reasoning_ended:
            await self.queue.put({"type": "reasoning_end"})
            self._reasoning_ended = True

    async def get_event(self, timeout: float = 0.1) -> Optional[dict]:
        """Get the next event (non-blocking with timeout)."""
        try:
            return await asyncio.wait_for(self.queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None


class DeepSeekStreamInterceptor(httpx.AsyncByteStream):
    """
    Wraps an httpx async byte stream to intercept and process SSE chunks.

    Extracts reasoning content and emits it to a ReasoningEventEmitter
    while passing through all data to the original consumer (Pydantic AI).
    """

    def __init__(
        self,
        original_stream: httpx.AsyncByteStream,
        emitter: Optional[ReasoningEventEmitter] = None
    ):
        self.original_stream = original_stream
        self.emitter = emitter
        self._buffer = ""

    async def __aiter__(self):
        """Iterate over the stream, extracting reasoning along the way."""
        async for chunk in self.original_stream:
            # Process the chunk to extract reasoning
            if self.emitter:
                await self._process_chunk(chunk)

            # Always yield the original chunk to Pydantic AI
            yield chunk

    async def _process_chunk(self, chunk: bytes):
        """Extract reasoning from SSE chunk and emit events."""
        text = chunk.decode('utf-8')
        self._buffer += text

        # Process complete lines
        while '\n' in self._buffer:
            line, self._buffer = self._buffer.split('\n', 1)
            line = line.strip()

            if not line or line.startswith(":"):
                continue

            if line.startswith("data: "):
                data_str = line[6:].strip()
                if data_str == "[DONE]":
                    await self.emitter.end_reasoning()
                    continue

                try:
                    chunk_data = json.loads(data_str)
                    choices = chunk_data.get("choices", [])
                    if choices:
                        delta = choices[0].get("delta", {})

                        # Extract reasoning
                        reasoning = delta.get("reasoning", "")
                        if reasoning:
                            await self.emitter.emit_reasoning(reasoning)

                        # If we see content, reasoning is done
                        content = delta.get("content", "")
                        if content:
                            await self.emitter.end_reasoning()

                except json.JSONDecodeError:
                    pass

    async def aclose(self):
        """Close the underlying stream."""
        await self.original_stream.aclose()


class DeepSeekTransport(httpx.AsyncHTTPTransport):
    """
    Custom httpx transport that intercepts streaming responses from OpenRouter.

    Wraps SSE streams with DeepSeekStreamInterceptor to extract reasoning.
    """

    def __init__(self, emitter: Optional[ReasoningEventEmitter] = None, **kwargs):
        super().__init__(**kwargs)
        self.emitter = emitter

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        """Handle a request, wrapping streaming responses."""
        response = await super().handle_async_request(request)

        # Only intercept streaming responses to OpenRouter chat completions
        if (
            "openrouter.ai" in str(request.url)
            and "chat/completions" in str(request.url)
            and self.emitter
        ):
            # Wrap the response stream
            original_stream = response.stream
            wrapped_stream = DeepSeekStreamInterceptor(original_stream, self.emitter)

            # Create a new response with the wrapped stream
            return httpx.Response(
                status_code=response.status_code,
                headers=response.headers,
                stream=wrapped_stream,
                extensions=response.extensions
            )

        return response


def create_deepseek_client(
    emitter: Optional[ReasoningEventEmitter] = None,
    **kwargs
) -> httpx.AsyncClient:
    """
    Create an httpx.AsyncClient configured for DeepSeek reasoning interception.

    Args:
        emitter: ReasoningEventEmitter to receive reasoning events
        **kwargs: Additional arguments for httpx.AsyncClient

    Returns:
        Configured httpx.AsyncClient
    """
    transport = DeepSeekTransport(emitter=emitter)
    return httpx.AsyncClient(transport=transport, **kwargs)
