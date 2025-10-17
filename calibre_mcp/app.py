# calibre_mcp/app.py
import sys
from calibre_mcp.server import mcp

# Import tools to register decorators
from calibre_mcp.tools import (
    semantic_search,
    duplicate_finder,
    isbn_tools,
    calibre_cli,
    book_details,
    metadata_enrichment
)

if __name__ == "__main__":
    # Check if we should use HTTP or stdio
    if "--http" in sys.argv:
        print("=" * 60)
        print("Starting Calibre MCP Server with HTTP transport")
        print("Server URL: http://127.0.0.1:8765/mcp")
        print("=" * 60)
        # Run with HTTP transport
        mcp.run(transport="http", host="127.0.0.1", port=8765, path="/mcp")
    else:
        # Default: stdio transport for Claude Desktop
        print("Starting Calibre MCP Server with stdio transport", file=sys.stderr)
        mcp.run(transport="stdio")
