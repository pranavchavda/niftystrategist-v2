"""
Capture assistant responses from AG-UI streaming for database persistence.
"""

import json
import logging
from typing import AsyncIterator, Optional, Callable

logger = logging.getLogger(__name__)

# Token estimation using tiktoken
try:
    import tiktoken
    _encoding = tiktoken.get_encoding("cl100k_base")  # GPT-4/Claude encoding

    def estimate_tokens(text: str) -> int:
        """Estimate token count for text using tiktoken."""
        if not text:
            return 0
        return len(_encoding.encode(text))
except ImportError:
    logger.warning("tiktoken not available - using rough token estimation")

    def estimate_tokens(text: str) -> int:
        """Rough token estimation (1 token ≈ 4 chars for English)."""
        if not text:
            return 0
        return len(text) // 4


class ResponseCapture:
    """Captures assistant response from AG-UI stream"""

    def __init__(self, on_complete: Optional[Callable] = None):
        """
        Initialize response capture.

        Args:
            on_complete: Callback when response is complete
                         (thread_id, response_text, message_id, tool_calls, reasoning, input_tokens, output_tokens)
        """
        self.response_buffer = []
        self.thread_id = None
        self.on_complete = on_complete
        self.message_id = None
        self.tool_calls = []  # Capture tool calls for persistence
        self.reasoning_buffer = []  # Capture reasoning for persistence
        self.input_content = ""  # Track input content for token estimation

    async def capture_stream(
        self,
        original_stream: AsyncIterator[bytes],
        thread_id: str,
        input_content: str = ""
    ) -> AsyncIterator[bytes]:
        """
        Capture response while passing through stream.

        Args:
            original_stream: Original SSE stream
            thread_id: Conversation thread ID
            input_content: The input message content (for token estimation)

        Yields:
            Original stream chunks (passed through)
        """
        self.thread_id = thread_id
        self.input_content = input_content
        content_started = False

        async for chunk in original_stream:
            # Pass through original chunk


            # Try to parse and capture content
            try:
                chunk_str = chunk.decode('utf-8') if isinstance(chunk, bytes) else chunk

                if chunk_str.startswith('data: '):
                    data_str = chunk_str[6:].strip()

                    if data_str and data_str != '[DONE]':
                        event = json.loads(data_str)
                        event_type = event.get('type', '')

                        # Log all events passing through (for debugging)
                        if event_type == 'TODO_UPDATE':
                            logger.info(f"[CAPTURE] TODO_UPDATE event passing through ResponseCapture: {event}")
                        elif event_type:
                            logger.debug(f"[CAPTURE] Event passing through: {event_type}")

                        # Capture message ID when available
                        if event_type == 'TEXT_MESSAGE_START':
                            # IMPORTANT: Only reset response buffer, NOT tool_calls!
                            # Tool calls happen BEFORE TEXT_MESSAGE_START, so we need to keep them
                            self.response_buffer = []
                            # DON'T clear tool_calls here - they belong to this message!
                            # DON'T clear reasoning_buffer here - it belongs to this message!
                            content_started = True
                            self.message_id = event.get('messageId')
                            logger.info(f"[CAPTURE] TEXT_MESSAGE_START - preserving {len(self.tool_calls)} tool calls and {len(self.reasoning_buffer)} reasoning chars")

                        # Capture content chunks
                        elif event_type == 'TEXT_MESSAGE_CONTENT':
                            content = event.get('delta', '')
                            if content:
                                self.response_buffer.append(content)

                        # Capture tool call events
                        elif event_type == 'TOOL_CALL_START':
                            # Pydantic AI field names: toolCallId, toolCallName, toolCallArguments
                            tool_call = {
                                'id': event.get('toolCallId'),
                                'name': event.get('toolCallName'),  # Correct Pydantic AI field
                                'description': event.get('description', ''),  # May not exist
                                'args': event.get('toolCallArguments', {}),  # May be empty - filled by TOOL_CALL_ARGS
                                'args_buffer': '',  # Buffer for streaming args
                                'result': None,  # Will be filled on TOOL_CALL_RESULT
                                'is_complete': False
                            }
                            self.tool_calls.append(tool_call)
                            logger.info(f"[CAPTURE] Captured tool call start: {tool_call['name']}")

                        elif event_type == 'TOOL_CALL_ARGS':
                            # Accumulate streamed args
                            tool_call_id = event.get('toolCallId')
                            delta = event.get('delta', '')
                            for tc in self.tool_calls:
                                if tc['id'] == tool_call_id:
                                    tc['args_buffer'] = tc.get('args_buffer', '') + delta
                                    break

                        elif event_type == 'TOOL_CALL_RESULT':
                            tool_call_id = event.get('tool_call_id') or event.get('toolCallId')  # Try both
                            result = event.get('content', '')
                            # Find matching tool call and update result
                            for tc in self.tool_calls:
                                if tc['id'] == tool_call_id:
                                    tc['result'] = result
                                    logger.info(f"[CAPTURE] Updated tool result for {tc['name']}: {len(result)} chars")
                                    break

                        elif event_type == 'TOOL_CALL_END':
                            tool_call_id = event.get('toolCallId')
                            # Parse accumulated args and mark tool call as complete
                            for tc in self.tool_calls:
                                if tc['id'] == tool_call_id:
                                    # Parse the accumulated args buffer
                                    args_buffer = tc.get('args_buffer', '')
                                    if args_buffer:
                                        try:
                                            tc['args'] = json.loads(args_buffer)
                                            logger.info(f"[CAPTURE] Parsed args for {tc['name']}: {list(tc['args'].keys())}")
                                        except json.JSONDecodeError as e:
                                            logger.warning(f"[CAPTURE] Failed to parse args for {tc['name']}: {e}")
                                            tc['args'] = {'_raw': args_buffer}
                                    # Clean up buffer (don't store in DB)
                                    tc.pop('args_buffer', None)
                                    tc['is_complete'] = True
                                    logger.debug(f"Marked tool call complete: {tc['name']}")
                                    break

                        # Capture reasoning events
                        elif event_type == 'REASONING_START':
                            # Start capturing reasoning
                            logger.debug(f"Started capturing reasoning for thread {thread_id}")

                        elif event_type == 'REASONING_CONTENT':
                            # Capture reasoning delta
                            reasoning_delta = event.get('delta', '')
                            if reasoning_delta:
                                self.reasoning_buffer.append(reasoning_delta)

                        elif event_type == 'REASONING_END':
                            # Reasoning complete
                            full_reasoning = ''.join(self.reasoning_buffer)
                            logger.debug(f"Captured complete reasoning: {len(full_reasoning)} chars")

                        # Handle completion
                        elif event_type == 'TEXT_MESSAGE_END':
                            full_response = ''.join(self.response_buffer)
                            full_reasoning = ''.join(self.reasoning_buffer) if self.reasoning_buffer else None
                            logger.info(f"[SAVE DEBUG] TEXT_MESSAGE_END - thread {thread_id}: {len(full_response)} chars, {len(self.tool_calls)} tool calls, reasoning: {len(full_reasoning) if full_reasoning else 0} chars")
                            logger.info(f"[SAVE DEBUG] Tool calls to save: {self.tool_calls}")
                            logger.info(f"[SAVE DEBUG] Message ID: {self.message_id}")

                            # Estimate tokens
                            input_tokens = estimate_tokens(self.input_content) if self.input_content else 0
                            output_tokens = estimate_tokens(full_response)
                            if full_reasoning:
                                output_tokens += estimate_tokens(full_reasoning)
                            logger.info(f"[TOKENS] Estimated: input={input_tokens}, output={output_tokens}")

                            # Call the completion callback if provided
                            if self.on_complete and full_response:
                                logger.info(f"[SAVE DEBUG] Calling save callback with {len(self.tool_calls)} tool calls")
                                try:
                                    await self.on_complete(
                                        thread_id, full_response, self.message_id,
                                        self.tool_calls, full_reasoning,
                                        input_tokens, output_tokens
                                    )
                                    logger.info(f"[SAVE DEBUG] Save callback completed successfully")
                                except Exception as e:
                                    logger.error(f"[SAVE DEBUG] Error in response capture callback: {e}", exc_info=True)

                            # Clear buffers after saving to prepare for next message
                            # Reasoning accumulated within this message has been saved,
                            # now reset for next message in the same run
                            self.response_buffer = []
                            self.tool_calls = []
                            self.reasoning_buffer = []  # Clear after saving - each message gets its own reasoning
                            content_started = False

                        elif event_type == 'RUN_FINISHED':
                            # Ensure we save even if TEXT_MESSAGE_END wasn't sent
                            if self.response_buffer and not content_started:
                                full_response = ''.join(self.response_buffer)
                                full_reasoning = ''.join(self.reasoning_buffer) if self.reasoning_buffer else None
                                input_tokens = estimate_tokens(self.input_content) if self.input_content else 0
                                output_tokens = estimate_tokens(full_response)
                                if full_reasoning:
                                    output_tokens += estimate_tokens(full_reasoning)
                                if self.on_complete and full_response:
                                    try:
                                        await self.on_complete(
                                            thread_id, full_response, self.message_id,
                                            self.tool_calls, full_reasoning,
                                            input_tokens, output_tokens
                                        )
                                    except Exception as e:
                                        logger.error(f"Error in response capture callback: {e}")

                            # Clear ALL buffers at RUN_FINISHED to prepare for next run
                            # (should already be cleared at TEXT_MESSAGE_END, but clear again for safety)
                            self.response_buffer = []
                            self.tool_calls = []
                            self.reasoning_buffer = []
                            logger.debug(f"[CAPTURE] Cleared all buffers at RUN_FINISHED")

            except Exception as e:
                logger.debug(f"Error parsing chunk for capture: {e}")
                # Continue streaming even if capture fails
                pass

            # Always yield the chunk after processing
            yield chunk