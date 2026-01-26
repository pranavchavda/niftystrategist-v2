"""
Raw SSE streaming for DeepSeek models with reasoning support.

DeepSeek V3.2 puts reasoning content in the 'reasoning' field, not 'content'.
Pydantic AI's stream methods don't expose reasoning incrementally, so we
stream the raw SSE ourselves to show reasoning in real-time.
"""

import json
import logging
import httpx
from typing import AsyncIterator, Optional, Dict, Any, List

logger = logging.getLogger(__name__)


async def stream_deepseek_response(
    api_key: str,
    model: str,
    messages: List[Dict[str, Any]],
    system_prompt: str,
    tools: Optional[List[Dict[str, Any]]] = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> AsyncIterator[Dict[str, Any]]:
    """
    Stream raw SSE from OpenRouter for DeepSeek models.

    Yields events in the format:
    - {"type": "reasoning", "delta": "..."}  - reasoning content
    - {"type": "content", "delta": "..."}    - text content
    - {"type": "tool_call", "id": "...", "name": "...", "arguments": "..."}
    - {"type": "done", "finish_reason": "..."}
    - {"type": "error", "message": "..."}

    Args:
        api_key: OpenRouter API key
        model: Model name (e.g., "deepseek/deepseek-v3.2")
        messages: Conversation messages
        system_prompt: System prompt for the model
        tools: Optional list of tool definitions in OpenAI format
        temperature: Sampling temperature
        max_tokens: Maximum tokens to generate
    """

    # Build the request payload
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            *messages
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
        "reasoning": {"enabled": True},
        "include_reasoning": True,
    }

    # Add tools if provided
    if tools:
        payload["tools"] = tools

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://node.idrinkcoffee.info",
        "X-Title": "EspressoBot"
    }

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST",
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload
            ) as response:
                if response.status_code != 200:
                    error_body = await response.aread()
                    yield {
                        "type": "error",
                        "message": f"OpenRouter error {response.status_code}: {error_body.decode()}"
                    }
                    return

                # Track accumulated tool calls
                tool_calls: Dict[int, Dict[str, Any]] = {}
                finish_reason = None

                async for line in response.aiter_lines():
                    # Skip empty lines and SSE comments
                    if not line or line.startswith(":"):
                        continue

                    # Parse SSE data line
                    if line.startswith("data: "):
                        data_str = line[6:].strip()

                        # Check for stream end
                        if data_str == "[DONE]":
                            yield {"type": "done", "finish_reason": finish_reason or "stop"}
                            return

                        try:
                            chunk = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue

                        # Extract choice delta
                        choices = chunk.get("choices", [])
                        if not choices:
                            continue

                        delta = choices[0].get("delta", {})
                        finish_reason = choices[0].get("finish_reason") or finish_reason

                        # Extract and yield reasoning
                        reasoning = delta.get("reasoning", "")
                        if reasoning:
                            yield {"type": "reasoning", "delta": reasoning}

                        # Extract and yield content
                        content = delta.get("content", "")
                        if content:
                            yield {"type": "content", "delta": content}

                        # Handle tool calls
                        tool_call_chunks = delta.get("tool_calls", [])
                        for tc_chunk in tool_call_chunks:
                            idx = tc_chunk.get("index", 0)

                            # Initialize tool call if new
                            if idx not in tool_calls:
                                tool_calls[idx] = {
                                    "id": tc_chunk.get("id", ""),
                                    "name": "",
                                    "arguments": ""
                                }

                            # Accumulate function data
                            func = tc_chunk.get("function", {})
                            if "name" in func:
                                tool_calls[idx]["name"] = func["name"]
                            if "arguments" in func:
                                tool_calls[idx]["arguments"] += func["arguments"]

                # Yield any accumulated tool calls
                for idx in sorted(tool_calls.keys()):
                    tc = tool_calls[idx]
                    yield {
                        "type": "tool_call",
                        "id": tc["id"],
                        "name": tc["name"],
                        "arguments": tc["arguments"]
                    }

                yield {"type": "done", "finish_reason": finish_reason or "stop"}

    except httpx.TimeoutException:
        yield {"type": "error", "message": "Request timed out"}
    except Exception as e:
        logger.error(f"[DeepSeek] Streaming error: {e}", exc_info=True)
        yield {"type": "error", "message": str(e)}
