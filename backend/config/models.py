"""
Model configuration for EspressoBot orchestrator.
Defines available models with their capabilities and pricing.
"""

from enum import Enum
from typing import List, Literal, TypedDict


class ModelProvider(str, Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    OPENROUTER = "openrouter"
    GATEWAY = "gateway"


class ModelInfo(TypedDict):
    """Model information and capabilities"""

    id: str  # Internal ID for frontend
    name: str  # Display name
    slug: str  # API model name
    provider: ModelProvider
    description: str
    context_window: int  # Input context in tokens
    max_output: int  # Max output tokens
    cost_input: str  # Cost per 1M input tokens
    cost_output: str  # Cost per 1M output tokens
    supports_thinking: bool  # Extended thinking/reasoning
    supports_vision: bool  # Vision/multimodal image processing
    speed: Literal["fast", "medium", "slow"]  # Relative speed
    intelligence: Literal["high", "very-high", "frontier"]  # Capability level
    recommended_for: List[str]  # Use cases


# Available models for orchestrator
ORCHESTRATOR_MODELS: dict[str, ModelInfo] = {
    "claude-haiku-4.5": {
        "id": "claude-haiku-4.5",
        "name": "Claude Haiku 4.5",
        "slug": "claude-haiku-4-5-20251001",
        "provider": ModelProvider.ANTHROPIC,
        "description": "Near-frontier performance at lightning speed (Default)",
        "context_window": 200_000,
        "max_output": 64_000,
        "cost_input": "$1.00",
        "cost_output": "$5.00",
        "supports_thinking": True,
        "supports_vision": True,
        "speed": "fast",
        "intelligence": "very-high",
        "recommended_for": [
            "Real-time chat",
            "Quick operations",
            "Cost-effective orchestration",
        ],
    },
    "claude-sonnet-4.5": {
        "id": "claude-sonnet-4.5",
        "name": "Claude Sonnet 4.5",
        "slug": "claude-sonnet-4-5-20250929",
        "provider": ModelProvider.ANTHROPIC,
        "description": "Highest intelligence, best for complex reasoning",
        "context_window": 200_000,
        "max_output": 64_000,
        "cost_input": "$3.00",
        "cost_output": "$15.00",
        "supports_thinking": True,
        "supports_vision": True,
        "speed": "medium",
        "intelligence": "frontier",
        "recommended_for": [
            "Complex workflows",
            "Critical operations",
            "Maximum accuracy",
        ],
    },
    "deepseek-v3.1": {
        "id": "deepseek-v3.1",
        "name": "DeepSeek V3.1 Terminus",
        "slug": "deepseek/deepseek-v3.1-terminus",
        "provider": ModelProvider.OPENROUTER,
        "description": "Open source, strong reasoning at low cost",
        "context_window": 64_000,
        "max_output": 8_000,
        "cost_input": "$0.14",
        "cost_output": "$0.14",
        "supports_thinking": True,
        "supports_vision": False,
        "speed": "medium",
        "intelligence": "high",
        "recommended_for": [
            "Budget-friendly",
            "Open source preference",
            "Experimentation",
        ],
    },
    "deepseek-v3.2": {
        "id": "deepseek-v3.2",
        "name": "DeepSeek V3.2",
        "slug": "deepseek/deepseek-v3.2",
        "provider": ModelProvider.OPENROUTER,
        "description": "Open source, strong reasoning at low cost",
        "context_window": 64_000,
        "max_output": 8_000,
        "cost_input": "$0.14",
        "cost_output": "$0.14",
        "supports_thinking": True,
        "supports_vision": False,
        "speed": "medium",
        "intelligence": "high",
        "recommended_for": [
            "Budget-friendly",
            "Open source preference",
            "Experimentation",
        ],
    },
    "deepseek-v3.2-special": {
        "id": "deepseek-v3.2-special",
        "name": "DeepSeek V3.2 Special",
        "slug": "deepseek/deepseek-v3.2-special",
        "provider": ModelProvider.OPENROUTER,
        "description": "Open source, strong reasoning at low cost",
        "context_window": 64_000,
        "max_output": 8_000,
        "cost_input": "$0.14",
        "cost_output": "$0.14",
        "supports_thinking": True,
        "supports_vision": False,
        "speed": "medium",
        "intelligence": "high",
        "recommended_for": [
            "Budget-friendly",
            "Open source preference",
            "Experimentation",
        ],
    },
    "glm-4.6": {
        "id": "glm-4.6",
        "name": "GLM 4.6",
        "slug": "z-ai/glm-4.6",
        "provider": ModelProvider.OPENROUTER,
        "description": "Best value - 1/5 cost of GPT-5, 200K context",
        "context_window": 200_000,
        "max_output": 16_000,
        "cost_input": "$0.50",
        "cost_output": "$2.00",
        "supports_thinking": False,
        "supports_vision": False,
        "speed": "fast",
        "intelligence": "high",
        "recommended_for": ["Long documents", "High volume", "Cost optimization"],
    },
    "glm-5": {
        "id": "glm-5",
        "name": "GLM 5",
        "slug": "z-ai/glm-5",
        "provider": ModelProvider.OPENROUTER,
        "description": "Smart and cheap — 200K context, tool calling",
        "context_window": 202_752,
        "max_output": 16_000,
        "cost_input": "$0.80",
        "cost_output": "$2.56",
        "supports_thinking": False,
        "supports_vision": False,
        "speed": "fast",
        "intelligence": "very-high",
        "recommended_for": ["Default orchestrator", "Tool calling", "Cost-effective"],
    },
    "gpt-5.1": {
        "id": "gpt-5.1",
        "name": "GPT-5.1",
        "slug": "openai/gpt-5.1",
        "provider": ModelProvider.OPENROUTER,
        "description": "OpenAI's latest, deep reasoning capabilities",
        "context_window": 128_000,
        "max_output": 64_000,
        "cost_input": "$2.50",
        "cost_output": "$10.00",
        "supports_thinking": True,
        "supports_vision": True,
        "speed": "slow",
        "intelligence": "frontier",
        "recommended_for": ["Complex analysis", "Deep reasoning", "Research tasks"],
    },
    "grok-4.1-fast": {
        "id": "grok-4.1-fast",
        "name": "Grok 4.1 Fast",
        "slug": "x-ai/grok-4.1-fast",
        "provider": ModelProvider.OPENROUTER,
        "description": "Ultra-fast with massive 2M context window",
        "context_window": 2_000_000,
        "max_output": 16_000,
        "cost_input": "$0.50",
        "cost_output": "$2.00",
        "supports_thinking": True,
        "supports_vision": False,
        "speed": "fast",
        "intelligence": "high",
        "recommended_for": ["Huge contexts", "Fast responses", "Memory extraction"],
    },
}

# Default model
DEFAULT_MODEL_ID = "glm-5"


def get_model_info(model_id: str) -> ModelInfo:
    """Get model info by ID"""
    return ORCHESTRATOR_MODELS.get(model_id, ORCHESTRATOR_MODELS[DEFAULT_MODEL_ID])


def get_model_slug(model_id: str) -> str:
    """Get API model slug from model ID"""
    return get_model_info(model_id)["slug"]


def get_model_provider(model_id: str) -> ModelProvider:
    """Get provider for model ID"""
    return get_model_info(model_id)["provider"]


def is_anthropic_model(model_id: str) -> bool:
    """Check if model uses Anthropic API"""
    return get_model_provider(model_id) == ModelProvider.ANTHROPIC


def get_all_models() -> List[ModelInfo]:
    """Get list of all available models"""
    return list(ORCHESTRATOR_MODELS.values())


def is_vision_capable(model_id: str) -> bool:
    """
    Check if a model supports vision/multimodal inputs.

    This checks both the hardcoded config defaults and can be extended
    to check database settings for custom/new models.

    Args:
        model_id: Model identifier (e.g., "claude-haiku-4.5")

    Returns:
        True if model supports vision, False otherwise
    """
    model_info = get_model_info(model_id)
    return model_info.get("supports_vision", False)
