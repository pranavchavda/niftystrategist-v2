"""
Custom OpenRouter streaming client that captures GPT-5's reasoning stream.
This allows us to expose the model's thought process to users.
"""

import os
import json
import asyncio
import logging
from typing import AsyncGenerator, Dict, Any, Optional, Tuple
import aiohttp
from dataclasses import dataclass
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class StreamChunk:
    """Represents a chunk of streaming data"""
    content: Optional[str] = None
    reasoning: Optional[str] = None
    role: Optional[str] = None
    finished: bool = False
    error: Optional[str] = None
    timestamp: float = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc).timestamp()


class ReasoningStreamClient:
    """
    OpenRouter streaming client that captures both content and reasoning.
    Designed specifically for GPT-5's thought stream capability.
    """

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the client with API key"""
        self.api_key = api_key or os.getenv('OPENROUTER_API_KEY')
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY is required")

        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
            'HTTP-Referer': os.getenv('FRONTEND_URL', 'http://localhost:5173'),
            'X-Title': 'NiftyStrategist'
        }

    async def stream_completion(
        self,
        messages: list[Dict[str, str]],
        model: str = "openai/gpt-5",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Stream a completion from OpenRouter, yielding both content and reasoning.

        Args:
            messages: Chat messages in OpenAI format
            model: Model to use (default: openai/gpt-5)
            temperature: Temperature for sampling
            max_tokens: Maximum tokens to generate

        Yields:
            StreamChunk objects containing content and/or reasoning
        """

        request_data = {
            'model': model,
            'messages': messages,
            'stream': True,
            'temperature': temperature
        }

        if max_tokens:
            request_data['max_tokens'] = max_tokens

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.base_url,
                    headers=self.headers,
                    json=request_data
                ) as response:

                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"OpenRouter API error: {response.status} - {error_text}")
                        yield StreamChunk(error=f"API Error: {response.status}")
                        return

                    async for line in response.content:
                        if not line:
                            continue

                        line_str = line.decode('utf-8').strip()

                        if not line_str.startswith('data: '):
                            continue

                        data_str = line_str[6:]  # Remove 'data: ' prefix

                        if data_str == '[DONE]':
                            yield StreamChunk(finished=True)
                            return

                        try:
                            data = json.loads(data_str)
                            chunk = self._parse_stream_data(data)
                            if chunk:
                                yield chunk

                        except json.JSONDecodeError as e:
                            logger.warning(f"Failed to parse SSE data: {e}")
                            continue

        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield StreamChunk(error=str(e))

    def _parse_stream_data(self, data: Dict[str, Any]) -> Optional[StreamChunk]:
        """Parse streaming data and extract content/reasoning"""

        if 'choices' not in data or not data['choices']:
            return None

        choice = data['choices'][0]

        # Check for delta (streaming response)
        if 'delta' in choice:
            delta = choice['delta']

            chunk = StreamChunk()

            # Extract role if present
            if 'role' in delta:
                chunk.role = delta['role']

            # Extract content
            if 'content' in delta:
                chunk.content = delta['content']

            # Extract reasoning (GPT-5 specific)
            if 'reasoning' in delta:
                chunk.reasoning = delta['reasoning']

            # Only return if we have some data
            if chunk.content or chunk.reasoning or chunk.role:
                return chunk

        return None

    async def complete_with_reasoning(
        self,
        messages: list[Dict[str, str]],
        model: str = "openai/gpt-5",
        temperature: float = 0.7
    ) -> Tuple[str, str]:
        """
        Get a complete response with both content and reasoning.

        Returns:
            Tuple of (content, reasoning)
        """

        content_parts = []
        reasoning_parts = []

        async for chunk in self.stream_completion(messages, model, temperature):
            if chunk.error:
                raise Exception(f"API Error: {chunk.error}")

            if chunk.content:
                content_parts.append(chunk.content)

            if chunk.reasoning:
                reasoning_parts.append(chunk.reasoning)

            if chunk.finished:
                break

        return ''.join(content_parts), ''.join(reasoning_parts)


async def test_reasoning_stream():
    """Test the reasoning stream client"""
    client = ReasoningStreamClient()

    messages = [
        {"role": "user", "content": "What is 25 * 17? Think step by step."}
    ]

    print("Testing reasoning stream...")
    print("=" * 60)

    reasoning_buffer = []
    content_buffer = []

    async for chunk in client.stream_completion(messages):
        if chunk.error:
            print(f"Error: {chunk.error}")
            break

        if chunk.reasoning:
            reasoning_buffer.append(chunk.reasoning)
            print(f"[REASONING]: {chunk.reasoning}", end='', flush=True)

        if chunk.content:
            content_buffer.append(chunk.content)
            # Don't print content during reasoning

        if chunk.finished:
            print("\n" + "=" * 60)
            print("FINAL CONTENT:", ''.join(content_buffer))
            print("=" * 60)
            print("FULL REASONING:", ''.join(reasoning_buffer))
            break


if __name__ == "__main__":
    # Test the client
    asyncio.run(test_reasoning_stream())