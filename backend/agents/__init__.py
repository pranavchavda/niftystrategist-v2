"""
Nifty Strategist v2 Agents Module

This module contains all specialized agents built with Pydantic AI.

Architecture:
- Trading orchestrator for market analysis and trade recommendations
- Web search for market news
- Vision for chart analysis
- Memory extraction for personalization
"""

from .base_agent import IntelligentBaseAgent, AgentConfig
from .orchestrator import OrchestratorAgent, OrchestratorDeps
from .web_search_agent import WebSearchAgent, WebSearchDeps
from .vision_agent import vision_agent
from .memory_extractor import MemoryExtractor, get_memory_extractor

__all__ = [
    "IntelligentBaseAgent",
    "AgentConfig",
    "OrchestratorAgent",
    "OrchestratorDeps",
    "WebSearchAgent",
    "WebSearchDeps",
    "vision_agent",
    "MemoryExtractor",
    "get_memory_extractor",
]