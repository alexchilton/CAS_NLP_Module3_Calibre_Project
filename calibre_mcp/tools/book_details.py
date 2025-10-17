# calibre_mcp/tools/book_details.py
import json
from calibre_mcp.server import mcp
from calibre_tools.cli_wrapper import get_book_metadata


@mcp.tool()
def calibre_get_book_details(book_id: int) -> str:
    """
    Get detailed metadata for a specific book in your Calibre library.

    This returns ALL available metadata including:
    - Title, Authors, Publisher, Languages
    - Published date, Timestamp
    - Comments/Description (full text)
    - ISBN and other identifiers
    - Series information
    - Tags, Rating
    - Custom columns (e.g., Genre)
    - File formats available
    - And more!

    Args:
        book_id: The Calibre book ID (from search or list results)

    Returns:
        JSON string with complete book metadata
    """
    metadata = get_book_metadata(book_id)

    return json.dumps(metadata, indent=2)
