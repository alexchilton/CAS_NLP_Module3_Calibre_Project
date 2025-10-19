#!/usr/bin/env python3
"""
Enrich books that have identifiers (ISBN, Amazon, ASIN) but missing descriptions.

This script finds books with identifiers but no descriptions and fetches
proper metadata using those identifiers.

Important: Books with no available metadata are tagged with 'metadata-unavailable'
to prevent endless retries. Use --retry-failed to re-attempt these books.

Usage:
    python enrich_by_identifier_sql.py                    # Preview 10 books
    python enrich_by_identifier_sql.py --limit 20         # Preview 20 books
    python enrich_by_identifier_sql.py --find-only        # Just find candidates
    python enrich_by_identifier_sql.py --auto-apply       # Auto-apply all updates
    python enrich_by_identifier_sql.py --retry-failed     # Include previously failed books
"""

import argparse
import sqlite3
import subprocess
from pathlib import Path
from calibre_tools.config import DEFAULT_CALIBRE_LIBRARY
from calibre_tools.cli_wrapper import fetch_ebook_metadata, set_metadata


def find_books_for_identifier_enrichment(limit=10, library_path=DEFAULT_CALIBRE_LIBRARY, retry_failed=False):
    """
    Find books with identifiers (ISBN, Amazon, ASIN) but no descriptions.

    Args:
        limit: Maximum number of books to return
        library_path: Path to Calibre library
        retry_failed: If True, include books tagged as 'metadata-unavailable'

    Returns:
        List of book dicts with id, title, authors, identifier_type, identifier_value
    """
    db_path = Path(library_path) / 'metadata.db'

    if not db_path.exists():
        raise Exception(f"Database not found at: {db_path}")

    # Build query with optional retry_failed clause
    exclude_failed_clause = ""
    if not retry_failed:
        exclude_failed_clause = "AND (t.name IS NULL OR t.name != 'metadata-unavailable')"

    # Use a subquery to get the best identifier per book
    # Priority: ISBN > Amazon > ASIN (ISBN is most reliable)
    query = f"""
        WITH RankedIdentifiers AS (
            SELECT
                b.id,
                b.title,
                b.author_sort as authors,
                i.type as identifier_type,
                i.val as identifier_value,
                CASE
                    WHEN i.type = 'isbn' THEN 1
                    WHEN i.type = 'amazon' THEN 2
                    WHEN i.type = 'asin' THEN 3
                    ELSE 4
                END as priority,
                ROW_NUMBER() OVER (PARTITION BY b.id ORDER BY
                    CASE
                        WHEN i.type = 'isbn' THEN 1
                        WHEN i.type = 'amazon' THEN 2
                        WHEN i.type = 'asin' THEN 3
                        ELSE 4
                    END
                ) as rn
            FROM books b
            LEFT JOIN comments c ON b.id = c.book
            INNER JOIN identifiers i ON b.id = i.book
            LEFT JOIN books_tags_link btl ON b.id = btl.book
            LEFT JOIN tags t ON btl.tag = t.id
            WHERE
                -- No description or empty description
                (c.text IS NULL OR c.text = '')
                -- Has identifier (ISBN, Amazon, or ASIN)
                AND i.type IN ('isbn', 'amazon', 'asin')
                -- Not magazines
                AND (c.text IS NULL OR c.text NOT LIKE '%periodical/magazine issue%')
                -- Optional: Not already marked as metadata-unavailable
                {exclude_failed_clause}
        )
        SELECT
            id,
            title,
            authors,
            identifier_type,
            identifier_value
        FROM RankedIdentifiers
        WHERE rn = 1
        ORDER BY id DESC
        LIMIT ?
    """

    # Execute query in read-only mode
    db_uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(db_uri, uri=True)
    conn.row_factory = sqlite3.Row

    try:
        cursor = conn.cursor()
        cursor.execute(query, (limit,))
        rows = cursor.fetchall()

        candidates = []
        for row in rows:
            candidates.append({
                'id': row['id'],
                'title': row['title'],
                'authors': row['authors'],
                'identifier_type': row['identifier_type'],
                'identifier_value': row['identifier_value']
            })

        return candidates

    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(
        description='Enrich books with identifiers but missing descriptions'
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
        '--library-path',
        type=str,
        default=DEFAULT_CALIBRE_LIBRARY,
        help=f'Path to Calibre library (default: {DEFAULT_CALIBRE_LIBRARY})'
    )
    parser.add_argument(
        '--retry-failed',
        action='store_true',
        help='Include books previously tagged as metadata-unavailable'
    )

    args = parser.parse_args()

    print("=" * 80)
    print("ENRICH BY IDENTIFIER (ISBN/Amazon/ASIN)")
    print("=" * 80)
    print(f"Library: {args.library_path}")
    print(f"Limit: {args.limit} books")
    print()

    # Find candidates
    print("Finding books with identifiers but missing descriptions (using SQL)...")

    try:
        candidates = find_books_for_identifier_enrichment(
            limit=args.limit,
            library_path=args.library_path,
            retry_failed=args.retry_failed
        )
    except Exception as e:
        print(f"✗ Error querying database: {e}")
        return

    if not candidates:
        print("✓ No books found that need identifier-based enrichment!")
        return

    print(f"\nFound {len(candidates)} book(s) for identifier-based enrichment:")
    print("-" * 80)

    for i, book in enumerate(candidates, 1):
        print(f"{i}. ID {book['id']}: {book['title']}")
        print(f"   Authors: {book['authors']}")
        print(f"   Identifier: {book['identifier_type'].upper()} = {book['identifier_value']}")
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
    print("ENRICHING BOOKS BY IDENTIFIER")
    print("=" * 80)

    successful = 0
    failed = 0
    no_metadata = 0

    for i, book in enumerate(candidates, 1):
        book_id = book['id']
        title = book['title']
        identifier_type = book['identifier_type']
        identifier_value = book['identifier_value']

        print(f"\n[{i}/{len(candidates)}] Enriching book {book_id}: {title}")
        print(f"Identifier: {identifier_type.upper()} = {identifier_value}")
        print("-" * 80)

        # Fetch metadata by identifier
        try:
            print(f"Fetching metadata using {identifier_type.upper()}: {identifier_value}...")

            # Different handling for ISBN vs other identifiers
            if identifier_type == 'isbn':
                metadata = fetch_ebook_metadata(isbn=identifier_value, timeout=30)
            else:
                # For Amazon/ASIN, use identifiers parameter with source:value format
                identifiers = [f"{identifier_type}:{identifier_value}"]
                metadata = fetch_ebook_metadata(identifiers=identifiers, timeout=30)

            if not metadata:
                print("✗ No metadata found")
                no_metadata += 1
                continue

            print("✓ Fetched metadata:")

            # DEBUG: Show all metadata fields returned
            print("\n[DEBUG] All metadata fields returned:")
            for key in metadata.keys():
                value = metadata[key]
                if key == 'Comments':
                    preview = value[:100] + "..." if len(value) > 100 else value
                    print(f"  - {key}: {preview}")
                else:
                    print(f"  - {key}: {value}")

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

            print("\nFields we'll update:")
            for meta_key, db_field in field_map.items():
                if meta_key in metadata and metadata[meta_key]:
                    value = metadata[meta_key]

                    # Show preview for comments
                    if meta_key == 'Comments':
                        preview = value[:100] + "..." if len(value) > 100 else value
                        print(f"  • {meta_key}: {preview}")
                    else:
                        print(f"  • {meta_key}: {value}")

                    # For identifier-based search, we can safely update all fields
                    # (identifier uniquely identifies the book)
                    updates[db_field] = value

            if not updates:
                print("  (No new metadata available)")
                no_metadata += 1

                # Add a tag to prevent re-trying this book in the future
                print("  → Marking book as 'metadata-unavailable' to skip in future runs...")
                try:
                    # Get existing tags
                    from calibre_tools.cli_wrapper import get_book_metadata
                    current_metadata = get_book_metadata(book_id, library_path=args.library_path)
                    existing_tags = current_metadata.get('Tags', '')

                    # Add the marker tag
                    if existing_tags:
                        new_tags = f"{existing_tags}, metadata-unavailable"
                    else:
                        new_tags = "metadata-unavailable"

                    set_metadata(book_id, library_path=args.library_path, tags=new_tags)
                    print("  ✓ Tagged as 'metadata-unavailable'")
                except Exception as e:
                    print(f"  ⚠ Could not tag book: {e}")

                continue

            # Apply updates
            if args.auto_apply:
                apply = True
            else:
                response = input(f"\nApply {len(updates)} update(s)? [Y/n]: ")
                apply = response.lower() != 'n'

            if apply:
                try:
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
