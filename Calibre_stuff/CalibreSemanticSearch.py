from fastmcp import FastMCP, MCPTool, MCPParameter, MCPRequest

# Import your existing semantic search functionality
from semantic_search import search, embeddings_dict, book_metadata, model

app = FastMCP()


@app.tool
class CalibreSemanticSearch(MCPTool):
    name = "calibre_semantic_search"
    description = "Search your Calibre library using semantic similarity"

    query: MCPParameter = MCPParameter(
        type="string",
        description="The search query in natural language"
    )

    top_n: MCPParameter = MCPParameter(
        type="integer",
        description="Number of results to return",
        default=5
    )

    def execute(self, request: MCPRequest):
        query = request.parameters["query"]
        top_n = request.parameters.get("top_n", 5)

        results = search(query, top_n=top_n, display_mode=None)

        formatted_results = []
        for result in results:
            book = result['metadata']
            formatted_results.append({
                "title": book.get('title', 'Unknown'),
                "author": book.get('authors', 'Unknown'),
                "similarity_score": float(result['score']),
                "calibre_id": int(book['id']),
                "tags": book.get('tags', []),
                "description": book.get('comments', '')[:200] + "..." if book.get('comments', '') else ""
            })

        return {"results": formatted_results}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)

