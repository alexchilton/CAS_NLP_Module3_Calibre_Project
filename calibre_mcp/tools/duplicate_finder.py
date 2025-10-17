# calibre_mcp/tools/duplicate_finder.py
import json
from calibre_mcp.server import mcp
from calibre_tools.duplicate_finder import find_all_duplicates, format_duplicate_results
from calibre_tools.config import DEFAULT_CALIBRE_LIBRARY


@mcp.tool()
def calibre_find_duplicates(library_path: str = DEFAULT_CALIBRE_LIBRARY, format_output: bool = True) -> str:
    """
    Find duplicate books in your Calibre library.

    Args:
        library_path: Path to Calibre library (default: ~/Calibre Library)
        format_output: Format output as markdown (default: True)

    Returns:
        JSON string with duplicate findings
    """
    # Find duplicates
    results = find_all_duplicates(library_path)

    # Count total duplicates
    total_duplicates = 0
    if results["exact_matches"]:
        for books in results["exact_matches"].values():
            total_duplicates += len(books) - 1  # Subtract 1 for the original book

    if results["similar_titles"]:
        for group in results["similar_titles"]:
            total_duplicates += len(group) - 1  # Subtract 1 for the original book

    if results["isbn_duplicates"]:
        for books in results["isbn_duplicates"].values():
            total_duplicates += len(books) - 1  # Subtract 1 for the original book

    # Format results if requested
    formatted_text = format_duplicate_results(results) if format_output else None

    return json.dumps({
        "total_duplicates": total_duplicates,
        "exact_match_groups": len(results["exact_matches"]),
        "similar_title_groups": len(results["similar_titles"]),
        "isbn_duplicate_groups": len(results["isbn_duplicates"]),
        "formatted_results": formatted_text
    }, indent=2)
