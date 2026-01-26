"""
Agent Response Models - Structured responses for agent operations

Provides clear success/error handling for agent interactions.
"""

from typing import Optional, Any
from pydantic import BaseModel, Field
from enum import Enum


class AgentResponseStatus(str, Enum):
    """Status of agent response"""
    SUCCESS = "success"
    ERROR = "error"


class AgentError(BaseModel):
    """Structured error information from an agent"""
    error_type: str = Field(description="Type of error (e.g., 'APIError', 'ValidationError', 'TimeoutError')")
    error_message: str = Field(description="Human-readable error message")
    agent_name: str = Field(description="Name of the agent that encountered the error")
    original_task: str = Field(description="The task that was being attempted")
    suggestions: list[str] = Field(default_factory=list, description="Suggestions for fixing the error or retrying")
    retryable: bool = Field(default=True, description="Whether this error can be retried")
    raw_error: Optional[str] = Field(default=None, description="Raw error details for debugging")

    def to_user_message(self) -> str:
        """Format error as a user-friendly message"""
        msg = f"❌ **Error in {self.agent_name} agent**\n\n"
        msg += f"**Task:** {self.original_task}\n\n"
        msg += f"**Error:** {self.error_message}\n\n"

        if self.suggestions:
            msg += "**Suggestions:**\n"
            for suggestion in self.suggestions:
                msg += f"- {suggestion}\n"
            msg += "\n"

        if self.retryable:
            msg += "This error may be temporary. I can try again with adjusted parameters or approach."
        else:
            msg += "This error requires manual intervention to resolve."

        return msg


class AgentResponse(BaseModel):
    """
    Unified response format for agent operations.

    This allows clean error propagation while maintaining structured data.
    """
    status: AgentResponseStatus
    agent_name: str
    task: str
    output: Optional[Any] = None  # Success output
    error: Optional[AgentError] = None  # Error details

    @classmethod
    def success(cls, agent_name: str, task: str, output: Any) -> "AgentResponse":
        """Create a successful response"""
        return cls(
            status=AgentResponseStatus.SUCCESS,
            agent_name=agent_name,
            task=task,
            output=output
        )

    @classmethod
    def failure(
        cls,
        agent_name: str,
        task: str,
        error_type: str,
        error_message: str,
        suggestions: list[str] = None,
        retryable: bool = True,
        raw_error: str = None
    ) -> "AgentResponse":
        """Create a failed response"""
        return cls(
            status=AgentResponseStatus.ERROR,
            agent_name=agent_name,
            task=task,
            error=AgentError(
                error_type=error_type,
                error_message=error_message,
                agent_name=agent_name,
                original_task=task,
                suggestions=suggestions or [],
                retryable=retryable,
                raw_error=raw_error
            )
        )

    def is_success(self) -> bool:
        """Check if response was successful"""
        return self.status == AgentResponseStatus.SUCCESS

    def is_error(self) -> bool:
        """Check if response was an error"""
        return self.status == AgentResponseStatus.ERROR

    def get_output_or_raise(self) -> Any:
        """Get output if success, otherwise raise exception"""
        if self.is_success():
            return self.output
        else:
            raise RuntimeError(self.error.to_user_message())

    def to_string(self) -> str:
        """Convert response to string for LLM consumption"""
        if self.is_success():
            # Return the actual output
            if hasattr(self.output, '__str__'):
                return str(self.output)
            return str(self.output)
        else:
            # Return formatted error for LLM to understand and potentially retry
            return self.error.to_user_message()
