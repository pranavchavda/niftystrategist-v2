"""
State and Context models for conversation management using Pydantic

Replaces LangGraph's state management with type-safe Pydantic models.
"""

from typing import Any, Dict, List, Optional, Set
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum

from utils.term_corrections import apply_term_corrections


class MessageRole(str, Enum):
    """Message roles in conversations"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class Message(BaseModel):
    """A single message in the conversation"""
    role: MessageRole
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)
    agent_name: Optional[str] = None


class AgentResult(BaseModel):
    """Result from an agent execution"""
    agent_name: str
    task: str
    result: Any
    success: bool = True
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)


class ExtractedContext(BaseModel):
    """Compressed context from conversation history"""
    key_facts: List[str] = Field(default_factory=list)
    entities: Dict[str, Any] = Field(default_factory=dict)
    user_preferences: Dict[str, Any] = Field(default_factory=dict)
    important_results: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Optional[str] = None


class ConversationMemory(BaseModel):
    """Long-term memory for conversations"""
    user_id: str
    facts: List[str] = Field(default_factory=list)
    preferences: Dict[str, Any] = Field(default_factory=dict)
    past_interactions: List[Dict[str, Any]] = Field(default_factory=list)
    categories: Set[str] = Field(default_factory=set)
    last_updated: datetime = Field(default_factory=datetime.now)


class TaskPlan(BaseModel):
    """Task plan for multi-step operations"""
    tasks: List[Dict[str, Any]] = Field(default_factory=list)
    current_task_index: int = 0
    completed_tasks: List[str] = Field(default_factory=list)
    status: str = "pending"


class ConversationState(BaseModel):
    """
    Complete conversation state - replaces LangGraph's state management.

    This is the main state object passed between agents and maintained
    throughout a conversation.
    """
    # Core conversation data
    thread_id: str
    user_id: str
    messages: List[Message] = Field(default_factory=list)
    user_request: str = ""

    # Agent coordination
    current_agent: Optional[str] = None
    next_agent: Optional[str] = None
    agent_context: Dict[str, Any] = Field(default_factory=dict)
    previous_results: Dict[str, Any] = Field(default_factory=dict)  # Agent-to-agent data passing

    # Results tracking
    agent_results: List[AgentResult] = Field(default_factory=list)
    agent_results_dict: Dict[str, str] = Field(default_factory=dict)  # For quick lookup

    # Memory & Context
    conversation_memory: Optional[ConversationMemory] = None
    compressed_context: Optional[ExtractedContext] = None

    # Task management
    task_plan: Optional[TaskPlan] = None
    has_active_task_plan: bool = False

    # Control flow
    max_agents_to_call: int = 5
    agents_called: int = 0

    # Error handling
    last_error: Optional[str] = None
    retry_count: int = 0
    same_agent_retries: int = 0
    last_agent_called: Optional[str] = None

    # Cache context (for performance)
    cache_context: Dict[str, Any] = Field(default_factory=dict)

    # Interruption & Message Queue
    is_interrupted: bool = False
    interrupted_at: Optional[datetime] = None
    partial_response: str = ""  # Partial response before interruption
    queued_messages: List[str] = Field(default_factory=list)  # Messages queued during processing
    interrupt_reason: Optional[str] = None

    # Metadata
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    def add_message(self, role: MessageRole, content: str, agent_name: Optional[str] = None):
        """Add a message to the conversation.

        For assistant messages, applies term corrections to fix deprecated API terms.
        This ensures the agent sees corrected terms in its conversation history.
        """
        # Apply term corrections to assistant messages so the agent
        # sees correct terms in its history (influences future tool calls)
        if role == MessageRole.ASSISTANT:
            content = apply_term_corrections(content)

        message = Message(
            role=role,
            content=content,
            agent_name=agent_name
        )
        self.messages.append(message)
        self.updated_at = datetime.now()
        return message

    def add_agent_result(self, agent_name: str, task: str, result: Any, success: bool = True, error: Optional[str] = None):
        """Record an agent's result"""
        agent_result = AgentResult(
            agent_name=agent_name,
            task=task,
            result=result,
            success=success,
            error=error
        )
        self.agent_results.append(agent_result)
        self.agent_results_dict[agent_name] = str(result)

        # Update previous_results for agent-to-agent passing
        self.previous_results[agent_name] = result
        self.agents_called += 1
        self.last_agent_called = agent_name
        self.updated_at = datetime.now()

        return agent_result

    def get_recent_messages(self, limit: int = 10) -> List[Message]:
        """Get recent messages from conversation"""
        return self.messages[-limit:] if self.messages else []

    def get_agent_results_summary(self) -> str:
        """Get a summary of all agent results"""
        if not self.agent_results:
            return "No agent results yet."

        summary_parts = []
        for result in self.agent_results:
            status = "✓" if result.success else "✗"
            summary_parts.append(f"{status} {result.agent_name}: {result.task}")

        return "\n".join(summary_parts)

    def should_call_another_agent(self) -> bool:
        """Determine if another agent should be called"""
        if self.agents_called >= self.max_agents_to_call:
            return False

        if self.last_error and self.retry_count >= 3:
            return False

        if self.same_agent_retries >= 2:
            return False

        return True

    def reset_for_new_request(self, user_request: str):
        """Reset state for a new user request while preserving memory"""
        self.user_request = user_request
        self.current_agent = None
        self.next_agent = None
        self.agent_context = {}
        self.previous_results = {}
        self.agent_results = []
        self.agent_results_dict = {}
        self.agents_called = 0
        self.last_error = None
        self.retry_count = 0
        self.same_agent_retries = 0
        self.last_agent_called = None
        self.updated_at = datetime.now()


class OrchestratorDecision(BaseModel):
    """Decision made by the orchestrator"""
    action: str  # "call_agent", "respond", "clarify", "error"
    agent_name: Optional[str] = None
    task: Optional[str] = None
    context: Dict[str, Any] = Field(default_factory=dict)
    reasoning: Optional[str] = None
    confidence: float = 1.0