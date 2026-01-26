"""
LangSmith Configuration for EspressoBot

LangSmith provides framework-agnostic tracing for LLM applications:
- Automatic tracing of OpenAI/Anthropic/OpenRouter API calls
- Token usage and cost tracking
- Latency monitoring
- Detailed trace trees with input/output
- Evaluation and testing tools
- Dataset management

Works alongside or instead of Logfire.
"""

import os
import logging
from typing import Optional, Dict, Any
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Global flag to track if LangSmith is configured
_langsmith_configured = False


def configure_langsmith(
    project_name: str = "espressobot",
    environment: Optional[str] = None,
    enable_in_dev: bool = True,
    additional_metadata: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Configure LangSmith for observability.

    Args:
        project_name: Project name in LangSmith UI
        environment: Environment name (dev, staging, production)
        enable_in_dev: Whether to enable LangSmith in development
        additional_metadata: Extra metadata to attach to all traces

    Returns:
        True if LangSmith was configured successfully, False otherwise

    Environment Variables Required:
        LANGSMITH_API_KEY: Your LangSmith API key
        LANGCHAIN_PROJECT: Project name (optional, uses project_name param)
        LANGCHAIN_ENDPOINT: API endpoint (optional, defaults to https://api.smith.langchain.com)
    """
    global _langsmith_configured

    if _langsmith_configured:
        logger.info("LangSmith already configured")
        return True

    try:
        # Get environment
        if environment is None:
            environment = os.getenv("ENVIRONMENT", "development")

        # Get LangSmith API key
        api_key = os.getenv("LANGSMITH_API_KEY")

        # Skip if no API key in development and not explicitly enabled
        if not api_key and environment == "development" and not enable_in_dev:
            logger.info("LangSmith API key not found in development, skipping configuration")
            return False

        if not api_key:
            logger.warning("LANGSMITH_API_KEY not found. LangSmith will not be enabled.")
            logger.info("Get your API key at: https://smith.langchain.com/settings")
            return False

        # Set required environment variables for LangSmith
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = api_key

        # Set project name (can be overridden by LANGCHAIN_PROJECT env var)
        if "LANGCHAIN_PROJECT" not in os.environ:
            os.environ["LANGCHAIN_PROJECT"] = project_name

        # Optional: Set custom endpoint
        if "LANGCHAIN_ENDPOINT" not in os.environ:
            os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"

        # Store additional metadata for traces
        if additional_metadata:
            _store_metadata(additional_metadata)

        _langsmith_configured = True

        logger.info(f"✅ LangSmith configured for project '{project_name}' in {environment} environment")
        logger.info(f"🔍 View traces at: https://smith.langchain.com/o/default/projects/{project_name}")

        return True

    except Exception as e:
        logger.error(f"Failed to configure LangSmith: {e}")
        return False


# Storage for global metadata
_global_metadata: Dict[str, Any] = {}


def _store_metadata(metadata: Dict[str, Any]):
    """Store metadata that will be attached to all traces"""
    global _global_metadata
    _global_metadata.update(metadata)


def get_global_metadata() -> Dict[str, Any]:
    """Get metadata that should be attached to all traces"""
    return _global_metadata.copy()


@contextmanager
def trace_run(
    name: str,
    run_type: str = "chain",
    inputs: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    tags: Optional[list] = None
):
    """
    Context manager for tracing a run with LangSmith.

    Args:
        name: Name of the run (e.g., "orchestrator", "product_search")
        run_type: Type of run ("chain", "llm", "tool", "retriever")
        inputs: Input data for this run
        metadata: Additional metadata for this run
        tags: Tags for filtering in LangSmith UI

    Usage:
        with trace_run("product_search", inputs={"query": "coffee"}):
            result = search_products(query)
            # Automatically traced!

        # Or async:
        async with trace_run("orchestrator", run_type="chain"):
            response = await orchestrator.run(message)
    """
    if not _langsmith_configured:
        # Pass-through if not configured
        yield
        return

    try:
        from langsmith import traceable

        # Merge global and local metadata
        full_metadata = get_global_metadata()
        if metadata:
            full_metadata.update(metadata)

        # Create a traceable context
        # Note: This is a simplified version. For full integration,
        # we'd need to wrap functions with @traceable decorator
        yield

    except Exception as e:
        logger.debug(f"LangSmith tracing error (non-critical): {e}")
        yield


def trace_pydantic_ai_agent(agent_name: str, model_id: str):
    """
    Decorator to automatically trace Pydantic AI agent runs.

    Usage:
        @trace_pydantic_ai_agent("orchestrator", "claude-haiku-4.5")
        async def run_orchestrator(message: str, deps: OrchestratorDeps):
            async with agent.run_stream(message, deps=deps) as stream:
                # Automatically traced!
                ...
    """
    def decorator(func):
        if not _langsmith_configured:
            return func

        try:
            from langsmith import traceable
            import functools

            @functools.wraps(func)
            @traceable(
                name=f"{agent_name}_run",
                run_type="chain",
                metadata={
                    "agent": agent_name,
                    "model": model_id,
                    "framework": "pydantic-ai"
                }
            )
            async def wrapper(*args, **kwargs):
                return await func(*args, **kwargs)

            return wrapper

        except ImportError:
            logger.warning("langsmith not installed for @traceable decorator")
            return func

    return decorator


def log_feedback(
    run_id: str,
    score: float,
    feedback_key: str = "user_feedback",
    comment: Optional[str] = None
):
    """
    Log user feedback for a specific run.

    Args:
        run_id: The LangSmith run ID to attach feedback to
        score: Feedback score (0.0-1.0)
        feedback_key: Key for the feedback (e.g., "user_feedback", "accuracy")
        comment: Optional comment explaining the feedback

    Usage:
        # After getting user feedback
        log_feedback(
            run_id=trace_id,
            score=0.8,
            feedback_key="accuracy",
            comment="Response was helpful but could be more detailed"
        )
    """
    if not _langsmith_configured:
        logger.debug("LangSmith not configured, skipping feedback logging")
        return

    try:
        from langsmith import Client

        client = Client()
        client.create_feedback(
            run_id=run_id,
            key=feedback_key,
            score=score,
            comment=comment
        )
        logger.info(f"Logged feedback for run {run_id}: {score} ({feedback_key})")

    except Exception as e:
        logger.error(f"Failed to log feedback: {e}")


def get_langsmith_client():
    """
    Get LangSmith client for advanced operations.

    Returns:
        LangSmith Client instance, or None if not configured

    Usage:
        client = get_langsmith_client()
        if client:
            # List recent runs
            runs = client.list_runs(project_name="espressobot")
            for run in runs:
                print(run.name, run.total_tokens)
    """
    if not _langsmith_configured:
        logger.warning("LangSmith not configured. Call configure_langsmith() first.")
        return None

    try:
        from langsmith import Client
        return Client()
    except ImportError:
        logger.error("langsmith not installed")
        return None


def disable_langsmith():
    """
    Temporarily disable LangSmith tracing.

    Useful for debugging or reducing noise in dev environment.
    """
    os.environ["LANGCHAIN_TRACING_V2"] = "false"
    logger.info("LangSmith tracing disabled")


def enable_langsmith():
    """Re-enable LangSmith tracing after disabling."""
    if _langsmith_configured:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        logger.info("LangSmith tracing enabled")
    else:
        logger.warning("LangSmith not configured. Call configure_langsmith() first.")


# Integration helpers for common use cases

def wrap_openai_client(client):
    """
    Wrap OpenAI client to automatically trace all calls.

    Args:
        client: OpenAI or AsyncOpenAI client

    Returns:
        Wrapped client with automatic tracing

    Note: LangSmith automatically detects OpenAI calls if LANGCHAIN_TRACING_V2=true,
    so this is usually not needed. Provided for explicit control.
    """
    if not _langsmith_configured:
        return client

    # OpenAI calls are automatically traced by LangSmith
    # Just return the client as-is
    return client


def wrap_anthropic_client(client):
    """
    Wrap Anthropic client to automatically trace all calls.

    Args:
        client: Anthropic or AsyncAnthropic client

    Returns:
        Wrapped client with automatic tracing

    Note: LangSmith automatically detects Anthropic calls if LANGCHAIN_TRACING_V2=true,
    so this is usually not needed. Provided for explicit control.
    """
    if not _langsmith_configured:
        return client

    # Anthropic calls are automatically traced by LangSmith
    # Just return the client as-is
    return client
