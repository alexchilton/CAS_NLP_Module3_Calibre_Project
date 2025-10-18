#!/usr/bin/env python3
"""
Find and manage duplicate books in Calibre library using SQL queries.

Finds duplicates by title, author, ISBN, and uses smart rules to determine
which copy to keep based on format preference and recency.

Usage:
    python find_duplicates_sql.py --find-only                    # Just find duplicates
    python find_duplicates_sql.py --interactive                  # Ask for each duplicate
    python find_duplicates_sql.py --auto-delete --dry-run        # Show what would be deleted
    python find_duplicates_sql.py --auto-delete                  # Delete duplicates automatically
    python find_duplicates_sql.py --format-priority "EPUB,PDF"   # Custom format preference
"""

import argparse
import sqlite3
import subprocess
import json
from pathlib import Path
from datetime import datetime
from calibre_tools.config import DEFAULT_CALIBRE_LIBRARY


# Default format preference hierarchy (higher index = higher priority)
DEFAULT_FORMAT_PRIORITY = ['DJVU', 'AZW3', 'MOBI', 'PDF', 'EPUB']


def find_duplicates_sql(library_path=DEFAULT_CALIBRE_LIBRARY):
    """
    Find duplicate books using direct SQL query.

    Returns:
        List of duplicate groups, where each group contains books that are duplicates
    """
    db_path = Path(library_path) / 'metadata.db'

    if not db_path.exists():
        raise Exception(f"Database not found at: {db_path}")

    # SQL query to find potential duplicates by title and author
    query = """
        SELECT
            b1.id as book1_id,
            b1.title as book1_title,
            b1.author_sort as book1_authors,
            b1.timestamp as book1_timestamp,
            b1.last_modified as book1_modified,
            b1.pubdate as book1_pubdate,
            b2.id as book2_id,
            b2.title as book2_title,
            b2.author_sort as book2_authors,
            b2.timestamp as book2_timestamp,
            b2.last_modified as book2_modified,
            b2.pubdate as book2_pubdate,
            c1.text as book1_comments,
            c2.text as book2_comments,
            i1.val as book1_isbn,
            i2.val as book2_isbn
        FROM books b1
        JOIN books b2 ON LOWER(TRIM(b1.title)) = LOWER(TRIM(b2.title))
            AND LOWER(TRIM(b1.author_sort)) = LOWER(TRIM(b2.author_sort))
            AND b1.id < b2.id
        LEFT JOIN comments c1 ON b1.id = c1.book
        LEFT JOIN comments c2 ON b2.id = c2.book
        LEFT JOIN identifiers i1 ON b1.id = i1.book AND i1.type = 'isbn'
        LEFT JOIN identifiers i2 ON b2.id = i2.book AND i2.type = 'isbn'
        WHERE
            -- Exclude magazines/periodicals
            (c1.text IS NULL OR c1.text NOT LIKE '%periodical/magazine issue%')
            AND (c2.text IS NULL OR c2.text NOT LIKE '%periodical/magazine issue%')
        ORDER BY b1.id, b2.id
    """

    # Execute query in read-only mode
    db_uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(db_uri, uri=True)
    conn.row_factory = sqlite3.Row

    try:
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()

        # Group duplicates
        duplicate_groups = {}

        for row in rows:
            book1_id = row['book1_id']
            book2_id = row['book2_id']

            # Create a key for this duplicate group
            # Use the smallest book ID as the group key
            group_key = min(book1_id, book2_id)

            if group_key not in duplicate_groups:
                duplicate_groups[group_key] = set()

            duplicate_groups[group_key].add(book1_id)
            duplicate_groups[group_key].add(book2_id)

        # Convert to list of lists
        result = [list(group) for group in duplicate_groups.values()]

        return result

    finally:
        conn.close()


def get_book_details(book_ids, library_path=DEFAULT_CALIBRE_LIBRARY):
    """
    Get detailed information about books including formats.

    Args:
        book_ids: List of book IDs
        library_path: Path to Calibre library

    Returns:
        Dict mapping book_id to book details
    """
    db_path = Path(library_path) / 'metadata.db'
    db_uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(db_uri, uri=True)
    conn.row_factory = sqlite3.Row

    try:
        placeholders = ','.join('?' * len(book_ids))
        query = f"""
            SELECT
                b.id,
                b.title,
                b.author_sort as authors,
                b.timestamp,
                b.last_modified,
                b.pubdate,
                GROUP_CONCAT(d.format, ',') as formats,
                c.text as comments,
                i.val as isbn
            FROM books b
            LEFT JOIN data d ON b.id = d.book
            LEFT JOIN comments c ON b.id = c.book
            LEFT JOIN identifiers i ON b.id = i.book AND i.type = 'isbn'
            WHERE b.id IN ({placeholders})
            GROUP BY b.id
        """

        cursor = conn.cursor()
        cursor.execute(query, book_ids)
        rows = cursor.fetchall()

        books = {}
        for row in rows:
            books[row['id']] = {
                'id': row['id'],
                'title': row['title'],
                'authors': row['authors'],
                'timestamp': row['timestamp'],
                'last_modified': row['last_modified'],
                'pubdate': row['pubdate'],
                'formats': row['formats'].split(',') if row['formats'] else [],
                'comments': row['comments'],
                'isbn': row['isbn']
            }

        return books

    finally:
        conn.close()


def score_book(book, format_priority):
    """
    Score a book based on format preference and recency.

    Higher score = better book to keep.

    Args:
        book: Book details dict
        format_priority: List of formats in order of preference (lowest to highest)

    Returns:
        Score (higher is better)
    """
    score = 0

    # Format score (most important)
    # Give points based on best format available
    max_format_score = 0
    for fmt in book['formats']:
        if fmt in format_priority:
            format_score = format_priority.index(fmt)
            max_format_score = max(max_format_score, format_score)

    score += max_format_score * 1000  # Format is most important

    # Recency score (secondary)
    # Use last_modified if available, otherwise timestamp
    date_str = book['last_modified'] or book['timestamp']
    if date_str:
        try:
            # Parse date and convert to score (more recent = higher score)
            date_obj = datetime.fromisoformat(date_str.replace('T', ' ').split('+')[0])
            # Days since epoch / 1000 to keep score manageable
            recency_score = int(date_obj.timestamp() / 86400)
            score += recency_score
        except:
            pass

    # Number of formats bonus (having multiple formats is good)
    score += len(book['formats']) * 10

    return score


def determine_keeper(duplicate_group, books, format_priority):
    """
    Determine which book to keep in a duplicate group.

    Args:
        duplicate_group: List of book IDs that are duplicates
        books: Dict of book details
        format_priority: List of formats in order of preference

    Returns:
        Tuple of (keeper_id, books_to_delete)
    """
    # Score each book
    scored_books = []
    for book_id in duplicate_group:
        book = books[book_id]
        score = score_book(book, format_priority)
        scored_books.append((book_id, score, book))

    # Sort by score (descending)
    scored_books.sort(key=lambda x: x[1], reverse=True)

    # Keep the highest scoring book
    keeper_id = scored_books[0][0]
    books_to_delete = [b[0] for b in scored_books[1:]]

    return keeper_id, books_to_delete


def delete_book(book_id, library_path=DEFAULT_CALIBRE_LIBRARY, dry_run=False):
    """
    Delete a book from Calibre library.

    Args:
        book_id: Book ID to delete
        library_path: Path to Calibre library
        dry_run: If True, don't actually delete

    Returns:
        True if successful (or dry run), False otherwise
    """
    if dry_run:
        return True

    try:
        cmd = [
            'calibredb', 'remove',
            '--library-path', library_path,
            str(book_id)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            print(f"    ✗ Error deleting book {book_id}: {result.stderr}")
            return False

        return True

    except Exception as e:
        print(f"    ✗ Exception deleting book {book_id}: {e}")
        return False


def log_deletion(book, log_file):
    """
    Log a book deletion to a file for recovery.

    Args:
        book: Book details dict
        log_file: Path to log file
    """
    with open(log_file, 'a') as f:
        timestamp = datetime.now().isoformat()
        f.write(f"\n{'=' * 80}\n")
        f.write(f"Deleted: {timestamp}\n")
        f.write(f"Book ID: {book['id']}\n")
        f.write(f"Title: {book['title']}\n")
        f.write(f"Authors: {book['authors']}\n")
        f.write(f"Formats: {', '.join(book['formats'])}\n")
        f.write(f"ISBN: {book['isbn']}\n")
        f.write(f"Timestamp: {book['timestamp']}\n")
        f.write(f"Last Modified: {book['last_modified']}\n")


def main():
    parser = argparse.ArgumentParser(
        description='Find and manage duplicate books using SQL queries'
    )
    parser.add_argument(
        '--find-only',
        action='store_true',
        help='Only find duplicates, do not delete anything'
    )
    parser.add_argument(
        '--interactive',
        action='store_true',
        help='Show each duplicate and ask which to keep'
    )
    parser.add_argument(
        '--auto-delete',
        action='store_true',
        help='Automatically delete duplicates based on smart rules'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be deleted without actually deleting'
    )
    parser.add_argument(
        '--format-priority',
        type=str,
        default=','.join(DEFAULT_FORMAT_PRIORITY),
        help=f'Format preference order (default: {",".join(DEFAULT_FORMAT_PRIORITY)})'
    )
    parser.add_argument(
        '--library-path',
        type=str,
        default=DEFAULT_CALIBRE_LIBRARY,
        help=f'Path to Calibre library (default: {DEFAULT_CALIBRE_LIBRARY})'
    )

    args = parser.parse_args()

    # Parse format priority
    format_priority = [f.strip().upper() for f in args.format_priority.split(',')]

    print("=" * 80)
    print("FIND AND MANAGE DUPLICATES")
    print("=" * 80)
    print(f"Library: {args.library_path}")
    print(f"Format Priority: {' > '.join(format_priority)} (highest priority last)")
    if args.dry_run:
        print("Mode: DRY RUN (no actual deletions)")
    elif args.find_only:
        print("Mode: Find only (no deletions)")
    elif args.interactive:
        print("Mode: Interactive (ask for each duplicate)")
    elif args.auto_delete:
        print("Mode: Auto-delete (based on smart rules)")
    print()

    # Find duplicates
    print("Finding duplicates using SQL...")
    duplicate_groups = find_duplicates_sql(args.library_path)

    if not duplicate_groups:
        print("✓ No duplicates found!")
        return

    print(f"\nFound {len(duplicate_groups)} duplicate group(s):")
    print("-" * 80)

    # Get details for all books in duplicate groups
    all_book_ids = []
    for group in duplicate_groups:
        all_book_ids.extend(group)

    books = get_book_details(all_book_ids, args.library_path)

    # Process each duplicate group
    deletion_log = []
    total_to_delete = 0

    for i, group in enumerate(duplicate_groups, 1):
        print(f"\nDuplicate Group {i}:")
        print("-" * 80)

        # Determine keeper
        keeper_id, to_delete = determine_keeper(group, books, format_priority)

        # Display all books in group
        for book_id in group:
            book = books[book_id]
            is_keeper = book_id == keeper_id

            status = "✓ KEEP" if is_keeper else "✗ DELETE"
            print(f"\n  [{status}] Book ID {book_id}")
            print(f"      Title: {book['title']}")
            print(f"      Authors: {book['authors']}")
            print(f"      Formats: {', '.join(book['formats'])}")
            print(f"      Added: {book['timestamp']}")
            print(f"      Modified: {book['last_modified']}")
            if book['isbn']:
                print(f"      ISBN: {book['isbn']}")

            score = score_book(book, format_priority)
            print(f"      Score: {score}")

        # Handle deletion
        if args.find_only:
            total_to_delete += len(to_delete)
            continue

        if args.interactive:
            print(f"\n  Recommended: Keep book {keeper_id}, delete {len(to_delete)} duplicate(s)")
            response = input("  Proceed with recommendation? [Y/n/s(kip)]: ").lower()

            if response == 's':
                print("  Skipped")
                continue
            elif response == 'n':
                keeper_input = input(f"  Enter book ID to keep (or 'skip'): ").strip()
                if keeper_input.lower() == 'skip':
                    print("  Skipped")
                    continue
                try:
                    keeper_id = int(keeper_input)
                    to_delete = [bid for bid in group if bid != keeper_id]
                except ValueError:
                    print("  Invalid input, skipping")
                    continue

        # Delete books
        if not args.find_only:
            for book_id in to_delete:
                book = books[book_id]

                if args.dry_run:
                    print(f"  [DRY RUN] Would delete book {book_id}: {book['title']}")
                    total_to_delete += 1
                else:
                    print(f"  Deleting book {book_id}: {book['title']}...")
                    if delete_book(book_id, args.library_path, args.dry_run):
                        print(f"    ✓ Deleted successfully")
                        deletion_log.append(book)
                        total_to_delete += 1
                    else:
                        print(f"    ✗ Failed to delete")

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Duplicate groups found: {len(duplicate_groups)}")
    if args.dry_run:
        print(f"Would delete: {total_to_delete} book(s)")
    elif args.find_only:
        print(f"Books that would be deleted: {total_to_delete}")
    else:
        print(f"Books deleted: {total_to_delete}")

    # Save deletion log
    if deletion_log and not args.dry_run:
        log_file = Path.home() / '.calibre_tools' / 'deletion_log.txt'
        log_file.parent.mkdir(exist_ok=True)

        for book in deletion_log:
            log_deletion(book, log_file)

        print(f"\nDeletion log saved to: {log_file}")
        print("You can use this log to recover deleted books if needed.")

    print()


if __name__ == "__main__":
    main()
