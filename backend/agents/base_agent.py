"""
Intelligent Base Agent for Pydantic AI - Enforces LLM-based decision making

This base class ensures all agents follow the PROJECT_BRIEF.md principles:
- LLM-based routing (no keyword matching)
- Real data only (no mock responses)
- Proper error handling
- Type safety with Pydantic models
"""

from typing import Any, Dict, List, Optional, Type, TypeVar, Generic
from abc import ABC, abstractmethod
import dataclasses
import logging
import os
from pydantic import BaseModel
from pydantic_ai import Agent, Tool, ModelSettings
from pydantic_ai.models.openai import OpenAIChatModel, OpenAIResponsesModel, OpenAIResponsesModelSettings
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic_ai.providers.openrouter import OpenRouterProvider  # Proper OpenRouter support with reasoning field
from pydantic_ai.profiles.openai import OpenAIModelProfile

logger = logging.getLogger(__name__)

# Type variables for dependency injection
DepsT = TypeVar('DepsT')
OutputT = TypeVar('OutputT')


class AgentConfig(BaseModel):
    """Configuration for an agent"""
    name: str
    description: str
    model_name: str = "gpt-5"  # Default to GPT-5
    use_openrouter: bool = True  # Use OpenRouter by default
    max_retries: int = 5  # Allow multiple retries for API errors and self-correction
    temperature: Optional[float] = None  # Optional temperature (defaults per model type)
    thinking_effort: Optional[str] = None  # Unified thinking: 'high', 'medium', 'low', or None


class IntelligentBaseAgent(ABC, Generic[DepsT, OutputT]):
    """
    Base class that enforces intelligent LLM-based decision making using Pydantic AI.
    All agents MUST inherit from this class to ensure compliance with PROJECT_BRIEF.md.

    Key Principles:
    ✓ Using LLM for routing (NOT keyword matching)
    ✓ Using real data (NO mock responses)
    ✓ Using approved models (GPT-5/4.1, NOT GPT-4)
    ✓ Type safety with Pydantic models
    """

    def __init__(
        self,
        config: AgentConfig,
        deps_type: Optional[Type[DepsT]] = None,
        output_type: Type[OutputT] = str,
        toolsets: list = None,
        builtin_tools: list = None
    ):
        """
        Initialize the intelligent agent with Pydantic AI.

        Args:
            config: Agent configuration
            deps_type: Type for dependency injection
            output_type: Expected output type
            toolsets: Optional list of MCP servers or other toolsets
        """
        self.config = config
        self.name = config.name
        self.description = config.description

        # Set up the model with OpenRouter or direct OpenAI
        # Returns (model, model_settings) tuple — settings needed for Agent constructor
        self.model, self.model_settings = self._setup_model(config)

        # Create the Pydantic AI agent
        # Use instructions instead of system_prompt per Pydantic AI docs
        # instructions are re-evaluated each time, system_prompt may be stripped with message_history
        #
        # NOTE: Subclasses can override:
        # - _get_dynamic_instructions() to add dynamic instructions via @agent.instructions decorator
        # - _get_history_processors() to add message history processing (e.g., context window management)
        agent_kwargs = {
            'model': self.model,
            'name': self.name,
            'deps_type': deps_type,
            'output_type': output_type,
            'instructions': self._get_system_prompt(),  # Static base instructions
            'retries': config.max_retries,
            'history_processors': self._get_history_processors(),  # Context window management
            'model_settings': self.model_settings,  # Reasoning settings etc. must be on Agent
        }

        # Add toolsets if provided
        if toolsets:
            agent_kwargs['toolsets'] = toolsets

        # Add builtin tools if provided (e.g., CodeExecutionTool)
        if builtin_tools:
            agent_kwargs['builtin_tools'] = builtin_tools

        self.agent = Agent(**agent_kwargs)

        # Register dynamic instructions (for memory injection, etc.)
        self._register_dynamic_instructions()

        # Register tools with the agent
        self._register_tools()

        logger.info(f"Initialized {self.name} with LLM-based intelligence using {config.model_name} (retries={config.max_retries})")

    def _setup_model(self, config: AgentConfig):
        """Set up the LLM model with appropriate provider.

        Uses pydantic-ai's unified 'thinking' model setting (v1.71+) to handle
        reasoning/thinking across all providers automatically. The effort level
        is configured per-model in config/models.py via thinking_effort.
        """
        logger.info(f"[GATEWAY-DEBUG] Setting up model: '{config.model_name}', use_openrouter={config.use_openrouter}")

        # Gateway models — Pydantic AI handles routing automatically
        if config.model_name.startswith('gateway/'):
            api_key = os.environ.get('PYDANTIC_AI_GATEWAY_API_KEY')
            if not api_key:
                from dotenv import load_dotenv
                load_dotenv()
                api_key = os.getenv('PYDANTIC_AI_GATEWAY_API_KEY')
            if not api_key:
                logger.error("PYDANTIC_AI_GATEWAY_API_KEY not found - gateway models require this!")
                raise ValueError("PYDANTIC_AI_GATEWAY_API_KEY is required for gateway models")
            logger.info(f"Using Pydantic AI Gateway with key: {api_key[:12]}...")
            return config.model_name, None

        # === Provider Setup ===
        is_anthropic = 'claude' in config.model_name.lower()
        use_responses_api = False
        model_name = config.model_name

        if is_anthropic:
            api_key = os.environ.get('ANTHROPIC_API_KEY')
            if not api_key:
                from dotenv import load_dotenv
                load_dotenv()
                api_key = os.getenv('ANTHROPIC_API_KEY')
            if not api_key:
                logger.error("ANTHROPIC_API_KEY not found in environment or .env file!")
                raise ValueError("ANTHROPIC_API_KEY is required for Anthropic models")
            logger.info(f"Using direct Anthropic API with key: {api_key[:8]}...")
            logger.debug(f"API key length: {len(api_key)}, ends with: '{api_key[-5:]}'")
            provider = AnthropicProvider(
                api_key=api_key.strip(),
                base_url="https://api.anthropic.com"
            )

        elif config.use_openrouter:
            api_key = os.environ.get('OPENROUTER_API_KEY')
            if not api_key:
                from dotenv import load_dotenv
                load_dotenv()
                api_key = os.getenv('OPENROUTER_API_KEY')
            if not api_key:
                logger.error("OPENROUTER_API_KEY not found in environment or .env file!")
                raise ValueError("OPENROUTER_API_KEY is required for OpenRouter models")
            logger.info(f"Using OpenRouterProvider with key: {api_key[:8]}...")
            # Pass a custom AsyncOpenAI client with higher max_retries (default is 2).
            # Free-tier OpenRouter models have aggressive rate limits — the extra retries
            # with exponential backoff (~0.5s, 1s, 2s, 4s, 8s) give ~15s for limits to clear.
            from openai import AsyncOpenAI as AsyncOpenAIClient
            openai_client = AsyncOpenAIClient(
                base_url='https://openrouter.ai/api/v1',
                api_key=api_key,
                max_retries=5,
            )
            provider = OpenRouterProvider(openai_client=openai_client)
            model_name = f"openai/{config.model_name}" if "/" not in config.model_name else config.model_name
            logger.info(f"Using model: {model_name} via OpenRouterProvider")
            use_responses_api = model_name.startswith('openai/')

        else:
            api_key = os.environ.get('OPENAI_API_KEY')
            if not api_key:
                from dotenv import load_dotenv
                load_dotenv()
                api_key = os.getenv('OPENAI_API_KEY')
            if not api_key:
                logger.error("OPENAI_API_KEY not found in environment or .env file!")
                raise ValueError("OPENAI_API_KEY is required for OpenAI models")
            provider = OpenAIProvider(api_key=api_key)
            model_name = config.model_name
            use_responses_api = True

        # === Model Settings ===
        model_settings_kwargs = {}

        # Max output tokens (provider-specific limits)
        model_settings_kwargs['max_tokens'] = 64000 if is_anthropic else 16000

        # Unified thinking — pydantic-ai translates to each provider's native format:
        # Anthropic → anthropic_thinking + temperature=1.0
        # OpenAI → openai_reasoning_effort
        # OpenRouter → provider-specific reasoning config
        # Models without thinking_effort just get a normal temperature setting
        if config.thinking_effort:
            model_settings_kwargs['thinking'] = config.thinking_effort
            logger.info(f"Thinking enabled for {config.model_name} with effort: {config.thinking_effort}")
        else:
            temperature = config.temperature if config.temperature is not None else 0.7
            model_settings_kwargs['temperature'] = temperature

        # OpenAI Responses API workarounds when thinking is active
        if use_responses_api and config.thinking_effort:
            model_settings_kwargs['openai_reasoning_summary'] = 'detailed'
            # Disable reasoning IDs — sliding window history processor can truncate
            # messages, causing "Item 'rs_123' provided without required following item" errors
            model_settings_kwargs['openai_send_reasoning_ids'] = False

        # Create model settings
        if use_responses_api:
            model_settings = OpenAIResponsesModelSettings(**model_settings_kwargs)
        else:
            model_settings = ModelSettings(**model_settings_kwargs)

        # === Model Creation ===
        if is_anthropic:
            return AnthropicModel(
                config.model_name, provider=provider, settings=model_settings
            ), model_settings

        # For OpenRouter models, override the profile if needed
        # pydantic-ai's OpenRouter profiles lag behind actual model capabilities —
        # most models have supports_thinking=False even when they support reasoning.
        profile_override = None
        if config.use_openrouter:
            default_profile = provider.model_profile(model_name)
            overrides = {}

            # Enable thinking in profile if we know the model supports it
            if config.thinking_effort and not default_profile.supports_thinking:
                overrides['supports_thinking'] = True
                logger.info(f"Profile override: supports_thinking=True for {model_name}")

            # DeepSeek needs strict tool definitions disabled
            if 'deepseek' in model_name.lower():
                overrides['openai_supports_strict_tool_definition'] = False

            if overrides:
                profile_override = dataclasses.replace(default_profile, **overrides)

        # OpenAI models use Responses API
        if use_responses_api:
            logger.info(f"Using OpenAIResponsesModel (Responses API) for {model_name}")
            return OpenAIResponsesModel(
                model_name, provider=provider, settings=model_settings,
                **({"profile": profile_override} if profile_override else {})
            ), model_settings

        # All other models (OpenRouter: Grok, GLM, DeepSeek, Gemini, etc.)
        return OpenAIChatModel(
            model_name, provider=provider, settings=model_settings,
            **({"profile": profile_override} if profile_override else {})
        ), model_settings

    @abstractmethod
    def _get_system_prompt(self) -> str:
        """
        Get the system prompt for this agent.
        Must be implemented by subclass.
        """
        pass

    def _register_dynamic_instructions(self) -> None:
        """
        Register dynamic instructions with the agent.
        Can be overridden by subclasses to add runtime-dependent instructions.

        Example:
        @self.agent.instructions
        def add_user_context(ctx: RunContext[MyDeps]) -> str:
            return f"User ID: {ctx.deps.user_id}"
        """
        # Default: no dynamic instructions
        pass

    def _get_history_processors(self) -> list:
        """
        Get history processors for context window management.
        Can be overridden by subclasses to add message history processing.

        History processors are called before each model request to filter/modify
        the message history (e.g., sliding window, token limits, privacy filtering).

        Returns:
            List of callables that take list[ModelMessage] and return list[ModelMessage]

        Example:
            def sliding_window(messages):
                return messages[-10:]  # Keep last 10 messages

            def _get_history_processors(self):
                return [sliding_window]
        """
        # Default: no history processing
        return []

    @abstractmethod
    def _register_tools(self) -> None:
        """
        Register tools with the agent.
        Must be implemented by subclass to add specific tools.

        Example:
        @self.agent.tool
        async def search_products(query: str) -> str:
            return await self._search_products_impl(query)
        """
        pass

    async def run(
        self,
        prompt: str,
        deps: Optional[DepsT] = None,
        **kwargs
    ) -> Any:
        """
        Run the agent with LLM-based intelligence.

        ENFORCES: No keyword matching, only LLM-based decisions

        Args:
            prompt: User prompt to process
            deps: Optional dependencies to inject
            **kwargs: Additional arguments for the agent

        Returns:
            Agent response
        """
        try:
            logger.info(f"{self.name} processing with LLM: {prompt[:100]}...")

            # Run the Pydantic AI agent
            result = await self.agent.run(prompt, deps=deps, **kwargs)

            return result

        except Exception as e:
            logger.error(f"Error in {self.name}: {e}")
            # ENFORCE: Real errors, not mock responses
            raise RuntimeError(f"Agent {self.name} encountered an error: {str(e)}")

    async def run_sync(
        self,
        prompt: str,
        deps: Optional[DepsT] = None,
        **kwargs
    ) -> Any:
        """Synchronous version of run for compatibility"""
        return self.agent.run_sync(prompt, deps=deps, **kwargs)

    async def stream(
        self,
        prompt: str,
        deps: Optional[DepsT] = None,
        **kwargs
    ):
        """
        Stream responses from the agent.

        Args:
            prompt: User prompt to process
            deps: Optional dependencies
            **kwargs: Additional arguments

        Yields:
            Streamed response chunks
        """
        async with self.agent.run_stream(prompt, deps=deps, **kwargs) as stream:
            async for chunk in stream.stream_text():
                yield chunk

    def validate_no_keyword_routing(self, code: str) -> bool:
        """
        Utility to verify no keyword-based routing in code.
        Can be used in tests or code reviews.
        """
        forbidden_patterns = [
            "if 'search' in",
            "if 'find' in",
            ".lower() in",
            "any(keyword in",
            "for keyword in",
            ".replace('search",
            "if query_lower"
        ]

        for pattern in forbidden_patterns:
            if pattern in code:
                raise ValueError(
                    f"Keyword-based routing detected: {pattern}\n"
                    f"This violates PROJECT_BRIEF.md principles. Use LLM intelligence instead."
                )

        return True


class KeywordRoutingError(Exception):
    """
    Raised when keyword-based routing is detected.
    This should NEVER happen in production code.
    """
    pass


def get_model_for_agent(agent_name: str) -> str:
    """
    Get the appropriate model for a given agent.
    Following the PROJECT_BRIEF.md guidelines.
    """
    model_mapping = {
        "orchestrator": "deepseek/deepseek-v3.1-terminus",           # Complex reasoning
        "products": "gpt-4.1-mini",        # Fast operations
        "orders": "gpt-4.1-mini",          # Fast operations
        "analytics": "gpt-4.1-mini",       # Data processing
        "extraction": "gpt-4.1-mini",      # Structured data extraction
        "simple": "gpt-4.1-nano",          # Simple operations
    }

    return model_mapping.get(agent_name, "gpt-5")  # Default to GPT-5