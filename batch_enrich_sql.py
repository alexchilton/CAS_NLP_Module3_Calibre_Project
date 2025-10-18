#!/usr/bin/env python3
"""
Batch enrichment script for Calibre library using direct SQL queries.

This version uses direct SQL queries against metadata.db to find candidate books,
which is much faster than the CLI-based batch_enrich.py script.

Usage:
    python batch_enrich_sql.py                    # Find and enrich 10 books
    python batch_enrich_sql.py --limit 20         # Enrich 20 books
    python batch_enrich_sql.py --find-only        # Just find candidates, don't enrich
    python batch_enrich_sql.py --missing comments # Only books missing descriptions
    python batch_enrich_sql.py --missing all      # Books missing any metadata
"""

import argparse
import sqlite3
import os
from pathlib import Path
from calibre_tools.batch_enrichment import enrich_single_book
from calibre_tools.cli_wrapper import set_metadata
from calibre_tools.config import DEFAULT_CALIBRE_LIBRARY


def find_books_with_sql(limit=10, missing_fields=['comments'],
                        library_path=DEFAULT_CALIBRE_LIBRARY):
    """
    Find books needing enrichment using direct SQL query.

    This is much faster than using calibredb CLI calls, especially for large libraries.

    Args:
        limit: Maximum number of books to return
        missing_fields: List of fields to check (comments, publisher, tags, series, rating)
        library_path: Path to Calibre library

    Returns:
        List of dicts with book info (id, title, authors, isbn, missing_fields)
    """
    db_path = Path(library_path) / 'metadata.db'

    if not db_path.exists():
        raise Exception(f"Database not found at: {db_path}")

    # Build WHERE clause conditions based on missing fields
    conditions = []

    for field in missing_fields:
        if field == 'comments':
            conditions.append("(c.text IS NULL OR c.text = '')")
        elif field == 'publisher':
            conditions.append("(bpl.id IS NULL)")
        elif field == 'tags':
            conditions.append("(btl.id IS NULL)")
        elif field == 'series':
            conditions.append("(bsl.id IS NULL)")
        elif field == 'rating':
            # Calibre stores ratings 1-10 (displayed as 1-5 stars * 2)
            # NULL or 0 means no rating
            conditions.append("(r.rating IS NULL OR r.rating = 0)")

    # Combine conditions with OR (book is missing ANY of the specified fields)
    if conditions:
        missing_clause = '(' + ' OR '.join(conditions) + ')'
    else:
        missing_clause = '1=1'  # Always true if no fields specified

    # Build the SQL query
    query = f"""
        SELECT DISTINCT
            b.id,
            b.title,
            b.author_sort as authors,
            i.val as isbn,
            CASE WHEN c.text IS NULL OR c.text = '' THEN 'comments' ELSE NULL END as missing_comments,
            CASE WHEN bpl.id IS NULL THEN 'publisher' ELSE NULL END as missing_publisher,
            CASE WHEN btl.id IS NULL THEN 'tags' ELSE NULL END as missing_tags,
            CASE WHEN bsl.id IS NULL THEN 'series' ELSE NULL END as missing_series,
            CASE WHEN r.rating IS NULL OR r.rating = 0 THEN 'rating' ELSE NULL END as missing_rating
        FROM books b
        INNER JOIN identifiers i ON b.id = i.book AND i.type = 'isbn'
        LEFT JOIN comments c ON b.id = c.book
        LEFT JOIN books_publishers_link bpl ON b.id = bpl.book
        LEFT JOIN books_tags_link btl ON b.id = btl.book
        LEFT JOIN books_series_link bsl ON b.id = bsl.book
        LEFT JOIN (
            -- Calibre has ratings stored separately, need to aggregate
            SELECT brl.book, MAX(rat.rating) as rating
            FROM books_ratings_link brl
            JOIN ratings rat ON brl.rating = rat.id
            GROUP BY brl.book
        ) r ON b.id = r.book
        WHERE {missing_clause}
            -- Exclude magazines/periodicals
            AND (c.text IS NULL OR c.text NOT LIKE '%periodical/magazine issue%')
        ORDER BY b.last_modified DESC
        LIMIT ?
    """

    # Execute query in read-only mode
    db_uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(db_uri, uri=True)
    conn.row_factory = sqlite3.Row  # Enable column access by name

    try:
        cursor = conn.cursor()
        cursor.execute(query, (limit,))
        rows = cursor.fetchall()

        # Convert to list of dicts matching the format of find_books_needing_enrichment()
        candidates = []
        for row in rows:
            # Collect which fields are actually missing
            book_missing_fields = []
            for field_check in ['missing_comments', 'missing_publisher', 'missing_tags',
                               'missing_series', 'missing_rating']:
                if row[field_check]:
                    book_missing_fields.append(row[field_check])

            candidates.append({
                'id': row['id'],
                'title': row['title'],
                'authors': row['authors'] or 'Unknown',
                'isbn': row['isbn'],
                'missing_fields': book_missing_fields
            })

        return candidates

    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(
        description='Batch enrich Calibre books with missing metadata (SQL version - faster)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=10,
        help='Maximum number of books to process (default: 10)'
    )
    parser.add_argument(
        '--missing',
        type=str,
        default='comments',
        choices=['comments', 'publisher', 'tags', 'series', 'rating', 'all'],
        help='Which field to check for missing data (default: comments/description)'
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
        '--refresh-search',
        action='store_true',
        help='Refresh semantic search cache after enrichment'
    )

    args = parser.parse_args()

    # Parse missing fields
    if args.missing == 'all':
        missing_fields = ['comments', 'publisher', 'tags', 'series', 'rating']
    else:
        missing_fields = [args.missing]

    print("=" * 60)
    print("CALIBRE BATCH ENRICHMENT (SQL VERSION)")
    print("=" * 60)
    print(f"Library: {args.library_path}")
    print(f"Limit: {args.limit} books")
    print(f"Missing fields: {', '.join(missing_fields)}")
    print()

    # Step 1: Find candidates using SQL
    print("Finding books with ISBNs missing metadata (using SQL)...")

    try:
        candidates = find_books_with_sql(
            limit=args.limit,
            missing_fields=missing_fields,
            library_path=args.library_path
        )
    except Exception as e:
        print(f"✗ Error querying database: {e}")
        return

    if not candidates:
        print("✓ No books found needing enrichment!")
        return

    print(f"\nFound {len(candidates)} book(s) needing enrichment:")
    print("-" * 60)

    for i, book in enumerate(candidates, 1):
        print(f"{i}. ID {book['id']}: {book['title']}")
        print(f"   Authors: {book['authors']}")
        print(f"   ISBN: {book['isbn']}")
        print(f"   Missing: {', '.join(book['missing_fields'])}")
        print()

    if args.find_only:
        print("(--find-only mode: not enriching)")
        return

    # Step 2: Enrich each book
    if not args.auto_apply:
        response = input(f"\nProceed with enriching {len(candidates)} book(s)? [y/N]: ")
        if response.lower() != 'y':
            print("Cancelled.")
            return

    print("\n" + "=" * 60)
    print("ENRICHING BOOKS")
    print("=" * 60)

    successful = 0
    failed = 0

    for i, book in enumerate(candidates, 1):
        book_id = book['id']

        print(f"\n[{i}/{len(candidates)}] Enriching book {book_id}: {book['title']}")
        print("-" * 60)

        # Fetch metadata
        result = enrich_single_book(book_id, library_path=args.library_path)

        if not result['success']:
            print(f"✗ Failed: {result['error']}")
            failed += 1
            continue

        print(f"✓ Fetched metadata using: {result['identifier_used']}")

        fetched = result['fetched_metadata']
        existing = result['existing_metadata']

        # Determine what to update
        updates = {}

        # Field mapping from fetched to calibredb field names
        field_map = {
            'Comments': ('comments', 'Description'),
            'Publisher': ('publisher', 'Publisher'),
            'Series': ('series', 'Series'),
            'Rating': ('rating', 'Rating'),
            'Tags': ('tags', 'Tags'),
            'Published': ('pubdate', 'Publication Date')
        }

        print("\nAvailable updates:")
        for fetched_key, (db_field, display_name) in field_map.items():
            if fetched_key in fetched and fetched[fetched_key]:
                existing_value = existing.get(fetched_key, '')

                # Skip if already has value
                if existing_value and existing_value != '0101-01-01T00:00:00+00:00':
                    continue

                fetched_value = fetched[fetched_key]

                # Show preview
                if fetched_key == 'Comments':
                    preview = fetched_value[:100] + "..." if len(fetched_value) > 100 else fetched_value
                    print(f"  • {display_name}: {preview}")
                else:
                    print(f"  • {display_name}: {fetched_value}")

                updates[db_field] = fetched_value

        if not updates:
            print("  (No new metadata available)")
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

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total processed: {len(candidates)}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"Skipped: {len(candidates) - successful - failed}")
    print()

    # Refresh semantic search cache if requested
    if args.refresh_search and successful > 0:
        print("=" * 60)
        print("REFRESHING SEMANTIC SEARCH CACHE")
        print("=" * 60)
        print("Updating embeddings with new metadata...")

        try:
            os.environ['FORCE_REFRESH'] = '1'

            from calibre_tools.semantic_search import search

            # Trigger cache rebuild by doing a simple search
            search("test", top_n=1)

            print("✓ Semantic search cache refreshed successfully!")
            print(f"  Updated {successful} book(s) with new metadata")
        except Exception as e:
            print(f"✗ Failed to refresh cache: {e}")
            print("  You can manually refresh by running:")
            print("  FORCE_REFRESH=1 python -c \"from calibre_tools.semantic_search import search; search('test', 1)\"")

        print()


if __name__ == "__main__":
    main()
