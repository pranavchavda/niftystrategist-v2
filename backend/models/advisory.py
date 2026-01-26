"""
Advisory Agent Models for Pydantic AI - Structured advice and recommendations

This module defines the data models for the advisor-based architecture where
specialized agents provide advice rather than executing directly.
"""

from typing import List, Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    """Risk levels for advisory recommendations"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RecommendationType(str, Enum):
    """Types of recommendations advisors can provide"""
    APPROACH = "approach"
    TOOL = "tool"
    PARAMETER = "parameter"
    SEQUENCE = "sequence"
    ALTERNATIVE = "alternative"
    VALIDATION = "validation"


class Risk(BaseModel):
    """Potential risk identified by an advisor"""
    level: RiskLevel
    category: str
    description: str
    impact: str
    mitigation: Optional[str] = None
    probability: float = Field(ge=0.0, le=1.0)


class Recommendation(BaseModel):
    """A specific recommendation from an advisor"""
    type: RecommendationType
    title: str
    description: str
    rationale: str
    confidence: float = Field(ge=0.0, le=1.0)
    priority: int = Field(ge=1, le=10)
    implementation: Optional[str] = None
    dependencies: List[str] = Field(default_factory=list)


class Alternative(BaseModel):
    """Alternative approach suggested by an advisor"""
    approach: str
    benefits: List[str]
    drawbacks: List[str]
    confidence: float = Field(ge=0.0, le=1.0)
    when_to_use: str


class DocumentationReference(BaseModel):
    """Reference to relevant documentation"""
    title: str
    url: Optional[str] = None
    section: Optional[str] = None
    content: str
    relevance_score: float = Field(ge=0.0, le=1.0)


class AdvisoryResponse(BaseModel):
    """Structured response from an advisor agent"""
    advisor_name: str
    advisor_type: str
    analysis: str  # Detailed analysis of the request
    recommendations: List[Recommendation]
    risks: List[Risk]
    alternatives: List[Alternative]
    documentation_references: List[DocumentationReference]
    overall_confidence: float = Field(ge=0.0, le=1.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def primary_recommendation(self) -> Optional[Recommendation]:
        """Get the highest priority recommendation"""
        if not self.recommendations:
            return None
        return max(self.recommendations, key=lambda r: (r.priority, r.confidence))

    @property
    def critical_risks(self) -> List[Risk]:
        """Get all critical and high-risk items"""
        return [r for r in self.risks if r.level in [RiskLevel.CRITICAL, RiskLevel.HIGH]]


class SynthesizedPlan(BaseModel):
    """Final execution plan synthesized from multiple advisors"""
    approach: str
    steps: List[Dict[str, Any]]
    tools_needed: List[str]
    parameters: Dict[str, Any]
    expected_outcomes: List[str]
    fallback_strategies: List[str]
    confidence_score: float = Field(ge=0.0, le=1.0)
    advisor_consensus: float = Field(ge=0.0, le=1.0)  # How much advisors agreed
    dissenting_opinions: List[str] = Field(default_factory=list)
    execution_agent: str  # Which agent should execute this plan


class AdvisorContext(BaseModel):
    """Context provided to advisors for analysis"""
    user_request: str
    conversation_history: List[Dict[str, Any]]
    current_state: Dict[str, Any]
    available_agents: List[str]
    available_tools: List[str]
    business_context: Optional[str] = None
    user_preferences: Optional[Dict[str, Any]] = None