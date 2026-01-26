"""
Wrapper for AG-UI handler to inject custom SSE events
"""

import json
import asyncio
import logging
from typing import AsyncIterator
from datetime import datetime
from .sse_events import SSEEventEmitter

logger = logging.getLogger(__name__)

# Import shared term corrections
from .term_corrections import apply_term_corrections


async def enhanced_ag_ui_stream(original_stream: AsyncIterator[bytes], deps=None, thread_id: str = None) -> AsyncIterator[bytes]:
    """
    Enhance AG-UI stream with additional SSE events for better user feedback.

    This wrapper:
    1. Passes through all original AG-UI events
    2. Detects certain patterns and injects additional events
    3. Tracks timing for latency warnings
    4. Emits TODO updates when todo_write tool is called
    5. Ensures RUN_FINISHED is always sent

    Args:
        original_stream: The original AG-UI event stream
        deps: OrchestratorDeps containing todo_list
        thread_id: Conversation thread ID
    """
    start_time = datetime.now()
    last_event_time = start_time
    has_started_streaming = False
    current_tool = None
    current_tool_call_id = None
    tool_call_map = {}  # Map tool_call_id -> tool_name (for parallel tool calls)
    current_message_id = None  # Track current message ID for tool call association
    last_message_id = None     # Track last message ID to associate inter-message tool calls
    pending_tool_calls = []  # Buffer tool calls that happened before TEXT_MESSAGE_START
    latency_warning_sent = {5: False, 10: False, 15: False}
    last_todo_state = None
    run_finished_sent = False  # Track if RUN_FINISHED was already sent

    # Send initial routing event
    yield SSEEventEmitter.agent_routing().encode()

    # Create HITL event stream for this thread
    if thread_id:
        from .hitl_streamer import hitl_streamer
        await hitl_streamer.create_stream(thread_id)

    # Create HITL event poller that runs independently
    async def hitl_event_poller():
        """Poll for HITL events every 100ms and yield them"""
        if not thread_id:
            return

        from .hitl_streamer import hitl_streamer
        import asyncio

        try:
            while True:
                hitl_event = hitl_streamer.try_get_event(thread_id)
                if hitl_event:
                    logger.info(f"[HITL] Poller found {hitl_event.event_type}")
                    yield ('hitl', hitl_event)

                # Poll every 100ms
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            logger.info(f"[HITL] Event poller cancelled for thread {thread_id}")
            raise  # Re-raise to properly handle cancellation

    # Merge the main stream with HITL events
    from .stream_merger import merge_streams

    try:
        async for item_type, item_data in merge_streams(original_stream, hitl_event_poller()):
            # Handle HITL events
            if item_type == 'hitl':
                hitl_event = item_data
                if hitl_event.event_type == "approval_request":
                    yield SSEEventEmitter.hitl_approval_request(
                        tool_name=hitl_event.tool_name,
                        tool_args=hitl_event.tool_args,
                        explanation=hitl_event.explanation,
                        approval_id=hitl_event.approval_id
                    ).encode()
                elif hitl_event.event_type == "approved":
                    yield SSEEventEmitter.hitl_approved(hitl_event.approval_id).encode()
                elif hitl_event.event_type == "rejected":
                    yield SSEEventEmitter.hitl_rejected(
                        hitl_event.approval_id,
                        hitl_event.reason
                    ).encode()
                elif hitl_event.event_type == "timeout":
                    yield SSEEventEmitter.hitl_timeout(hitl_event.approval_id).encode()
                continue  # Don't process as chunk

            # Handle stream errors
            if item_type == 'error':
                error = item_data
                error_msg = str(error)
                logger.error(f"[AG-UI] Stream error from Anthropic API: {error_msg}")

                # Check if this is an Anthropic API error (500, rate limit, etc.)
                if 'status_code: 500' in error_msg or 'api_error' in error_msg:
                    error_event = {
                        "type": "ERROR",
                        "error": "The AI model encountered an internal error. This is usually temporary - please try again."
                    }
                elif 'rate_limit' in error_msg.lower() or '429' in error_msg:
                    error_event = {
                        "type": "ERROR",
                        "error": "Rate limit exceeded. Please wait a moment and try again."
                    }
                else:
                    error_event = {
                        "type": "ERROR",
                        "error": f"Stream error: {error_msg}"
                    }

                yield f"data: {json.dumps(error_event)}\n\n".encode()

                # Mark that we need to send RUN_FINISHED
                run_finished_sent = False
                break  # Exit the stream loop

            # Item is from main stream
            chunk = item_data
            
            # Check if we need to inject messageId into the chunk
            # This ensures consistency between frontend and backend (DB)
            chunk_to_yield = chunk
            
            try:
                chunk_str = chunk.decode('utf-8') if isinstance(chunk, bytes) else chunk
                if chunk_str.startswith('data: '):
                    data_str = chunk_str[6:].strip()
                    if data_str and data_str != '[DONE]':
                        event = json.loads(data_str)
                        event_type = event.get('type')
                        
                        modified = False
                        if event_type == 'TEXT_MESSAGE_START':
                            if not event.get('messageId'):
                                import uuid
                                if not current_message_id:
                                    current_message_id = f"msg_{uuid.uuid4().hex[:12]}"
                                event['messageId'] = current_message_id
                                modified = True
                            else:
                                current_message_id = event.get('messageId')
                                
                        elif event_type == 'TEXT_MESSAGE_CONTENT':
                            # Apply term corrections to agent speech (not tool calls)
                            content = event.get('delta') or event.get('content') or event.get('text')
                            if content:
                                corrected = apply_term_corrections(content)
                                if corrected != content:
                                    # Update whichever field was present
                                    if 'delta' in event:
                                        event['delta'] = corrected
                                    elif 'content' in event:
                                        event['content'] = corrected
                                    elif 'text' in event:
                                        event['text'] = corrected
                                    modified = True
                            if not event.get('messageId') and current_message_id:
                                event['messageId'] = current_message_id
                                modified = True

                        elif event_type == 'TEXT_MESSAGE_END':
                            if not event.get('messageId') and current_message_id:
                                event['messageId'] = current_message_id
                                modified = True
                                
                        if modified:
                            chunk_to_yield = f"data: {json.dumps(event)}\n\n".encode()
                            chunk = chunk_to_yield # Update chunk variable so downstream logic uses modified version
                            
            except Exception as e:
                # If parsing fails, just yield original chunk
                pass
                
            yield chunk_to_yield

            try:

                # Try to parse the chunk to understand what's happening
                chunk_str = chunk.decode('utf-8') if isinstance(chunk, bytes) else chunk

                # Check if it's an SSE data line
                if chunk_str.startswith('data: '):
                    try:
                        data_str = chunk_str[6:].strip()
                        if data_str and data_str != '[DONE]':
                            event = json.loads(data_str)

                            # Inject custom events based on AG-UI events
                            event_type = event.get('type', '')

                            # Debug: Log ALL event types for A2UI debugging
                            logger.info(f"[AG-UI EVENT] {event_type}")

                            # Track if RUN_FINISHED was sent by Pydantic AI
                            if event_type == 'RUN_FINISHED':
                                run_finished_sent = True
                                logger.info("[AG-UI] RUN_FINISHED received from Pydantic AI")

                            # Log RUN_ERROR with full details
                            if event_type == 'RUN_ERROR':
                                error_message = event.get('message', 'Unknown error')
                                logger.error(f"[AG-UI] RUN_ERROR received: {error_message}")
                                logger.error(f"[AG-UI] Full error event: {event}")

                            if event_type == 'TEXT_MESSAGE_START':
                                # Capture message ID for tool call association
                                current_message_id = event.get('messageId')
                                if current_message_id:
                                    logger.info(f"[MESSAGE] Starting message {current_message_id}")

                                    # Associate any pending tool calls with this message
                                    if pending_tool_calls:
                                        logger.info(f"[TOOL] Associating {len(pending_tool_calls)} pending tool calls with message {current_message_id}")
                                        for tool_call_id in pending_tool_calls:
                                            # Emit an update event for the tool call with parentMessageId
                                            update_event = {
                                                "type": "TOOL_CALL_UPDATE",
                                                "toolCallId": tool_call_id,
                                                "parentMessageId": current_message_id
                                            }
                                            yield f"data: {json.dumps(update_event)}\n\n".encode()
                                        pending_tool_calls.clear()

                                has_started_streaming = True
                                yield SSEEventEmitter.writing().encode()

                            elif event_type == 'TEXT_MESSAGE_END':
                                # Clear current message ID so tool calls after this belong to next message
                                logger.info(f"[MESSAGE] Ending message {current_message_id}")
                                last_message_id = current_message_id
                                current_message_id = None

                            elif event_type == 'TOOL_CALL_START':
                                # Different models may use different field names
                                tool_name = event.get('toolCallName') or event.get('tool_name') or event.get('name') or 'unknown'
                                current_tool = tool_name
                                current_tool_call_id = event.get('toolCallId') or event.get('tool_call_id') or event.get('id')

                                # Store in map for parallel tool call support
                                if current_tool_call_id:
                                    tool_call_map[current_tool_call_id] = tool_name

                                logger.info(f"[TOOL] Tool call started: {tool_name} (id: {current_tool_call_id})")
                                logger.info(f"[TOOL] Full TOOL_CALL_START event: {event}")

                                # If tool call happens before TEXT_MESSAGE_START, check if we can associate with previous message
                                # If tool call happens before TEXT_MESSAGE_START, check if we can associate with previous message
                                if not current_message_id:
                                    if last_message_id:
                                        # Associate with previous message to maintain flow (Msg A -> Tool -> Msg B)
                                        logger.info(f"[TOOL] Associating tool call {tool_name} with PREVIOUS message {last_message_id}")
                                        update_event = {
                                            "type": "TOOL_CALL_UPDATE",
                                            "toolCallId": current_tool_call_id,
                                            "parentMessageId": last_message_id
                                        }
                                        yield f"data: {json.dumps(update_event)}\n\n".encode()
                                    else:
                                        # No previous message, buffer for next one
                                        logger.info(f"[TOOL] Buffering tool call {tool_name} (no message yet)")
                                        pending_tool_calls.append(current_tool_call_id)
                                else:
                                    # We are inside a message. Associate with CURRENT message.
                                    logger.info(f"[TOOL] Associating tool call {tool_name} with CURRENT message {current_message_id}")
                                    update_event = {
                                        "type": "TOOL_CALL_UPDATE",
                                        "toolCallId": current_tool_call_id,
                                        "parentMessageId": current_message_id
                                    }
                                    yield f"data: {json.dumps(update_event)}\n\n".encode()

                                # Inject thinking event before tool
                                yield SSEEventEmitter.thinking(f"Preparing to use {tool_name}").encode()

                                # Inject specific event based on tool type
                                if 'search' in tool_name.lower():
                                    yield SSEEventEmitter.searching(
                                        query=event.get('toolCallArguments', {}).get('query', ''),
                                        source="Shopify API"
                                    ).encode()
                                elif 'analyze' in tool_name.lower():
                                    yield SSEEventEmitter.analyzing("data").encode()

                                # NOTE: Original event already passed through at line 47

                            elif event_type == 'TOOL_CALL_ARGS':
                                # Tool arguments streaming - pass through (already happened at line 47)
                                # Just log it so it doesn't show as "unhandled"
                                logger.debug(f"[TOOL] Tool args streaming for {current_tool}")

                            elif event_type == 'TOOL_CALL_RESULT':
                                # Tool result - this fires AFTER tool function executes
                                # Look up actual tool name from ID (parallel tool call support)
                                result_tool_call_id = event.get('toolCallId') or event.get('tool_call_id')
                                result_tool_name = tool_call_map.get(result_tool_call_id, current_tool)
                                logger.info(f"[TOOL] Tool result received for {result_tool_name} (id: {result_tool_call_id})")

                                # If this was a render_ui tool, emit A2UI_RENDER events NOW
                                # (The tool function has executed and queued surfaces)
                                if result_tool_name == 'render_ui':
                                    logger.info(f"[A2UI] Detected render_ui tool RESULT")
                                    logger.info(f"[A2UI] deps present: {deps is not None}")
                                    logger.info(f"[A2UI] current_message_id: {current_message_id}, last_message_id: {last_message_id}")
                                    if deps and hasattr(deps, 'pending_a2ui_surfaces'):
                                        surfaces = deps.pending_a2ui_surfaces
                                        logger.info(f"[A2UI] Found {len(surfaces)} pending A2UI surface(s)")

                                        for surface in surfaces:
                                            # A2UI v0.8 spec: surfaceUpdate message
                                            # We emit both for backwards compatibility during migration
                                            surface_update_event = {
                                                "type": "surfaceUpdate",
                                                "surfaceId": surface["surfaceId"],
                                                "components": surface["components"],
                                                "title": surface.get("title"),
                                                "messageId": current_message_id or last_message_id
                                            }
                                            event_json = json.dumps(surface_update_event)
                                            logger.info(f"[A2UI] Emitting surfaceUpdate event for surface {surface['surfaceId']}")
                                            yield f"data: {event_json}\n\n".encode()

                                            # Also emit legacy A2UI_RENDER for backwards compatibility
                                            legacy_event = {
                                                "type": "A2UI_RENDER",
                                                "surfaceId": surface["surfaceId"],
                                                "components": surface["components"],
                                                "title": surface.get("title"),
                                                "messageId": current_message_id or last_message_id
                                            }
                                            yield f"data: {json.dumps(legacy_event)}\n\n".encode()

                                        # Clear pending surfaces
                                        deps.pending_a2ui_surfaces.clear()
                                    else:
                                        logger.warning(f"[A2UI] No pending surfaces - deps: {deps}, has pending_a2ui_surfaces: {hasattr(deps, 'pending_a2ui_surfaces') if deps else False}")

                                # Clear current_tool after processing result
                                current_tool = None

                            elif event_type == 'TOOL_CALL_END':
                                # Look up tool name from ID (parallel tool call support)
                                end_tool_call_id = event.get('toolCallId') or event.get('tool_call_id')
                                end_tool_name = tool_call_map.get(end_tool_call_id, current_tool)
                                logger.info(f"[TOOL] Tool call ended: {end_tool_name} (id: {end_tool_call_id})")

                                if end_tool_name:
                                    yield SSEEventEmitter.tool_progress(
                                        end_tool_name,
                                        1.0,
                                        "Completed"
                                    ).encode()

                                    # If this was a todo_write tool, emit TODO update event
                                    if end_tool_name == 'todo_write':
                                        logger.info(f"[TODO] Detected todo_write tool completion, deps present: {deps is not None}")
                                        if deps and hasattr(deps, 'todo_list'):
                                            todo_list = deps.todo_list
                                            logger.info(f"[TODO] Found todo_list with {len(todo_list.todos)} todos")

                                            # Convert TodoList to dict
                                            todos_dict = [
                                                {
                                                    "content": todo.content,
                                                    "status": todo.status,
                                                    "activeForm": todo.activeForm,
                                                    "id": i
                                                }
                                                for i, todo in enumerate(todo_list.todos)
                                            ]

                                            # Emit TODO update event
                                            todo_event = {
                                                "type": "TODO_UPDATE",
                                                "todos": todos_dict
                                            }
                                            event_json = json.dumps(todo_event)
                                            logger.info(f"[TODO] Emitting TODO_UPDATE event: {event_json}")
                                            yield f"data: {event_json}\n\n".encode()
                                            last_todo_state = todos_dict
                                        else:
                                            logger.warning(f"[TODO] Could not emit TODO event - deps: {deps}, has todo_list: {hasattr(deps, 'todo_list') if deps else False}")

                                    # If this was a write_to_scratchpad tool, emit SCRATCHPAD_UPDATE event
                                    elif end_tool_name == 'write_to_scratchpad' and thread_id:
                                        logger.info(f"[SCRATCHPAD] Detected write_to_scratchpad tool completion for thread {thread_id}")
                                        # Emit scratchpad update event
                                        scratchpad_event = {
                                            "type": "SCRATCHPAD_UPDATE",
                                            "threadId": thread_id
                                        }
                                        event_json = json.dumps(scratchpad_event)
                                        logger.info(f"[SCRATCHPAD] Emitting SCRATCHPAD_UPDATE event: {event_json}")
                                        yield f"data: {event_json}\n\n".encode()

                                    # NOTE: A2UI render_ui is handled in TOOL_CALL_RESULT (after tool executes)

                                # Clean up tool call from map when done
                                if end_tool_call_id and end_tool_call_id in tool_call_map:
                                    del tool_call_map[end_tool_call_id]

                                # Clear tool call ID but NOT current_tool (needed for TOOL_CALL_RESULT)
                                current_tool_call_id = None
                                # DON'T clear current_tool here - we need it for TOOL_CALL_RESULT

                                # NOTE: Original event already passed through at line 47

                            # Map Pydantic AI thinking events to frontend REASONING events
                            # DeepSeek models emit THINKING_TEXT_MESSAGE_* events
                            # Anthropic models emit ANTHROPIC_THINKING_* events
                            # GLM 4.6 reasoning is not yet supported by Pydantic AI
                            elif event_type == 'THINKING_TEXT_MESSAGE_START' or event_type == 'ANTHROPIC_THINKING_START':
                                logger.info(f"[REASONING] Thinking started (event: {event_type})")
                                reasoning_event = {
                                    "type": "REASONING_START"
                                }
                                yield f"data: {json.dumps(reasoning_event)}\n\n".encode()

                            elif event_type == 'THINKING_TEXT_MESSAGE_CONTENT' or event_type == 'ANTHROPIC_THINKING_CONTENT':
                                # Debug: log the entire event to see structure
                                logger.info(f"[REASONING] THINKING_TEXT_MESSAGE_CONTENT event: {event}")

                                # Try multiple possible field names
                                content_delta = event.get('content') or event.get('delta') or event.get('text') or event.get('message') or ''

                                # Apply term corrections to agent thinking (not tool calls)
                                content_delta = apply_term_corrections(content_delta)

                                logger.info(f"[REASONING] Extracted content: '{content_delta}' (length: {len(content_delta)})")

                                if content_delta:
                                    reasoning_event = {
                                        "type": "REASONING_CONTENT",
                                        "delta": content_delta
                                    }
                                    yield f"data: {json.dumps(reasoning_event)}\n\n".encode()
                                else:
                                    logger.warning(f"[REASONING] No content found in event keys: {list(event.keys())}")

                            elif event_type == 'THINKING_TEXT_MESSAGE_END' or event_type == 'ANTHROPIC_THINKING_END':
                                logger.info(f"[REASONING] Thinking ended (event: {event_type})")
                                reasoning_event = {
                                    "type": "REASONING_END"
                                }
                                yield f"data: {json.dumps(reasoning_event)}\n\n".encode()

                            elif event_type == 'TEXT_MESSAGE_CONTENT':
                                has_started_streaming = True

                            elif event_type == 'MODEL_RESPONSE_START':
                                # Agent is thinking
                                yield SSEEventEmitter.thinking("Processing your request with AI").encode()

                            # Handle alternative tool call event names (from different providers)
                            elif event_type == 'FUNCTION_CALL_START' or event_type == 'TOOL_USE_START':
                                # Map to standard TOOL_CALL_START format
                                tool_name = event.get('name') or event.get('function_name') or 'unknown'
                                logger.info(f"[TOOL] Alternative tool call event: {event_type} -> {tool_name}")
                                # Re-emit as standard TOOL_CALL_START
                                standard_event = {
                                    "type": "TOOL_CALL_START",
                                    "toolCallId": event.get('id') or event.get('call_id'),
                                    "toolCallName": tool_name,
                                    "toolCallArguments": event.get('arguments') or event.get('parameters') or {}
                                }
                                yield f"data: {json.dumps(standard_event)}\n\n".encode()

                            # Log unknown event types that might contain reasoning or tool calls
                            # This helps us discover new event types from different models
                            elif event_type and not event_type.startswith('TEXT_MESSAGE') and event_type != 'RUN_FINISHED':
                                # Log with INFO level for tool/reasoning related events
                                if 'tool' in event_type.lower() or 'function' in event_type.lower() or 'thinking' in event_type.lower():
                                    logger.info(f"[EVENT] Unhandled event type: {event_type}, keys: {list(event.keys())}")
                                else:
                                    logger.debug(f"[EVENT] Unknown event type: {event_type}, keys: {list(event.keys())}")

                            # NOTE: All events (handled and unhandled) are already passed through at line 47
                            # No need for explicit pass-through here

                            last_event_time = datetime.now()

                    except json.JSONDecodeError:
                        # Not valid JSON, ignore
                        pass
                    except Exception as e:
                        logger.debug(f"Error parsing SSE event: {e}")

                # Check for latency warnings
                elapsed = (datetime.now() - start_time).total_seconds()

                if not has_started_streaming:
                    if elapsed > 5 and not latency_warning_sent[5]:
                        yield SSEEventEmitter.latency_warning(5).encode()
                        latency_warning_sent[5] = True
                    elif elapsed > 10 and not latency_warning_sent[10]:
                        yield SSEEventEmitter.latency_warning(10).encode()
                        latency_warning_sent[10] = True
                    elif elapsed > 15 and not latency_warning_sent[15]:
                        yield SSEEventEmitter.latency_warning(15).encode()
                        latency_warning_sent[15] = True

            except Exception as e:
                logger.error(f"Error in enhanced AG-UI stream: {e}")
                # Pass through the original chunk even if we can't enhance it
                yield chunk

    finally:
        # Ensure RUN_FINISHED is always sent, even if stream ended abruptly
        if not run_finished_sent:
            logger.warning("[AG-UI] Stream ended without RUN_FINISHED - sending it now")
            run_finished_event = {
                "type": "RUN_FINISHED"
            }
            yield f"data: {json.dumps(run_finished_event)}\n\n".encode()
        else:
            logger.info("[AG-UI] Stream ended cleanly with RUN_FINISHED")

        # Note: Cannot drain async iterator in generator finally block - handled in outer wrapper

        # Clean up HITL stream
        if thread_id:
            from .hitl_streamer import hitl_streamer
            await hitl_streamer.cleanup(thread_id)


async def enhanced_handle_ag_ui_request(
    agent,
    request,
    deps=None,
    model_settings=None,
    thread_id=None
):
    """
    Enhanced AG-UI handler that adds custom SSE events and interrupt support.

    This wraps the original handle_ag_ui_request and enhances the stream.
    """
    from pydantic_ai.ag_ui import handle_ag_ui_request
    from .interruptible_stream import make_interruptible_stream
    import asyncio

    # Get the original response
    response = await handle_ag_ui_request(
        agent,
        request,
        deps=deps,
        model_settings=model_settings
    )

    # If it's a StreamingResponse, enhance it
    if hasattr(response, 'body_iterator'):
        # Store reference to original iterator for cleanup
        original_iterator = response.body_iterator

        # Wrap the stream with proper cleanup
        async def stream_with_cleanup():
            """Wrapper that ensures cleanup even if client disconnects"""
            cleanup_task = None
            stream_completed = False
            try:
                # First layer: enhanced stream with TODO tracking and custom events
                enhanced_stream = enhanced_ag_ui_stream(
                    original_iterator,
                    deps=deps,
                    thread_id=thread_id
                )

                # Second layer: interruptible wrapper if thread_id provided
                if thread_id:
                    conversation_state = deps.state if deps and hasattr(deps, 'state') else None
                    final_stream = make_interruptible_stream(
                        enhanced_stream,
                        thread_id,
                        conversation_state
                    )
                else:
                    final_stream = enhanced_stream

                # Stream all chunks
                async for chunk in final_stream:
                    yield chunk

                # Mark as completed if we reached the end naturally
                stream_completed = True
                logger.info(f"[AG-UI] Stream completed successfully for thread {thread_id}")

            except asyncio.CancelledError:
                # Client disconnected - ensure original stream is consumed to close spans
                logger.warning(f"[AG-UI] Client disconnected for thread {thread_id}, draining stream to close spans")

                # Create background task to consume remaining stream
                async def drain_stream():
                    """Consume remaining stream to ensure Pydantic AI context exits"""
                    try:
                        async for _ in original_iterator:
                            pass  # Just consume, don't process
                        logger.info(f"[AG-UI] Successfully drained stream for thread {thread_id}")
                    except Exception as e:
                        logger.debug(f"[AG-UI] Error draining stream (expected): {e}")

                # Run drain in background (don't await - let it complete async)
                cleanup_task = asyncio.create_task(drain_stream())
                raise  # Re-raise to close connection

            except Exception as e:
                logger.error(f"[AG-UI] Stream error for thread {thread_id}: {e}", exc_info=True)
                raise
            finally:
                logger.info(f"[AG-UI] Stream cleanup started for thread {thread_id} (completed={stream_completed})")

                # CRITICAL: ALWAYS drain original iterator to close Pydantic AI span
                # The span only closes when agent.run_stream().__aexit__ is called,
                # which happens when the async iterator is exhausted
                # Even if stream_completed=True, wrapper layers may not have consumed all chunks
                logger.error(f"[SPAN-CLOSE] Starting drain of original iterator for thread {thread_id} (stream_completed={stream_completed})")
                try:
                    chunk_count = 0
                    async for _ in original_iterator:
                        chunk_count += 1
                    if chunk_count > 0:
                        logger.error(f"[SPAN-CLOSE] ⚠️  Drained {chunk_count} remaining chunks for thread {thread_id}")
                    else:
                        logger.error(f"[SPAN-CLOSE] ✅ No remaining chunks - iterator was fully consumed for thread {thread_id}")
                except Exception as e:
                    # Expected if iterator already exhausted
                    logger.error(f"[SPAN-CLOSE] ❌ Error draining stream for thread {thread_id}: {type(e).__name__}: {e}")

                # If we created a cleanup task, let it finish
                if cleanup_task and not cleanup_task.done():
                    try:
                        await asyncio.wait_for(cleanup_task, timeout=2.0)
                    except asyncio.TimeoutError:
                        logger.warning(f"[AG-UI] Cleanup task timeout for thread {thread_id}")
                    except Exception as e:
                        logger.debug(f"[AG-UI] Cleanup task error: {e}")

                logger.info(f"[AG-UI] Stream cleanup completed for thread {thread_id}")

        # Create new StreamingResponse with wrapped stream
        from fastapi.responses import StreamingResponse
        return StreamingResponse(
            stream_with_cleanup(),
            media_type=response.media_type,
            headers=dict(response.headers) if hasattr(response, 'headers') else None
        )

    return response
