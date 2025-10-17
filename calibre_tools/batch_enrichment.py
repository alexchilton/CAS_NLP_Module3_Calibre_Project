# calibre_tools/batch_enrichment.py
"""
Batch enrichment tools for finding and enriching books with missing metadata
"""
import subprocess
import json
from calibre_tools.config import DEFAULT_CALIBRE_LIBRARY
from calibre_tools.cli_wrapper import list_books, fetch_ebook_metadata
from calibre_tools.isbn_tools import get_book_isbn


def find_books_needing_enrichment(library_path=DEFAULT_CALIBRE_LIBRARY,
                                   limit=10,
                                   require_isbn=True,
                                   missing_fields=None,
                                   search_all=False):
    """
    Find books that are missing metadata and could be enriched.

    Args:
        library_path: Path to Calibre library
        limit: Maximum number of books to return
        require_isbn: If True, only return books that have an ISBN
        missing_fields: List of fields to check (default: ['comments', 'publisher', 'tags'])
        search_all: If True, search entire library (slower but more thorough)

    Returns:
        List of book dictionaries with 'id', 'title', 'authors', 'isbn', 'missing_fields'
    """
    if missing_fields is None:
        missing_fields = ['comments', 'publisher', 'tags']

    # Get a larger batch of books to search through
    # We fetch more than the limit because some won't match our criteria
    if search_all:
        batch_size = None  # Get all books
        all_books = list_books(library_path)
        print(f"Searching entire library ({len(all_books)} books)...")
    else:
        batch_size = min(limit * 10, 500)  # Cap at 500 to avoid overwhelming
        all_books = list_books(library_path, limit=batch_size)

    candidates = []
    checked_count = 0
    max_checks = len(all_books) if search_all else batch_size

    if not search_all:
        print(f"Checking up to {batch_size} books from library...")

    for book in all_books:
        checked_count += 1

        # Progress indicator every 50 books
        if checked_count % 50 == 0:
            print(f"  Checked {checked_count} books, found {len(candidates)} candidates so far...")

        # Stop early if we found enough
        if len(candidates) >= limit:
            print(f"  Found {limit} candidates after checking {checked_count} books.")
            break

        # Stop if we've checked too many (only applies when not search_all)
        if not search_all and checked_count >= max_checks:
            print(f"  Reached check limit of {max_checks} books.")
            break
        book_id = book.get('id')

        # Get full metadata using show_metadata
        from calibre_tools.cli_wrapper import get_book_metadata

        try:
            metadata = get_book_metadata(book_id, library_path)
        except:
            continue

        # Check what fields are missing
        fields_missing = []

        for field in missing_fields:
            # Map field names to metadata keys
            field_key_map = {
                'comments': 'Comments',
                'publisher': 'Publisher',
                'tags': 'Tags',
                'series': 'Series',
                'rating': 'Rating',
                'pubdate': 'Published'
            }

            metadata_key = field_key_map.get(field, field.title())
            value = metadata.get(metadata_key, '')

            if not value or value == '0101-01-01T00:00:00+00:00':  # Empty or default date
                fields_missing.append(field)

        # Skip if no fields are missing
        if not fields_missing:
            continue

        # Try to find ISBN if required
        isbn = None
        if require_isbn:
            # Check identifiers field
            identifiers = metadata.get('Identifiers', '')
            if 'isbn:' in identifiers.lower():
                import re
                match = re.search(r'isbn:([0-9X-]+)', identifiers, re.IGNORECASE)
                if match:
                    isbn = match.group(1).replace('-', '')

            # Skip if no ISBN found and it's required
            if not isbn:
                continue

        # Add to candidates
        candidates.append({
            'id': book_id,
            'title': metadata.get('Title', 'Unknown'),
            'authors': metadata.get('Author(s)', 'Unknown'),
            'isbn': isbn,
            'missing_fields': fields_missing,
            'identifiers': metadata.get('Identifiers', '')
        })

        # Stop if we hit the limit
        if len(candidates) >= limit:
            break

    return candidates


def enrich_single_book(book_id, library_path=DEFAULT_CALIBRE_LIBRARY,
                       identifier_type=None, identifier_value=None):
    """
    Enrich a single book with metadata from online sources.

    Args:
        book_id: Calibre book ID
        library_path: Path to Calibre library
        identifier_type: Optional - 'isbn', 'amazon', 'goodreads'
        identifier_value: Optional - the identifier value

    Returns:
        Dictionary with:
        - success: bool
        - book_id: int
        - fetched_metadata: dict (if successful)
        - error: str (if failed)
    """
    from calibre_tools.cli_wrapper import get_book_metadata

    try:
        # Get existing metadata
        existing = get_book_metadata(book_id, library_path)

        # If no identifier provided, try to auto-detect
        if not identifier_type or not identifier_value:
            import re

            title = existing.get('Title', '')
            identifiers_str = existing.get('Identifiers', '')

            # Try ISBN from identifiers
            if 'isbn:' in identifiers_str.lower():
                match = re.search(r'isbn:([0-9X-]+)', identifiers_str, re.IGNORECASE)
                if match:
                    identifier_type = 'isbn'
                    identifier_value = match.group(1).replace('-', '')

            # Try ASIN from identifiers
            if not identifier_value and 'amazon:' in identifiers_str:
                match = re.search(r'amazon:([A-Z0-9]+)', identifiers_str)
                if match:
                    identifier_type = 'amazon'
                    identifier_value = match.group(1)

            # Try ASIN from title
            if not identifier_value:
                asin_match = re.search(r'\b(B[A-Z0-9]{9})\b', title)
                if asin_match:
                    identifier_type = 'amazon'
                    identifier_value = asin_match.group(1)

            # Try ISBN from title
            if not identifier_value:
                isbn_match = re.search(r'\b(97[89]\d{10})\b', title)
                if isbn_match:
                    identifier_type = 'isbn'
                    identifier_value = isbn_match.group(1)

        # If still no identifier, fail
        if not identifier_value:
            return {
                'success': False,
                'book_id': book_id,
                'error': 'No ISBN or ASIN found'
            }

        # Fetch metadata
        if identifier_type == 'isbn':
            fetched = fetch_ebook_metadata(isbn=identifier_value, timeout=30)
        else:
            fetched = fetch_ebook_metadata(
                identifiers=[f"{identifier_type}:{identifier_value}"],
                timeout=30
            )

        return {
            'success': True,
            'book_id': book_id,
            'identifier_used': f"{identifier_type}:{identifier_value}",
            'existing_metadata': existing,
            'fetched_metadata': fetched
        }

    except Exception as e:
        return {
            'success': False,
            'book_id': book_id,
            'error': str(e)
        }


def batch_enrich_books(book_ids=None, library_path=DEFAULT_CALIBRE_LIBRARY,
                      find_candidates=True, limit=10):
    """
    Batch enrich multiple books.

    Args:
        book_ids: List of book IDs to enrich (optional)
        library_path: Path to Calibre library
        find_candidates: If True and book_ids is None, automatically find books needing enrichment
        limit: Maximum number of books to process

    Returns:
        Dictionary with:
        - total_processed: int
        - successful: int
        - failed: int
        - results: list of enrichment results
    """
    if book_ids is None and find_candidates:
        # Find books that need enrichment
        candidates = find_books_needing_enrichment(
            library_path=library_path,
            limit=limit,
            require_isbn=True
        )
        book_ids = [c['id'] for c in candidates]

    if not book_ids:
        return {
            'total_processed': 0,
            'successful': 0,
            'failed': 0,
            'results': [],
            'message': 'No books to enrich'
        }

    results = []
    successful = 0
    failed = 0

    for book_id in book_ids[:limit]:
        result = enrich_single_book(book_id, library_path)
        results.append(result)

        if result['success']:
            successful += 1
        else:
            failed += 1

    return {
        'total_processed': len(results),
        'successful': successful,
        'failed': failed,
        'results': results
    }
