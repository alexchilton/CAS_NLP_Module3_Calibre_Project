# calibre_mcp/tools/sql_query.py
"""
Direct SQL query tool for Calibre's metadata.db database.

Provides read-only SQL access to the Calibre library database for advanced queries
and data analysis.
"""

import json
import sqlite3
from pathlib import Path
from calibre_mcp.server import mcp


@mcp.tool()
def calibre_sql(query: str, library_path: str = "/Users/alexchilton/Calibre Library") -> str:
    """
    Execute a read-only SQL query against Calibre's metadata.db database.

    This tool provides direct SQL access to Calibre's SQLite database for advanced
    queries, complex filters, and data analysis that may not be possible with other tools.

    IMPORTANT: Database is opened in read-only mode to prevent corruption.

    Args:
        query: SQL query to execute (SELECT statements only)
        library_path: Path to Calibre library (default: /Users/alexchilton/Library/Calibre Library)

    Returns:
        JSON string with:
        - columns: Array of column names
        - rows: Array of row data (each row is an array of values)
        - row_count: Number of rows returned

    Key Database Tables:
        books - Main book table
            Columns: id, title, sort, timestamp, pubdate, series_index, author_sort,
                    isbn, lccn, path, flags, uuid, has_cover, last_modified

        authors - Author information
            Columns: id, name, sort, link

        books_authors_link - Links books to authors
            Columns: id, book, author

        publishers - Publisher information
            Columns: id, name, sort

        books_publishers_link - Links books to publishers
            Columns: id, book, publisher

        tags - Tags/categories
            Columns: id, name

        books_tags_link - Links books to tags
            Columns: id, book, tag

        comments - Book descriptions/comments
            Columns: id, book, text

        identifiers - ISBNs and other identifiers
            Columns: id, book, type, val
            Common types: 'isbn', 'amazon', 'goodreads', 'google', 'kobo'

        series - Series information
            Columns: id, name, sort

        books_series_link - Links books to series
            Columns: id, book, series

        data - File formats and locations
            Columns: id, book, format, uncompressed_size, name

        languages - Language information
            Columns: id, lang_code

        books_languages_link - Links books to languages
            Columns: id, book, lang_code, item_order

    Example Queries:

        Find all books by a specific author:
        SELECT b.id, b.title, a.name as author
        FROM books b
        JOIN books_authors_link bal ON b.id = bal.book
        JOIN authors a ON bal.author = a.id
        WHERE a.name LIKE '%Tolkien%'

        Find books without ISBNs:
        SELECT b.id, b.title
        FROM books b
        LEFT JOIN identifiers i ON b.id = i.book AND i.type = 'isbn'
        WHERE i.val IS NULL

        Count books by publisher:
        SELECT p.name, COUNT(*) as book_count
        FROM publishers p
        JOIN books_publishers_link bpl ON p.id = bpl.publisher
        GROUP BY p.id
        ORDER BY book_count DESC

        Find books with no description:
        SELECT b.id, b.title
        FROM books b
        LEFT JOIN comments c ON b.id = c.book
        WHERE c.text IS NULL OR c.text = ''

        Get book details with all metadata:
        SELECT b.id, b.title,
               GROUP_CONCAT(DISTINCT a.name) as authors,
               p.name as publisher,
               c.text as description,
               GROUP_CONCAT(DISTINCT t.name) as tags,
               i.val as isbn
        FROM books b
        LEFT JOIN books_authors_link bal ON b.id = bal.book
        LEFT JOIN authors a ON bal.author = a.id
        LEFT JOIN books_publishers_link bpl ON b.id = bpl.publisher
        LEFT JOIN publishers p ON bpl.publisher = p.id
        LEFT JOIN comments c ON b.id = c.book
        LEFT JOIN books_tags_link btl ON b.id = btl.book
        LEFT JOIN tags t ON btl.tag = t.id
        LEFT JOIN identifiers i ON b.id = i.book AND i.type = 'isbn'
        WHERE b.id = 1762
        GROUP BY b.id

    Security Notes:
        - Database opened in read-only mode (uri parameter with mode=ro)
        - Only SELECT queries recommended
        - No transactions or modifications allowed
        - Connection closed immediately after query
    """
    try:
        # Construct database path
        db_path = Path(library_path) / "metadata.db"

        # Check if database exists
        if not db_path.exists():
            return json.dumps({
                "error": f"Database not found at: {db_path}",
                "hint": "Check that library_path is correct"
            }, indent=2)

        # Open database in read-only mode
        # Use URI mode to ensure read-only access
        db_uri = f"file:{db_path}?mode=ro"
        conn = sqlite3.connect(db_uri, uri=True)
        conn.row_factory = sqlite3.Row  # Enable column access by name

        try:
            cursor = conn.cursor()
            cursor.execute(query)

            # Get column names
            if cursor.description:
                columns = [desc[0] for desc in cursor.description]
            else:
                columns = []

            # Fetch all rows
            rows = cursor.fetchall()

            # Convert rows to list of lists (JSON serializable)
            row_data = [list(row) for row in rows]

            result = {
                "columns": columns,
                "rows": row_data,
                "row_count": len(row_data)
            }

            return json.dumps(result, indent=2, default=str)

        except sqlite3.Error as e:
            return json.dumps({
                "error": f"SQL execution error: {str(e)}",
                "query": query,
                "hint": "Check SQL syntax and table/column names"
            }, indent=2)

        finally:
            conn.close()

    except sqlite3.Error as e:
        return json.dumps({
            "error": f"Database connection error: {str(e)}",
            "library_path": library_path,
            "db_path": str(db_path) if 'db_path' in locals() else None
        }, indent=2)

    except Exception as e:
        return json.dumps({
            "error": f"Unexpected error: {str(e)}",
            "type": type(e).__name__
        }, indent=2)
