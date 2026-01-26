"""
EspressoBot Agents Module

This module contains all specialized agents built with Pydantic AI.

Architecture (2025-10-06):
- Documentation-driven approach for Shopify operations
- Only domain-specific agents (google_workspace, web_search)
- Generic doc_specialist spawned on-demand
"""

from .base_agent import IntelligentBaseAgent, AgentConfig
from .orchestrator import OrchestratorAgent, OrchestratorDeps
from .doc_specialist import GenericDocSpecialist, SpecialistDeps, create_specialist
from .google_workspace_agent import GoogleWorkspaceAgent, GoogleWorkspaceDeps
from .web_search_agent import WebSearchAgent, WebSearchDeps
from .memory_extractor import MemoryExtractor, get_memory_extractor

__all__ = [
    "IntelligentBaseAgent",
    "AgentConfig",
    "OrchestratorAgent",
    "OrchestratorDeps",
    "GenericDocSpecialist",
    "SpecialistDeps",
    "create_specialist",
    "GoogleWorkspaceAgent",
    "GoogleWorkspaceDeps",
    "WebSearchAgent",
    "WebSearchDeps",
    "MemoryExtractor",
    "get_memory_extractor",
]