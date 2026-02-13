"""
API endpoints for tools and agents information
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import List, Dict, Any
from auth import get_current_user, User
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tools", tags=["tools"])


class ToolInfo(BaseModel):
    """Information about a single tool"""
    name: str
    description: str
    category: str  # "core", "agent", "file", "cache", "docs", "user"


class AgentInfo(BaseModel):
    """Information about a specialized agent"""
    name: str
    description: str
    capabilities: List[str]


class ToolsResponse(BaseModel):
    """Complete list of available tools and agents"""
    tools: List[ToolInfo]
    agents: List[AgentInfo]


@router.get("/", response_model=ToolsResponse)
async def get_available_tools(current_user: User = Depends(get_current_user)):
    """
    Get list of all available tools and agents for the orchestrator.

    Includes:
    - Core orchestrator tools
    - Specialized agents (with OAuth status)
    - Custom MCP tools (from user settings)
    """
    from database.session import AsyncSessionLocal
    from services.mcp_manager import MCPManager
    from sqlalchemy import select
    from database.models import UserMCPServer

    # Core orchestrator tools
    core_tools = [
        ToolInfo(
            name="execute_bash",
            description="Execute CLI tools and Python scripts (nf-quote, nf-analyze, etc.)",
            category="core"
        ),
        ToolInfo(
            name="call_agent",
            description="Delegate tasks to specialized agents (web_search, vision)",
            category="core"
        ),
        ToolInfo(
            name="todo_write",
            description="Create and update task lists",
            category="core"
        ),
        ToolInfo(
            name="todo_read",
            description="Read current task list",
            category="core"
        ),
        ToolInfo(
            name="write_to_scratchpad",
            description="Store temporary notes and context",
            category="core"
        ),
    ]

    # File operation tools
    file_tools = [
        ToolInfo(
            name="read_file",
            description="Read file contents",
            category="file"
        ),
        ToolInfo(
            name="write_file",
            description="Write content to files",
            category="file"
        ),
        ToolInfo(
            name="edit_file",
            description="Edit existing files",
            category="file"
        ),
    ]

    # Cache tools
    cache_tools = [
        ToolInfo(
            name="cache_lookup",
            description="Search cached results",
            category="cache"
        ),
        ToolInfo(
            name="cache_retrieve",
            description="Retrieve cached data",
            category="cache"
        ),
        ToolInfo(
            name="cache_store",
            description="Store data in cache",
            category="cache"
        ),
    ]

    # Documentation tools
    doc_tools = [
        ToolInfo(
            name="read_docs",
            description="Read local documentation and CLI tool references",
            category="docs"
        ),
        ToolInfo(
            name="search_docs",
            description="Search documentation files by keyword",
            category="docs"
        ),
        ToolInfo(
            name="spawn_specialist",
            description="Create temporary specialist for complex doc analysis",
            category="docs"
        ),
    ]

    # Other tools
    other_tools = [
        ToolInfo(
            name="analyze_image",
            description="Analyze images using vision models",
            category="vision"
        ),
        ToolInfo(
            name="get_user_profile",
            description="Get user profile and preferences",
            category="user"
        ),
    ]

    # Get specialized agents dynamically from orchestrator
    agents = []
    try:
        from main import get_orchestrator_for_model
        from config.models import DEFAULT_MODEL_ID
        orchestrator = await get_orchestrator_for_model(DEFAULT_MODEL_ID)

        # Get agent metadata from orchestrator
        agents_metadata = orchestrator.get_agent_metadata()

        # Convert to AgentInfo objects
        agents = [
            AgentInfo(
                name=agent["name"],
                description=agent["description"],
                capabilities=agent["capabilities"]
            )
            for agent in agents_metadata
        ]
    except Exception as e:
        logger.error(f"Error fetching agents from orchestrator: {e}")
        # Fallback to empty list if orchestrator unavailable
        agents = []

    # Fetch custom MCP tools from user settings
    user_mcp_tools = []
    try:
        async with AsyncSessionLocal() as db:
            # Get user's enabled MCP servers
            result = await db.execute(
                select(UserMCPServer).where(
                    UserMCPServer.user_id == current_user.id,
                    UserMCPServer.enabled == True
                )
            )
            mcp_servers = result.scalars().all()

            for server in mcp_servers:
                # Add a tool entry for each MCP server
                # Note: We can't easily introspect MCP tools without spawning the server,
                # so we just show the server itself
                user_mcp_tools.append(
                    ToolInfo(
                        name=f"mcp:{server.name}",
                        description=server.description or f"Custom MCP server: {server.name}",
                        category="mcp"
                    )
                )
    except Exception as e:
        logger.error(f"Error fetching user MCP servers: {e}")
        # Continue without MCP tools if there's an error

    all_tools = core_tools + file_tools + cache_tools + doc_tools + other_tools + user_mcp_tools

    return ToolsResponse(
        tools=all_tools,
        agents=agents
    )
