# calibre_mcp/server.py
"""
MCP server instance - imported by both app.py and tool modules
to avoid circular dependencies.
"""
from fastmcp import FastMCP

# Initialize MCP server
mcp = FastMCP("calibre-mcp")
