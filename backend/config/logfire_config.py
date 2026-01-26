"""
Logfire Configuration for EspressoBot

Provides observability for:
- FastAPI endpoints
- Pydantic AI agent runs
- Database operations
- HTTP requests
- Custom business logic
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Global flag to track if Logfire is configured
_logfire_configured = False


def configure_logfire(
    service_name: str = "espressobot",
    environment: Optional[str] = None,
    enable_in_dev: bool = True
) -> bool:
    """
    Configure Logfire for observability.

    Args:
        service_name: Name of the service for grouping traces
        environment: Environment name (dev, staging, production)
        enable_in_dev: Whether to enable Logfire in development

    Returns:
        True if Logfire was configured successfully, False otherwise
    """
    global _logfire_configured

    if _logfire_configured:
        logger.info("Logfire already configured")
        return True

    try:
        import logfire

        # Get environment from env var or parameter
        if environment is None:
            environment = os.getenv("ENVIRONMENT", "development")

        # Get Logfire token from environment
        logfire_token = os.getenv("LOGFIRE_TOKEN")

        # Skip configuration if no token in development and not explicitly enabled
        if not logfire_token and environment == "development" and not enable_in_dev:
            logger.info("Logfire token not found in development, skipping configuration")
            return False

        # Configure Logfire
        # Note: If token is not set, Logfire will use local mode

        # Disable scrubbing entirely to see full LLM context in traces
        # This allows debugging token usage and context issues
        # WARNING: This means sensitive data (API keys, passwords) will NOT be redacted
        # Only enable in development/debugging environments

        if logfire_token:
            logfire.configure(
                service_name=service_name,
                token=logfire_token,
                scrubbing=False,  # Disable scrubbing for full context visibility
            )
        else:
            # Local mode without token
            logfire.configure(
                service_name=service_name,
                scrubbing=False,  # Disable scrubbing for full context visibility
            )

        # Enable automatic instrumentation for:
        # - httpx (for API calls)
        # - SQLAlchemy (for database operations) - optional, requires extra package
        # Note: FastAPI instrumentation requires app instance, call instrument_app() separately
        # Note: Pydantic AI has built-in Logfire support

        try:
            logfire.instrument_httpx(
                capture_request_json_body=True,
                capture_response_json_body=True
            )
            logger.info("  ✓ httpx instrumentation enabled (with full request/response bodies)")
        except Exception as e:
            logger.warning(f"  ✗ httpx instrumentation failed: {e}")

        try:
            logfire.instrument_sqlalchemy()
            logger.info("  ✓ SQLAlchemy instrumentation enabled")
        except Exception as e:
            logger.debug(f"  ✗ SQLAlchemy instrumentation skipped (install 'logfire[sqlalchemy]' for database tracing)")

        _logfire_configured = True
        logger.info(f"✅ Logfire configured for {service_name} in {environment} environment")

        # Log token status
        if logfire_token:
            logger.info("🔐 Logfire using API token (cloud mode)")
        else:
            logger.info("🏠 Logfire using local mode (no token)")

        return True

    except ImportError:
        logger.warning("Logfire not installed. Install with: pip install 'pydantic-ai-slim[ag-ui]'")
        return False
    except Exception as e:
        logger.error(f"Failed to configure Logfire: {e}")
        return False


def instrument_app(app):
    """
    Instrument a FastAPI app with Logfire.

    Must be called after Logfire is configured and after the FastAPI app is created.

    Args:
        app: FastAPI application instance

    Returns:
        True if instrumentation succeeded, False otherwise
    """
    if not _logfire_configured:
        logger.warning("Logfire not configured. Call configure_logfire() first.")
        return False

    try:
        import logfire
        logfire.instrument_fastapi(app)
        logger.info("✅ FastAPI app instrumented with Logfire")
        return True
    except Exception as e:
        logger.error(f"Failed to instrument FastAPI app: {e}")
        return False


def get_logfire():
    """
    Get the Logfire instance for manual instrumentation.

    Returns None if Logfire is not configured.
    """
    if not _logfire_configured:
        logger.warning("Logfire not configured. Call configure_logfire() first.")
        return None

    try:
        import logfire
        return logfire
    except ImportError:
        return None


def trace_function(name: Optional[str] = None):
    """
    Decorator to trace a function with Logfire.

    Usage:
        @trace_function("my_function")
        async def my_function(arg1, arg2):
            ...
    """
    def decorator(func):
        if not _logfire_configured:
            # Return original function if Logfire not configured
            return func

        import logfire
        import functools
        import asyncio

        # Use function name if not provided
        span_name = name or f"{func.__module__}.{func.__name__}"

        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                with logfire.span(span_name):
                    return await func(*args, **kwargs)
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                with logfire.span(span_name):
                    return func(*args, **kwargs)
            return sync_wrapper

    return decorator


def log_user_message(
    thread_id: str,
    user_id: str,
    message: str,
    has_images: bool = False,
    model: Optional[str] = None,
    metadata: Optional[dict] = None,
    context: Optional[dict] = None,
    conversation_history: Optional[list] = None
):
    """
    Log a user message with full context to Logfire.

    Args:
        thread_id: Conversation thread ID
        user_id: User identifier
        message: User message content
        has_images: Whether message includes images
        model: Model being used for response
        metadata: Additional metadata (hitl_enabled, use_todo, etc.)
        context: Full context being passed to orchestrator (memories, user_bio, etc.)
        conversation_history: Full list of messages in the conversation (for context size tracking)
    """
    if not _logfire_configured:
        return

    try:
        import logfire

        log_data = {
            'thread_id': thread_id,
            'user_id': user_id,
            'message_length': len(message),
            'message_preview': message[:200] + ('...' if len(message) > 200 else ''),
            'has_images': has_images,
            'model': model,
        }

        if metadata:
            log_data.update(metadata)

        # Add full context information if provided
        if context:
            # Log user memories that are being injected
            if 'user_memories' in context and context['user_memories']:
                memories_list = context['user_memories']
                log_data['memories_injected'] = len(memories_list)
                # Log preview of memory content
                memory_previews = []
                for mem in memories_list[:3]:  # Only log first 3 for brevity
                    if hasattr(mem, 'content'):
                        preview = mem.content[:100] + ('...' if len(mem.content) > 100 else '')
                        memory_previews.append(preview)
                if memory_previews:
                    log_data['memory_previews'] = memory_previews

            # Log user profile context
            if 'user_name' in context and context['user_name']:
                log_data['user_name'] = context['user_name']
            if 'user_bio' in context and context['user_bio']:
                log_data['user_bio_length'] = len(context['user_bio'])
                log_data['user_bio_preview'] = context['user_bio'][:200] + ('...' if len(context['user_bio']) > 200 else '')

            # Log HITL and TODO settings
            if 'hitl_enabled' in context:
                log_data['hitl_enabled'] = context['hitl_enabled']
            if 'use_todo' in context:
                log_data['use_todo'] = context['use_todo']

            # Log available agents
            if 'available_agents' in context:
                log_data['available_agents'] = list(context['available_agents'].keys()) if hasattr(context['available_agents'], 'keys') else []

        # Log full conversation context (for debugging and token tracking)
        if conversation_history:
            log_data['conversation_message_count'] = len(conversation_history)

            # Estimate context tokens using tiktoken
            try:
                import tiktoken
                encoding = tiktoken.get_encoding("cl100k_base")

                def estimate_tokens(text: str) -> int:
                    if not text:
                        return 0
                    return len(encoding.encode(text))
            except ImportError:
                def estimate_tokens(text: str) -> int:
                    if not text:
                        return 0
                    return len(text) // 4

            # Calculate total context tokens
            total_context_tokens = 0
            full_context_parts = []

            for msg in conversation_history:
                content = msg.get('content', '')
                role = msg.get('role', 'unknown')
                msg_tokens = estimate_tokens(content)
                total_context_tokens += msg_tokens
                full_context_parts.append(f"[{role}]: {content}")

            # Add system prompt estimate (~3k tokens)
            system_prompt_tokens = 3000
            total_context_tokens += system_prompt_tokens

            # Add memory injection tokens
            if context and context.get('user_memories'):
                for mem in context['user_memories']:
                    if hasattr(mem, 'content'):
                        total_context_tokens += estimate_tokens(mem.content)

            log_data['context_tokens_estimated'] = total_context_tokens
            log_data['context_tokens_breakdown'] = {
                'system_prompt': system_prompt_tokens,
                'conversation': total_context_tokens - system_prompt_tokens
            }

            # Include the full context for debugging (truncated if too long)
            full_context = "\n\n".join(full_context_parts)
            if len(full_context) > 50000:
                # Truncate but keep beginning and end
                log_data['full_context'] = full_context[:25000] + "\n\n... [TRUNCATED] ...\n\n" + full_context[-25000:]
                log_data['full_context_truncated'] = True
            else:
                log_data['full_context'] = full_context
                log_data['full_context_truncated'] = False

        logfire.info('user_message', **log_data)
    except Exception as e:
        logger.debug(f"Failed to log user message: {e}")


def log_agent_response(
    thread_id: str,
    user_id: str,
    response: str,
    model: Optional[str] = None,
    tokens_used: Optional[int] = None,
    latency_ms: Optional[float] = None,
    metadata: Optional[dict] = None
):
    """
    Log an agent response with metrics to Logfire.

    Args:
        thread_id: Conversation thread ID
        user_id: User identifier
        response: Agent response content
        model: Model that generated the response
        tokens_used: Total tokens consumed
        latency_ms: Response latency in milliseconds
        metadata: Additional metadata
    """
    if not _logfire_configured:
        return

    try:
        import logfire

        log_data = {
            'thread_id': thread_id,
            'user_id': user_id,
            'response_length': len(response),
            'response_preview': response[:200] + ('...' if len(response) > 200 else ''),
            'model': model,
            'tokens_used': tokens_used,
            'latency_ms': latency_ms,
        }

        if metadata:
            log_data.update(metadata)

        logfire.info('agent_response', **log_data)
    except Exception as e:
        logger.debug(f"Failed to log agent response: {e}")


def log_tool_call(
    thread_id: str,
    tool_name: str,
    tool_args: dict,
    result_preview: Optional[str] = None,
    error: Optional[str] = None,
    latency_ms: Optional[float] = None
):
    """
    Log a tool call with arguments and results to Logfire.

    Args:
        thread_id: Conversation thread ID
        tool_name: Name of the tool called
        tool_args: Tool arguments
        result_preview: Preview of the result
        error: Error message if tool call failed
        latency_ms: Tool execution latency
    """
    if not _logfire_configured:
        return

    try:
        import logfire

        log_data = {
            'thread_id': thread_id,
            'tool_name': tool_name,
            'tool_args': tool_args,
            'success': error is None,
            'latency_ms': latency_ms,
        }

        if result_preview:
            log_data['result_preview'] = result_preview[:200]

        if error:
            log_data['error'] = error
            logfire.error('tool_call_failed', **log_data)
        else:
            logfire.info('tool_call', **log_data)
    except Exception as e:
        logger.debug(f"Failed to log tool call: {e}")


def log_memory_retrieval(
    user_id: str,
    query: str,
    memories_found: int,
    method: str = "semantic_search",
    latency_ms: Optional[float] = None
):
    """
    Log memory retrieval with search details.

    Args:
        user_id: User identifier
        query: Search query
        memories_found: Number of memories retrieved
        method: Retrieval method (semantic_search, recent, etc.)
        latency_ms: Retrieval latency
    """
    if not _logfire_configured:
        return

    try:
        import logfire

        logfire.info('memory_retrieval',
            user_id=user_id,
            query_preview=query[:100],
            memories_found=memories_found,
            method=method,
            latency_ms=latency_ms
        )
    except Exception as e:
        logger.debug(f"Failed to log memory retrieval: {e}")


def log_agent_call(
    thread_id: str,
    agent_name: str,
    original_task: str,
    enhanced_task: Optional[str] = None,
    conversation_summary: Optional[str] = None,
    context: Optional[dict] = None
):
    """
    Log an agent call with full context including conversation summary.

    Args:
        thread_id: Conversation thread ID
        agent_name: Name of the agent being called
        original_task: Original task description
        enhanced_task: Enhanced task with conversation summary (if applicable)
        conversation_summary: Conversation summary that was generated
        context: Additional context passed to the agent
    """
    if not _logfire_configured:
        return

    try:
        import logfire

        log_data = {
            'thread_id': thread_id,
            'agent_name': agent_name,
            'original_task_length': len(original_task),
            'original_task_preview': original_task[:300] + ('...' if len(original_task) > 300 else ''),
        }

        # Log enhanced task if provided
        if enhanced_task:
            log_data['enhanced_task_length'] = len(enhanced_task)
            log_data['enhanced_task_preview'] = enhanced_task[:500] + ('...' if len(enhanced_task) > 500 else '')
            log_data['has_conversation_summary'] = True

        # Log conversation summary if provided
        if conversation_summary:
            log_data['conversation_summary_length'] = len(conversation_summary)
            log_data['conversation_summary'] = conversation_summary  # Log full summary for debugging

        # Log additional context
        if context:
            # Filter out large objects, only log metadata
            safe_context = {}
            for key, value in context.items():
                if isinstance(value, (str, int, float, bool)):
                    safe_context[key] = value
                elif isinstance(value, dict):
                    safe_context[f'{key}_keys'] = list(value.keys())
                elif isinstance(value, list):
                    safe_context[f'{key}_count'] = len(value)
            if safe_context:
                log_data['context_metadata'] = safe_context

        logfire.info('agent_call', **log_data)
    except Exception as e:
        logger.debug(f"Failed to log agent call: {e}")
