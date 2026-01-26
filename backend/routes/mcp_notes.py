"""
FastAPI route for Notes MCP Server integration

Exposes the Notes MCP server instance and ASGI app for mounting.
The MCP app's lifespan will be integrated with the main FastAPI app's lifespan.
"""
from fastapi import APIRouter
import logging
import sys
import os

# Add MCP server directory to path
mcp_server_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'mcp_servers')
if mcp_server_path not in sys.path:
    sys.path.insert(0, mcp_server_path)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["mcp", "notes"])

# Import MCP server instance and create ASGI app
try:
    from notes_server import mcp as notes_mcp

    # Create the ASGI app
    notes_mcp_app = notes_mcp.http_app()

    logger.info("✅ Notes MCP server imported successfully")
    logger.info(f"   Server name: {notes_mcp.name}")
    logger.info(f"   Version: {notes_mcp.version}")

except Exception as e:
    logger.error(f"❌ Failed to import Notes MCP server: {e}")
    notes_mcp = None
    notes_mcp_app = None


@router.get("/info")
async def mcp_notes_info():
    """
    Get information about the Notes MCP server.

    Returns server capabilities, tools, and configuration.
    """
    try:
        from notes_server import mcp

        # Get tools count properly from FastMCP
        tools_list = []
        try:
            # FastMCP stores tools in _tools dict
            if hasattr(mcp, '_tools'):
                tools_list = list(mcp._tools.values())
        except:
            pass

        return {
            "name": "EspressoBot Notes",
            "version": "1.0.0",
            "description": "MCP server for managing notes in your Second Brain",
            "transport": "streamable-http",
            "endpoint": "/mcp/notes/mcp",
            "tools": len(tools_list),
            "resources": 2,  # info and stats resources
            "authentication": "JWT Bearer token required",
            "capabilities": {
                "crud": ["create", "read", "update", "delete"],
                "search": ["semantic", "fulltext"],
                "features": ["tags", "wikilinks", "backlinks", "similar_notes", "obsidian_import"]
            }
        }
    except Exception as e:
        logger.error(f"Error getting MCP notes info: {e}")
        return {"error": str(e)}
