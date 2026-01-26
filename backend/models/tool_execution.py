"""
Structured outputs for tool execution tracking

Provides Pydantic models for enforcing structured outputs that verify
tools were actually executed, not just described.
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime


class ToolCall(BaseModel):
    """Record of a single tool call"""

    tool_name: str = Field(description="Name of the tool that was called")
    arguments: Dict[str, Any] = Field(description="Arguments passed to the tool")
    result: str = Field(description="Result returned from the tool")
    timestamp: datetime = Field(default_factory=datetime.now)
    duration_ms: Optional[int] = Field(
        None, description="Time taken to execute (milliseconds)"
    )


class ActionResult(BaseModel):
    """
    Structured output for operations that must execute tools.

    Use this model as output_type when you want to enforce that the
    agent actually called tools and didn't just describe what it would do.

    Example:
        agent = Agent(
            'gpt-5',
            output_type=ActionResult,
            instructions='You must actually call tools to complete tasks'
        )
    """

    tools_called: List[ToolCall] = Field(
        description="List of tools that were ACTUALLY CALLED (not described)",
        min_items=1,  # At least one tool must be called
    )
    summary: str = Field(
        description="Brief summary of what was accomplished (not what you planned to do)"
    )
    success: bool = Field(description="Whether all actions succeeded")
    errors: List[str] = Field(
        default_factory=list, description="Any errors encountered"
    )


class PricingUpdateResult(BaseModel):
    """
    Structured output for pricing update operations.

    Forces the agent to actually update prices and return verification.
    """

    products_updated: List[str] = Field(
        description="Product IDs that were actually updated"
    )
    update_commands_executed: List[str] = Field(
        description="Actual bash commands that were executed"
    )
    verification_results: Dict[str, Any] = Field(
        description="Results from verifying the updates (e.g., fetching updated product)"
    )
    summary: str = Field(description="Summary of changes made")


class ProductCreationResult(BaseModel):
    """
    Structured output for product creation operations.

    Forces the agent to actually create products and return product IDs.
    """

    product_id: str = Field(description="Shopify product ID (gid://...)")
    variant_ids: List[str] = Field(
        description="Shopify variant IDs created (gid://...)"
    )
    commands_executed: List[str] = Field(
        description="Actual bash commands that were executed"
    )
    verification_result: str = Field(
        description="Result from fetching the created product to verify"
    )
    summary: str = Field(description="Summary of what was created")


# Registry of structured outputs for different operation types
STRUCTURED_OUTPUT_REGISTRY = {
    "pricing_update": PricingUpdateResult,
    "product_creation": ProductCreationResult,
    "generic_action": ActionResult,
}


def get_structured_output_for_operation(operation_type: str):
    """
    Get the appropriate structured output model for an operation type.

    Args:
        operation_type: Type of operation (e.g., 'pricing_update', 'product_creation')

    Returns:
        Pydantic model class for structured output, or None if not found
    """
    return STRUCTURED_OUTPUT_REGISTRY.get(operation_type)
