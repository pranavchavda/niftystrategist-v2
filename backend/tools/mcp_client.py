"""
MCP Client Stub - Placeholder for MCP Manager

In pydanticebot, we're using direct MCP tools instead of a manager.
This stub allows imports to work while we refactor to use direct tools.
"""

import logging

logger = logging.getLogger(__name__)


class MCPManager:
    """Stub MCP Manager"""

    def __init__(self):
        logger.warning("Using stub MCP Manager - direct tools should be used instead")

    async def call_tool(self, server_name: str, tool_name: str, arguments: dict):
        """Stub method - should not be called"""
        logger.error(f"MCPManager.call_tool called but not implemented: {server_name}.{tool_name}")
        raise NotImplementedError("Use direct MCP tools instead of MCP Manager")


async def get_mcp_manager() -> MCPManager:
    """Get MCP manager instance (stub)"""
    return MCPManager()