
from fastmcp import FastMCP, MCPTool, MCPParameter, MCPRequest


@app.tool
class CalibreLibraryTools(MCPTool):
    name = "calibre_library"
    description = "Tools for interacting with your Calibre library"

    @app.subtool
    def semantic_search(
            query: MCPParameter = MCPParameter(type="string", description="Search query in natural language"),
            top_n: MCPParameter = MCPParameter(type="integer", description="Number of results", default=5)
    ):
        """Search your Calibre library using semantic similarity"""
        # Implementation as above

    @app.subtool
    def get_book_details(
            book_id: MCPParameter = MCPParameter(type="integer", description="Calibre book ID")
    ):
        """Get detailed information about a specific book"""
        # Implementation

    @app.subtool
    def find_similar_books(
            book_id: MCPParameter = MCPParameter(type="integer",
                                                 description="Calibre book ID to find similar books for"),
            top_n: MCPParameter = MCPParameter(type="integer", description="Number of results", default=5)
    ):
        """Find books similar to a given book"""
        # Implementation