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
import logging
import os
from pydantic import BaseModel
from pydantic_ai import Agent, Tool, ModelSettings
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic_ai.providers.openrouter import OpenRouterProvider  # Proper OpenRouter support with reasoning field
from pydantic_ai.profiles.openai import OpenAIModelProfile
from providers.openrouter_gemini import OpenRouterGeminiModel

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
        self.model = self._setup_model(config)

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
            'history_processors': self._get_history_processors()  # Context window management
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
        """Set up the LLM model with appropriate provider"""
        # DEBUG: Log what model name we're checking
        logger.info(f"[GATEWAY-DEBUG] Setting up model: '{config.model_name}', use_openrouter={config.use_openrouter}")

        # Check if this is a Gateway model - handle it first before other checks
        if config.model_name.startswith('gateway/'):
            logger.info(f"Detected Pydantic AI Gateway model: {config.model_name}")
            # For gateway models, Pydantic AI automatically detects and routes when:
            # 1. Model string starts with "gateway/"
            # 2. PYDANTIC_AI_GATEWAY_API_KEY is set in environment

            # Load gateway API key from environment
            api_key = os.environ.get('PYDANTIC_AI_GATEWAY_API_KEY')
            if not api_key:
                from dotenv import load_dotenv
                load_dotenv()
                api_key = os.getenv('PYDANTIC_AI_GATEWAY_API_KEY')

            if not api_key:
                logger.error("PYDANTIC_AI_GATEWAY_API_KEY not found - gateway models require this!")
                raise ValueError("PYDANTIC_AI_GATEWAY_API_KEY is required for gateway models")

            logger.info(f"Using Pydantic AI Gateway with key: {api_key[:12]}...")

            # For gateway models, return the model STRING directly
            # Pydantic AI's Agent class will handle gateway routing automatically
            # No need to create a custom provider - this is the documented way!
            return config.model_name  # e.g., "gateway/groq:openai/gpt-oss-120b"

        # Check if this is an Anthropic model (Claude)
        is_anthropic = 'claude' in config.model_name.lower()

        if is_anthropic:
            # Use direct Anthropic API for Claude models
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

            # Create Anthropic provider with API key
            # Explicitly set base_url to override any empty ANTHROPIC_BASE_URL env var
            provider = AnthropicProvider(
                api_key=api_key.strip(),
                base_url="https://api.anthropic.com"
            )
            logger.info(f"Enabling extended thinking mode for {config.model_name}")

            # Create model settings with temperature and extended thinking
            # IMPORTANT: Anthropic requires temperature=1.0 when thinking is enabled
            # IMPORTANT: max_tokens must be GREATER than budget_tokens
            # budget_tokens: Max thinking tokens (12K = balanced for complex orchestration)
            # max_tokens: Total output tokens (thinking + response) - Claude Haiku 4.5 max is 64K
            # With 12K thinking budget, leaves ~52K for actual response
            # Note: For very long operations, the sliding_window_history_processor truncates context
            model_settings_kwargs = {
                'temperature': 1.0,  # Required by Anthropic when thinking is enabled
                'max_tokens': 64000,  # Claude Haiku 4.5 maximum (can't exceed this)
                'anthropic_thinking': {
                    'type': 'enabled',
                    'budget_tokens': 12000  # Balanced: enough thinking for orchestration, room for long responses
                }
            }
            model_settings = ModelSettings(**model_settings_kwargs)

            return AnthropicModel(
                config.model_name,
                provider=provider,
                settings=model_settings
            )

        elif config.use_openrouter:
            # Use OpenRouterProvider for proper OpenRouter support
            # This enables reasoning field parsing for DeepSeek, Gemini, etc.
            # First check OS environment, then fall back to dotenv if needed
            api_key = os.environ.get('OPENROUTER_API_KEY')
            if not api_key:
                from dotenv import load_dotenv
                load_dotenv()
                api_key = os.getenv('OPENROUTER_API_KEY')

            if not api_key:
                logger.error("OPENROUTER_API_KEY not found in environment or .env file!")
                raise ValueError("OPENROUTER_API_KEY is required for OpenRouter models")

            logger.info(f"Using OpenRouterProvider with key: {api_key[:8]}...")
            # Use dedicated OpenRouterProvider - properly handles reasoning field
            # This enables automatic ThinkingPart parsing for DeepSeek, etc.
            provider = OpenRouterProvider(api_key=api_key)
            # OpenRouter uses format: provider/model
            model_name = f"openai/{config.model_name}" if not "/" in config.model_name else config.model_name
            logger.info(f"Using model: {model_name} via OpenRouterProvider")
        else:
            # Direct OpenAI API
            # First check OS environment, then fall back to dotenv if needed
            api_key = os.environ.get('OPENAI_API_KEY')
            if not api_key:
                from dotenv import load_dotenv
                load_dotenv()
                api_key = os.getenv('OPENAI_API_KEY')

            if not api_key:
                logger.error("OPENAI_API_KEY not found in environment or .env file!")
                raise ValueError("OPENAI_API_KEY is required for OpenAI models")

            provider = OpenAIProvider(
                api_key=api_key
            )
            model_name = config.model_name

        # Create model settings with temperature and max_tokens
        # Add reasoning_effort for models that support it
        # Default temperature: 0.7 for non-reasoning models
        temperature = config.temperature if config.temperature is not None else 0.7
        model_settings_kwargs = {
            'temperature': temperature,
            'max_tokens': 16000  # Set generous limit to prevent abrupt stops (16K tokens)
        }

        # Add reasoning_effort for models that support reasoning
        if 'grok-4' in model_name.lower():
            model_settings_kwargs['reasoning_effort'] = 'medium'
            logger.info(f"Enabling reasoning for {model_name} with effort: medium")
        elif 'gpt-5-mini' in model_name.lower():
            # GPT-5-mini: Use medium reasoning for cost/performance balance
            model_settings_kwargs['reasoning_effort'] = 'medium'
            logger.info(f"Enabling reasoning for {model_name} with effort: medium")
        elif 'gpt-5' in model_name.lower():
            # GPT-5 always uses reasoning, but let's explicitly enable it
            model_settings_kwargs['reasoning'] = {'effort': 'high'}
            logger.info(f"Enabling reasoning for {model_name} with effort: high")
        elif 'openai/gpt-oss-120b' in model_name.lower():
            model_settings_kwargs['reasoning'] = {'effort': 'high'}
            logger.info(f"Enabling reasoning for {model_name} with effort: high")
        # elif 'glm' in model_name.lower():
            # GLM 4.6 supports thinking mode via OpenRouter
            # API format: {"thinking": {"type": "enabled"}}
            # Use extra_body to pass custom parameters to OpenRouter
        elif 'deepseek' in model_name.lower():
            # DeepSeek models support reasoning via OpenRouter
            # V3.1 Terminus uses: reasoning: { effort: 'high' }
            # V3.2+ uses: reasoning: true (boolean only)
            if 'v3.1' in model_name.lower() or 'terminus' in model_name.lower():
                model_settings_kwargs['extra_body'] = {
                    'reasoning': {
                        'effort': 'high'  # V3.1 uses effort parameter
                    },
                    'include_reasoning': True
                }
                logger.info(f"Enabling reasoning for {model_name} with effort: high (V3.1 API)")
            else:
                # V3.2 and newer use enabled object format
                model_settings_kwargs['extra_body'] = {
                    'reasoning': {'enabled': True},  # V3.2 uses enabled object
                    'include_reasoning': True
                }
                logger.info(f"Enabling reasoning for {model_name} with reasoning.enabled: true (V3.2 API)")
        elif 'gemini' in model_name.lower():
            # Gemini models (including Gemini 3.0 Pro) are "mandatory reasoning" models
            # They ALWAYS use reasoning internally - we just need to request that reasoning be included in responses
            # For multi-turn tool calling, Pydantic AI will automatically preserve reasoning_details
            # IMPORTANT: Do NOT send reasoning config (max_tokens/effort) as it applies to ALL requests
            # and conflicts with reasoning_details preservation in follow-up requests
            model_settings_kwargs['extra_body'] = {
                'include_reasoning': True,  # Disable reasoning output to enable proper streaming
                'reasoning': {
                        'effort': 'high'  # V3.1 uses effort parameter
                    },
            }
            logger.info(f"Enabling reasoning output for {model_name} to enable streaming")
        elif 'claude' in model_name.lower():
            # Claude models support thinking through Anthropic's beta API
            # Pydantic AI should handle this automatically
            logger.info(f"Using Claude model {model_name} with thinking support")

        model_settings = ModelSettings(**model_settings_kwargs)

        if config.use_openrouter and 'gemini' in model_name.lower():
            logger.info(f"Using custom OpenRouterGeminiModel for {model_name}")
            return OpenRouterGeminiModel(
                model_name,
                provider=provider,
                settings=model_settings
            )

        # DeepSeek models don't support mixing strict and non-strict tools
        # Must disable strict tool definitions to prevent "Cannot use strict tool
        # with non-strict tool in the same request" error
        if 'deepseek' in model_name.lower():
            logger.info(f"Using custom profile for {model_name} (strict tools disabled)")
            profile = OpenAIModelProfile(openai_supports_strict_tool_definition=False)
            return OpenAIChatModel(
                model_name,
                provider=provider,
                settings=model_settings,
                profile=profile
            )

        return OpenAIChatModel(
            model_name,
            provider=provider,
            settings=model_settings
        )

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