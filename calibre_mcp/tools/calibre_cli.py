# calibre_mcp/tools/calibre_cli.py
import json
from calibre_mcp.server import mcp
from calibre_tools.cli_wrapper import (
    list_books,
    add_book,
    remove_book,
    set_metadata as set_book_metadata,
    convert_book,
    search_library
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
    tags: str = None
) -> str:
    """
    Set metadata for a book in the Calibre library.

    Args:
        book_id: Calibre book ID
        library_path: Path to Calibre library (default: ~/Calibre Library)
        title: Book title
        authors: Book authors
        isbn: Book ISBN
        tags: Book tags (comma separated)

    Returns:
        JSON string with result
    """
    success = set_book_metadata(
        book_id,
        library_path=library_path,
        title=title,
        authors=authors,
        isbn=isbn,
        tags=tags
    )

    return json.dumps({
        "success": success,
        "book_id": book_id
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
