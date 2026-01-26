"""
MCP Tool Adapter for Pydantic AI

This module provides adapters to integrate existing MCP (Model Context Protocol) servers
as toolsets in Pydantic AI agents. It handles both stdio and HTTP-based MCP servers.
"""

import os
import logging
from typing import List, Dict, Any, Optional, Callable
from pathlib import Path
from pydantic_ai.mcp import MCPServerStdio, MCPServerHTTP, MCPServerStreamableHTTP
from pydantic_ai import Agent

logger = logging.getLogger(__name__)


class MCPToolAdapter:
    """
    Adapter to integrate MCP servers as Pydantic AI toolsets.

    This class provides methods to:
    1. Load MCP servers from the mcp-servers directory
    2. Convert them to Pydantic AI toolsets
    3. Register them with agents
    """

    def __init__(self, mcp_servers_dir: str = "/home/pranav/pydanticebot/mcp-servers"):
        """
        Initialize the MCP tool adapter.

        Args:
            mcp_servers_dir: Directory containing MCP server scripts
        """
        self.mcp_servers_dir = Path(mcp_servers_dir)
        self.servers = {}
        self.server_configs = self._load_server_configs()

    def _load_server_configs(self) -> Dict[str, Dict[str, Any]]:
        """Load configuration for known MCP servers"""
        return {
            "products": {
                "script": "mcp-products-server.py",
                "description": "Product search and management",
                "type": "stdio"
            },
            "pricing": {
                "script": "mcp-pricing-server.py",
                "description": "Product pricing operations",
                "type": "stdio"
            },
            "inventory": {
                "script": "mcp-inventory-server.py",
                "description": "Inventory management",
                "type": "stdio"
            },
            "media": {
                "script": "mcp-media-server.py",
                "description": "Product media and images",
                "type": "stdio"
            },
            "product-management": {
                "script": "mcp-product-management-server.py",
                "description": "Product creation and updates",
                "type": "stdio"
            },
            "features": {
                "script": "mcp-features-server.py",
                "description": "Product features and variants",
                "type": "stdio"
            },
            "orders": {
                "script": "mcp-orders-server.py",
                "description": "Order analytics and reports",
                "type": "stdio"
            },
            "skuvault": {
                "script": "mcp-skuvault-server.py",
                "description": "SkuVault inventory sync",
                "type": "stdio"
            },
            "graphql": {
                "script": "mcp-graphql-server.py",
                "description": "Direct Shopify GraphQL API",
                "type": "stdio"
            }
        }

    def create_stdio_server(self, server_name: str) -> Optional[MCPServerStdio]:
        """
        Create a stdio-based MCP server.

        Args:
            server_name: Name of the server to create

        Returns:
            MCPServerStdio instance or None if not found
        """
        if server_name not in self.server_configs:
            logger.error(f"Unknown MCP server: {server_name}")
            return None

        config = self.server_configs[server_name]
        script_path = self.mcp_servers_dir / config["script"]

        if not script_path.exists():
            logger.error(f"MCP server script not found: {script_path}")
            return None

        # Create the MCP server with Python interpreter
        # Add tool_prefix to avoid conflicts between servers
        server = MCPServerStdio(
            command="python",
            args=[str(script_path)],
            tool_prefix=f"{server_name}_"  # Prefix tools with server name
        )

        logger.info(f"Created stdio MCP server: {server_name} ({config['description']})")
        return server

    def create_http_server(self, url: str, api_key: Optional[str] = None) -> MCPServerHTTP:
        """
        Create an HTTP-based MCP server.

        Args:
            url: URL of the MCP server
            api_key: Optional API key for authentication

        Returns:
            MCPServerHTTP instance
        """
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        server = MCPServerHTTP(url, headers=headers if headers else None)
        logger.info(f"Created HTTP MCP server: {url}")
        return server

    def create_streamable_http_server(self, url: str, api_key: Optional[str] = None) -> MCPServerStreamableHTTP:
        """
        Create a streamable HTTP-based MCP server.

        Args:
            url: URL of the MCP server
            api_key: Optional API key for authentication

        Returns:
            MCPServerStreamableHTTP instance
        """
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        server = MCPServerStreamableHTTP(url, headers=headers if headers else None)
        logger.info(f"Created streamable HTTP MCP server: {url}")
        return server

    def load_servers_for_agent(self, server_names: List[str]) -> List[Any]:
        """
        Load multiple MCP servers for an agent.

        Args:
            server_names: List of server names to load

        Returns:
            List of MCP server instances to use as toolsets
        """
        toolsets = []

        for name in server_names:
            if name in self.servers:
                # Reuse existing server
                toolsets.append(self.servers[name])
            else:
                # Create new server
                server = self.create_stdio_server(name)
                if server:
                    self.servers[name] = server
                    toolsets.append(server)

        logger.info(f"Loaded {len(toolsets)} MCP servers for agent")
        return toolsets

    def register_with_agent(self, agent: Agent, server_names: List[str]):
        """
        Register MCP servers with a Pydantic AI agent.

        Args:
            agent: The Pydantic AI agent
            server_names: List of server names to register

        Note: This modifies the agent's toolsets in place
        """
        toolsets = self.load_servers_for_agent(server_names)

        # In Pydantic AI, toolsets are provided during agent creation
        # This method would need to be called before agent initialization
        # or we need to modify the agent's internal toolsets
        logger.warning(
            "Toolsets should be provided during agent creation in Pydantic AI. "
            "Consider using load_servers_for_agent() and passing to Agent constructor."
        )

    async def __aenter__(self):
        """Enter async context - starts all loaded servers"""
        for server in self.servers.values():
            await server.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context - stops all loaded servers"""
        for server in self.servers.values():
            await server.__aexit__(exc_type, exc_val, exc_tb)


class NativeToolAdapter:
    """
    Adapter for native Python tools as an alternative to MCP servers.

    Native tools are faster as they avoid MCP serialization overhead.
    """

    def __init__(self, tools_dir: str = "/home/pranav/pydanticebot/backend/tools/native"):
        """
        Initialize the native tool adapter.

        Args:
            tools_dir: Directory containing native Python tools
        """
        self.tools_dir = Path(tools_dir)
        self.tools = {}

    def load_tool(self, tool_name: str) -> Optional[Callable]:
        """
        Load a native Python tool.

        Args:
            tool_name: Name of the tool to load

        Returns:
            Tool function or None if not found
        """
        tool_path = self.tools_dir / f"{tool_name}.py"

        if not tool_path.exists():
            logger.error(f"Native tool not found: {tool_path}")
            return None

        # Dynamic import of the tool module
        import importlib.util
        spec = importlib.util.spec_from_file_location(tool_name, tool_path)
        if not spec or not spec.loader:
            logger.error(f"Failed to load tool spec: {tool_name}")
            return None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Look for the main function (e.g., search_products, update_pricing)
        if hasattr(module, tool_name):
            tool_func = getattr(module, tool_name)
            self.tools[tool_name] = tool_func
            logger.info(f"Loaded native tool: {tool_name}")
            return tool_func

        # Try alternative naming conventions
        for func_name in [f"run_{tool_name}", "main", "execute"]:
            if hasattr(module, func_name):
                tool_func = getattr(module, func_name)
                self.tools[tool_name] = tool_func
                logger.info(f"Loaded native tool: {tool_name} (function: {func_name})")
                return tool_func

        logger.error(f"No suitable function found in tool: {tool_name}")
        return None

    def register_native_tools_with_agent(self, agent: Agent, tool_names: List[str]):
        """
        Register native Python tools directly with an agent.

        Args:
            agent: The Pydantic AI agent
            tool_names: List of tool names to register

        Note: This uses agent.tool decorator to register tools
        """
        for tool_name in tool_names:
            tool_func = self.load_tool(tool_name)
            if tool_func:
                # Register the tool with the agent
                # This would typically be done using @agent.tool decorator
                # but we're doing it dynamically here
                agent.tool(tool_func)
                logger.info(f"Registered native tool with agent: {tool_name}")


def create_hybrid_toolset(
    mcp_servers: List[str] = [],
    native_tools: List[str] = [],
    http_servers: List[Dict[str, str]] = []
) -> List[Any]:
    """
    Create a hybrid toolset combining MCP servers and native tools.

    Args:
        mcp_servers: List of stdio MCP server names
        native_tools: List of native tool names
        http_servers: List of HTTP server configs with 'url' and optional 'api_key'

    Returns:
        List of toolsets for Pydantic AI agent

    Example:
        toolsets = create_hybrid_toolset(
            mcp_servers=["products", "pricing"],
            native_tools=["search_products", "update_pricing"],
            http_servers=[{"url": "http://localhost:8000", "api_key": "secret"}]
        )
        agent = Agent(model, toolsets=toolsets)
    """
    toolsets = []

    # Add MCP stdio servers
    if mcp_servers:
        mcp_adapter = MCPToolAdapter()
        toolsets.extend(mcp_adapter.load_servers_for_agent(mcp_servers))

    # Add native tools
    if native_tools:
        native_adapter = NativeToolAdapter()
        # Native tools need to be registered differently
        # They would be added as regular tools to the agent
        logger.info(f"Native tools should be registered using @agent.tool: {native_tools}")

    # Add HTTP servers
    for server_config in http_servers:
        url = server_config.get("url")
        api_key = server_config.get("api_key")
        if url:
            mcp_adapter = MCPToolAdapter()
            if server_config.get("streamable"):
                server = mcp_adapter.create_streamable_http_server(url, api_key)
            else:
                server = mcp_adapter.create_http_server(url, api_key)
            toolsets.append(server)

    return toolsets