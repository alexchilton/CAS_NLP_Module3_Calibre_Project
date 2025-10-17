#!/usr/bin/env python3
"""
Manual testing script for Calibre tools
Run each method individually to see actual CLI output
"""

import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from calibre_tools import cli_wrapper, isbn_tools, duplicate_finder, semantic_search
from calibre_tools.config import DEFAULT_CALIBRE_LIBRARY
import json


def print_section(title):
    """Print a section header"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_result(result, truncate=True):
    """Pretty print results"""
    if isinstance(result, (list, dict)):
        result_str = json.dumps(result, indent=2)
        if truncate and len(result_str) > 1000:
            print(result_str[:1000] + "\n... (truncated)")
        else:
            print(result_str)
    else:
        print(result)


class ManualTester:
    """Interactive manual testing"""

    def __init__(self, library_path=None):
        self.library_path = library_path or DEFAULT_CALIBRE_LIBRARY
        print(f"Using Calibre library: {self.library_path}")

    # ============================================================
    # CLI WRAPPER TESTS
    # ============================================================

    def test_list_books(self, limit=5):
        """Test listing books"""
        print_section("LIST BOOKS")
        print(f"Getting first {limit} books from library...")

        try:
            books = cli_wrapper.list_books(
                library_path=self.library_path,
                limit=limit
            )
            print(f"\nFound {len(books)} books:")
            print_result(books)
            return books
        except Exception as e:
            print(f"Error: {e}")
            return None

    def test_list_books_with_search(self, search_term="fantasy"):
        """Test listing books with search"""
        print_section("LIST BOOKS WITH SEARCH")
        print(f"Searching for: '{search_term}'")

        try:
            books = cli_wrapper.list_books(
                library_path=self.library_path,
                search_term=search_term,
                limit=5
            )
            print(f"\nFound {len(books)} books:")
            print_result(books)
            return books
        except Exception as e:
            print(f"Error: {e}")
            return None

    def test_list_books_sorted(self, sort_by="title", limit=5):
        """Test listing books with sorting"""
        print_section("LIST BOOKS SORTED")
        print(f"Sorting by: {sort_by}")

        try:
            books = cli_wrapper.list_books(
                library_path=self.library_path,
                sort_by=sort_by,
                limit=limit
            )
            print(f"\nFirst {limit} books sorted by {sort_by}:")
            for book in books:
                print(f"  - {book.get('title', 'N/A')}")
            return books
        except Exception as e:
            print(f"Error: {e}")
            return None

    def test_search_library(self, query="author:tolkien"):
        """Test searching library"""
        print_section("SEARCH LIBRARY")
        print(f"Search query: '{query}'")

        try:
            books = cli_wrapper.search_library(
                query=query,
                library_path=self.library_path
            )
            print(f"\nFound {len(books)} books:")
            print_result(books, truncate=True)
            return books
        except Exception as e:
            print(f"Error: {e}")
            return None

    def test_add_book(self, file_path):
        """Test adding a book"""
        print_section("ADD BOOK")
        print(f"Adding book: {file_path}")
        print("WARNING: This will actually add a book to your library!")

        confirm = input("Continue? (yes/no): ")
        if confirm.lower() != 'yes':
            print("Skipped")
            return None

        try:
            book_id = cli_wrapper.add_book(
                file_path=file_path,
                library_path=self.library_path,
                title="Test Book",
                authors="Test Author"
            )
            print(f"\nBook added with ID: {book_id}")
            return book_id
        except Exception as e:
            print(f"Error: {e}")
            return None

    def test_remove_book(self, book_id):
        """Test removing a book"""
        print_section("REMOVE BOOK")
        print(f"Removing book ID: {book_id}")
        print("WARNING: This will actually remove a book from your library!")

        confirm = input("Continue? (yes/no): ")
        if confirm.lower() != 'yes':
            print("Skipped")
            return None

        try:
            result = cli_wrapper.remove_book(
                book_id=book_id,
                library_path=self.library_path,
                permanent=False
            )
            print(f"\nBook removed: {result}")
            return result
        except Exception as e:
            print(f"Error: {e}")
            return None

    def test_set_metadata(self, book_id):
        """Test setting book metadata"""
        print_section("SET METADATA")
        print(f"Setting metadata for book ID: {book_id}")
        print("WARNING: This will actually modify your book metadata!")

        confirm = input("Continue? (yes/no): ")
        if confirm.lower() != 'yes':
            print("Skipped")
            return None

        try:
            result = cli_wrapper.set_metadata(
                book_id=book_id,
                library_path=self.library_path,
                tags="test,manual-testing"
            )
            print(f"\nMetadata updated: {result}")
            return result
        except Exception as e:
            print(f"Error: {e}")
            return None

    # ============================================================
    # ISBN TOOLS TESTS
    # ============================================================

    def test_validate_isbn(self, isbn="9780547928227"):
        """Test ISBN validation"""
        print_section("VALIDATE ISBN")
        print(f"Validating ISBN: {isbn}")

        try:
            is_valid = isbn_tools.validate_isbn(isbn)
            print(f"\nISBN is valid: {is_valid}")

            # Also test individual validators
            isbn_clean = isbn.replace('-', '').replace(' ', '')
            if len(isbn_clean) == 10:
                isbn10_valid = isbn_tools.validate_isbn10(isbn)
                print(f"ISBN-10 validation: {isbn10_valid}")
            elif len(isbn_clean) == 13:
                isbn13_valid = isbn_tools.validate_isbn13(isbn)
                print(f"ISBN-13 validation: {isbn13_valid}")

            return is_valid
        except Exception as e:
            print(f"Error: {e}")
            return None

    def test_extract_isbn_from_text(self, text=None):
        """Test extracting ISBN from text"""
        print_section("EXTRACT ISBN FROM TEXT")

        if text is None:
            text = """
            This book has ISBN-13: 978-0-547-92822-7
            Another book has ISBN: 0-306-40615-2
            """

        print(f"Extracting ISBNs from text:\n{text}")

        try:
            isbns = isbn_tools.extract_isbn_from_text(text)
            print(f"\nFound {len(isbns)} ISBNs:")
            for isbn in isbns:
                print(f"  - {isbn}")
            return isbns
        except Exception as e:
            print(f"Error: {e}")
            return None

    def test_extract_isbn_from_file(self, file_path):
        """Test extracting ISBN from ebook file"""
        print_section("EXTRACT ISBN FROM FILE")
        print(f"Extracting ISBN from: {file_path}")

        try:
            isbns = isbn_tools.extract_isbn_from_file(file_path)
            print(f"\nFound {len(isbns)} ISBNs:")
            for isbn in isbns:
                print(f"  - {isbn}")
            return isbns
        except Exception as e:
            print(f"Error: {e}")
            return None

    def test_find_books_by_isbn(self, isbn="9780547928227"):
        """Test finding books by ISBN"""
        print_section("FIND BOOKS BY ISBN")
        print(f"Searching for books with ISBN: {isbn}")

        try:
            books = isbn_tools.find_books_by_isbn(
                isbn=isbn,
                library_path=self.library_path
            )
            print(f"\nFound {len(books)} books:")
            print_result(books)
            return books
        except Exception as e:
            print(f"Error: {e}")
            return None

    def test_get_book_isbn(self, book_id):
        """Test getting ISBN from book"""
        print_section("GET BOOK ISBN")
        print(f"Getting ISBN for book ID: {book_id}")

        try:
            isbn = isbn_tools.get_book_isbn(
                book_id=book_id,
                library_path=self.library_path
            )
            print(f"\nISBN: {isbn}")
            return isbn
        except Exception as e:
            print(f"Error: {e}")
            return None

    # ============================================================
    # DUPLICATE FINDER TESTS
    # ============================================================

    def test_find_all_duplicates(self):
        """Test finding all types of duplicates"""
        print_section("FIND ALL DUPLICATES")
        print("Searching for duplicates in library...")
        print("This may take a while for large libraries...")

        try:
            results = duplicate_finder.find_all_duplicates(
                library_path=self.library_path
            )

            print(f"\nExact matches: {len(results['exact_matches'])} groups")
            print(f"Similar titles: {len(results['similar_titles'])} groups")
            print(f"ISBN duplicates: {len(results['isbn_duplicates'])} groups")

            # Show formatted results
            formatted = duplicate_finder.format_duplicate_results(results)
            if formatted:
                print("\n" + formatted[:500])
                if len(formatted) > 500:
                    print("... (truncated)")

            return results
        except Exception as e:
            print(f"Error: {e}")
            return None

    # ============================================================
    # SEMANTIC SEARCH TESTS
    # ============================================================

    def test_semantic_search(self, query="fantasy adventure with dragons", top_n=5):
        """Test semantic search"""
        print_section("SEMANTIC SEARCH")
        print(f"Searching for: '{query}'")
        print(f"Top {top_n} results")
        print("\nNote: This will download/load the embedding model on first run...")

        try:
            results = semantic_search.search(
                query=query,
                top_n=top_n
            )

            print(f"\nFound {len(results)} results:")
            for i, result in enumerate(results, 1):
                book = result['metadata']
                score = result['score']
                print(f"\n{i}. {book.get('title', 'N/A')} (Score: {score:.3f})")
                print(f"   Author: {book.get('authors', 'N/A')}")
                print(f"   Tags: {book.get('tags', 'N/A')}")

            return results
        except Exception as e:
            print(f"Error: {e}")
            return None


# ============================================================
# INTERACTIVE MENU
# ============================================================

def interactive_menu():
    """Interactive testing menu"""
    print("\n" + "=" * 60)
    print("  CALIBRE TOOLS - MANUAL TESTING")
    print("=" * 60)

    library_path = input(f"\nCalibbre library path (press Enter for default: {DEFAULT_CALIBRE_LIBRARY}): ").strip()
    if not library_path:
        library_path = DEFAULT_CALIBRE_LIBRARY

    tester = ManualTester(library_path)

    while True:
        print("\n" + "=" * 60)
        print("SELECT A TEST:")
        print("=" * 60)
        print("\nCLI WRAPPER:")
        print("  1. List books")
        print("  2. List books with search")
        print("  3. List books sorted")
        print("  4. Search library")
        print("  5. Add book (WARNING: modifies library)")
        print("  6. Remove book (WARNING: modifies library)")
        print("  7. Set metadata (WARNING: modifies library)")

        print("\nISBN TOOLS:")
        print("  8. Validate ISBN")
        print("  9. Extract ISBN from text")
        print("  10. Extract ISBN from file")
        print("  11. Find books by ISBN")
        print("  12. Get book ISBN")

        print("\nDUPLICATE FINDER:")
        print("  13. Find all duplicates")

        print("\nSEMANTIC SEARCH:")
        print("  14. Semantic search")

        print("\nOTHER:")
        print("  0. Exit")

        choice = input("\nEnter choice: ").strip()

        if choice == "0":
            print("Goodbye!")
            break
        elif choice == "1":
            tester.test_list_books()
        elif choice == "2":
            search = input("Search term: ").strip() or "fantasy"
            tester.test_list_books_with_search(search)
        elif choice == "3":
            sort = input("Sort by (title/author/timestamp): ").strip() or "title"
            tester.test_list_books_sorted(sort)
        elif choice == "4":
            query = input("Search query (e.g., 'author:tolkien'): ").strip() or "author:tolkien"
            tester.test_search_library(query)
        elif choice == "5":
            file_path = input("Book file path: ").strip()
            if file_path:
                tester.test_add_book(file_path)
        elif choice == "6":
            book_id = input("Book ID to remove: ").strip()
            if book_id:
                tester.test_remove_book(int(book_id))
        elif choice == "7":
            book_id = input("Book ID to modify: ").strip()
            if book_id:
                tester.test_set_metadata(int(book_id))
        elif choice == "8":
            isbn = input("ISBN to validate: ").strip() or "9780547928227"
            tester.test_validate_isbn(isbn)
        elif choice == "9":
            tester.test_extract_isbn_from_text()
        elif choice == "10":
            file_path = input("Ebook file path: ").strip()
            if file_path:
                tester.test_extract_isbn_from_file(file_path)
        elif choice == "11":
            isbn = input("ISBN to search: ").strip() or "9780547928227"
            tester.test_find_books_by_isbn(isbn)
        elif choice == "12":
            book_id = input("Book ID: ").strip()
            if book_id:
                tester.test_get_book_isbn(int(book_id))
        elif choice == "13":
            tester.test_find_all_duplicates()
        elif choice == "14":
            query = input("Search query: ").strip() or "fantasy adventure with dragons"
            top_n = input("Number of results (default 5): ").strip()
            top_n = int(top_n) if top_n else 5
            tester.test_semantic_search(query, top_n)
        else:
            print("Invalid choice")


def quick_test():
    """Run a quick test of common functions"""
    print("\n" + "=" * 60)
    print("  QUICK TEST - COMMON FUNCTIONS")
    print("=" * 60)

    tester = ManualTester()

    # Test list books
    books = tester.test_list_books(limit=3)

    if books and len(books) > 0:
        # Get first book ID for other tests
        book_id = books[0]['id']

        # Test search
        tester.test_search_library("author:*")

        # Test ISBN validation
        tester.test_validate_isbn("9780547928227")

        # Test getting ISBN from book
        tester.test_get_book_isbn(book_id)

        # Test duplicate finder
        print("\nSkipping duplicate finder (slow)...")

        # Test semantic search
        print("\nSkipping semantic search (downloads model)...")

    print("\n" + "=" * 60)
    print("  QUICK TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    print("Calibre Tools - Manual Testing Script")
    print("=" * 60)
    print("\nOptions:")
    print("  1. Interactive menu (choose individual tests)")
    print("  2. Quick test (run common functions)")
    print("  3. Exit")

    choice = input("\nEnter choice: ").strip()

    if choice == "1":
        interactive_menu()
    elif choice == "2":
        quick_test()
    else:
        print("Goodbye!")
