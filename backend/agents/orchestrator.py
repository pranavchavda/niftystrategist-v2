"""
Orchestrator Agent - Main routing and coordination using Pydantic AI

This is the central orchestrator that:
1. Receives user requests
2. Determines which specialized agents to call
3. Coordinates multi-agent workflows
4. Synthesizes results

Uses Pydantic AI's agent delegation pattern for clean multi-agent coordination.
"""

import asyncio
import json
import logging
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from models.state import ConversationState, MessageRole, OrchestratorDecision
from models.todo import (
    TodoItem,
    TodoList,
    create_todo_list,
    mark_completed,
    mark_in_progress,
)
from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext, Tool, ToolDefinition, ModelRetry
from pydantic_ai.builtin_tools import CodeExecutionTool
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    SystemPromptPart,
    TextPart,
    ThinkingPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from tools.native.scratchpad import Scratchpad

from .base_agent import AgentConfig, IntelligentBaseAgent

# Logfire for observability
try:
    from config import get_logfire

    logfire = get_logfire()
except Exception:
    logfire = None

logger = logging.getLogger(__name__)


def sliding_window_history_processor(
    messages: list[ModelMessage],
) -> list[ModelMessage]:
    """
    Context window management for orchestrator model.

    Keeps last N messages to avoid hitting token limits while preserving:
    - System prompts (always kept)
    - Recent conversation history (last 50 messages = ~25 exchanges)

    IMPORTANT: When using Claude models with extended thinking, assistant messages
    from previous turns must include thinking blocks. To avoid this complexity,
    we filter out old assistant messages and keep only recent exchanges.

    This follows Pydantic AI's recommended pattern for managing token usage.
    See: https://docs.pydantic.dev/pydantic-ai/agents/#processing-message-history
    """
    MAX_HISTORY_MESSAGES = 50  # Keep last 25 exchanges (user + assistant pairs)

    # Early return if messages list is empty to avoid processing
    if not messages:
        logger.warning("History processor received empty messages list")
        return messages

    if len(messages) <= MAX_HISTORY_MESSAGES:
        return messages

    # Separate system prompts from conversation messages
    system_messages = []
    conversation_messages = []

    for msg in messages:
        if isinstance(msg, ModelRequest):
            # Check if this request contains system prompts
            has_system_prompt = any(
                isinstance(part, SystemPromptPart) for part in msg.parts
            )
            if has_system_prompt:
                system_messages.append(msg)
            else:
                conversation_messages.append(msg)
        else:
            conversation_messages.append(msg)

    # Keep only the most recent conversation messages
    recent_messages = conversation_messages[-MAX_HISTORY_MESSAGES:]

    # CRITICAL FIX for Claude thinking mode:
    # Convert assistant messages without thinking blocks into user context messages
    # Also handle tool calls/results to prevent orphaned tool_result errors
    # This preserves ALL conversation context while satisfying Claude's API requirements
    transformed_messages = []
    removed_tool_call_ids = set()  # Track tool calls we've converted to text

    for msg in recent_messages:
        # For user/system messages, filter out tool results that reference removed tool calls
        if isinstance(msg, ModelRequest):
            # Check if this message contains tool returns
            has_tool_returns = any(
                isinstance(part, ToolReturnPart) for part in msg.parts
            )

            if has_tool_returns:
                # Filter out tool returns for removed tool calls, convert to context text
                filtered_parts = []
                context_descriptions = []

                for part in msg.parts:
                    if isinstance(part, ToolReturnPart):
                        # Check if this tool result references a removed tool call
                        if part.tool_call_id in removed_tool_call_ids:
                            # Convert to descriptive text instead
                            tool_result = str(part.content)[:200]  # Limit length
                            context_descriptions.append(
                                f"[Tool result]: {tool_result}..."
                            )
                            logger.debug(
                                f"Converted orphaned tool result {part.tool_call_id} to context"
                            )
                        else:
                            # Keep this tool return as-is (has valid tool_use)
                            filtered_parts.append(part)
                    else:
                        # Keep other parts as-is
                        filtered_parts.append(part)

                # If we converted any tool results, add them as context text
                if context_descriptions:
                    filtered_parts.append(
                        UserPromptPart(content="\n".join(context_descriptions))
                    )

                # Create new request with filtered parts
                if filtered_parts:
                    transformed_messages.append(ModelRequest(parts=filtered_parts))
            else:
                # No tool returns, keep message as-is
                transformed_messages.append(msg)

        # For assistant messages (ModelResponse), check if they have thinking parts
        elif isinstance(msg, ModelResponse):
            has_thinking = any(isinstance(part, ThinkingPart) for part in msg.parts)

            if has_thinking:
                # Keep assistant messages that have thinking blocks
                transformed_messages.append(msg)
            else:
                # Convert assistant message without thinking into user context message
                # Extract all content (text and tool calls)
                text_parts = []
                tool_descriptions = []

                for part in msg.parts:
                    if isinstance(part, TextPart):
                        text_parts.append(part.content)
                    elif isinstance(part, ToolCallPart):
                        # Track this tool call ID as removed
                        removed_tool_call_ids.add(part.tool_call_id)
                        # Describe the tool call
                        tool_descriptions.append(
                            f"  - Called tool '{part.tool_name}' with args: {part.args}"
                        )

                assistant_text = "".join(text_parts) if text_parts else "[no content]"

                # Build context message with both text and tool call descriptions
                context_lines = ["[Context from previous exchange]"]
                if assistant_text:
                    context_lines.append(f"Assistant said: {assistant_text}")
                if tool_descriptions:
                    context_lines.append("Assistant called tools:")
                    context_lines.extend(tool_descriptions)

                context_content = "\n".join(context_lines)

                # Create a new user message with context
                transformed_messages.append(
                    ModelRequest(parts=[UserPromptPart(content=context_content)])
                )

                logger.debug(
                    f"Converted assistant message without thinking into context "
                    f"({len(assistant_text)} chars, {len(tool_descriptions)} tools)"
                )

    # Reconstruct: system prompts + transformed conversation messages
    result = system_messages + transformed_messages

    # SAFETY CHECK: Ensure we always have at least one message
    # Claude API requires at least one message in the history
    if not result:
        logger.error(
            f"History processor produced empty message list! "
            f"Original: {len(messages)} messages, "
            f"System: {len(system_messages)}, "
            f"Conversation: {len(conversation_messages)}, "
            f"Recent: {len(recent_messages)}, "
            f"Transformed: {len(transformed_messages)}"
        )
        # Fallback: Keep at least the last few messages regardless of thinking blocks
        # This prevents empty message list but may trigger thinking block errors
        # (which is better than "no messages" error)
        fallback_count = min(5, len(messages))
        logger.warning(f"Using fallback: returning last {fallback_count} messages")
        return messages[-fallback_count:] if messages else []

    logger.info(
        f"Context window truncated: {len(messages)} messages → {len(result)} messages "
        f"({len(system_messages)} system + {len(transformed_messages)} conversation, "
        f"{len(removed_tool_call_ids)} tool calls converted to context)"
    )

    return result


class OrchestratorDeps(BaseModel):
    """Dependencies for the orchestrator agent"""

    state: ConversationState
    available_agents: Dict[str, Any] = Field(default_factory=dict)
    user_preferences: Dict[str, Any] = Field(default_factory=dict)
    todo_list: TodoList = Field(default_factory=TodoList)
    user_memories: List[str] = Field(
        default_factory=list
    )  # Injected memories for this conversation
    user_name: Optional[str] = None  # User's display name
    user_bio: Optional[str] = None  # User's bio for context
    hitl_enabled: bool = False  # Human-in-the-loop approval mode
    use_todo: bool = False  # Enable TODO tracking for this conversation
    interrupt_signal: Optional[Any] = None  # Interrupt signal for cancellation
    used_bash_tools: set = Field(
        default_factory=set
    )  # Track scripts used in this conversation
    docs_checked_scripts: set = Field(
        default_factory=set
    )  # Scripts whose docs were checked (for enforcement)
    pending_a2ui_surfaces: List[Dict[str, Any]] = Field(
        default_factory=list
    )  # A2UI surfaces to render (cleared after emission)
    upstox_access_token: Optional[str] = None  # Injected as NF_ACCESS_TOKEN for CLI tools
    user_id: Optional[int] = None  # Numeric DB user ID, injected as NF_USER_ID for CLI tools


class OrchestratorAgent(IntelligentBaseAgent[OrchestratorDeps, str]):
    """
    Main orchestrator agent that routes requests to specialized agents.

    Follows these principles:
    ✓ LLM-based routing (no keyword matching)
    ✓ Real data only (no mock responses)
    ✓ Agent-to-agent context passing
    ✓ Progressive agent calling with compressed context
    """

    def __init__(
        self,
        model_id: str = "claude-haiku-4.5",
        model_slug: str = None,
        use_openrouter: bool = None,
        user_mcp_toolsets: Optional[List[Any]] = None,
    ):
        """
        Initialize the orchestrator agent with specified model.

        Args:
            model_id: Model ID (e.g., "claude-haiku-4.5", "kimi-k2")
            model_slug: API model slug (e.g., "claude-haiku-4-5-20251001", "moonshotai/kimi-k2-thinking")
                       If not provided, will attempt to look up from config.models (fallback)
            use_openrouter: Whether to use OpenRouter API. If not provided, will attempt to infer.
            user_mcp_toolsets: Optional list of user-specific MCP server instances to add to orchestrator
        """
        self.model_id = model_id  # Store for logging

        # If model details not provided, try to get from config (fallback for backward compatibility)
        if model_slug is None or use_openrouter is None:
            from config.models import get_model_slug, is_anthropic_model

            try:
                model_slug = model_slug or get_model_slug(model_id)
                use_openrouter = (
                    use_openrouter
                    if use_openrouter is not None
                    else (not is_anthropic_model(model_id))
                )
            except KeyError:
                # Model not in config.models, assume it's a database-only model
                # Default to treating as OpenRouter model if not specified
                if model_slug is None:
                    logger.warning(
                        f"Model {model_id} not found in config, using model_id as slug"
                    )
                    model_slug = model_id
                if use_openrouter is None:
                    logger.warning(
                        f"Provider not specified for {model_id}, defaulting to OpenRouter"
                    )
                    use_openrouter = True

        logger.info(
            f"Initializing orchestrator with model: {model_id} (slug: {model_slug}, openrouter: {use_openrouter})"
        )

        config = AgentConfig(
            name="orchestrator",
            description="Main orchestrator coordinating all specialized agents",
            model_name=model_slug,
            use_openrouter=use_openrouter,
            # temperature removed - thinking mode requires temperature=1.0 (set automatically in base_agent)
        )

        # Initialize builtin tools for Claude models
        # CodeExecutionTool enables the Analysis Tool with uploaded "skills" context
        builtin_tools_list = None
        # if 'claude' in model_slug.lower():
        #     builtin_tools_list = [CodeExecutionTool()]
        #     logger.info("✓ Enabled CodeExecutionTool for Claude model (Analysis Tool with skills context)")

        super().__init__(
            config=config,
            deps_type=OrchestratorDeps,
            output_type=str,
            toolsets=user_mcp_toolsets,  # User-specific MCP servers (if provided)
            builtin_tools=builtin_tools_list,
        )

        # NOTE: We do NOT register output validators on the orchestrator because:
        # - Pydantic AI doesn't allow both output_type and output validators
        # - The orchestrator needs flexibility for custom output types
        # - Layer 1 (system prompt) provides the primary guardrail
        # - Output validators should be used on specialized agents instead

        # Dictionary to hold specialized agents (will be populated later)
        self.specialized_agents = {}

        # Register output validator to catch XML hallucinations
        # This forces the model to retry if it uses XML tags or incorrect formats instead of native tool calls
        @self.agent.output_validator
        async def validate_malformed_tool_calls(ctx: RunContext[OrchestratorDeps], result: str) -> str:
            from utils.function_call_validator import get_function_call_validator

            validator = get_function_call_validator()
            error = validator.detect_malformed_call(result)
            
            if error:
                # Check for loops (repeated errors)
                is_loop = validator.record_error(error)
                
                # Get recovery instructions
                instructions = validator.get_recovery_instructions(error, text=result)
                
                if is_loop:
                    # If looping, we might want to be more aggressive or suggest fallback
                    # For now, we append a strong warning
                    instructions += "\n\nCRITICAL: You are repeating this error. STOP using XML/Markdown for tool calls."
                
                raise ModelRetry(instructions)
                
            return result

        # Register output validator to catch fake tool call claims
        # Uses a fast LLM to detect when model claims results without making actual tool calls
        @self.agent.output_validator
        async def validate_tool_claims(ctx: RunContext[OrchestratorDeps], result: str) -> str:
            """Use LLM to detect fake tool call claims."""

            # 1. Extract actual tool calls from message history
            actual_tool_calls = []
            for msg in ctx.messages:
                if isinstance(msg, ModelResponse):
                    for part in msg.parts:
                        if isinstance(part, ToolCallPart):
                            actual_tool_calls.append(part.tool_name)

            # 2. Skip validation if tools were called (common case, saves API cost)
            if actual_tool_calls:
                # Tools were called - likely legitimate claims
                return result

            # 3. Skip validation for short responses or obvious non-claims
            if len(result) < 50:
                return result

            # 4. Use fast LLM to check for fabricated claims
            # Using gpt-oss-safeguard-20b via OpenRouter (Groq provider puts output in reasoning field)

            validation_prompt = f"""You are a strict validator checking if an AI assistant fabricated tool results.

CRITICAL: The assistant response below was generated with NO TOOLS CALLED. If it claims to have retrieved data, called an agent, executed a query, or presents specific results - it is FABRICATING.

RESPONSE TO ANALYZE:
{result[:2000]}

TOOLS ACTUALLY CALLED: NONE (zero tools were invoked)

FAKE INDICATORS (any of these = FAKE):
- Says "Here's the documentation/data/results" but no tool was called
- Says "The agent returned" or "The agent is working" but no agent was called
- Says "I found X products/items/results" but no search was performed
- Says "Perfect!" or "Success!" followed by data that would require a tool call
- Presents code examples, documentation, or structured data as if retrieved
- Claims an operation completed successfully

VALID INDICATORS:
- Says "Let me check..." or "I'll search..." (future intent)
- Asks a question like "Should I look this up?"
- Discusses what WOULD happen hypothetically
- Provides general knowledge without claiming to have retrieved it

OUTPUT ONLY ONE OF:
- "VALID" - if response doesn't fabricate tool results
- "FAKE: <reason>" - if response claims results without tool calls"""

            try:
                # Use OpenRouter for the safety-optimized model
                import httpx

                async with httpx.AsyncClient() as http_client:
                    response = await http_client.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": "openai/gpt-oss-safeguard-20b",
                            "messages": [{"role": "user", "content": validation_prompt}],
                            "max_tokens": 1000,  # Reasoning model needs headroom for CoT + answer
                            "temperature": 0,
                        },
                        timeout=10.0,
                    )
                    response.raise_for_status()
                    data = response.json()

                msg = data["choices"][0]["message"]
                # Groq provider returns output in reasoning field, others in content
                judgment = (msg.get("content") or msg.get("reasoning") or "").strip()
                logger.info(f"[VALIDATOR] Tool claim check result: {judgment[:100]}")

                if judgment.startswith("FAKE:"):
                    reason = judgment[5:].strip()
                    logger.warning(f"LLM detected fake tool claim: {reason}")
                    raise ModelRetry(
                        f"Your response appears to fabricate tool results: {reason}\n\n"
                        f"Tools actually called: {actual_tool_calls if actual_tool_calls else 'none'}\n\n"
                        "You MUST call the appropriate tool before claiming results. "
                        "Do NOT fabricate data or claim actions you haven't taken."
                    )
            except ModelRetry:
                # Re-raise ModelRetry exceptions
                raise
            except Exception as e:
                # Don't block on validation errors - log and continue
                logger.error(f"Tool claim validation error: {e}")

            return result

        mcp_count = len(user_mcp_toolsets) if user_mcp_toolsets else 0
        logger.info(
            f"Orchestrator agent initialized with {config.model_name} ({mcp_count} user MCP servers loaded)"
        )

    async def _auto_invalidate_cache(self, command: str, thread_id: str):
        """
        Automatically invalidate relevant cache entries based on bash command execution.

        Parses the command to identify the operation and triggers appropriate cache invalidations.
        """
        from tools.native.tool_cache import ToolCache

        # Map script names to invalidation triggers
        # Trading CLI tools don't currently need cache invalidation,
        # but the map is kept for future use (e.g., order placement invalidating portfolio cache)
        invalidation_map: Dict[str, list] = {}

        # Extract script name from command
        script_name = None
        for potential_script in invalidation_map.keys():
            if potential_script in command:
                script_name = potential_script
                break

        if not script_name:
            # No matching script, nothing to invalidate
            return

        # Get triggers for this script
        triggers = invalidation_map.get(script_name, [])
        if not triggers:
            return

        # Invalidate cache entries
        cache = ToolCache(thread_id)
        for trigger in triggers:
            invalidated_count = cache.invalidate(trigger)
            if invalidated_count > 0:
                logger.info(
                    f"Cache invalidation: {trigger} triggered by {script_name}, "
                    f"invalidated {invalidated_count} entries"
                )

    async def _auto_cache_result(
        self, command: str, result: str, execution_time_ms: int, thread_id: str
    ):
        """
        Automatically cache ALL bash operation results.

        Caches every bash command result to ensure consistency and avoid redundant operations.
        Even small results save tokens and prevent the agent from fumbling with tool calls.
        """
        import re

        from tools.native.tool_cache import ToolCache

        # Calculate result size in approximate tokens (4 chars per token)
        result_tokens = len(result) // 4

        # Skip only truly trivial outputs (empty or error messages)
        if result_tokens < 10:
            return

        # Map script patterns to cache metadata
        cache_patterns = {
            # Trading CLI tools
            "nf-quote": {
                "tool_name": "nf_quote",
                "invalidation_triggers": [],
                "summary_template": "Stock quote data",
            },
            "nf-analyze": {
                "tool_name": "nf_analyze",
                "invalidation_triggers": [],
                "summary_template": "Technical analysis results",
            },
            "nf-portfolio": {
                "tool_name": "nf_portfolio",
                "invalidation_triggers": ["order_placed"],
                "summary_template": "Portfolio data",
            },
            "nf-watchlist": {
                "tool_name": "nf_watchlist",
                "invalidation_triggers": ["watchlist_update"],
                "summary_template": "Watchlist data",
            },
            "nf-order": {
                "tool_name": "nf_order",
                "invalidation_triggers": ["order_placed"],
                "summary_template": "Order data",
            },
        }

        # Find matching pattern
        cache_info = None
        script_name = None
        for pattern, info in cache_patterns.items():
            if pattern in command:
                cache_info = info
                script_name = pattern
                break

        # If no specific pattern matched, create a generic cache entry
        if not cache_info:
            # Extract script name from command (if it's a Python script)
            python_script_match = re.search(
                r"python3?\s+(?:bash-tools/)?([a-zA-Z0-9_-]+\.py)", command
            )
            if python_script_match:
                script_name = python_script_match.group(1)
                cache_info = {
                    "tool_name": f"bash_{script_name.replace('.py', '')}",
                    "invalidation_triggers": [],
                    "summary_template": f"Bash script: {script_name}",
                }
            else:
                # Generic bash command (not a Python script)
                cache_info = {
                    "tool_name": "bash_command",
                    "invalidation_triggers": [],
                    "summary_template": "Bash command execution",
                }
                script_name = "bash_command"

        # Extract parameters from command
        parameters = {"command": command}

        # Try to extract query/search terms for better cache lookup
        query_match = re.search(
            r'--query\s+["\']([^"\']+)["\']|--query\s+(\S+)', command
        )
        if query_match:
            parameters["query"] = query_match.group(1) or query_match.group(2)

        # Generate summary with searchable keywords
        summary = cache_info["summary_template"]
        if "query" in parameters:
            query_value = parameters["query"]
            summary += f" for '{query_value}'"
            # Add key search terms to summary for better cache lookup
            summary += f" | Keywords: {query_value}"
        summary += f" ({result_tokens} tokens, {execution_time_ms}ms)"

        # Store in cache
        cache = ToolCache(thread_id)
        cache_id = cache.store(
            tool_name=cache_info["tool_name"],
            parameters=parameters,
            result=result,
            summary=summary,
            invalidation_triggers=cache_info["invalidation_triggers"],
            tokens_saved=result_tokens,  # Tokens saved on future cache hits
            execution_time_ms=execution_time_ms,
        )

        logger.info(
            f"Auto-cached {script_name} result: {cache_id} "
            f"({result_tokens} tokens, {execution_time_ms}ms)"
        )

    async def _auto_cache_agent_result(
        self, agent_name: str, task: str, result: str, thread_id: str
    ):
        """
        Automatically cache agent call results.

        Agent calls are always cached since they're expensive (OAuth setup, external APIs, etc.)
        """
        from tools.native.tool_cache import ToolCache

        # Calculate result size in approximate tokens (4 chars per token)
        result_tokens = len(result) // 4

        # Skip only truly trivial outputs
        if result_tokens < 10:
            return

        # Define invalidation triggers for each agent type
        invalidation_map = {
            "web_search": [],  # External search results, no invalidation
            "vision": [],  # Image analysis doesn't change
        }

        # Generate cache metadata
        cache_info = {
            "tool_name": f"agent_{agent_name}",
            "invalidation_triggers": invalidation_map.get(agent_name, []),
            "summary_template": f"{agent_name} agent call",
        }

        # Extract key terms from task for better cache lookups
        parameters = {
            "agent_name": agent_name,
            "task": task[:200],  # Truncate very long tasks
        }

        # Generate summary
        summary = f"{agent_name} agent: {task[:60]}..."
        if len(task) > 60:
            summary += f" ({result_tokens} tokens)"

        # Store in cache
        cache = ToolCache(thread_id)
        cache_id = cache.store(
            tool_name=cache_info["tool_name"],
            parameters=parameters,
            result=result,
            summary=summary,
            invalidation_triggers=cache_info["invalidation_triggers"],
            tokens_saved=result_tokens,
            execution_time_ms=0,  # Agent calls don't track execution time
        )

        logger.info(
            f"Auto-cached {agent_name} agent result: {cache_id} "
            f"({result_tokens} tokens)"
        )

    async def _auto_cache_specialist_result(
        self,
        role: str,
        docs: List[str],
        task_description: str,
        result: dict,
        thread_id: str,
    ):
        """
        Automatically cache spawn_specialist results.

        Specialists are expensive (multi-doc synthesis, web research, many LLM calls),
        so we always cache their results.
        """
        import json

        from tools.native.tool_cache import ToolCache

        # Convert result to string for storage
        result_str = (
            json.dumps(result, indent=2) if isinstance(result, dict) else str(result)
        )

        # Calculate result size in approximate tokens (4 chars per token)
        result_tokens = len(result_str) // 4

        # Skip only truly trivial outputs
        if result_tokens < 10:
            return

        # Determine invalidation triggers based on task type
        invalidation_triggers = []
        task_lower = task_description.lower()

        if (
            any(word in task_lower for word in ["create", "add", "new"])
            and "product" in task_lower
        ):
            invalidation_triggers.extend(["product_create", "product_search"])
        elif "update" in task_lower and "product" in task_lower:
            invalidation_triggers.extend(["product_update", "product_search"])
        elif any(word in task_lower for word in ["order", "sales", "analytics"]):
            invalidation_triggers.extend(["order_create", "sales_analytics"])
        elif "metaobject" in task_lower or "cms" in task_lower:
            invalidation_triggers.extend(["metaobject_create", "metaobject_update"])

        # Generate cache parameters
        parameters = {
            "role": role,
            "docs": docs,
            "task": task_description[:200],  # Truncate very long tasks
        }

        # Generate summary
        command_preview = ""
        if isinstance(result, dict) and "command" in result:
            command_preview = f" → {result['command'][:40]}..."

        summary = f"Specialist '{role}': {task_description[:50]}...{command_preview} ({result_tokens} tokens)"

        # Store in cache
        cache = ToolCache(thread_id)
        cache_id = cache.store(
            tool_name="spawn_specialist",
            parameters=parameters,
            result=result_str,
            summary=summary,
            invalidation_triggers=invalidation_triggers,
            tokens_saved=result_tokens,
            execution_time_ms=0,  # Specialists don't track execution time
        )

        logger.info(
            f"Auto-cached specialist result: {cache_id} "
            f"({result_tokens} tokens, role={role})"
        )

    async def _generate_conversation_summary(
        self, ctx: RunContext[OrchestratorDeps]
    ) -> str:
        """
        Generate a comprehensive summary of the conversation history before calling an agent.

        This provides agents with rich context about:
        - What the user has requested throughout the conversation
        - Actions that have been taken
        - Information that has been gathered
        - Current state and context
        - Relevant decisions or preferences expressed

        Returns:
            Comprehensive conversation summary string
        """
        try:
            from pydantic_ai import Agent
            from pydantic_ai.messages import (
                ModelMessage,
                ModelRequest,
                ModelResponse,
                TextPart,
                ToolCallPart,
                ToolReturnPart,
                UserPromptPart,
            )

            # Get message history from the agent
            message_history = ctx.messages if hasattr(ctx, "messages") else []

            if not message_history or len(message_history) == 0:
                return "No previous conversation history available."

            # Build a readable conversation transcript
            transcript_lines = []

            for msg in message_history:
                if isinstance(msg, ModelRequest):
                    # Extract user messages
                    for part in msg.parts:
                        if isinstance(part, UserPromptPart):
                            transcript_lines.append(f"User: {part.content}")
                        elif isinstance(part, ToolReturnPart):
                            # Include tool results for context
                            tool_result = str(part.content)[:300]  # Limit length
                            transcript_lines.append(f"[Tool Result]: {tool_result}")

                elif isinstance(msg, ModelResponse):
                    # Extract assistant messages and tool calls
                    text_parts = []
                    tool_calls = []

                    for part in msg.parts:
                        if isinstance(part, TextPart):
                            text_parts.append(part.content)
                        elif isinstance(part, ToolCallPart):
                            tool_calls.append(f"Called {part.tool_name}({part.args})")

                    if text_parts:
                        assistant_text = "".join(text_parts)
                        transcript_lines.append(f"Assistant: {assistant_text}")

                    if tool_calls:
                        for tool_call in tool_calls:
                            transcript_lines.append(f"[Action]: {tool_call}")

            # Join transcript
            full_transcript = "\n".join(transcript_lines)

            # If transcript is empty, return early
            if not full_transcript.strip():
                return "No significant conversation history to summarize."

            # Use a fast, cheap model for summarization (Claude Haiku 4.5 or gpt-4.1-mini)
            # Choose gpt-4.1-mini for cost efficiency ($0.10/$0.40 per 1M tokens)
            summarization_prompt = f"""You are analyzing a conversation between a user and an AI assistant (the Nifty Strategist orchestrator) for Indian stock market trading and analysis.

Your task: Generate a COMPREHENSIVE - but losslessly concise summary that will be provided to a specialized agent being called to help with this conversation. Focus on capturing all relevant context without omitting important details.

The summary MUST include:
1. **User's Goals**: What is the user trying to accomplish? (main objectives across all messages)
2. **Actions Taken**: What has the orchestrator done so far? (tool calls, agent calls, operations)
3. **Information Gathered**: What data/facts have been discovered? (product details, analytics, status info)
4. **Current State**: What is the current situation? (pending tasks, recent completions, context)
5. **Key Decisions**: Any important preferences or constraints mentioned by the user?

CONVERSATION TRANSCRIPT:
{full_transcript}

Generate a comprehensive, well-structured summary (3-5 paragraphs) that provides rich context for a specialized agent."""

            # Create a lightweight summarization agent
            from pydantic_ai.models.openai import OpenAIChatModel
            from pydantic_ai.providers.openai import OpenAIProvider

            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                from dotenv import load_dotenv

                load_dotenv()
                api_key = os.getenv("OPENAI_API_KEY")

            provider = OpenAIProvider(api_key=api_key)
            summarization_model = OpenAIChatModel("gpt-4.1-nano", provider=provider)

            summarization_agent = Agent(
                model=summarization_model,
                output_type=str,
                name="conversation_summarizer",
            )

            # Generate summary
            result = await summarization_agent.run(summarization_prompt)
            summary = result.output

            logger.info(f"Generated conversation summary ({len(summary)} chars)")

            return summary

        except Exception as e:
            logger.error(f"Error generating conversation summary: {e}")
            # Return a basic fallback summary
            return f"Conversation context: The user is working with the orchestrator on trading and market analysis tasks. Previous conversation history is available but could not be fully summarized due to an error: {str(e)}"

    def _register_dynamic_instructions(self):
        """Override base class to inject dynamic context (date, memories, user info, etc.)"""

        @self.agent.instructions
        def inject_dynamic_context(ctx: RunContext[OrchestratorDeps]) -> str:
            """Inject current date/time, user info, scratchpad, and user memories dynamically"""
            from datetime import datetime
            from zoneinfo import ZoneInfo

            from tools.native.scratchpad import Scratchpad

            sections = []

            # Always inject current date/time in Eastern Time (EST/EDT)
            # Get current time in UTC first, then convert to Eastern
            utc_now = datetime.now(ZoneInfo("UTC"))
            eastern_now = utc_now.astimezone(ZoneInfo("America/New_York"))

            date_section = f"\n\n## CURRENT DATE & TIME\n\n"
            date_section += (
                f"**Today's date:** {eastern_now.strftime('%A, %B %d, %Y')}\n"
            )
            date_section += f"**Current time:** {eastern_now.strftime('%I:%M %p %Z')}\n"
            date_section += f"**ISO format:** {eastern_now.isoformat()}\n"
            date_section += f"**Timezone:** {eastern_now.tzname()} (Eastern Time)\n"
            date_section += "\n**IMPORTANT:** All times are in Eastern Time (EST/EDT). When the user says 'today', 'this morning', 'this afternoon', 'tonight', use this date and time.\n"
            sections.append(date_section)

            # Inject user information if available
            if ctx.deps.user_name or ctx.deps.user_bio:
                user_section = "\n\n## USER INFORMATION\n\n"
                if ctx.deps.user_name:
                    user_section += f"**Name:** {ctx.deps.user_name}\n"
                if ctx.deps.user_bio:
                    user_section += f"**Bio:** {ctx.deps.user_bio}\n"
                user_section += "\nUse this information to personalize your responses and understand the user's context.\n"
                sections.append(user_section)

            # Inject scratchpad content if available
            thread_id = ctx.deps.state.thread_id
            if thread_id:
                scratchpad = Scratchpad(thread_id)
                entries = scratchpad.get_entries()
                if entries:
                    scratchpad_section = "\n\n## SCRATCHPAD\n\n"
                    scratchpad_section += (
                        "This is a shared scratchpad for important context:\n"
                    )
                    for entry in entries:
                        scratchpad_section += f"- [{entry.get('timestamp', '')}][{entry.get('author', 'unknown')}] {entry.get('content', '')}\n"
                    scratchpad_section += (
                        "\nRefer to this information to maintain context.\n"
                    )
                    sections.append(scratchpad_section)

            # Inject cache statistics and recent entries (with intelligent guidance)
            if thread_id:
                from tools.native.tool_cache import ToolCache

                try:
                    cache = ToolCache(thread_id)
                    stats = cache.get_stats()

                    if stats["valid_entries"] > 0:
                        cache_section = "\n\n## 💾 Cached Data Available\n\n"

                        tokens_saved = stats["total_tokens_saved"]
                        cache_section += f"**{stats['valid_entries']} cached entries** ({tokens_saved:,} tokens)\n\n"

                        # Show recent cache entries preview (last 3)
                        recent_entries = cache.lookup()[:3]
                        if recent_entries:
                            cache_section += "**Recent cache entries:**\n"
                            for i, entry in enumerate(recent_entries, 1):
                                age_min = entry["age_minutes"]
                                freshness = "🟢" if age_min < 5 else "🟡" if age_min < 15 else "🟠"
                                cache_section += f"{i}. {freshness} **{entry['tool_name']}** ({age_min}m ago): {entry['summary'][:60]}...\n"

                        # Intelligent cache decision guidance
                        cache_section += "\n**When to USE cache:**\n"
                        cache_section += "- Repeating a similar search (same product type, vendor, or category)\n"
                        cache_section += "- Referencing data you already fetched this conversation\n"
                        cache_section += "- Analytics/reports where real-time precision isn't critical\n"
                        cache_section += "- Follow-up questions about previously fetched data\n\n"

                        cache_section += "**When to SKIP cache and fetch fresh:**\n"
                        cache_section += "- User says: 'refresh', 'current', 'now', 'latest', 'again', 'new search'\n"
                        cache_section += "- After you just created/updated/deleted something\n"
                        cache_section += "- Query is clearly different from cached entries\n"
                        cache_section += "- User is troubleshooting or verifying a change took effect\n"
                        cache_section += "- Real-time data needed (live stock prices, portfolio positions)\n\n"

                        cache_section += "**Tool execution order:** search_docs (get syntax) → cache_lookup (optional) → execute_bash\n"

                        sections.append(cache_section)
                except Exception as e:
                    logger.error(f"Error getting cache stats: {e}")

            # Inject memories if available
            if ctx.deps.user_memories:
                memories_section = "\n\n## REMEMBERED INFORMATION\n\n"
                memories_section += "From previous conversations, I remember:\n"
                for i, memory in enumerate(ctx.deps.user_memories, 1):
                    memories_section += f"{i}. {memory}\n"
                memories_section += (
                    "\nUse this information to provide personalized assistance.\n"
                )
                sections.append(memories_section)

            # Inject TODO mode instruction if enabled
            if ctx.deps.use_todo:
                logger.info("[TODO] Injecting TODO mode instruction into agent prompt")
                todo_section = "\n\n## 📋 TODO MODE ENABLED\n\n"
                todo_section += (
                    "The user has enabled TODO mode for this conversation.\n\n"
                )
                todo_section += "**YOU MUST actively use the `todo_write` tool to:**\n"
                todo_section += "1. Break down complex requests into actionable tasks\n"
                todo_section += "2. Track progress through the conversation\n"
                todo_section += (
                    "3. Update task statuses (pending → in_progress → completed)\n"
                )
                todo_section += (
                    "4. Maintain a clear, visible task list for the user\n\n"
                )
                todo_section += "**When to use TODO tracking:**\n"
                todo_section += "- Multi-step workflows (3+ distinct actions)\n"
                todo_section += "- Complex tasks requiring careful planning\n"
                todo_section += "- User explicitly requests task breakdown\n"
                todo_section += "- Tasks with multiple dependencies\n\n"
                todo_section += "**Expected behavior:**\n"
                todo_section += "- Create todos at the START of complex tasks\n"
                todo_section += "- Mark ONE task as in_progress before working on it\n"
                todo_section += "- Complete tasks IMMEDIATELY after finishing them\n"
                todo_section += (
                    "- Keep the user informed of progress via the TODO panel\n"
                )
                sections.append(todo_section)
            else:
                logger.info(
                    f"[TODO] TODO mode NOT enabled (use_todo={ctx.deps.use_todo})"
                )

            return "".join(sections)

    def _get_history_processors(self) -> list:
        """
        Override base class to add context window management.
        Uses Pydantic AI's history_processors pattern for sliding window.
        """
        return [sliding_window_history_processor]

    def _get_system_prompt(self) -> str:
        """
        System prompt for the orchestrator.

        Note: This returns the base prompt. For dynamic content like memories,
        use system_prompt_runner which can access RunContext.
        """
        return """
# Nifty Strategist - AI Trading Assistant

## Identity & Purpose

You are **Nifty Strategist**, an AI-powered trading assistant for the Indian stock market (NSE). Your purpose is to help users:
- Analyze stocks using technical indicators
- Understand market opportunities
- Execute trades with human-in-the-loop (HITL) approval
- Manage their portfolio and watchlists

**Target Audience**: Non-technical users who want to learn trading while leveraging AI assistance.

**Key Principles**:
- Maximum autonomy for analysis and recommendations
- HITL approval required ONLY for actual transactions (place_order, cancel_order)
- Educational focus: explain reasoning in beginner-friendly language
- Never fabricate data or claim actions that didn't happen

---

## Tool Calling Rules

1. **NATIVE ONLY**: Use the native tool calling protocol - never use XML tags or markdown code blocks for tool calls
2. **NO PREAMBLE**: When calling a tool, just call it - don't narrate "I will now..."
3. **HITL FOR TRADES**: place_order and cancel_order require user approval before execution

---

## Available Tools

### Trading CLI Tools (via execute_bash)

All trading operations use CLI tools in `cli-tools/`. Run them with execute_bash.
Use `--json` for structured output. Use `--help` for any tool's full syntax.

**Market Data:**
- `python cli-tools/nf-market-status [--json]` — Check if market is open/closed (no token needed)
- `python cli-tools/nf-quote SYMBOL [SYMBOL2 ...] [--json]` — Live quotes
- `python cli-tools/nf-quote SYMBOL --historical [--interval day] [--days 30]` — OHLCV candles
- `python cli-tools/nf-quote --list` — Nifty 50 stocks (curated)
- `python cli-tools/nf-quote --search TERM` — Search any NSE stock by name/symbol (8000+ available)

**Technical Analysis:**
- `python cli-tools/nf-analyze SYMBOL [--interval 15minute|30minute|day] [--json]` — Full analysis
- `python cli-tools/nf-analyze SYMBOL1 SYMBOL2 --compare [--json]` — Compare signals

**Portfolio:**
- `python cli-tools/nf-portfolio [--json]` — Portfolio summary with all positions
- `python cli-tools/nf-portfolio --position SYMBOL [--json]` — Single position details
- `python cli-tools/nf-portfolio --calc-size SYMBOL --risk 5000 --sl 2 [--json]` — Position size calculator

**Orders (HITL-protected — orchestrator will request user approval):**
- `python cli-tools/nf-order buy SYMBOL QTY [--type LIMIT --price P] [--dry-run] [--json]`
- `python cli-tools/nf-order sell SYMBOL QTY [--type LIMIT --price P] [--json]`
- `python cli-tools/nf-order list [--all] [--json]` — View open/all orders
- `python cli-tools/nf-order cancel ORDER_ID [--json]`

**Watchlist:**
- `python cli-tools/nf-watchlist [--json]` — View watchlist with live prices
- `python cli-tools/nf-watchlist add SYMBOL [--buy P] [--sell P] [--notes "..."]`
- `python cli-tools/nf-watchlist remove SYMBOL`
- `python cli-tools/nf-watchlist update SYMBOL [--buy P] [--sell P]`
- `python cli-tools/nf-watchlist alerts [--json]` — Check triggered price alerts

For full documentation: `cat cli-tools/INDEX.md`

### Utility Tools
- **execute_bash(command)**: Run system commands and CLI tools
- **read_file(path)**: Read file contents
- **write_file(path, content)**: Write to files
- **todo_write(tasks)**: Track multi-step tasks
- **write_to_scratchpad(content)**: Store working notes

---

## Response Guidelines

**Tone**: Helpful, patient, educational. Explain technical terms for beginners.

**Format**: Use Markdown for clarity. Tables for comparisons. Emojis sparingly for visual signaling.

**Analysis Flow**:
1. Fetch current data (quote or historical)
2. Run technical analysis if needed
3. Explain findings in plain language
4. Provide actionable recommendation with reasoning
5. If user wants to trade, use HITL tools

**Risk Warnings**: Always remind users:
- Past performance doesn't guarantee future results
- Never invest more than you can afford to lose
- Diversification is important
- Paper trading mode for practice (no real money at risk)

---

## Trading Best Practices

When recommending trades:
1. Calculate position size based on risk tolerance (default 2% per trade)
2. Always suggest stop-loss levels
3. Consider risk-reward ratio (prefer >= 2:1)
4. Check if stock is already in portfolio before buying more

When analyzing:
1. Look at multiple timeframes (15min for intraday, daily for swing)
2. Consider RSI, MACD, and trend together for confluence
3. Note support/resistance levels
4. Check volume for confirmation

---

## Memory System

Relevant memories about user preferences are automatically injected. Use them to personalize:
- Risk tolerance (conservative, moderate, aggressive)
- Trading style (day trader, swing trader, long-term)
- Sector preferences
- Stocks to avoid
- Communication preferences

---

## Paper Trading Mode

Currently operating in **paper trading mode**:
- Orders are simulated, not real
- Starting capital: 10,00,000 (10 lakh rupees)
- No real money at risk
- Perfect for learning and testing strategies

---

## Prime Directives

| Rule | Description |
|------|-------------|
| **HONESTY-1** | Never fabricate prices, indicators, or analysis results |
| **HONESTY-2** | Never claim a trade was executed unless it actually was |
| **SAFETY-1** | Always require HITL approval for real trades |
| **EDUCATION-1** | Explain reasoning so users learn |
"""

    def _check_interrupted(self, ctx: RunContext[OrchestratorDeps]) -> None:
        """
        Check if the operation has been interrupted.

        Raises an exception if interrupted to stop execution immediately.
        """
        if ctx.deps.interrupt_signal and ctx.deps.interrupt_signal.is_set():
            reason = ctx.deps.interrupt_signal.reason or "User requested stop"
            logger.info(f"[Interrupt] Operation interrupted in tool: {reason}")
            raise RuntimeError(f"Operation interrupted: {reason}")

    def _register_tools(self) -> None:
        """Register tools for agent delegation"""

        # Register all trading tools (market data, analysis, portfolio, orders, watchlist)
        from tools.trading import register_all_trading_tools
        register_all_trading_tools(self.agent, OrchestratorDeps)

        @self.agent.tool
        async def execute_bash(
            ctx: RunContext[OrchestratorDeps],
            command: str,
            timeout: Optional[int] = None,
        ) -> str:  # pyright: ignore[reportUnusedFunction]
            """
            Execute a bash command and return the output.

            🚨 MANDATORY: Before executing any bash-tools script, first get its syntax:
            1. Use search_docs() to find documentation, OR
            2. Run with --help flag: "python bash-tools/script.py --help"
            Only execute once you have the correct syntax in context.

            📍 WORKING DIRECTORY: You are already in /backend - do NOT use "cd backend &&".
            Run scripts directly: "python bash-tools/script.py ..." (not "cd backend && python...")

            Args:
                command: The bash command to execute
                timeout: Maximum time in seconds to wait for command completion (default: 300 seconds / 5 minutes)

            Returns:
                Command output or error message
            """
            # Check for interruption
            self._check_interrupted(ctx)

            # Sanitize command input to handle model hallucinations
            # Kimi K2 sometimes sends ": nothing to execute" or ": <command>"
            original_command = command
            command = command.lstrip(":").strip()
            
            # Check for specific hallucination patterns where model sends conversational text instead of command
            hallucination_patterns = [
                "nothing to execute",
                "no command",
                "none",
                "agent not available",
                "tool not available"
            ]
            
            if not command or any(p in command.lower() for p in hallucination_patterns):
                # If command is empty or matches hallucination pattern
                logger.warning(f"Detected invalid bash command input: '{original_command}'")
                return (
                    f"❌ ERROR: You sent an invalid command string: '{original_command}'\n"
                    f"You must send the ACTUAL bash command to execute (e.g., 'ls -la', 'python script.py').\n"
                    f"Do not send conversational filler or 'nothing to execute'."
                )

            # HITL: Request approval before executing write operation
            if ctx.deps.hitl_enabled:
                from utils.hitl_manager import get_hitl_manager

                hitl_manager = get_hitl_manager()

                # Create explanation
                explanation = f"Execute bash command: {command[:100]}"
                if len(command) > 100:
                    explanation += "..."

                # Request approval (blocks until user responds or timeout)
                approval_result = await hitl_manager.request_approval(
                    tool_name="execute_bash",
                    tool_args={"command": command, "timeout": timeout},
                    explanation=explanation,
                    timeout_seconds=60,
                    thread_id=ctx.deps.state.thread_id,
                )

                if not approval_result["approved"]:
                    reason = approval_result.get("reason", "User rejected")
                    return f"❌ Command not executed: {reason}"

            import time
            import uuid
            from datetime import datetime

            from tools.native.tool_cache import ToolCache
            from utils.bash_streamer import BashOutputEvent, bash_streamer

            # Default timeout: 5 minutes
            if timeout is None:
                timeout = 300

            # Generate unique tool call ID for this execution
            tool_call_id = str(uuid.uuid4())
            thread_id = ctx.deps.state.thread_id
            start_time = time.time()

            try:
                # Log the command being executed
                logger.info(f"Executing bash command: {command}")

                # AUTO-HELP INJECTION: Detect bash-tools or cli-tools scripts and provide help on first use
                help_text = None
                script_name = None

                # Check if command is running a script from bash-tools/ or cli-tools/
                import re

                bash_tools_match = re.search(
                    r"python3?\s+.*?bash-tools/([^\s]+\.py)", command
                )
                cli_tools_match = re.search(
                    r"(?:python3?\s+)?(?:\./)?\s*cli-tools/(nf-[^\s]+)", command
                )
                docs_warning = None
                script_match = bash_tools_match or cli_tools_match
                if script_match:
                    script_name = script_match.group(1)

                    # ENFORCEMENT: Check if docs were looked up before execution
                    docs_checked = script_name in ctx.deps.docs_checked_scripts
                    first_use = script_name not in ctx.deps.used_bash_tools

                    if first_use and not docs_checked:
                        # First use without docs lookup - this is the anti-pattern we want to prevent
                        docs_warning = (
                            f"\n⚠️ DOCS-FIRST REMINDER: Executing {script_name} without prior docs lookup.\n"
                            f"For reliable results, always search_docs() or run --help before executing scripts.\n"
                            f"This helps avoid syntax errors and ensures correct parameter usage.\n"
                        )
                        logger.warning(
                            f"⚠️ Enforcement: {script_name} executed without prior docs lookup"
                        )

                    # Check if this is the first time using this script
                    if first_use:
                        ctx.deps.used_bash_tools.add(script_name)
                        logger.info(f"First use of {script_name} - fetching help text")

                        # Extract the full path to the script
                        if bash_tools_match:
                            script_path_match = re.search(
                                r"(.*?bash-tools/[^\s]+\.py)", command
                            )
                            help_cmd = f"python3 {script_path_match.group(1)} --help" if script_path_match else None
                        else:
                            script_path_match = re.search(
                                r"((?:\./)?\s*cli-tools/nf-[^\s]+)", command
                            )
                            help_cmd = f"python3 {script_path_match.group(1)} --help" if script_path_match else None

                        if help_cmd:
                            # Run --help to get usage information
                            try:
                                help_process = await asyncio.create_subprocess_shell(
                                    help_cmd,
                                    stdout=asyncio.subprocess.PIPE,
                                    stderr=asyncio.subprocess.PIPE,
                                    cwd=str(Path(__file__).parent.parent),
                                )
                                help_stdout, help_stderr = await asyncio.wait_for(
                                    help_process.communicate(), timeout=5
                                )

                                if help_process.returncode == 0 and help_stdout:
                                    help_text = help_stdout.decode(
                                        "utf-8", errors="replace"
                                    )
                                    logger.info(
                                        f"✓ Auto-injected help for {script_name}"
                                    )
                            except Exception as help_error:
                                logger.warning(
                                    f"Could not fetch help for {script_name}: {help_error}"
                                )

                # Emit command event
                await bash_streamer.emit(
                    BashOutputEvent(
                        thread_id=thread_id,
                        tool_call_id=tool_call_id,
                        event_type="command",
                        content=command,
                        timestamp=datetime.now(),
                    )
                )

                # Build subprocess env — inject NF_ACCESS_TOKEN for CLI tools
                import os as _os
                subprocess_env = _os.environ.copy()
                if ctx.deps.upstox_access_token:
                    subprocess_env["NF_ACCESS_TOKEN"] = ctx.deps.upstox_access_token
                if ctx.deps.user_id:
                    subprocess_env["NF_USER_ID"] = str(ctx.deps.user_id)

                # Run the command with asyncio, streaming output
                # cwd=backend/ so cli-tools/ and bash-tools/ resolve correctly
                process = await asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=str(Path(__file__).parent.parent),
                    env=subprocess_env,
                )

                # Collect all output
                stdout_lines = []
                stderr_lines = []

                # Read stdout line by line and stream
                async def read_stdout():
                    if process.stdout:
                        async for line in process.stdout:
                            line_text = line.decode("utf-8", errors="replace")
                            stdout_lines.append(line_text)
                            # Emit output event for each line
                            await bash_streamer.emit(
                                BashOutputEvent(
                                    thread_id=thread_id,
                                    tool_call_id=tool_call_id,
                                    event_type="output",
                                    content=line_text,
                                    timestamp=datetime.now(),
                                )
                            )

                # Read stderr line by line and stream
                async def read_stderr():
                    if process.stderr:
                        async for line in process.stderr:
                            line_text = line.decode("utf-8", errors="replace")
                            stderr_lines.append(line_text)
                            # Emit error output event
                            await bash_streamer.emit(
                                BashOutputEvent(
                                    thread_id=thread_id,
                                    tool_call_id=tool_call_id,
                                    event_type="output",
                                    content=line_text,
                                    timestamp=datetime.now(),
                                )
                            )

                # Wait for the command to complete with timeout
                try:
                    await asyncio.wait_for(
                        asyncio.gather(read_stdout(), read_stderr(), process.wait()),
                        timeout=timeout,
                    )
                except asyncio.TimeoutError:
                    process.kill()
                    await bash_streamer.emit(
                        BashOutputEvent(
                            thread_id=thread_id,
                            tool_call_id=tool_call_id,
                            event_type="error",
                            content=f"Command timed out after {timeout} seconds",
                            timestamp=datetime.now(),
                            exit_code=-1,
                        )
                    )
                    return f"Command timed out after {timeout} seconds"

                # Combine output
                stdout_text = "".join(stdout_lines)
                stderr_text = "".join(stderr_lines)

                # Emit completion event
                await bash_streamer.emit(
                    BashOutputEvent(
                        thread_id=thread_id,
                        tool_call_id=tool_call_id,
                        event_type="complete",
                        content=f"Command completed with exit code {process.returncode}",
                        timestamp=datetime.now(),
                        exit_code=process.returncode,
                    )
                )

                # Smart cache invalidation
                if process.returncode == 0:
                    await self._auto_invalidate_cache(command, thread_id)

                # Calculate execution time
                execution_time_ms = int((time.time() - start_time) * 1000)

                # Return combined output
                if process.returncode == 0:
                    result = stdout_text or "Command executed successfully (no output)"

                    # Prepend docs warning if enforcement triggered
                    if docs_warning:
                        result = f"{docs_warning}\n{result}"

                    # Prepend help text if this was the first use of a bash-tool
                    if help_text:
                        result = (
                            f"📖 TOOL USAGE GUIDE for {script_name}:\n"
                            f"{'=' * 60}\n"
                            f"{help_text}\n"
                            f"{'=' * 60}\n\n"
                            f"EXECUTION RESULT:\n"
                            f"{result}"
                        )

                    # Auto-cache expensive operations
                    await self._auto_cache_result(
                        command=command,
                        result=result,
                        execution_time_ms=execution_time_ms,
                        thread_id=thread_id,
                    )

                    return result
                else:
                    error_msg = f"Command failed with exit code {process.returncode}"
                    if stderr_text:
                        error_msg += f"\nError: {stderr_text}"
                    if stdout_text:
                        error_msg += f"\nOutput: {stdout_text}"

                    # Prepend docs warning if enforcement triggered (especially important for errors!)
                    if docs_warning:
                        error_msg = f"{docs_warning}\n{error_msg}"

                    # Prepend help text if this was the first use (especially helpful for errors!)
                    if help_text:
                        error_msg = (
                            f"📖 TOOL USAGE GUIDE for {script_name}:\n"
                            f"{'=' * 60}\n"
                            f"{help_text}\n"
                            f"{'=' * 60}\n\n"
                            f"EXECUTION FAILED:\n"
                            f"{error_msg}"
                        )

                    return error_msg

            except Exception as e:
                logger.error(f"Error executing bash command: {e}")
                # Emit error event
                await bash_streamer.emit(
                    BashOutputEvent(
                        thread_id=thread_id,
                        tool_call_id=tool_call_id,
                        event_type="error",
                        content=str(e),
                        timestamp=datetime.now(),
                        exit_code=-1,
                    )
                )
                return f"Error executing command: {str(e)}"

        @self.agent.tool
        async def call_agent(
            ctx: RunContext[OrchestratorDeps],
            agent_name: str,
            task: str,
            context: Optional[Dict[str, Any]] = None,
        ) -> str:  # pyright: ignore[reportUnusedFunction]
            """Call a domain-specific agent for specialized operations.

            💡 Cache tip: If you've already called this agent for similar data in this conversation,
            consider using cache_lookup() first to avoid redundant API calls. Skip cache if the user
            wants fresh/current data or if the query is clearly different from previous calls.

            Available agents:
            - web_search: Web search using Perplexity API for current information
            - vision: Image analysis, OCR, and visual Q&A

            Args:
                agent_name: Name of the agent to call (web_search, vision)
                task: The task description for the agent
                context: Optional context dictionary with additional parameters

            Returns:
                The agent's response as a string
            """
            # Check for interruption
            self._check_interrupted(ctx)

            # Normalize agent name to handle potential hallucinated formats (e.g. "{marketing}", ": marketing")
            # Some models like Kimi K2 struggle with the exact string format
            agent_name_clean = agent_name.lower().strip()
            
            # Only allow domain-specific agents
            allowed_agents = [
                "web_search",
                "vision",
            ]

            # Robust matching strategy:
            # 1. Check exact match
            # 2. Check if valid agent name is a substring of the input (fuzzy match)
            matched_name = None
            
            if agent_name_clean in allowed_agents:
                matched_name = agent_name_clean
            else:
                # Fuzzy match: check if any allowed agent is in the input string
                # e.g. "agent_name: marketing" -> matches "marketing"
                for allowed in allowed_agents:
                    if allowed in agent_name_clean:
                        matched_name = allowed
                        logger.info(f"Fuzzy matched agent '{matched_name}' from input '{agent_name}'")
                        break
            
            # FIX: Handle case where model passes context as a JSON string instead of a dictionary
            # Some models (e.g. Kimi k1.5) incorrectly JSON-serialize the dictionary
            if isinstance(context, str):
                try:
                    logger.warning(f"Context passed as string, attempting to parse: {context[:100]}...")
                    # Try to clean up potential markdown code blocks if present
                    clean_context = context.strip()
                    if clean_context.startswith("```json"):
                        clean_context = clean_context[7:]
                    if clean_context.startswith("```"):
                        clean_context = clean_context[3:]
                    if clean_context.endswith("```"):
                        clean_context = clean_context[:-3]
                    
                    context = json.loads(clean_context.strip())
                    if not isinstance(context, dict):
                        logger.warning(f"Parsed context is not a dict, got {type(context)}. Resetting to empty dict.")
                        context = {}
                    else:
                        logger.info("Successfully parsed context string into dictionary")
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse context string: {e}. using empty dict.")
                    context = {}
                except Exception as e:
                    logger.error(f"Unexpected error parsing context string: {e}. using empty dict.")
                    context = {}
            
            # If we found a valid agent, use it
            if matched_name:
                agent_name = matched_name
            else:
                # Fallthrough to error if no match found
                return f"""Agent '{agent_name}' is not available.

Available agents: {allowed_agents}
"""

            if agent_name not in self.specialized_agents:
                return f"Agent '{agent_name}' not registered. This is a configuration error."

            agent = self.specialized_agents[agent_name]
            logger.info(f"Calling {agent_name} agent with task: {task}")

            # Generate comprehensive conversation summary
            logger.info("Generating conversation summary for agent context...")
            conversation_summary = await self._generate_conversation_summary(ctx)
            logger.info(
                f"Conversation summary generated: {len(conversation_summary)} chars"
            )

            # Enhance the task with conversation summary
            enhanced_task = f"""## CONVERSATION CONTEXT

{conversation_summary}

---

## CURRENT TASK

{task}"""

            logger.info(
                f"Enhanced task with conversation summary for {agent_name} agent"
            )

            # Log agent call with full context to Logfire
            try:
                from config.logfire_config import log_agent_call

                log_agent_call(
                    thread_id=ctx.deps.state.thread_id,
                    agent_name=agent_name,
                    original_task=task,
                    enhanced_task=enhanced_task,
                    conversation_summary=conversation_summary,
                    context=context,
                )
            except Exception as log_error:
                logger.debug(f"Failed to log agent call to Logfire: {log_error}")

            # Prepare context based on agent type
            if context is None:
                context = {}

            # Wrap agent call in try-except to catch and format errors
            try:
                # Handle web_search agent
                if agent_name == "web_search":
                    from agents.web_search_agent import WebSearchDeps

                    # Get Perplexity API key from environment
                    perplexity_api_key = os.getenv("PERPLEXITY_SEARCH_KEY")

                    web_search_deps = WebSearchDeps(
                        state=ctx.deps.state, perplexity_api_key=perplexity_api_key
                    )
                    result = await agent.run(enhanced_task, deps=web_search_deps)

                # Handle vision agent
                elif agent_name == "vision":
                    from agents.vision_agent import VisionDeps

                    # Extract image path from context (should be in the task or context)
                    image_path = context.get("image_path") if context else None

                    if not image_path:
                        return "Error: Vision agent requires 'image_path' in context. Please provide the path to the image file."

                    vision_deps = VisionDeps(
                        user_email=ctx.deps.state.user_id,
                        conversation_id=ctx.deps.state.thread_id,
                    )

                    # Call the appropriate method based on task
                    if (
                        "extract text" in enhanced_task.lower()
                        or "ocr" in enhanced_task.lower()
                    ):
                        result = await agent.extract_text(
                            image_path=image_path,
                            user_email=vision_deps.user_email,
                            conversation_id=vision_deps.conversation_id,
                        )
                    elif "product" in enhanced_task.lower():
                        result = await agent.analyze_product_image(
                            image_path=image_path,
                            user_email=vision_deps.user_email,
                            conversation_id=vision_deps.conversation_id,
                        )
                    else:
                        result = await agent.analyze_image(
                            image_path=image_path,
                            query=enhanced_task,
                            user_email=vision_deps.user_email,
                            conversation_id=vision_deps.conversation_id,
                        )

                # Handle any other future agents
                else:
                    result = await agent.run(enhanced_task, deps=context)

                logger.info(f"{agent_name} agent returned: {result}")

                # Extract result string
                result_str = str(result.output if hasattr(result, "output") else result)

                # Auto-cache agent call results
                await self._auto_cache_agent_result(
                    agent_name=agent_name,
                    task=task,
                    result=result_str,
                    thread_id=ctx.deps.state.thread_id,
                )

                return result_str

            except Exception as e:
                # Agent crashed - format error for LLM to understand and potentially retry
                logger.error(
                    f"❌ Agent '{agent_name}' crashed: {type(e).__name__}: {str(e)}"
                )

                # Try to extract useful error information
                error_type = type(e).__name__
                error_msg = str(e)

                # Analyze error to provide suggestions
                suggestions = []
                retryable = True

                # Check for common error patterns
                if "unrecognized field" in error_msg.lower():
                    suggestions.append(
                        "The API field name may be incorrect or not exist for this resource"
                    )
                    suggestions.append(
                        "Check the API documentation for valid field names"
                    )
                    retryable = True
                elif (
                    "authentication" in error_msg.lower()
                    or "credentials" in error_msg.lower()
                    or "token" in error_msg.lower()
                ):
                    suggestions.append("OAuth credentials may be expired or invalid")
                    suggestions.append("User may need to re-authenticate")
                    retryable = False
                elif "timeout" in error_msg.lower():
                    suggestions.append(
                        "API request timed out - try again or simplify the query"
                    )
                    retryable = True
                elif "rate limit" in error_msg.lower():
                    suggestions.append(
                        "API rate limit exceeded - wait a moment before retrying"
                    )
                    retryable = True
                else:
                    suggestions.append("Review the error message for specific guidance")
                    suggestions.append(f"This is a {error_type} error")

                # Format error message for LLM
                error_response = f"""❌ **{agent_name} Agent Error**

**Task:** {task}

**Error Type:** {error_type}

**Error Message:** {error_msg}

**Suggestions:**
"""
                for i, suggestion in enumerate(suggestions, 1):
                    error_response += f"{i}. {suggestion}\n"

                if retryable:
                    error_response += "\n**This error appears to be retryable.** You can try again with:"
                    error_response += "\n- Adjusted parameters"
                    error_response += (
                        "\n- Better instructions based on the suggestions above"
                    )
                    error_response += "\n- Alternative approaches"
                else:
                    error_response += "\n⚠️ **This error requires user intervention.** Please inform the user about the issue."

                return error_response

        @self.agent.tool
        async def get_user_profile(ctx: RunContext[OrchestratorDeps]) -> str:
            """
            Get current user profile information including name, email, and bio.

            This provides context about the user to personalize responses and
            understand the user's background, role, and preferences.

            Returns:
                User profile information including name, email, bio, and other relevant details
            """
            try:
                user_id = ctx.deps.state.user_id

                # Try to get user from database
                async with AsyncSessionLocal() as db:
                    from database.models import User as DBUser
                    from sqlalchemy import select

                    result = await db.execute(
                        select(DBUser).where(DBUser.email == user_id)
                    )
                    db_user = result.scalar_one_or_none()

                    if db_user:
                        profile_info = f"""User Profile:
- Name: {db_user.name or "Not set"}
- Email: {db_user.email}
- User ID: {db_user.id}
- Trading Mode: {getattr(db_user, 'trading_mode', 'paper')}
- Upstox: {"Connected" if db_user.upstox_access_token else "Not connected"}"""

                        return profile_info
                    else:
                        return f"User profile not found for: {user_id}"

            except Exception as e:
                logger.error(f"Error retrieving user profile: {e}")
                return f"Error retrieving user profile: {str(e)}"

        @self.agent.tool
        async def cache_lookup(
            ctx: RunContext[OrchestratorDeps], query: Optional[str] = None
        ) -> str:
            """
            Browse the tool call cache to see what results are available.

            Use this BEFORE making expensive tool calls (product searches, agent calls, analytics queries)
            to check if you've already performed similar operations.

            Args:
                query: Optional search term to filter cache entries (e.g., "espresso machines", "Q4 sales")

            Returns:
                JSON list of available cache entries with:
                - cache_id: Unique identifier to retrieve result
                - tool_name: Original tool that was called
                - parameters: Parameters used in the call
                - summary: Brief description of result
                - timestamp: When result was cached
                - age_minutes: How old the cache entry is
                - tokens_saved: Tokens that will be saved by using cache

            Examples:
                cache_lookup()  # List all cached results
                cache_lookup("stock quote")  # Find stock quote caches
                cache_lookup("RELIANCE")  # Find caches mentioning RELIANCE
            """
            try:
                from tools.native.tool_cache import ToolCache

                thread_id = ctx.deps.state.thread_id
                cache = ToolCache(thread_id)
                entries = cache.lookup(query)

                if not entries:
                    return (
                        "No cache entries found."
                        if not query
                        else f"No cache entries matching '{query}' found."
                    )

                # Format output with actionable suggestions
                output = f"Found {len(entries)} cached result(s)"
                if query:
                    output += f" matching '{query}'"
                output += ":\n\n"

                for i, entry in enumerate(entries, 1):
                    age_min = entry["age_minutes"]
                    tokens = entry["tokens_saved"]

                    # Age indicator
                    if age_min < 5:
                        freshness = "🟢 Very fresh"
                    elif age_min < 15:
                        freshness = "🟡 Recent"
                    elif age_min < 60:
                        freshness = "🟠 Older"
                    else:
                        freshness = "🔴 Stale"

                    output += f"{i}. {freshness} ({age_min}m ago)\n"
                    output += f"   Tool: {entry['tool_name']}\n"
                    output += f"   Summary: {entry['summary']}\n"
                    output += f"   Cache ID: {entry['cache_id']}\n"
                    output += f"   💰 Savings: ~{tokens:,} tokens (~${(tokens / 1_000_000) * 3:.3f})\n"
                    output += f"   ▶️  To use: cache_retrieve('{entry['cache_id']}')\n\n"

                total_tokens = sum(e["tokens_saved"] for e in entries)
                output += f"💡 TIP: Using cached results saves {total_tokens:,} tokens total (~${(total_tokens / 1_000_000) * 3:.3f})\n"

                return output

            except Exception as e:
                logger.error(f"Error looking up cache: {e}")
                return f"Error looking up cache: {str(e)}"

        @self.agent.tool
        async def cache_retrieve(
            ctx: RunContext[OrchestratorDeps], cache_id: str
        ) -> str:
            """
            Retrieve a specific cached tool call result.

            Use this AFTER browsing the cache with cache_lookup() to get the actual result data.
            This avoids re-running expensive operations.

            Args:
                cache_id: The cache_id from cache_lookup results

            Returns:
                The full cached result from the previous tool call

            Example:
                1. cache_lookup("product search") → Get list with cache_ids
                2. cache_retrieve("abc-123") → Get the actual product search results
            """
            try:
                from tools.native.tool_cache import ToolCache

                thread_id = ctx.deps.state.thread_id
                cache = ToolCache(thread_id)
                entry = cache.get_entry(cache_id)

                if not entry:
                    return f"Cache entry not found: {cache_id}"

                # Return both metadata and result for context
                return json.dumps(
                    {
                        "tool_name": entry["tool_name"],
                        "parameters": entry["parameters"],
                        "summary": entry.get("summary", ""),
                        "cached_at": entry["timestamp"],
                        "result": entry["result"],
                    },
                    indent=2,
                )

            except Exception as e:
                logger.error(f"Error retrieving cache: {e}")
                return f"Error retrieving cache: {str(e)}"

        @self.agent.tool
        async def cache_store(
            ctx: RunContext[OrchestratorDeps],
            tool_name: str,
            parameters: Dict[str, Any],
            result: str,
            summary: str,
            invalidation_triggers: Optional[List[str]] = None,
        ) -> str:
            """
            Store a tool call result in the cache for future use.

            Use this AFTER expensive operations to avoid repeating them in the same conversation.

            Args:
                tool_name: Name of the tool that was called (e.g., "search_products", "call_agent")
                parameters: Parameters used in the call (as dict)
                result: The result from the tool call
                summary: Brief description of what this result contains (1-2 sentences)
                invalidation_triggers: List of actions that should invalidate this cache
                    Common triggers:
                    - "product_create", "product_update" - for product searches
                    - "order_create" - for sales/analytics queries
                    - "inventory_update" - for inventory queries

            Returns:
                cache_id for future retrieval

            Examples:
                # After stock quote
                cache_store(
                    tool_name="nf_quote",
                    parameters={"symbol": "RELIANCE"},
                    result=<quote data>,
                    summary="RELIANCE live quote with OHLCV data",
                    invalidation_triggers=[]
                )

                # After technical analysis
                cache_store(
                    tool_name="nf_analyze",
                    parameters={"symbol": "HDFCBANK"},
                    result=<analysis>,
                    summary="HDFCBANK technical analysis with RSI, MACD signals",
                    invalidation_triggers=[]
                )
            """
            try:
                from tools.native.tool_cache import ToolCache

                thread_id = ctx.deps.state.thread_id
                cache = ToolCache(thread_id)

                # Estimate tokens saved (rough heuristic: 4 chars per token)
                tokens_saved = len(result) // 4

                cache_id = cache.store(
                    tool_name=tool_name,
                    parameters=parameters,
                    result=result,
                    summary=summary,
                    invalidation_triggers=invalidation_triggers,
                    tokens_saved=tokens_saved,
                )

                return f"Cached with ID: {cache_id}. Estimated tokens saved on next lookup: {tokens_saved}"

            except Exception as e:
                logger.error(f"Error storing cache: {e}")
                return f"Error storing cache: {str(e)}"

        @self.agent.tool
        async def todo_write(
            ctx: RunContext[OrchestratorDeps], todos: List[TodoItem]
        ) -> str:
            """
            Create or update the TODO list to track task progress.

            CRITICAL RULES:
            1. ONLY ONE task should be 'in_progress' at a time
            2. Tasks have two forms:
               - content: Imperative ("Run tests", "Fix bug")
               - activeForm: Present continuous ("Running tests", "Fixing bug")
            3. Mark tasks as completed IMMEDIATELY after finishing
            4. Use for complex tasks (3+ steps) or user-provided lists

            Args:
                todos: List of TodoItem objects with content, status, and activeForm

            Returns:
                Confirmation message with progress summary

            Example:
                todos=[
                    TodoItem(content="Analyze codebase", status="completed", activeForm="Analyzing codebase"),
                    TodoItem(content="Fix authentication", status="in_progress", activeForm="Fixing authentication"),
                    TodoItem(content="Run tests", status="pending", activeForm="Running tests")
                ]
            """
            try:
                # Create new TodoList
                new_todo_list = TodoList(todos=todos)

                # Validate single in_progress rule
                if not new_todo_list.validate_single_in_progress():
                    return "ERROR: Multiple tasks marked as 'in_progress'. Only ONE task can be in_progress at a time."

                # Update dependencies
                ctx.deps.todo_list = new_todo_list

                # Build summary
                total = new_todo_list.get_total_count()
                completed = new_todo_list.get_completed_count()
                in_progress = new_todo_list.get_in_progress()
                pending = new_todo_list.get_pending_count()
                progress_pct = new_todo_list.get_progress_percentage()

                summary_parts = [
                    f"TODO list updated: {completed}/{total} completed ({progress_pct:.0f}%)"
                ]

                if in_progress:
                    summary_parts.append(f"Currently: {in_progress.activeForm}")

                if pending > 0:
                    summary_parts.append(f"{pending} tasks remaining")

                summary = " | ".join(summary_parts)

                logger.info(f"TODO list updated: {summary}")

                return summary

            except Exception as e:
                logger.error(f"Error updating TODO list: {e}")
                return f"Error updating TODO list: {str(e)}"

        @self.agent.tool
        async def write_to_scratchpad(
            ctx: RunContext[OrchestratorDeps], content: str
        ) -> str:
            """
            Write a note to the scratchpad for the current thread.

            Use this to remember important details, observations, or context
            that will be useful for future steps in the conversation. The
            scratchpad is injected into the system prompt on every turn.

            Args:
                content: The text to write to the scratchpad.

            Returns:
                A confirmation message.
            """
            try:
                thread_id = ctx.deps.state.thread_id
                if not thread_id:
                    return "Error: Could not determine the thread ID."

                scratchpad = Scratchpad(thread_id)
                scratchpad.add_entry(content, author="agent")
                logger.info(
                    f"Agent wrote to scratchpad for thread {thread_id}: {content}"
                )
                return "Content successfully written to scratchpad."
            except Exception as e:
                logger.error(f"Error writing to scratchpad: {e}")
                return f"Error writing to scratchpad: {str(e)}"

        @self.agent.tool
        async def todo_read(ctx: RunContext[OrchestratorDeps]) -> str:
            """
            Read the current TODO list to check progress.

            Returns:
                Formatted TODO list with status for each task

            Example output:
                TODO List (2/4 completed, 50%):
                ✓ Analyze codebase [completed]
                ⟳ Fix authentication [in_progress]
                ○ Run tests [pending]
                ○ Deploy changes [pending]
            """
            try:
                todo_list = ctx.deps.todo_list

                if todo_list.get_total_count() == 0:
                    return "No TODO list created yet. Use todo_write to create one for complex tasks."

                # Build formatted output
                total = todo_list.get_total_count()
                completed = todo_list.get_completed_count()
                progress_pct = todo_list.get_progress_percentage()

                lines = [
                    f"TODO List ({completed}/{total} completed, {progress_pct:.0f}%):"
                ]

                for i, todo in enumerate(todo_list.todos):
                    if todo.status == "completed":
                        icon = "✓"
                    elif todo.status == "in_progress":
                        icon = "⟳"
                    else:  # pending
                        icon = "○"

                    lines.append(f"{icon} {todo.content} [{todo.status}]")

                output = "\n".join(lines)
                logger.info(f"TODO list read: {completed}/{total} completed")

                return output

            except Exception as e:
                logger.error(f"Error reading TODO list: {e}")
                return f"Error reading TODO list: {str(e)}"

        @self.agent.tool
        async def read_docs(ctx: RunContext[OrchestratorDeps], doc_path: str) -> str:
            """
            Read documentation files from database. Use for simple tasks where you just need to reference docs.

            Supports glob patterns for reading multiple files at once.

            Args:
                doc_path: Path to documentation file or glob pattern
                         Examples:
                         - "docs/INDEX.md" - Read the index
                         - "docs/product-guidelines/*.md" - Read all product guidelines
                         - "docs/product-guidelines/09-new-product-workflow.md" - Specific file
                         - "graphql-operations/products/*.md" - Read all product operations

            Returns:
                Content of the documentation file(s)

            Use this for:
            - Simple queries that need doc reference
            - Quick lookups
            - When you don't need complex analysis

            For complex tasks requiring analysis, use spawn_specialist instead.
            """
            try:
                from services.doc_manager import DocManager

                # DB stores paths with "docs/" prefix, so ensure it's present
                normalized_path = doc_path
                if normalized_path.startswith("/"):
                    # Absolute path - extract relative portion
                    if "/docs/" in normalized_path:
                        normalized_path = "docs/" + normalized_path.split("/docs/", 1)[1]
                elif not normalized_path.startswith("docs/"):
                    # Add docs/ prefix if missing
                    normalized_path = f"docs/{normalized_path}"

                manager = DocManager()

                # Handle glob patterns
                if "*" in normalized_path or "?" in normalized_path:
                    docs = await manager.get_doc_by_glob(normalized_path)
                    await manager.close()

                    if not docs:
                        return f"No files found matching pattern: {doc_path}"

                    logger.info(f"Reading {len(docs)} files matching: {doc_path}")

                    # Format all matching documents
                    content_parts = []
                    for doc in docs:
                        filename = doc.doc_path.split("/")[-1]
                        content_parts.append(
                            f"# FILE: {filename}\n\n{doc.content}\n\n{'=' * 80}\n"
                        )

                    # Track bash-tools scripts mentioned in read content
                    import re as read_re

                    full_content = "\n".join(content_parts)
                    script_matches = read_re.findall(
                        r"bash-tools/([^\s\"']+\.py)", full_content
                    )
                    for script_name in script_matches:
                        ctx.deps.docs_checked_scripts.add(script_name)
                        logger.info(f"📚 Tracked docs lookup for: {script_name}")

                    return full_content

                # Single file
                else:
                    doc = await manager.get_doc(normalized_path)

                    if not doc:
                        # Try to suggest similar files from DB
                        similar_docs = await manager.get_doc_by_glob(
                            f"%{normalized_path.split('/')[-1]}%"
                        )
                        await manager.close()

                        if similar_docs:
                            suggestions = [d.doc_path for d in similar_docs[:5]]
                            return (
                                f"File not found: {doc_path}\n\nDid you mean:\n"
                                + "\n".join(f"  - {s}" for s in suggestions)
                            )
                        return f"Documentation file not found: {doc_path}"

                    await manager.close()

                    content = doc.content
                    logger.info(f"Read {len(content)} chars from {doc_path}")

                    # Track bash-tools scripts mentioned in read content
                    import re as read_single_re

                    script_matches = read_single_re.findall(
                        r"bash-tools/([^\s\"']+\.py)", content
                    )
                    for script_name in script_matches:
                        ctx.deps.docs_checked_scripts.add(script_name)
                        logger.info(f"📚 Tracked docs lookup for: {script_name}")

                    return content

            except Exception as e:
                logger.error(f"Error reading docs at {doc_path}: {e}")
                return f"Error reading documentation: {str(e)}"

        @self.agent.tool
        async def search_docs(
            ctx: RunContext[OrchestratorDeps],
            query: str,
            limit: int = 5,
            similarity_threshold: float = 0.35,
        ) -> str:
            """
            Semantically search documentation for relevant information.

            This tool searches through all documentation files using semantic similarity
            to find the most relevant chunks. Use this when you need to find specific
            information across all docs without knowing exactly which file contains it.

            Args:
                query: Natural language query describing what you're looking for
                       Examples:
                       - "How do I create a product with variants?"
                       - "What are the requirements for MAP sales?"
                       - "How to handle preorder products?"
                limit: Maximum number of results to return (default: 5)
                similarity_threshold: Minimum relevance score 0.0-1.0 (default: 0.35)

            Returns:
                Formatted search results with file paths, headings, and content

            Use this for:
            - Finding specific procedures or guidelines
            - Discovering relevant documentation
            - When you don't know which specific file to read
            - Cross-referencing information across multiple docs

            For simple file reading when you know the path, use read_docs() instead.
            """
            try:
                import openai

                # Generate embedding for query
                client = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
                logger.info(f"Generating embedding for query: {query[:100]}...")

                embedding_response = await client.embeddings.create(
                    model="text-embedding-3-large", input=query
                )
                query_embedding = embedding_response.data[0].embedding

                # Search documentation
                from database.operations import DocsOps
                from database.session import AsyncSessionLocal

                async with AsyncSessionLocal() as db:
                    results = await DocsOps.search_docs_semantic(
                        session=db,
                        embedding=query_embedding,
                        limit=limit,
                        similarity_threshold=similarity_threshold,
                    )

                if not results:
                    return f"No relevant documentation found for: {query}\n\nTry:\n- Lowering similarity_threshold (current: {similarity_threshold})\n- Using different search terms\n- Using read_docs() to browse specific files"

                # Format results
                output_lines = [
                    f"Found {len(results)} relevant documentation chunks for: {query}\n"
                ]

                for i, (chunk, similarity) in enumerate(results, 1):
                    output_lines.append(f"{'=' * 80}")
                    output_lines.append(f"Result {i} - Relevance: {similarity:.2%}")
                    output_lines.append(f"File: {chunk.file_path}")
                    if chunk.heading_context:
                        output_lines.append(f"Section: {chunk.heading_context}")
                    output_lines.append(f"Tokens: {chunk.chunk_tokens}")
                    output_lines.append(f"\n{chunk.chunk_text}\n")

                # Track bash-tools scripts mentioned in search results for enforcement
                import re as search_re

                full_output = "\n".join(output_lines)
                script_matches = search_re.findall(
                    r"bash-tools/([^\s\"']+\.py)", full_output
                )
                for script_name in script_matches:
                    ctx.deps.docs_checked_scripts.add(script_name)
                    logger.info(f"📚 Tracked docs lookup for: {script_name}")

                logger.info(
                    f"Returned {len(results)} search results for: {query[:50]}..."
                )
                return full_output

            except Exception as e:
                logger.error(f"Error searching docs: {e}")
                return f"Error searching documentation: {str(e)}\n\nFallback to read_docs() for direct file access."

        @self.agent.tool
        async def spawn_specialist(
            ctx: RunContext[OrchestratorDeps],
            role: str,
            docs: List[str],
            task_description: str,
        ) -> dict:
            """
            Spawn a documentation specialist for complex tasks requiring deep doc analysis.

            💡 Cache tip: Specialists are expensive (multi-doc synthesis). If you've spawned a similar
            specialist earlier in this conversation, check cache_lookup() first. Skip cache if the
            task is clearly different or if the user needs updated guidance.

            This creates a temporary specialist agent that:
            - Reads local documentation files
            - Can fetch specific URLs for current API docs or specs
            - Can search the web for current best practices or information
            - Synthesizes information from multiple sources
            - Returns structured command recommendations

            Args:
                role: The specialist role (e.g., "Trading Strategy Expert", "Technical Analysis Specialist")
                docs: List of documentation paths to read (supports glob patterns)
                      Examples:
                      - ["docs/trading/*.md"]
                      - ["cli-tools/INDEX.md"]
                task_description: Detailed description of what needs to be accomplished

            Returns:
                Dictionary with:
                - command: The bash command to execute
                - explanation: What the command does
                - expected_output: What to expect back
                - error_handling: How to handle errors

            Example:
                result = await spawn_specialist(
                    role="Technical Analysis Specialist",
                    docs=["cli-tools/INDEX.md"],
                    task_description="Analyze RELIANCE stock for swing trading entry"
                )
                # Returns: {command: "python cli-tools/nf-analyze RELIANCE ...", ...}

            The specialist has access to:
            - read_docs: Local documentation files
            - web_fetch: Fetch specific URLs (API docs, specs, etc.)
            - web_search: Search the web via Perplexity AI (for best practices, tutorials, current info)

            Use this for:
            - Complex multi-step analysis workflows
            - Tasks requiring synthesis of multiple docs + web research
            - When you need expert analysis combining local docs and online resources
            """
            # Check for interruption
            self._check_interrupted(ctx)

            try:
                from agents.doc_specialist import GenericDocSpecialist, SpecialistDeps

                logger.info(f"Spawning specialist: {role} for task: {task_description}")

                # Create specialist instance
                specialist = GenericDocSpecialist()

                # Create dependencies with web research capabilities
                deps = SpecialistDeps(
                    role=role,
                    docs_to_read=docs,
                    task_description=task_description,
                    available_agents=ctx.deps.available_agents,  # Pass web_search agent for research
                )

                # Run specialist with usage limits to prevent infinite loops
                # UsageLimits prevents runaway tool loops while allowing enough calls for complex tasks
                from pydantic_ai.usage import UsageLimits

                result = await specialist.agent.run(
                    task_description,
                    deps=deps,
                    usage_limits=UsageLimits(
                        tool_calls_limit=10,  # Max 10 tool calls - forces efficiency (1-2 reads + 1 search if needed)
                        request_limit=8,  # Max 8 LLM requests - prevents over-research loops
                    ),
                )

                # Extract output
                if hasattr(result, "output"):
                    output = result.output
                else:
                    output = result

                # Try to parse JSON if string
                if isinstance(output, str):
                    import json

                    try:
                        output = json.loads(output)
                    except json.JSONDecodeError:
                        logger.warning("Specialist output is not valid JSON")
                        output = {"raw_response": output}

                logger.info(f"Specialist completed: {role}")

                # Auto-cache specialist results
                await self._auto_cache_specialist_result(
                    role=role,
                    docs=docs,
                    task_description=task_description,
                    result=output,
                    thread_id=ctx.deps.state.thread_id,
                )

                return output

            except Exception as e:
                from pydantic_ai.exceptions import UsageLimitExceeded

                if isinstance(e, UsageLimitExceeded):
                    logger.warning(f"Specialist hit usage limits: {e}")
                    return {
                        "error": "Specialist exceeded usage limits - task may be too complex or underspecified",
                        "suggestion": "Try breaking down the task into smaller steps or provide more specific requirements",
                        "command": None,
                        "explanation": "The specialist made too many tool calls without reaching a conclusion. This usually means the task needs to be simplified or clarified.",
                    }
                else:
                    logger.error(f"Error spawning specialist: {e}")
                    return {
                        "error": f"Failed to spawn specialist: {str(e)}",
                        "command": None,
                        "explanation": "Specialist failed to provide guidance",
                    }

        @self.agent.tool
        async def read_file(ctx: RunContext[OrchestratorDeps], file_path: str) -> str:
            """
            Read the contents of a file.

            Use this to inspect existing files, especially when creating or modifying
            temporary tools in the bash-tools/ directory.

            Args:
                file_path: Absolute path to the file to read

            Returns:
                File contents as a string

            Example:
                read_file("backend/bash-tools/temp_search_reviews.py")
            """
            try:
                if not os.path.isabs(file_path):
                    return f"Error: file_path must be absolute. Got: {file_path}"

                if not os.path.exists(file_path):
                    return f"Error: File not found: {file_path}"

                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                logger.info(f"Read {len(content)} bytes from {file_path}")
                return content

            except Exception as e:
                logger.error(f"Error reading file {file_path}: {e}")
                return f"Error reading file: {str(e)}"

        @self.agent.tool
        async def write_file(
            ctx: RunContext[OrchestratorDeps], file_path: str, content: str
        ) -> str:
            """
            Write content to a file (overwrites if exists).

            Use this to create new temporary Python tools in bash-tools/ or modify
            existing files. Python scripts are automatically made executable.

            Args:
                file_path: Absolute path to the file to write
                content: Content to write to the file

            Returns:
                Confirmation message with file size

            Example:
                write_file(
                    "backend/cli-tools/temp_helper.py",
                    "#!/usr/bin/env python3\\nimport json\\n..."
                )
            """
            # HITL: Request approval before writing file
            if ctx.deps.hitl_enabled:
                from utils.hitl_manager import get_hitl_manager

                hitl_manager = get_hitl_manager()

                # Create explanation
                file_size_kb = len(content) / 1024
                explanation = f"Write {file_size_kb:.1f}KB to file: {file_path}"

                # Request approval
                approval_result = await hitl_manager.request_approval(
                    tool_name="write_file",
                    tool_args={"file_path": file_path, "content_length": len(content)},
                    explanation=explanation,
                    timeout_seconds=60,
                    thread_id=ctx.deps.state.thread_id,
                )

                if not approval_result["approved"]:
                    reason = approval_result.get("reason", "User rejected")
                    return f"❌ File write cancelled: {reason}"

            try:
                if not os.path.isabs(file_path):
                    return f"Error: file_path must be absolute. Got: {file_path}"

                # Ensure parent directory exists
                parent_dir = os.path.dirname(file_path)
                if not os.path.exists(parent_dir):
                    os.makedirs(parent_dir, exist_ok=True)

                # Write file
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)

                # Make executable if it's a Python script
                if file_path.endswith(".py"):
                    os.chmod(file_path, 0o755)
                    logger.info(f"Made {file_path} executable")

                logger.info(f"Wrote {len(content)} bytes to {file_path}")
                return f"✓ Wrote {len(content)} bytes to {file_path}"

            except Exception as e:
                logger.error(f"Error writing file {file_path}: {e}")
                return f"Error writing file: {str(e)}"

        @self.agent.tool
        async def edit_file(
            ctx: RunContext[OrchestratorDeps],
            file_path: str,
            old_string: str,
            new_string: str,
            replace_all: bool = False,
        ) -> str:
            """
            Replace exact string match in a file.

            Use this to modify existing files, especially when refining temporary
            tools or fixing bugs. Safer than rewriting the entire file.

            Args:
                file_path: Absolute path to the file to edit
                old_string: Exact string to find and replace
                new_string: Replacement string
                replace_all: If True, replace all occurrences; if False, replace first only (default: False)

            Returns:
                Confirmation message with replacement count

            Example:
                edit_file(
                    "backend/bash-tools/temp_search_reviews.py",
                    "# TODO: Implement search",
                    "results = client.search_reviews(query)"
                )
            """
            # HITL: Request approval before editing file
            if ctx.deps.hitl_enabled:
                from utils.hitl_manager import get_hitl_manager

                hitl_manager = get_hitl_manager()

                # Create explanation
                explanation = f"Edit file {file_path}: Replace '{old_string[:50]}...' with '{new_string[:50]}...'"

                # Request approval
                approval_result = await hitl_manager.request_approval(
                    tool_name="edit_file",
                    tool_args={
                        "file_path": file_path,
                        "old_string_length": len(old_string),
                        "new_string_length": len(new_string),
                        "replace_all": replace_all,
                    },
                    explanation=explanation,
                    timeout_seconds=60,
                    thread_id=ctx.deps.state.thread_id,
                )

                if not approval_result["approved"]:
                    reason = approval_result.get("reason", "User rejected")
                    return f"❌ File edit cancelled: {reason}"

            try:
                if not os.path.isabs(file_path):
                    return f"Error: file_path must be absolute. Got: {file_path}"

                if not os.path.exists(file_path):
                    return f"Error: File not found: {file_path}"

                # Read file
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                # Check if string exists
                if old_string not in content:
                    return f"❌ String not found in {file_path}\n\nLooking for:\n{old_string[:200]}"

                # Check for multiple matches if replace_all is False
                match_count = content.count(old_string)
                if not replace_all and match_count > 1:
                    return f"❌ Found {match_count} matches in {file_path}. Use replace_all=True to replace all, or provide more context to make old_string unique."

                # Replace
                if replace_all:
                    new_content = content.replace(old_string, new_string)
                else:
                    new_content = content.replace(old_string, new_string, 1)

                # Write back
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(new_content)

                replacements = match_count if replace_all else 1
                logger.info(f"Replaced {replacements} occurrence(s) in {file_path}")
                return f"✓ Replaced {replacements} occurrence(s) in {file_path}"

            except Exception as e:
                logger.error(f"Error editing file {file_path}: {e}")
                return f"Error editing file: {str(e)}"

        @self.agent.tool
        async def analyze_image(
            ctx: RunContext[OrchestratorDeps],
            image_path: str,
            query: str = "Describe this image in detail",
        ) -> str:
            """
            Analyze an image at a given file path and answer questions about it.

            This tool intelligently uses vision capabilities:
            - If your model supports vision (Claude Haiku 4.5, Sonnet 4.5, GPT-5): Analyzes directly
            - If your model lacks vision (DeepSeek, GLM, Grok): Delegates to vision specialist

            Use this to:
            - Analyze product images for descriptions, quality, compliance
            - Extract text from images (OCR)
            - Answer questions about screenshots or documents
            - Identify brands, models, specifications from photos
            - Analyze multiple images in sequence

            Args:
                image_path: Absolute or relative path to the image file
                query: Question or instruction about the image (default: "Describe this image in detail")

            Returns:
                Analysis result as text

            Examples:
                analyze_image("backend/uploads/product.jpg", "What product is this?")
                analyze_image("/tmp/screenshot.png", "Extract all visible text")
                analyze_image("image.jpg", "Is this a good quality product photo?")
            """
            import mimetypes
            from pathlib import Path

            from config.models import is_vision_capable
            from pydantic_ai.messages import BinaryContent

            try:
                # Validate image path
                image_path_obj = Path(image_path)
                if not image_path_obj.exists():
                    return f"Error: Image file not found at {image_path}"

                # Make path absolute
                if not image_path_obj.is_absolute():
                    image_path_obj = image_path_obj.resolve()

                logger.info(f"[Orchestrator] Analyzing image: {image_path_obj}")

                # Check if current model supports vision
                current_model = self.model_id
                has_vision = is_vision_capable(current_model)

                if has_vision:
                    # Use native vision capability
                    logger.info(f"[Orchestrator] Using native vision ({current_model})")

                    # Read image file
                    with open(image_path_obj, "rb") as f:
                        image_data = f.read()

                    # Detect media type
                    media_type, _ = mimetypes.guess_type(str(image_path_obj))
                    if not media_type or not media_type.startswith("image/"):
                        media_type = "image/jpeg"

                    # Create multimodal prompt
                    vision_prompt = [
                        BinaryContent(image_data, media_type=media_type),
                        query,
                    ]

                    # Run sub-analysis with streaming (required for Anthropic timeout constraints)
                    # Use the same model but with a focused vision task
                    async with self.agent.run_stream(
                        vision_prompt, deps=ctx.deps
                    ) as stream:
                        # Collect all text from the stream
                        full_response = ""
                        async for chunk in stream.stream_text():
                            full_response = (
                                chunk  # stream_text() returns cumulative text
                            )

                    return full_response

                else:
                    # Delegate to vision specialist
                    logger.info(
                        f"[Orchestrator] Delegating to vision agent (model {current_model} lacks vision)"
                    )

                    from agents.vision_agent import vision_agent

                    result = await vision_agent.analyze_image(
                        image_path=str(image_path_obj),
                        query=query,
                        user_email=ctx.deps.state.user_id,
                        conversation_id=ctx.deps.state.thread_id,
                    )

                    return result

            except Exception as e:
                logger.error(
                    f"[Orchestrator] Error analyzing image: {e}", exc_info=True
                )
                return f"Error analyzing image: {str(e)}"

        @self.agent.tool
        async def save_note(
            ctx: RunContext[OrchestratorDeps],
            title: str,
            content: str,
            tags: Optional[List[str]] = None,
            category: str = "personal",
        ) -> str:  # pyright: ignore[reportUnusedFunction]
            """
            Save a note to user's second brain / personal knowledge management system.

            Use this when user explicitly asks to:
            - "remember this"
            - "save this as a note"
            - "take a note"
            - "add this to my notes"

            All authenticated users can save notes. Notes are private and user-specific.

            Args:
                title: Short descriptive title for the note (max 500 chars)
                content: Full note content in markdown format
                tags: Optional list of tags for organization (e.g., ["project", "research"])
                category: Category for organization (default: "personal", also: "work", "ideas", "reference")

            Returns:
                Confirmation message with note ID

            Examples:
                save_note("Trading Strategy", "Swing trade setup:\n- Entry: support bounce\n- SL: 2% below entry\n- Target: 1:2 RR", tags=["trading", "strategy"])
                save_note("Market Notes", "Nifty showing weakness near 22000...", category="analysis")
            """
            # Check for interruption
            self._check_interrupted(ctx)

            try:
                from database.notes_operations import NotesOperations
                from database.session import AsyncSessionLocal

                # Get user email from context
                user_email = ctx.deps.state.user_id
                thread_id = ctx.deps.state.thread_id

                # Get database session
                async with AsyncSessionLocal() as db:
                    # Create note
                    note = await NotesOperations.create_note(
                        db=db,
                        user_id=user_email,
                        title=title,
                        content=content,
                        category=category,
                        tags=tags or [],
                        conversation_id=thread_id,
                    )

                    logger.info(
                        f"[Notes] Created note #{note['id']} for {user_email}: {title}"
                    )

                    return f"""✅ Note saved successfully!

**Title**: {title}
**Category**: {category}
**Tags**: {", ".join(tags or [])}
**Note ID**: #{note["id"]}

Your note has been added to your second brain and is now searchable."""

            except Exception as e:
                logger.error(f"[Notes] Error saving note: {e}", exc_info=True)
                return f"❌ Error saving note: {str(e)}"

        @self.agent.tool
        async def search_notes(
            ctx: RunContext[OrchestratorDeps],
            query: str,
            category: Optional[str] = None,
            limit: int = 5,
        ) -> str:  # pyright: ignore[reportUnusedFunction]
            """
            Search user's personal notes using AI-powered semantic search.

            🔒 RESTRICTED ACCESS: Super Admin only (requires admin.manage_roles permission)

            Use this when:
            - User explicitly asks to search their notes
            - User asks "what did I write about X?"
            - User requests information from their second brain
            - Docs and memories don't have relevant context

            This is a FALLBACK tool - check docs and memories first before searching notes.

            Args:
                query: Search query (supports natural language)
                category: Optional category filter ("personal", "work", "ideas", "reference")
                limit: Max number of results to return (default: 5)

            Returns:
                Formatted list of matching notes with titles, content snippets, and metadata

            Examples:
                search_notes("swing trading setups")
                search_notes("RELIANCE analysis", category="analysis")
                search_notes("project ideas", limit=10)
            """
            # Check for interruption
            self._check_interrupted(ctx)

            # SECURITY: Only allow admins to search notes via chat
            user_email = ctx.deps.state.user_id

            try:
                from database.models import Role
                from database.models import User as DBUser
                from database.notes_operations import NotesOperations
                from database.session import AsyncSessionLocal
                from sqlalchemy import select
                from sqlalchemy.orm import selectinload

                # Single async session for both permission check AND notes search
                async with AsyncSessionLocal() as db:
                    # First, check permissions
                    result = await db.execute(
                        select(DBUser)
                        .where(DBUser.email == user_email)
                        .options(
                            selectinload(DBUser.roles).selectinload(Role.permissions)
                        )
                    )
                    db_user = result.scalar_one_or_none()

                    if not db_user:
                        return "❌ User not found"

                    # Check if user has admin.manage_roles permission (Super Admin only)
                    user_permissions = [
                        p.name for role in db_user.roles for p in role.permissions
                    ]
                    is_super_admin = "admin.manage_roles" in user_permissions

                    if not is_super_admin:
                        return """❌ Access Denied

The `search_notes` tool is restricted to Super Admin only.

You can:
- Save notes using `save_note()` tool
- Browse and search your notes via the UI at /notes route

Your notes are private and can only be accessed by you via the UI."""

                    # Permission granted - proceed with search
                    # Semantic search
                    results = await NotesOperations.search_notes_semantic(
                        db=db,
                        user_id=user_email,
                        query=query,
                        category=category,
                        limit=limit,
                    )

                    if not results:
                        return f"""🔍 No notes found for query: "{query}"

Try:
- Broadening your search terms
- Checking category filter (currently: {category or "all categories"})
- Using different keywords"""

                    # Format results
                    output_lines = [
                        f"🔍 Found {len(results)} note(s) matching '{query}':\n"
                    ]

                    for i, note in enumerate(results, 1):
                        # Get content snippet (first 200 chars)
                        content_snippet = note["content"][:200]
                        if len(note["content"]) > 200:
                            content_snippet += "..."

                        similarity_pct = int(note["similarity"] * 100)

                        output_lines.append(f"""
{i}. **{note["title"]}** (Note #{note["id"]})
   📊 Relevance: {similarity_pct}%
   📁 Category: {note["category"]}
   🏷️ Tags: {", ".join(note.get("tags", []))}
   📅 Created: {note["created_at"][:10]}

   {content_snippet}

   ---""")

                    output_lines.append(
                        f"\n💡 To view full note: Ask user to open /notes route and search for note ID"
                    )

                    logger.info(
                        f"[Notes] Search for '{query}' returned {len(results)} results"
                    )

                    return "\n".join(output_lines)

            except Exception as e:
                logger.error(f"[Notes] Error searching notes: {e}", exc_info=True)
                return f"❌ Error searching notes: {str(e)}"

        @self.agent.tool
        async def edit_note(
            ctx: RunContext[OrchestratorDeps],
            note_id: int,
            title: Optional[str] = None,
            content: Optional[str] = None,
            category: Optional[str] = None,
            tags: Optional[List[str]] = None,
            find_text: Optional[str] = None,
            replace_text: Optional[str] = None,
        ) -> str:
            """
            Edit an existing note. Only specified fields are updated.

            Use this when user asks to:
            - "update my note about X"
            - "edit note #123"
            - "change the title/content/category/tags of my note"
            - "replace 'foo' with 'bar' in note #123"

            Args:
                note_id: ID of note to edit (from search_notes or get_note_by_id)
                title: New title (optional)
                content: New content (optional, supports markdown and [[wikilinks]])
                category: New category (optional)
                tags: New tags list (replaces existing) (optional, supports nested tags like 'trading/analysis')
                find_text: Text to find and replace (optional, use with replace_text) - simpler than re-typing whole content
                replace_text: Text to replace find_text with (optional, use with find_text)

            Returns:
                Confirmation message with updated note details

            Examples:
                edit_note(123, title="Updated Title")
                edit_note(456, content="New content with [[Other Note]] link")
                edit_note(789, category="work", tags=["project", "urgent"])
                edit_note(101, find_text="old text", replace_text="new text")
            """
            # Check for interruption
            self._check_interrupted(ctx)

            try:
                from database.notes_operations import NotesOperations
                from database.session import AsyncSessionLocal

                user_email = ctx.deps.state.user_id

                async with AsyncSessionLocal() as db:
                    # Update note
                    updated_note = await NotesOperations.update_note(
                        db=db,
                        note_id=note_id,
                        user_id=user_email,
                        title=title,
                        content=content,
                        category=category,
                        tags=tags,
                        find_text=find_text,
                        replace_text=replace_text,
                    )

                    if not updated_note:
                        return f"❌ Note #{note_id} not found or you don't have permission to edit it."

                    logger.info(f"[Notes] Updated note #{note_id} for {user_email}")

                    # Build update summary
                    updates = []
                    if title is not None:
                        updates.append(f"Title → {title}")
                    if content is not None:
                        updates.append(f"Content updated ({len(content)} chars)")
                    if category is not None:
                        updates.append(f"Category → {category}")
                    if tags is not None:
                        updates.append(f"Tags → {', '.join(tags)}")
                    if find_text is not None and replace_text is not None:
                        updates.append(f"Replaced text '{find_text}'")

                    if not updates and find_text is not None:
                        # If find_text was provided but no updates recorded, it implies replacement failed (text not found)
                        # We should warn the user, although update_note returns the original note if no updates
                        # Note: update_note logic was: if replacement fails, content is None, so field not updated.
                        return f"❌ Text replacement failed: '{find_text}' not found in note #{note_id}."

                    return f"""✅ Note updated successfully!

**Note ID**: #{note_id}
**Updates**: {", ".join(updates)}

Your note has been updated and re-indexed for search."""

            except Exception as e:
                logger.error(f"[Notes] Error editing note: {e}", exc_info=True)
                return f"❌ Error editing note: {str(e)}"

        @self.agent.tool
        async def get_note_by_id(
            ctx: RunContext[OrchestratorDeps], note_id: int
        ) -> str:
            """
            Retrieve a specific note by its ID.

            Use this to:
            - Get full details of a note referenced by ID
            - View complete note content before editing
            - Check note metadata (created date, tags, etc.)

            Args:
                note_id: Note ID (from search results or user reference)

            Returns:
                Full note details including title, content, metadata

            Examples:
                get_note_by_id(123)
            """
            # Check for interruption
            self._check_interrupted(ctx)

            try:
                from database.notes_operations import NotesOperations
                from database.session import AsyncSessionLocal

                user_email = ctx.deps.state.user_id

                async with AsyncSessionLocal() as db:
                    note = await NotesOperations.get_note(db, note_id, user_email)

                    if not note:
                        return f"❌ Note #{note_id} not found or you don't have permission to access it."

                    logger.info(f"[Notes] Retrieved note #{note_id} for {user_email}")

                    return f"""📝 **{note["title"]}** (Note #{note["id"]})

**Category**: {note["category"]}
**Tags**: {", ".join(note.get("tags", []))}
**Created**: {note["created_at"][:10]}
**Updated**: {note["updated_at"][:10]}
**Starred**: {"⭐" if note["is_starred"] else "☆"}

**Content**:
{note["content"]}

---
💡 Use edit_note() to update this note or get_backlinks() to see what links to it."""

            except Exception as e:
                logger.error(f"[Notes] Error getting note: {e}", exc_info=True)
                return f"❌ Error getting note: {str(e)}"

        @self.agent.tool
        async def get_similar_notes(
            ctx: RunContext[OrchestratorDeps],
            note_id: int,
            limit: int = 5,
            threshold: float = 0.7,
        ) -> str:
            """
            Find notes semantically similar to the given note using AI embeddings.

            Use this to:
            - Discover related notes the user has written
            - Find connections between ideas
            - Surface relevant context from past notes
            - Identify duplicate or overlapping content

            Args:
                note_id: Source note ID to find similar notes for
                limit: Maximum number of similar notes to return (default: 5)
                threshold: Minimum similarity score 0.0-1.0 (default: 0.7, higher = more similar)

            Returns:
                List of similar notes with similarity scores and snippets

            Examples:
                get_similar_notes(123)
                get_similar_notes(456, limit=10, threshold=0.5)
            """
            # Check for interruption
            self._check_interrupted(ctx)

            try:
                from database.notes_operations import NotesOperations
                from database.session import AsyncSessionLocal

                user_email = ctx.deps.state.user_id

                async with AsyncSessionLocal() as db:
                    # First get the source note to show context
                    source_note = await NotesOperations.get_note(
                        db, note_id, user_email
                    )
                    if not source_note:
                        return f"❌ Source note #{note_id} not found."

                    # Get similar notes
                    similar_notes = await NotesOperations.get_similar_notes(
                        db=db, note_id=note_id, user_id=user_email, limit=limit
                    )

                    # Filter by threshold
                    similar_notes = [
                        n for n in similar_notes if n["similarity"] >= threshold
                    ]

                    if not similar_notes:
                        return f"""🔍 No similar notes found for: "{source_note["title"]}"

Try lowering the threshold (current: {threshold}) or creating more notes on related topics."""

                    logger.info(
                        f"[Notes] Found {len(similar_notes)} similar notes for #{note_id}"
                    )

                    output_lines = [
                        f"""🔗 Found {len(similar_notes)} note(s) similar to: **{source_note["title"]}** (#{note_id})
"""
                    ]

                    for i, note in enumerate(similar_notes, 1):
                        similarity_pct = int(note["similarity"] * 100)
                        content_snippet = note["content"][:150]
                        if len(note["content"]) > 150:
                            content_snippet += "..."

                        output_lines.append(f"""
{i}. **{note["title"]}** (Note #{note["id"]})
   📊 Similarity: {similarity_pct}%
   📁 Category: {note["category"]}
   🏷️ Tags: {", ".join(note.get("tags", []))}

   {content_snippet}

   ---""")

                    output_lines.append(
                        f"\n💡 Use get_note_by_id() to view full content or edit_note() to update."
                    )

                    return "\n".join(output_lines)

            except Exception as e:
                logger.error(f"[Notes] Error getting similar notes: {e}", exc_info=True)
                return f"❌ Error getting similar notes: {str(e)}"

        @self.agent.tool
        async def get_backlinks(ctx: RunContext[OrchestratorDeps], note_id: int) -> str:
            """
            Get all notes that link to this note via [[Note Title]] wikilinks.

            This implements bidirectional linking (like Obsidian/Roam Research) by finding
            all notes that reference this note using the [[wikilink]] syntax.

            Use this to:
            - See which notes reference this one
            - Discover connections in your knowledge graph
            - Navigate bidirectional links

            Args:
                note_id: Target note ID to find backlinks for

            Returns:
                List of notes that contain [[wikilinks]] to this note

            Examples:
                get_backlinks(123)
            """
            # Check for interruption
            self._check_interrupted(ctx)

            try:
                from database.notes_operations import NotesOperations
                from database.session import AsyncSessionLocal

                user_email = ctx.deps.state.user_id

                async with AsyncSessionLocal() as db:
                    # First get the target note
                    target_note = await NotesOperations.get_note(
                        db, note_id, user_email
                    )
                    if not target_note:
                        return f"❌ Note #{note_id} not found."

                    # Get backlinks
                    backlinks = await NotesOperations.get_backlinks(
                        db, note_id, user_email
                    )

                    if not backlinks:
                        return f"""🔗 No backlinks found for: **{target_note["title"]}** (#{note_id})

This note is not referenced by any other notes yet. To create a backlink, add [[{target_note["title"]}]] to another note."""

                    logger.info(
                        f"[Notes] Found {len(backlinks)} backlinks for #{note_id}"
                    )

                    output_lines = [
                        f"""🔗 {len(backlinks)} note(s) link to: **{target_note["title"]}** (#{note_id})
"""
                    ]

                    for i, note in enumerate(backlinks, 1):
                        output_lines.append(f"""
{i}. **{note["title"]}** (Note #{note["id"]})
   📁 Category: {note["category"]}
   📅 Created: {note["created_at"][:10]}

   Context: ...{note["snippet"]}...

   ---""")

                    output_lines.append(
                        f"\n💡 These notes reference [[{target_note['title']}]] in their content."
                    )

                    return "\n".join(output_lines)

            except Exception as e:
                logger.error(f"[Notes] Error getting backlinks: {e}", exc_info=True)
                return f"❌ Error getting backlinks: {str(e)}"

        @self.agent.tool
        async def delete_note(ctx: RunContext[OrchestratorDeps], note_id: int) -> str:
            """
            Delete a note permanently.

            ⚠️ WARNING: This action is irreversible. The note will be permanently deleted.

            Use this when user explicitly requests deletion:
            - "Delete note #123"
            - "Remove that note I just created"
            - "Delete all my draft notes"

            IMPORTANT: Always confirm the note details with the user before deleting.
            Use get_note_by_id() first to show them what will be deleted.

            Args:
                note_id: ID of the note to delete

            Returns:
                Confirmation message

            Examples:
                # First show the note
                note = get_note_by_id(123)
                # Then confirm and delete
                delete_note(123)
            """
            # Check for interruption
            self._check_interrupted(ctx)

            try:
                from database.notes_operations import NotesOperations
                from database.session import AsyncSessionLocal

                user_email = ctx.deps.state.user_id

                async with AsyncSessionLocal() as db:
                    # First get the note to confirm it exists and show details
                    note = await NotesOperations.get_note(db, note_id, user_email)

                    if not note:
                        return f"❌ Note #{note_id} not found or you don't have permission to delete it."

                    # Delete the note
                    success = await NotesOperations.delete_note(db, note_id, user_email)

                    if success:
                        logger.info(
                            f"[Notes] Deleted note #{note_id} for {user_email}: {note['title']}"
                        )

                        return f"""✅ Note deleted successfully!

**Deleted Note**:
- Title: {note["title"]}
- Category: {note["category"]}
- Note ID: #{note_id}

The note has been permanently removed from your second brain."""
                    else:
                        return f"❌ Failed to delete note #{note_id}. Please try again."

            except Exception as e:
                logger.error(f"[Notes] Error deleting note: {e}", exc_info=True)
                return f"❌ Error deleting note: {str(e)}"

        @self.agent.tool
        async def render_ui(
            ctx: RunContext[OrchestratorDeps],
            components: List[Dict[str, Any]],
            title: Optional[str] = None,
        ) -> str:  # pyright: ignore[reportUnusedFunction]
            """
            Render a dynamic UI by COMPOSING from these primitives only.

            CRITICAL: You must compose UIs from the primitives listed below.
            DO NOT invent types like "product_card", "order_summary", etc.
            Instead, BUILD a product card using: Card > Row > [Image, Column > [Text, Badge, Button]]

            Args:
                components: Nested tree using ONLY these primitive types.
                title: Optional title for the UI surface.

            ALLOWED PRIMITIVES (use these exact type names):

                Layout containers:
                - Card: Container with border. Props: variant (default|elevated|bordered), padding (1-6), title, body, actions
                - Row: Horizontal flex. Props: gap (1-6), align (start|center|end), justify (start|center|end|between)
                - Column: Vertical flex. Props: gap (1-6), align (start|center|end)
                - Divider: Visual separator line.

                Content display:
                - Text: Text/headings. Props: content (the text), variant (h1|h2|h3|body|caption)
                - Image: Image. Props: src (URL), alt, width, height
                - Badge: Status pill. Props: content, color (green|yellow|red|blue|gray)

                Interactive:
                - Button: Clickable. Props: label, variant (primary|secondary|outline), action, payload

            REQUIRED STRUCTURE:
                {"type": "Card", "children": [...]}  # Use children for nesting
                OR simplified: {"type": "Card", "title": "...", "body": "...", "actions": [...]}

            EXAMPLE - Stock card (compose from primitives):
                [{"type": "Card", "children": [
                    {"type": "Column", "gap": 2, "children": [
                        {"type": "Text", "content": "RELIANCE", "variant": "h3"},
                        {"type": "Row", "gap": 2, "children": [
                            {"type": "Badge", "content": "NSE", "color": "blue"},
                            {"type": "Badge", "content": "Buy Signal", "color": "green"}
                        ]},
                        {"type": "Text", "content": "₹2,450.75", "variant": "h2"},
                        {"type": "Text", "content": "RSI: 42.3 | MACD: Bullish crossover", "variant": "body"},
                        {"type": "Button", "label": "View Analysis", "action": "open_url", "payload": {"url": "https://..."}}
                    ]}
                ]}]

            Returns: Confirmation message
            """
            import uuid

            # Generate unique surface ID
            surface_id = f"surface_{uuid.uuid4().hex[:8]}"

            # Assign IDs to components that don't have them
            def assign_ids(component: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
                if "id" not in component:
                    component["id"] = f"{prefix}{component.get('type', 'unknown')}_{uuid.uuid4().hex[:6]}"
                if "children" in component:
                    component["children"] = [
                        assign_ids(child, f"{component['id']}_")
                        for child in component["children"]
                    ]
                return component

            processed_components = [assign_ids(c) for c in components]

            # Store in deps for emission by ag_ui_wrapper
            ctx.deps.pending_a2ui_surfaces.append({
                "surfaceId": surface_id,
                "components": processed_components,
                "title": title,
            })

            logger.info(f"[A2UI] Queued surface {surface_id} with {len(components)} top-level components")

            return f"✓ Rendered UI surface '{title or surface_id}' with {len(components)} component(s). The interactive UI is now displayed in the chat."

    def register_agent(self, name: str, agent: Any):
        """
        Register a specialized agent with the orchestrator.

        Args:
            name: Name of the agent (e.g., "products", "orders")
            agent: The agent instance
        """
        self.specialized_agents[name] = agent
        logger.info(f"Registered specialized agent: {name}")

    def get_agent_metadata(self) -> list[dict]:
        """
        Get metadata for all registered agents.

        Returns:
            List of agent metadata dicts with name, description, and capabilities
        """
        agents_metadata = []

        for name, agent in self.specialized_agents.items():
            # Extract metadata from agent
            metadata = {
                "name": name,
                "description": getattr(
                    agent, "description", f"{name.replace('_', ' ').title()} agent"
                ),
                "capabilities": [],
            }

            # Add agent-specific capabilities based on known agents
            if name == "web_search":
                metadata["capabilities"] = ["web_search", "current_events", "research"]
            elif name == "vision":
                metadata["capabilities"] = ["image_analysis", "visual_understanding"]

            agents_metadata.append(metadata)

        return agents_metadata

    async def orchestrate(self, user_request: str, state: ConversationState) -> str:
        """
        Main orchestration logic - coordinates multi-agent workflows.

        Args:
            user_request: The user's request
            state: Current conversation state

        Returns:
            Final synthesized response
        """
        import time

        # Create Logfire span for entire orchestration
        if logfire:
            span = logfire.span(
                "orchestrator.run",
                user_id=state.user_id,
                thread_id=state.thread_id,
                request_preview=user_request[:100],
                request_length=len(user_request),
            )
        else:
            from contextlib import nullcontext

            span = nullcontext()

        try:
            async with span:
                start_time = time.time()

                # Reset state for new request
                state.reset_for_new_request(user_request)

                # Add user message to state
                state.add_message(MessageRole.USER, user_request)

                # Create dependencies
                deps = OrchestratorDeps(
                    state=state, available_agents=self.specialized_agents
                )

                # Simply process the request with the LLM
                logger.info(f"Processing request: {user_request}")
                if logfire:
                    logfire.info(
                        "orchestrator.request_received", request=user_request[:200]
                    )

                # Run the agent directly with the user request
                llm_start = time.time()

                # Use streaming to avoid 10-minute timeout from Anthropic API
                if logfire:
                    with logfire.span(
                        "orchestrator.llm_call", model=self.config.model_name
                    ):
                        async with self.agent.run_stream(
                            user_request, deps=deps
                        ) as stream:
                            result = await stream.get_output()
                else:
                    async with self.agent.run_stream(user_request, deps=deps) as stream:
                        result = await stream.get_output()

                llm_time = time.time() - llm_start
                logger.info(f"LLM response time: {llm_time:.2f}s")

                # Extract the response
                if hasattr(result, "output"):
                    response = result.output
                else:
                    response = str(result)

                # Add assistant message to state
                state.add_message(
                    MessageRole.ASSISTANT, response, agent_name="orchestrator"
                )

                # Log completion metrics
                total_time = time.time() - start_time
                if logfire:
                    logfire.info(
                        "orchestrator.completed",
                        total_time_ms=int(total_time * 1000),
                        llm_time_ms=int(llm_time * 1000),
                        response_length=len(response),
                        agents_called=len(state.agents_called),
                        tool_calls=len(
                            [m for m in state.messages if hasattr(m, "agent_name")]
                        ),
                    )

                # Return the actual response from the LLM
                return response

        except Exception as e:
            logger.error(f"Orchestration error: {e}")
            if logfire:
                logfire.error(
                    "orchestrator.error", error=str(e), error_type=type(e).__name__
                )
            state.last_error = str(e)
            raise

    async def stream_orchestrate(self, user_request: str, state: ConversationState):
        """
        Stream orchestration responses for real-time feedback.

        Args:
            user_request: The user's request
            state: Current conversation state

        Yields:
            Response chunks
        """
        try:
            state.reset_for_new_request(user_request)
            state.add_message(MessageRole.USER, user_request)

            deps = OrchestratorDeps(
                state=state, available_agents=self.specialized_agents
            )

            # Stream the response using Pydantic AI's run_stream
            async with self.agent.run_stream(
                "Process this request and provide a response", deps=deps
            ) as stream:
                async for text in stream.stream_text():
                    yield text

        except Exception as e:
            logger.error(f"Stream orchestration error: {e}")
            yield f"\nError: {str(e)}"
