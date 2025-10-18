# calibre_mcp/tools/calibre_cli.py
import json
from typing import List
from calibre_mcp.server import mcp
from calibre_tools.cli_wrapper import (
    list_books,
    add_book,
    remove_book,
    set_metadata as set_book_metadata,
    convert_book,
    search_library,
    bulk_update_comments
)
from calibre_tools.config import DEFAULT_CALIBRE_LIBRARY


@mcp.tool()
def calibre_list_books(
    library_path: str = DEFAULT_CALIBRE_LIBRARY,
    search_term: str = None,
    sort_by: str = None,
    limit: int = None
) -> str:
    """
    List books in the Calibre library.

    Args:
        library_path: Path to Calibre library (default: ~/Calibre Library)
        search_term: Search term for filtering books
        sort_by: Field to sort results by
        limit: Maximum number of books to return

    Returns:
        JSON string with book list
    """
    books = list_books(library_path, search_term, sort_by, limit)
    return json.dumps({
        "count": len(books),
        "books": books
    }, indent=2)


@mcp.tool()
def calibre_add_book(
    file_path: str,
    library_path: str = DEFAULT_CALIBRE_LIBRARY,
    title: str = None,
    authors: str = None,
    isbn: str = None,
    tags: str = None
) -> str:
    """
    Add a book to the Calibre library.

    Args:
        file_path: Path to ebook file
        library_path: Path to Calibre library (default: ~/Calibre Library)
        title: Book title
        authors: Book authors
        isbn: Book ISBN
        tags: Book tags (comma separated)

    Returns:
        JSON string with result
    """
    book_id = add_book(
        file_path,
        library_path=library_path,
        title=title,
        authors=authors,
        isbn=isbn,
        tags=tags
    )

    return json.dumps({
        "success": book_id is not None,
        "book_id": book_id,
        "file_path": file_path
    }, indent=2)


@mcp.tool()
def calibre_remove_book(
    book_id: int,
    library_path: str = DEFAULT_CALIBRE_LIBRARY,
    permanent: bool = False
) -> str:
    """
    Remove a book from the Calibre library.

    Args:
        book_id: Calibre book ID
        library_path: Path to Calibre library (default: ~/Calibre Library)
        permanent: Permanently delete book files (default: False)

    Returns:
        JSON string with result
    """
    success = remove_book(book_id, library_path, permanent)
    return json.dumps({
        "success": success,
        "book_id": book_id,
        "permanent": permanent
    }, indent=2)


@mcp.tool()
def calibre_set_book_metadata(
    book_id: int,
    library_path: str = DEFAULT_CALIBRE_LIBRARY,
    title: str = None,
    authors: str = None,
    isbn: str = None,
    tags: str = None,
    publisher: str = None,
    comments: str = None,
    pubdate: str = None,
    series: str = None,
    rating: float = None,
    language: str = None
) -> str:
    """
    Set metadata for a book in the Calibre library.

    Args:
        book_id: Calibre book ID
        library_path: Path to Calibre library (default: ~/Calibre Library)
        title: Book title
        authors: Book authors (comma separated for multiple)
        isbn: Book ISBN
        tags: Book tags (comma separated)
        publisher: Book publisher
        comments: Book description/comments (supports HTML)
        pubdate: Publication date (YYYY-MM-DD format)
        series: Series name
        rating: Rating (0-5)
        language: Language code (e.g., 'eng', 'spa')

    Returns:
        JSON string with result

    Note:
        All parameters are optional - only provide the fields you want to update.
        The comments field can contain HTML for rich text descriptions.
    """
    # Build metadata dict with only non-None values
    metadata = {}
    if title is not None:
        metadata['title'] = title
    if authors is not None:
        metadata['authors'] = authors
    if isbn is not None:
        metadata['isbn'] = isbn
    if tags is not None:
        metadata['tags'] = tags
    if publisher is not None:
        metadata['publisher'] = publisher
    if comments is not None:
        metadata['comments'] = comments
    if pubdate is not None:
        metadata['pubdate'] = pubdate
    if series is not None:
        metadata['series'] = series
    if rating is not None:
        metadata['rating'] = str(rating)
    if language is not None:
        metadata['language'] = language

    success = set_book_metadata(
        book_id,
        library_path=library_path,
        **metadata
    )

    return json.dumps({
        "success": success,
        "book_id": book_id,
        "updated_fields": list(metadata.keys())
    }, indent=2)


@mcp.tool()
def calibre_convert_book(
    book_id: int,
    output_format: str,
    library_path: str = DEFAULT_CALIBRE_LIBRARY
) -> str:
    """
    Convert a book to another format.

    Args:
        book_id: Calibre book ID
        output_format: Output format (e.g., EPUB, MOBI, PDF)
        library_path: Path to Calibre library (default: ~/Calibre Library)

    Returns:
        JSON string with result
    """
    output_path = convert_book(book_id, output_format, library_path)
    return json.dumps({
        "success": True,
        "book_id": book_id,
        "output_format": output_format,
        "output_path": output_path
    }, indent=2)


@mcp.tool()
def calibre_search_library(query: str, library_path: str = DEFAULT_CALIBRE_LIBRARY) -> str:
    """
    Search the Calibre library using Calibre's search syntax.

    Args:
        query: Search query in Calibre syntax
        library_path: Path to Calibre library (default: ~/Calibre Library)

    Returns:
        JSON string with search results
    """
    books = search_library(query, library_path)
    return json.dumps({
        "count": len(books),
        "query": query,
        "books": books
    }, indent=2)


@mcp.tool()
def calibre_bulk_update_comments(
    book_ids: List[int],
    comment_text: str,
    library_path: str = DEFAULT_CALIBRE_LIBRARY
) -> str:
    """
    Update the comments/description field for multiple books at once.

    This is particularly useful for adding generic descriptions to groups of books
    (e.g., magazines, periodicals) to prevent them from being picked up by metadata
    enrichment tools that target books with missing descriptions.

    Args:
        book_ids: List of Calibre book IDs to update (e.g., [1234, 1235, 1236])
        comment_text: The description/comment text to set for all books.
                     Supports HTML formatting.
        library_path: Path to Calibre library (default: ~/Calibre Library)

    Returns:
        JSON string with:
        - success_count: Number of books successfully updated
        - failure_count: Number of books that failed to update
        - total: Total number of books processed
        - updated_ids: List of successfully updated book IDs
        - errors: List of errors (if any), each with book_id and error message

    Example use cases:
        - Add generic description to magazine issues
        - Batch update descriptions for a series
        - Mark books as periodicals/magazines to exclude from enrichment

    Example comment_text:
        "This is a periodical/magazine issue and does not require metadata enrichment."
    """
    results = bulk_update_comments(book_ids, comment_text, library_path)

    return json.dumps({
        "success_count": results['success_count'],
        "failure_count": results['failure_count'],
        "total": len(book_ids),
        "updated_ids": results['updated_ids'],
        "errors": results['errors'] if results['errors'] else None
    }, indent=2)
