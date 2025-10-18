#!/usr/bin/env python3
"""
Extract ISBNs from book files and enrich metadata.

Finds books without ISBNs in the Calibre library, extracts ISBNs from their
ebook files, and optionally enriches them with metadata from online sources.

Usage:
    python extract_and_enrich_isbns.py                    # Process 10 books
    python extract_and_enrich_isbns.py --limit 20         # Process 20 books
    python extract_and_enrich_isbns.py --find-only        # Just extract ISBNs, don't enrich
    python extract_and_enrich_isbns.py --missing-description  # Only books without descriptions
    python extract_and_enrich_isbns.py --formats EPUB,PDF # Only scan EPUB and PDF files
"""

import argparse
import sqlite3
import os
import subprocess
from pathlib import Path
from calibre_tools.config import DEFAULT_CALIBRE_LIBRARY
from calibre_tools.isbn_tools import extract_isbn_from_file
from calibre_tools.cli_wrapper import fetch_ebook_metadata, set_metadata


def find_books_without_isbn(limit=10, missing_description=False,
                            formats=['EPUB', 'PDF', 'MOBI', 'AZW3'],
                            library_path=DEFAULT_CALIBRE_LIBRARY):
    """
    Find books without ISBNs using direct SQL query.

    Args:
        limit: Maximum number of books to return
        missing_description: Only return books missing descriptions
        formats: List of file formats to scan
        library_path: Path to Calibre library

    Returns:
        List of dicts with book info (id, title, authors, file_path, format)
    """
    db_path = Path(library_path) / 'metadata.db'

    if not db_path.exists():
        raise Exception(f"Database not found at: {db_path}")

    # Build format clause
    format_placeholders = ','.join('?' * len(formats))
    format_clause = f"d.format IN ({format_placeholders})"

    # Build missing description clause
    if missing_description:
        description_clause = "AND (c.text IS NULL OR c.text = '')"
    else:
        description_clause = ""

    # Build the SQL query
    query = f"""
        SELECT DISTINCT
            b.id,
            b.title,
            b.author_sort as authors,
            b.path,
            d.name as filename,
            d.format,
            CASE WHEN c.text IS NULL OR c.text = '' THEN 1 ELSE 0 END as missing_description
        FROM books b
        JOIN data d ON b.id = d.book
        LEFT JOIN identifiers i ON b.id = i.book AND i.type = 'isbn'
        LEFT JOIN comments c ON b.id = c.book
        WHERE
            i.val IS NULL
            AND {format_clause}
            {description_clause}
            -- Exclude magazines/periodicals
            AND (c.text IS NULL OR c.text NOT LIKE '%periodical/magazine issue%')
        ORDER BY b.last_modified DESC
        LIMIT ?
    """

    # Execute query in read-only mode
    db_uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(db_uri, uri=True)
    conn.row_factory = sqlite3.Row

    try:
        cursor = conn.cursor()
        cursor.execute(query, (*formats, limit))
        rows = cursor.fetchall()

        # Convert to list of dicts
        candidates = []
        for row in rows:
            # Build full file path
            file_path = Path(library_path) / row['path'] / f"{row['filename']}.{row['format'].lower()}"

            candidates.append({
                'id': row['id'],
                'title': row['title'],
                'authors': row['authors'] or 'Unknown',
                'format': row['format'],
                'file_path': str(file_path),
                'missing_description': bool(row['missing_description'])
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
        description='Extract ISBNs from book files and enrich metadata'
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
        help='Only extract ISBNs, do not enrich with metadata'
    )
    parser.add_argument(
        '--auto-apply',
        action='store_true',
        help='Automatically apply all updates without prompting'
    )
    parser.add_argument(
        '--missing-description',
        action='store_true',
        help='Only process books without descriptions'
    )
    parser.add_argument(
        '--formats',
        type=str,
        default='EPUB,PDF,MOBI,AZW3',
        help='Comma-separated list of formats to scan (default: EPUB,PDF,MOBI,AZW3)'
    )
    parser.add_argument(
        '--library-path',
        type=str,
        default=DEFAULT_CALIBRE_LIBRARY,
        help=f'Path to Calibre library (default: {DEFAULT_CALIBRE_LIBRARY})'
    )

    args = parser.parse_args()

    # Parse formats
    formats = [f.strip().upper() for f in args.formats.split(',')]

    print("=" * 60)
    print("EXTRACT AND ENRICH ISBNs")
    print("=" * 60)
    print(f"Library: {args.library_path}")
    print(f"Limit: {args.limit} books")
    print(f"Formats: {', '.join(formats)}")
    if args.missing_description:
        print("Filter: Only books without descriptions")
    print()

    # Step 1: Find books without ISBNs
    print("Finding books without ISBNs (using SQL)...")

    try:
        candidates = find_books_without_isbn(
            limit=args.limit,
            missing_description=args.missing_description,
            formats=formats,
            library_path=args.library_path
        )
    except Exception as e:
        print(f"✗ Error querying database: {e}")
        return

    if not candidates:
        print("✓ No books found without ISBNs!")
        return

    print(f"\nFound {len(candidates)} book(s) without ISBNs:")
    print("-" * 60)

    for i, book in enumerate(candidates, 1):
        desc_status = "no description" if book['missing_description'] else "has description"
        print(f"{i}. ID {book['id']}: {book['title']}")
        print(f"   Authors: {book['authors']}")
        print(f"   Format: {book['format']} ({desc_status})")
        print(f"   File: {book['file_path']}")
        print()

    # Step 2: Extract ISBNs from files
    if not args.auto_apply and not args.find_only:
        response = input(f"\nProceed with extracting ISBNs from {len(candidates)} book(s)? [y/N]: ")
        if response.lower() != 'y':
            print("Cancelled.")
            return

    print("\n" + "=" * 60)
    print("EXTRACTING ISBNs")
    print("=" * 60)

    extracted_count = 0
    enriched_count = 0
    failed_count = 0
    extraction_results = []

    for i, book in enumerate(candidates, 1):
        book_id = book['id']

        print(f"\n[{i}/{len(candidates)}] Processing book {book_id}: {book['title']}")
        print("-" * 60)

        # Check if file exists
        if not Path(book['file_path']).exists():
            print(f"✗ File not found: {book['file_path']}")
            failed_count += 1
            continue

        # Extract ISBN from file
        print(f"Extracting ISBN from {book['format']} file...")
        try:
            isbns = extract_isbn_from_file(book['file_path'])

            if not isbns:
                print("✗ No ISBN found in file")
                failed_count += 1
                continue

            isbn = isbns[0]  # Use first ISBN found
            print(f"✓ Found ISBN: {isbn}")

            # Add ISBN to book
            print(f"Adding ISBN to book {book_id}...")
            if add_isbn_to_book(book_id, isbn, args.library_path):
                print(f"✓ ISBN added successfully")
                extracted_count += 1

                extraction_results.append({
                    'book_id': book_id,
                    'title': book['title'],
                    'isbn': isbn,
                    'extracted': True
                })
            else:
                print(f"✗ Failed to add ISBN")
                failed_count += 1
                continue

        except Exception as e:
            print(f"✗ Error extracting ISBN: {e}")
            failed_count += 1
            continue

        # Step 3: Enrich with metadata (if not find-only mode)
        if not args.find_only:
            print(f"\nFetching metadata for ISBN {isbn}...")
            try:
                metadata = fetch_ebook_metadata(isbn=isbn, timeout=30)

                if not metadata:
                    print("✗ No metadata found")
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
                    'Series': 'series'
                }

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

                        updates[db_field] = value

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
                        enriched_count += 1
                    except Exception as e:
                        print(f"✗ Failed to apply updates: {e}")
                else:
                    print("Skipped metadata updates")

            except Exception as e:
                print(f"✗ Error fetching metadata: {e}")
                continue

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total processed: {len(candidates)}")
    print(f"ISBNs extracted: {extracted_count}")
    if not args.find_only:
        print(f"Books enriched: {enriched_count}")
    print(f"Failed: {failed_count}")
    print()

    if extraction_results:
        print("Successfully extracted ISBNs:")
        for result in extraction_results:
            print(f"  • Book {result['book_id']}: {result['title']}")
            print(f"    ISBN: {result['isbn']}")


if __name__ == "__main__":
    main()
