# calibre_mcp/tools/isbn_tools.py
import json
from calibre_mcp.server import mcp
from calibre_tools.isbn_tools import (
    extract_isbn_from_text,
    extract_isbn_from_file,
    find_books_by_isbn,
    validate_isbn,
    get_book_isbn
)
from calibre_tools.config import DEFAULT_CALIBRE_LIBRARY


@mcp.tool()
def calibre_isbn_extract_from_text(text: str) -> str:
    """
    Extract ISBN numbers from text.

    Args:
        text: Text to extract ISBN numbers from

    Returns:
        JSON string with found ISBNs
    """
    isbns = extract_isbn_from_text(text)
    return json.dumps({
        "found": len(isbns) > 0,
        "isbns": isbns
    }, indent=2)


@mcp.tool()
def calibre_isbn_extract_from_file(file_path: str) -> str:
    """
    Extract ISBN numbers from an ebook file.

    Args:
        file_path: Path to ebook file

    Returns:
        JSON string with found ISBNs
    """
    isbns = extract_isbn_from_file(file_path)
    return json.dumps({
        "found": len(isbns) > 0,
        "isbns": isbns,
        "file_path": file_path
    }, indent=2)


@mcp.tool()
def calibre_isbn_validate(isbn: str) -> str:
    """
    Validate an ISBN number.

    Args:
        isbn: ISBN to validate

    Returns:
        JSON string with validation result
    """
    is_valid = validate_isbn(isbn)
    return json.dumps({
        "isbn": isbn,
        "is_valid": is_valid
    }, indent=2)


@mcp.tool()
def calibre_isbn_find_books(isbn: str, library_path: str = DEFAULT_CALIBRE_LIBRARY) -> str:
    """
    Find books with a specific ISBN in your Calibre library.

    Args:
        isbn: ISBN to search for
        library_path: Path to Calibre library (default: ~/Calibre Library)

    Returns:
        JSON string with found books
    """
    books = find_books_by_isbn(isbn, library_path)
    return json.dumps({
        "isbn": isbn,
        "found": len(books) > 0,
        "books": books
    }, indent=2)


@mcp.tool()
def calibre_isbn_get_book_isbn(book_id: int, library_path: str = DEFAULT_CALIBRE_LIBRARY) -> str:
    """
    Get ISBN for a specific book in your Calibre library.

    Args:
        book_id: Calibre book ID
        library_path: Path to Calibre library (default: ~/Calibre Library)

    Returns:
        JSON string with book ISBN
    """
    isbn = get_book_isbn(book_id, library_path)
    return json.dumps({
        "book_id": book_id,
        "found": isbn is not None,
        "isbn": isbn
    }, indent=2)
