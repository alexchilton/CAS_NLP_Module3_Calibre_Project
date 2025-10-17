# calibre_mcp/tools/semantic_search.py
import json
from calibre_mcp.server import mcp
from calibre_tools.semantic_search import search


@mcp.tool()
def calibre_semantic_search(query: str, top_n: int = 5) -> str:
    """
    Search your Calibre library using semantic similarity.

    Args:
        query: The search query in natural language
        top_n: Number of results to return (default: 5)

    Returns:
        JSON string with search results
    """
    results = search(query, top_n=top_n)

    formatted_results = []
    for result in results:
        book = result['metadata']

        # Extract all available metadata
        book_info = {
            "title": book.get('title', 'Unknown'),
            "authors": book.get('authors', 'Unknown'),
            "similarity_score": result['score'],
            "calibre_id": int(book['id']),
            "isbn": book.get('isbn', ''),
            "publisher": book.get('publisher', ''),
            "pubdate": book.get('pubdate', ''),
            "series": book.get('series', ''),
            "series_index": book.get('series_index', ''),
            "tags": book.get('tags', []),
            "rating": book.get('rating', ''),
            "languages": book.get('languages', []),
            "identifiers": book.get('identifiers', {}),
            "formats": book.get('formats', []),
            "last_modified": book.get('last_modified', ''),
            "comments": book.get('comments', ''),
            "description_preview": book.get('comments', '')[:200] + "..." if book.get('comments', '') and len(book.get('comments', '')) > 200 else book.get('comments', '')
        }

        formatted_results.append(book_info)

    return json.dumps({"results": formatted_results}, indent=2)
