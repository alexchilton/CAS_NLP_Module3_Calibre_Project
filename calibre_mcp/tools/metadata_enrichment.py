# calibre_mcp/tools/metadata_enrichment.py
import json
from calibre_mcp.server import mcp
from calibre_tools.cli_wrapper import fetch_ebook_metadata


@mcp.tool()
def calibre_fetch_metadata_by_identifier(identifier_type: str, identifier_value: str) -> str:
    """
    Fetch book metadata from online sources using an identifier.

    This tool queries Amazon, Goodreads, Google Books, and other sources
    to retrieve rich metadata including descriptions, ratings, series info, etc.

    Supported identifier types:
    - amazon: Amazon ASIN (e.g., "B004XFYWNY")
    - goodreads: Goodreads book ID (e.g., "39799149")
    - isbn: ISBN-10 or ISBN-13 (e.g., "9780547928227")

    Args:
        identifier_type: Type of identifier (amazon, goodreads, isbn)
        identifier_value: The identifier value

    Returns:
        JSON string with complete metadata from online sources

    Examples:
        - identifier_type="amazon", identifier_value="B004XFYWNY"
        - identifier_type="goodreads", identifier_value="39799149"
        - identifier_type="isbn", identifier_value="9780547928227"
    """
    try:
        # Build identifier string
        if identifier_type.lower() == "isbn":
            # ISBN can be passed directly
            metadata = fetch_ebook_metadata(isbn=identifier_value, timeout=30)
        else:
            # Other identifiers use the identifier format
            identifier = f"{identifier_type}:{identifier_value}"
            metadata = fetch_ebook_metadata(identifiers=[identifier], timeout=30)

        return json.dumps(metadata, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


@mcp.tool()
def calibre_fetch_metadata_by_title(title: str, authors: str = None) -> str:
    """
    Fetch book metadata from online sources using title and optional author.

    This tool searches Amazon, Goodreads, Google Books, and other sources
    to retrieve rich metadata for a book.

    Args:
        title: Book title to search for
        authors: Optional author name(s) to narrow search

    Returns:
        JSON string with complete metadata from online sources

    Examples:
        - title="The Hobbit", authors="J.R.R. Tolkien"
        - title="Foundation"
    """
    try:
        metadata = fetch_ebook_metadata(
            title=title,
            authors=authors,
            timeout=30
        )
        return json.dumps(metadata, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


@mcp.tool()
def calibre_enrich_book_metadata(book_id: int, identifier_type: str = None,
                                 identifier_value: str = None) -> str:
    """
    Enrich a book's metadata by fetching additional information from online sources.

    This tool AUTOMATICALLY detects and uses identifiers from:
    - Book title (ASIN like "B004XFYWNY", ISBN-13, ISBN-10)
    - Identifiers field (amazon:, isbn:, goodreads:)

    Or you can manually provide an identifier.

    Auto-detection priority:
    1. ASIN in title (e.g., "B004XFYWNY")
    2. ISBN-13 in title (e.g., "9780547928227")
    3. ISBN-10 in title (e.g., "0547928227")
    4. ASIN in identifiers field (amazon:B004XFYWNY)
    5. ISBN in identifiers field (isbn:9780547928227)
    6. Goodreads ID in identifiers field (goodreads:39799149)

    Args:
        book_id: The Calibre book ID to enrich
        identifier_type: Optional - type of identifier to use (amazon, goodreads, isbn)
        identifier_value: Optional - the identifier value

    Returns:
        JSON string with:
        - existing_metadata: Current metadata from Calibre
        - fetched_metadata: New metadata from online sources
        - suggested_updates: Fields that could be updated
        - identifier_used: (if auto-detected) Which identifier was found and used

    Example workflow:
        1. Use calibre_get_book_details to see current metadata
        2. Use calibre_enrich_book_metadata to fetch online data (auto-detects identifiers!)
        3. Use calibre_update_metadata to apply selected updates
    """
    from calibre_tools.cli_wrapper import get_book_metadata

    try:
        # Get existing metadata
        existing = get_book_metadata(book_id)

        # Fetch new metadata
        if identifier_type and identifier_value:
            # Use provided identifier
            if identifier_type.lower() == "isbn":
                fetched = fetch_ebook_metadata(isbn=identifier_value, timeout=30)
            else:
                identifier = f"{identifier_type}:{identifier_value}"
                fetched = fetch_ebook_metadata(identifiers=[identifier], timeout=30)
        else:
            # Auto-detect identifiers from existing metadata
            import re

            title = existing.get('Title', '')
            identifiers_str = existing.get('Identifiers', '')

            # Helper function to try fetching metadata with fallback
            def try_fetch(identifier_list, source):
                try:
                    return fetch_ebook_metadata(identifiers=identifier_list, timeout=30), source
                except:
                    return None, source

            fetched = None
            used_source = None

            # Priority 1: Check title for ASIN (10 characters, alphanumeric, starts with B)
            asin_in_title = re.search(r'\b(B[A-Z0-9]{9})\b', title)
            if asin_in_title:
                asin = asin_in_title.group(1)
                fetched, used_source = try_fetch([f"amazon:{asin}"], f"ASIN from title: {asin}")

            # Priority 2: Check title for ISBN-13 (13 digits, starts with 978 or 979)
            if not fetched:
                isbn13_in_title = re.search(r'\b(97[89]\d{10})\b', title)
                if isbn13_in_title:
                    isbn = isbn13_in_title.group(1)
                    fetched, used_source = try_fetch([], f"ISBN-13 from title: {isbn}")
                    if not fetched:
                        # Try directly with ISBN
                        try:
                            fetched = fetch_ebook_metadata(isbn=isbn, timeout=30)
                            used_source = f"ISBN-13 from title: {isbn}"
                        except:
                            pass

            # Priority 3: Check title for ISBN-10 (10 characters)
            if not fetched:
                isbn10_in_title = re.search(r'\b(\d{9}[\dX])\b', title)
                if isbn10_in_title:
                    isbn = isbn10_in_title.group(1)
                    try:
                        fetched = fetch_ebook_metadata(isbn=isbn, timeout=30)
                        used_source = f"ISBN-10 from title: {isbn}"
                    except:
                        pass

            # Priority 4: Check identifiers field for ASIN
            if not fetched and 'amazon:' in identifiers_str:
                match = re.search(r'amazon:([A-Z0-9]+)', identifiers_str)
                if match:
                    asin = match.group(1)
                    fetched, used_source = try_fetch([f"amazon:{asin}"], f"ASIN from identifiers: {asin}")

            # Priority 5: Check identifiers field for ISBN
            if not fetched and 'isbn:' in identifiers_str.lower():
                match = re.search(r'isbn:([0-9X-]+)', identifiers_str, re.IGNORECASE)
                if match:
                    isbn = match.group(1).replace('-', '')
                    try:
                        fetched = fetch_ebook_metadata(isbn=isbn, timeout=30)
                        used_source = f"ISBN from identifiers: {isbn}"
                    except:
                        pass

            # Priority 6: Check identifiers field for Goodreads ID
            if not fetched and 'goodreads:' in identifiers_str:
                match = re.search(r'goodreads:(\d+)', identifiers_str)
                if match:
                    gr_id = match.group(1)
                    fetched, used_source = try_fetch([f"goodreads:{gr_id}"], f"Goodreads ID from identifiers: {gr_id}")

            # If nothing worked, return error
            if not fetched:
                return json.dumps({
                    "error": "No suitable identifiers found. Please provide identifier_type and identifier_value.",
                    "existing_title": title,
                    "existing_identifiers": identifiers_str,
                    "hint": "Look for ASIN (starts with B), ISBN, or use identifier_type/identifier_value parameters"
                }, indent=2)

        # Compare and suggest updates
        suggested_updates = {}

        # Check for missing or different fields
        field_mapping = {
            'Title': 'Title',
            'Author(s)': 'Authors',
            'Publisher': 'Publisher',
            'Published': 'Published',
            'Series': 'Series',
            'Rating': 'Rating',
            'Tags': 'Tags',
            'Comments': 'Comments'
        }

        for existing_key, fetched_key in field_mapping.items():
            existing_value = existing.get(existing_key, '')
            fetched_value = fetched.get(fetched_key, '')

            if fetched_value and not existing_value:
                suggested_updates[existing_key] = {
                    "current": existing_value,
                    "suggested": fetched_value,
                    "reason": "Missing in Calibre"
                }
            elif fetched_value and fetched_value != existing_value:
                suggested_updates[existing_key] = {
                    "current": existing_value,
                    "suggested": fetched_value,
                    "reason": "Different from online source"
                }

        result = {
            "book_id": book_id,
            "existing_metadata": existing,
            "fetched_metadata": fetched,
            "suggested_updates": suggested_updates
        }

        # Add source information if auto-detected
        if not (identifier_type and identifier_value) and used_source:
            result["identifier_used"] = used_source

        return json.dumps(result, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


@mcp.tool()
def calibre_apply_metadata_updates(book_id: int, fields_to_update: str) -> str:
    """
    Apply metadata updates to a book in Calibre after reviewing suggested changes.

    This is typically used after calibre_enrich_book_metadata shows you suggested updates.
    You can choose which fields to update.

    Args:
        book_id: The Calibre book ID to update
        fields_to_update: Comma-separated list of field names to update, or "all"
                         Examples: "Publisher,Series,Rating" or "all"

    Returns:
        JSON string with:
        - book_id: The book that was updated
        - fields_updated: List of fields that were successfully updated
        - status: "success" or "partial" if some failed

    Important:
        This tool requires the enrichment data to be fetched first with
        calibre_enrich_book_metadata. The suggested updates will be applied.

    Example workflow:
        1. calibre_enrich_book_metadata(1762) → shows suggested updates
        2. User reviews and says "update the publisher and series"
        3. calibre_apply_metadata_updates(1762, "Publisher,Series")
        4. Returns confirmation of updates applied
    """
    from calibre_tools.cli_wrapper import set_metadata, get_book_metadata

    try:
        # Get the enrichment data (this would ideally be cached, but for now we'll
        # fetch it again to get the suggested updates)
        # In a real implementation, you'd want to pass the updates as a parameter

        result = json.loads(calibre_enrich_book_metadata(book_id))

        if "error" in result:
            return json.dumps({
                "error": "Could not fetch enrichment data. Run calibre_enrich_book_metadata first.",
                "details": result["error"]
            }, indent=2)

        suggested_updates = result.get("suggested_updates", {})

        if not suggested_updates:
            return json.dumps({
                "book_id": book_id,
                "message": "No updates suggested. Book metadata is already up to date.",
                "status": "no_updates_needed"
            }, indent=2)

        # Parse fields to update
        if fields_to_update.lower() == "all":
            fields_list = list(suggested_updates.keys())
        else:
            fields_list = [f.strip() for f in fields_to_update.split(",")]

        # Apply updates
        updated_fields = []
        failed_fields = []

        # Map Calibre field names to calibredb field names
        field_name_mapping = {
            'Title': 'title',
            'Author(s)': 'authors',
            'Publisher': 'publisher',
            'Published': 'pubdate',
            'Series': 'series',
            'Rating': 'rating',
            'Tags': 'tags',
            'Comments': 'comments'
        }

        metadata_updates = {}

        for field in fields_list:
            if field in suggested_updates:
                suggested_value = suggested_updates[field]["suggested"]
                calibredb_field = field_name_mapping.get(field, field.lower())

                metadata_updates[calibredb_field] = suggested_value
                updated_fields.append(field)
            else:
                failed_fields.append(f"{field} (not in suggested updates)")

        # Apply all updates at once
        if metadata_updates:
            try:
                set_metadata(book_id, **metadata_updates)
            except Exception as e:
                return json.dumps({
                    "error": f"Failed to update metadata: {str(e)}",
                    "book_id": book_id
                }, indent=2)

        status = "success" if not failed_fields else "partial"

        return json.dumps({
            "book_id": book_id,
            "status": status,
            "fields_updated": updated_fields,
            "fields_failed": failed_fields if failed_fields else None,
            "message": f"Successfully updated {len(updated_fields)} field(s)"
        }, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


@mcp.tool()
def calibre_find_books_needing_enrichment(limit: int = 10, missing_field: str = "comments") -> str:
    """
    Find books in your library that are missing metadata and have ISBNs.

    This tool scans your library for books that:
    - Have an ISBN (can be enriched from online sources)
    - Are missing specific metadata fields (description, publisher, tags, etc.)

    Args:
        limit: Maximum number of books to return (default: 10)
        missing_field: Which field to check: "comments" (description), "publisher",
                      "tags", "series", "rating", or "all" to check multiple

    Returns:
        JSON string with:
        - total_found: Number of books found
        - books: List of books with their IDs, titles, ISBNs, and missing fields

    Example:
        Find 10 books missing descriptions:
        → calibre_find_books_needing_enrichment(10, "comments")

        Find books missing any metadata:
        → calibre_find_books_needing_enrichment(20, "all")
    """
    from calibre_tools.batch_enrichment import find_books_needing_enrichment

    try:
        # Parse missing_field parameter
        if missing_field == "all":
            fields_to_check = ['comments', 'publisher', 'tags', 'series', 'rating']
        else:
            fields_to_check = [missing_field]

        candidates = find_books_needing_enrichment(
            limit=limit,
            require_isbn=True,
            missing_fields=fields_to_check
        )

        return json.dumps({
            "total_found": len(candidates),
            "books": candidates,
            "message": f"Found {len(candidates)} book(s) with ISBNs missing {missing_field}"
        }, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


@mcp.tool()
def calibre_batch_enrich_books(limit: int = 10) -> str:
    """
    Automatically find and enrich multiple books with missing metadata.

    This tool:
    1. Finds books with ISBNs that are missing metadata
    2. Fetches metadata from online sources for each book
    3. Returns the enrichment results for review

    After reviewing the results, use calibre_apply_metadata_updates to apply changes.

    Args:
        limit: Maximum number of books to process (default: 10, max: 50)

    Returns:
        JSON string with:
        - total_processed: Number of books processed
        - successful: Number of successful enrichments
        - failed: Number of failed enrichments
        - results: Detailed results for each book

    Example workflow:
        1. calibre_batch_enrich_books(10) → Fetches metadata for 10 books
        2. Review the results
        3. calibre_apply_metadata_updates(book_id, "all") → Apply updates one by one
    """
    from calibre_tools.batch_enrichment import batch_enrich_books

    try:
        # Cap limit at 50 to avoid overwhelming the system
        limit = min(limit, 50)

        results = batch_enrich_books(
            find_candidates=True,
            limit=limit
        )

        return json.dumps(results, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)
