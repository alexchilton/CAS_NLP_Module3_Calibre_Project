#!/usr/bin/env python3
"""
Enrich books by title and author when no ISBN is available.

Finds books without ISBNs or descriptions but with good title/author information,
and enriches them using title-based metadata fetching.

Usage:
    python enrich_by_title_sql.py                     # Enrich 10 books
    python enrich_by_title_sql.py --limit 20          # Enrich 20 books
    python enrich_by_title_sql.py --find-only         # Just find candidates
    python enrich_by_title_sql.py --auto-apply        # Auto-apply all updates
"""

import argparse
import sqlite3
import subprocess
import re
from pathlib import Path
from calibre_tools.config import DEFAULT_CALIBRE_LIBRARY
from calibre_tools.cli_wrapper import fetch_ebook_metadata, set_metadata


# Bad author names to skip (only really problematic ones)
BAD_AUTHORS = [
    'welcome.html', 'libgen.li', 'unknown'
]

# Title patterns to skip (non-book content)
BAD_TITLE_PATTERNS = [
    r'PowerPoint',
    r'\.indd$',
    r'^Chapter \d+$',
    r'^Untitled',
    r'^Document\d*$',
    r'^\d{13,}$',  # ISBN as title
    r'^B[A-Z0-9]{9}$',  # ASIN as title
]


def parse_author_sort(author_sort):
    """
    Parse author_sort format (Last, First & Last2, First2) to normal format.

    Args:
        author_sort: Author in "Last, First" format

    Returns:
        Author in "First Last" format
    """
    if not author_sort:
        return ""

    # Handle multiple authors separated by &
    authors = author_sort.split(' & ')
    parsed_authors = []

    for author in authors:
        author = author.strip()
        if ',' in author:
            # Split "Last, First" format
            parts = author.split(',', 1)
            last = parts[0].strip()
            first = parts[1].strip() if len(parts) > 1 else ''

            if first:
                parsed_authors.append(f"{first} {last}")
            else:
                parsed_authors.append(last)
        else:
            # Already in normal format or single name
            parsed_authors.append(author)

    return ' & '.join(parsed_authors)


def is_bad_title(title):
    """Check if title looks like a non-book or bad filename."""
    if not title:
        return True

    for pattern in BAD_TITLE_PATTERNS:
        if re.search(pattern, title, re.IGNORECASE):
            return True

    return False


def is_bad_author(author_sort):
    """Check if author is in the bad authors list."""
    if not author_sort:
        return True

    for bad_author in BAD_AUTHORS:
        if bad_author.lower() in author_sort.lower():
            return True

    return False


def find_books_for_title_enrichment(limit=10, min_title_length=10,
                                     library_path=DEFAULT_CALIBRE_LIBRARY):
    """
    Find books without ISBNs or descriptions but with good title/author info.

    Args:
        limit: Maximum number of books to return
        min_title_length: Minimum title length to consider
        library_path: Path to Calibre library

    Returns:
        List of book dicts with id, title, authors
    """
    db_path = Path(library_path) / 'metadata.db'

    if not db_path.exists():
        raise Exception(f"Database not found at: {db_path}")

    # Build bad authors clause
    bad_authors_clause = " AND ".join([f"b.author_sort NOT LIKE '%{author}%'"
                                       for author in BAD_AUTHORS])

    query = f"""
        SELECT
            b.id,
            b.title,
            b.author_sort as authors
        FROM books b
        LEFT JOIN comments c ON b.id = c.book
        LEFT JOIN identifiers i ON b.id = i.book AND i.type = 'isbn'
        WHERE
            -- No description
            (c.text IS NULL OR c.text = '')
            -- No ISBN
            AND i.val IS NULL
            -- Title not too short
            AND LENGTH(b.title) > ?
            -- Not magazines
            AND (c.text IS NULL OR c.text NOT LIKE '%periodical/magazine issue%')
            -- Exclude bad authors
            AND {bad_authors_clause}
        ORDER BY b.last_modified DESC
        LIMIT ?
    """

    # Execute query in read-only mode
    db_uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(db_uri, uri=True)
    conn.row_factory = sqlite3.Row

    try:
        cursor = conn.cursor()
        cursor.execute(query, (min_title_length, limit))
        rows = cursor.fetchall()

        # Filter out bad titles and authors
        candidates = []
        for row in rows:
            title = row['title']
            author_sort = row['authors']

            # Skip bad titles
            if is_bad_title(title):
                continue

            # Skip bad authors
            if is_bad_author(author_sort):
                continue

            # Parse author to normal format
            author_normal = parse_author_sort(author_sort)

            candidates.append({
                'id': row['id'],
                'title': title,
                'author_sort': author_sort,
                'author_normal': author_normal
            })

        return candidates

    finally:
        conn.close()


def add_isbn_to_book(book_id, isbn, library_path=DEFAULT_CALIBRE_LIBRARY):
    """
    Add ISBN to a book's identifiers.

    Args:
        book_id: Calibre book ID
        isbn: ISBN to add
        library_path: Path to Calibre library

    Returns:
        True if successful, False otherwise
    """
    try:
        cmd = [
            'calibredb', 'set_metadata',
            '--library-path', library_path,
            '--field', f'identifiers:isbn:{isbn}',
            str(book_id)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise Exception(f"Failed to add ISBN: {result.stderr}")

        return True

    except Exception as e:
        print(f"    ✗ Error adding ISBN: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Enrich books by title/author when no ISBN is available'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=10,
        help='Maximum number of books to process (default: 10)'
    )
    parser.add_argument(
        '--find-only',
        action='store_true',
        help='Only find candidates, do not enrich'
    )
    parser.add_argument(
        '--auto-apply',
        action='store_true',
        help='Automatically apply all updates without prompting'
    )
    parser.add_argument(
        '--min-title-length',
        type=int,
        default=10,
        help='Minimum title length (default: 10)'
    )
    parser.add_argument(
        '--library-path',
        type=str,
        default=DEFAULT_CALIBRE_LIBRARY,
        help=f'Path to Calibre library (default: {DEFAULT_CALIBRE_LIBRARY})'
    )

    args = parser.parse_args()

    print("=" * 80)
    print("ENRICH BY TITLE AND AUTHOR")
    print("=" * 80)
    print(f"Library: {args.library_path}")
    print(f"Limit: {args.limit} books")
    print(f"Minimum title length: {args.min_title_length}")
    print()

    # Find candidates
    print("Finding books without ISBNs but with good title/author info (using SQL)...")

    try:
        candidates = find_books_for_title_enrichment(
            limit=args.limit,
            min_title_length=args.min_title_length,
            library_path=args.library_path
        )
    except Exception as e:
        print(f"✗ Error querying database: {e}")
        return

    if not candidates:
        print("✓ No suitable books found for title-based enrichment!")
        return

    print(f"\nFound {len(candidates)} book(s) for title-based enrichment:")
    print("-" * 80)

    for i, book in enumerate(candidates, 1):
        print(f"{i}. ID {book['id']}: {book['title']}")
        print(f"   Author (sort): {book['author_sort']}")
        print(f"   Author (normal): {book['author_normal']}")
        print()

    if args.find_only:
        print("(--find-only mode: not enriching)")
        return

    # Enrich each book
    if not args.auto_apply:
        response = input(f"\nProceed with enriching {len(candidates)} book(s)? [y/N]: ")
        if response.lower() != 'y':
            print("Cancelled.")
            return

    print("\n" + "=" * 80)
    print("ENRICHING BOOKS BY TITLE/AUTHOR")
    print("=" * 80)

    successful = 0
    failed = 0
    no_metadata = 0

    for i, book in enumerate(candidates, 1):
        book_id = book['id']
        title = book['title']
        author_normal = book['author_normal']

        print(f"\n[{i}/{len(candidates)}] Enriching book {book_id}: {title}")
        print(f"Author: {author_normal}")
        print("-" * 80)

        # Fetch metadata by title/author
        # Try with author first, then fall back to title-only if no results
        metadata = None

        # Check if author looks legitimate (not empty, not just garbage)
        has_good_author = author_normal and len(author_normal.strip()) > 2

        if has_good_author:
            print(f"Fetching metadata for '{title}' by '{author_normal}'...")
            try:
                metadata = fetch_ebook_metadata(
                    title=title,
                    authors=author_normal,
                    timeout=30
                )
            except Exception as e:
                print(f"  ⚠ Title+author search failed: {e}")

        # Fall back to title-only if author search failed or no author
        if not metadata:
            if has_good_author:
                print(f"  → Retrying with title only...")
            else:
                print(f"Fetching metadata for '{title}' (title only, no author)...")

            try:
                metadata = fetch_ebook_metadata(
                    title=title,
                    timeout=30
                )
            except Exception as e:
                print(f"✗ Title-only search also failed: {e}")

        try:
            if not metadata:
                print("✗ No metadata found")
                no_metadata += 1
                continue

            print("✓ Fetched metadata:")

            # Determine what to update
            updates = {}
            field_map = {
                'Title': 'title',
                'Author(s)': 'authors',
                'Publisher': 'publisher',
                'Comments': 'comments',
                'Tags': 'tags',
                'Published': 'pubdate',
                'Series': 'series',
                'Rating': 'rating'
            }

            # Track if we found an ISBN
            found_isbn = None

            print("\nAvailable updates:")
            for meta_key, db_field in field_map.items():
                if meta_key in metadata and metadata[meta_key]:
                    value = metadata[meta_key]

                    # Show preview for comments
                    if meta_key == 'Comments':
                        preview = value[:100] + "..." if len(value) > 100 else value
                        print(f"  • {meta_key}: {preview}")
                    else:
                        print(f"  • {meta_key}: {value}")

                    # Only update if we're confident it's the same book
                    # (for title-based search, we skip updating title/author)
                    if db_field not in ['title', 'authors']:
                        updates[db_field] = value

            # Check for ISBN in metadata
            if 'ISBN' in metadata:
                found_isbn = metadata['ISBN'].replace('-', '').replace(' ', '')
                print(f"  • ISBN: {found_isbn}")

            if not updates and not found_isbn:
                print("  (No new metadata available)")
                no_metadata += 1
                continue

            # Apply updates
            if args.auto_apply:
                apply = True
            else:
                update_count = len(updates) + (1 if found_isbn else 0)
                response = input(f"\nApply {update_count} update(s)? [Y/n]: ")
                apply = response.lower() != 'n'

            if apply:
                try:
                    # Add ISBN first if found
                    if found_isbn:
                        print(f"Adding ISBN {found_isbn}...")
                        if add_isbn_to_book(book_id, found_isbn, args.library_path):
                            print(f"  ✓ ISBN added")

                    # Apply other updates
                    if updates:
                        set_metadata(book_id, library_path=args.library_path, **updates)
                        print(f"✓ Applied {len(updates)} update(s) to book {book_id}")

                    successful += 1

                except Exception as e:
                    print(f"✗ Failed to apply updates: {e}")
                    failed += 1
            else:
                print("Skipped")

        except Exception as e:
            print(f"✗ Error fetching metadata: {e}")
            failed += 1
            continue

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total processed: {len(candidates)}")
    print(f"Successful: {successful}")
    print(f"No metadata found: {no_metadata}")
    print(f"Failed: {failed}")
    print()


if __name__ == "__main__":
    main()
