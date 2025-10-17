#!/usr/bin/env python3
"""
Batch enrichment script for Calibre library.

Finds books with ISBNs that are missing metadata and enriches them
from online sources (Amazon, Goodreads, Google Books).

Usage:
    python batch_enrich.py                    # Find and enrich 10 books
    python batch_enrich.py --limit 20         # Enrich 20 books
    python batch_enrich.py --find-only        # Just find candidates, don't enrich
    python batch_enrich.py --missing comments # Only books missing descriptions
    python batch_enrich.py --missing all      # Books missing any metadata
"""

import argparse
from calibre_tools.batch_enrichment import (
    find_books_needing_enrichment,
    enrich_single_book
)
from calibre_tools.cli_wrapper import set_metadata


def main():
    parser = argparse.ArgumentParser(
        description='Batch enrich Calibre books with missing metadata'
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
        '--search-all',
        action='store_true',
        help='Search entire library instead of just first batch (slower but more thorough)'
    )

    args = parser.parse_args()

    # Parse missing fields
    if args.missing == 'all':
        missing_fields = ['comments', 'publisher', 'tags', 'series', 'rating']
    else:
        missing_fields = [args.missing]

    print("=" * 60)
    print("CALIBRE BATCH ENRICHMENT")
    print("=" * 60)
    print(f"Limit: {args.limit} books")
    print(f"Missing fields: {', '.join(missing_fields)}")
    if args.search_all:
        print("Mode: Search entire library")
    else:
        print(f"Mode: Search first ~{args.limit * 10} books")
    print()

    # Step 1: Find candidates
    print("Finding books with ISBNs missing metadata...")
    candidates = find_books_needing_enrichment(
        limit=args.limit,
        require_isbn=True,
        missing_fields=missing_fields,
        search_all=args.search_all
    )

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
        result = enrich_single_book(book_id)

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
                set_metadata(book_id, **updates)
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


if __name__ == "__main__":
    main()
