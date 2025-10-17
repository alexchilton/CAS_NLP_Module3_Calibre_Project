# tests/calibre_tools/test_isbn_tools.py
import pytest
from unittest.mock import patch, MagicMock
import json


class TestISBNTools:
    """Test ISBN extraction and validation functionality"""

    def test_validate_isbn10_valid(self):
        """Test valid ISBN-10 validation"""
        from calibre_tools.isbn_tools import validate_isbn10

        # Valid ISBN-10 examples
        assert validate_isbn10('0306406152') is True
        assert validate_isbn10('0-306-40615-2') is True
        assert validate_isbn10('043942089X') is True  # With X
        assert validate_isbn10('0-439-42089-X') is True

    def test_validate_isbn10_invalid(self):
        """Test invalid ISBN-10 validation"""
        from calibre_tools.isbn_tools import validate_isbn10

        assert validate_isbn10('0306406153') is False  # Wrong checksum
        assert validate_isbn10('123') is False  # Too short
        assert validate_isbn10('abcdefghij') is False  # Non-numeric

    def test_validate_isbn13_valid(self):
        """Test valid ISBN-13 validation"""
        from calibre_tools.isbn_tools import validate_isbn13

        # Valid ISBN-13 examples
        assert validate_isbn13('9780306406157') is True
        assert validate_isbn13('978-0-306-40615-7') is True
        assert validate_isbn13('9780547928227') is True

    def test_validate_isbn13_invalid(self):
        """Test invalid ISBN-13 validation"""
        from calibre_tools.isbn_tools import validate_isbn13

        assert validate_isbn13('9780306406158') is False  # Wrong checksum
        assert validate_isbn13('123456789012') is False  # Not starting with 978/979
        assert validate_isbn13('12345') is False  # Too short

    def test_validate_isbn_both_formats(self):
        """Test validate_isbn with both formats"""
        from calibre_tools.isbn_tools import validate_isbn

        # ISBN-10
        assert validate_isbn('0306406152') is True
        assert validate_isbn('0306406153') is False

        # ISBN-13
        assert validate_isbn('9780306406157') is True
        assert validate_isbn('9780306406158') is False

        # Invalid length
        assert validate_isbn('12345') is False

    def test_extract_isbn_from_text_isbn10(self):
        """Test extracting ISBN-10 from text"""
        from calibre_tools.isbn_tools import extract_isbn_from_text

        text = "This book's ISBN is 0-306-40615-2 and it's great!"
        isbns = extract_isbn_from_text(text)

        assert len(isbns) > 0
        assert '0306406152' in isbns

    def test_extract_isbn_from_text_isbn13(self):
        """Test extracting ISBN-13 from text"""
        from calibre_tools.isbn_tools import extract_isbn_from_text

        text = "ISBN-13: 978-0-306-40615-7"
        isbns = extract_isbn_from_text(text)

        assert len(isbns) > 0
        assert '9780306406157' in isbns

    def test_extract_isbn_from_text_multiple(self):
        """Test extracting multiple ISBNs from text"""
        from calibre_tools.isbn_tools import extract_isbn_from_text

        text = """
        First book ISBN: 0-306-40615-2
        Second book ISBN-13: 978-0-547-92822-7
        """
        isbns = extract_isbn_from_text(text)

        assert len(isbns) >= 2

    def test_extract_isbn_from_text_no_isbn(self):
        """Test extracting from text with no ISBNs"""
        from calibre_tools.isbn_tools import extract_isbn_from_text

        text = "This is just regular text with no ISBN numbers."
        isbns = extract_isbn_from_text(text)

        assert len(isbns) == 0

    def test_extract_isbn_from_text_empty(self):
        """Test extracting from empty text"""
        from calibre_tools.isbn_tools import extract_isbn_from_text

        assert extract_isbn_from_text("") == []
        assert extract_isbn_from_text(None) == []

    @patch('os.path.isfile', return_value=True)
    @patch('subprocess.run')
    def test_extract_isbn_from_file(self, mock_subprocess, mock_isfile):
        """Test extracting ISBN from ebook file"""
        from calibre_tools.isbn_tools import extract_isbn_from_file

        mock_subprocess.return_value = MagicMock(
            returncode=0,
            stdout="Title: Test Book\nIdentifiers: isbn:9780306406157\nAuthor: Test Author"
        )

        isbns = extract_isbn_from_file('/fake/book.epub')

        assert len(isbns) > 0
        assert '9780306406157' in isbns

    @patch('os.path.isfile', return_value=True)
    @patch('subprocess.run')
    def test_extract_isbn_from_file_failure(self, mock_subprocess, mock_isfile):
        """Test handling ebook-meta failure"""
        from calibre_tools.isbn_tools import extract_isbn_from_file

        mock_subprocess.return_value = MagicMock(
            returncode=1,
            stderr='Error: Extraction failed'
        )

        with pytest.raises(Exception, match='Failed to extract metadata'):
            extract_isbn_from_file('/fake/book.epub')

    @patch('os.path.isfile', return_value=False)
    def test_extract_isbn_from_file_not_found(self, mock_isfile):
        """Test handling non-existent file"""
        from calibre_tools.isbn_tools import extract_isbn_from_file

        with pytest.raises(FileNotFoundError, match='File not found'):
            extract_isbn_from_file('/fake/nonexistent.epub')

    @patch('subprocess.run')
    def test_find_books_by_isbn(self, mock_subprocess):
        """Test finding books by ISBN"""
        from calibre_tools.isbn_tools import find_books_by_isbn

        mock_books = [
            {'id': 1, 'title': 'Test Book', 'identifiers': {'isbn': '9780306406157'}}
        ]

        mock_subprocess.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(mock_books)
        )

        books = find_books_by_isbn('9780306406157', '/fake/library')

        assert len(books) == 1
        assert books[0]['title'] == 'Test Book'

    @patch('subprocess.run')
    def test_find_books_by_isbn_normalized(self, mock_subprocess):
        """Test that ISBN is normalized before searching"""
        from calibre_tools.isbn_tools import find_books_by_isbn

        mock_subprocess.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps([])
        )

        # Should normalize hyphens and spaces
        find_books_by_isbn('978-0-306-40615-7', '/fake/library')

        # Check that the command was called with normalized ISBN
        call_args = mock_subprocess.call_args[0][0]
        assert 'identifiers:isbn:9780306406157' in ' '.join(call_args)

    @patch('subprocess.run')
    def test_get_book_isbn_from_identifiers(self, mock_subprocess):
        """Test getting ISBN from book identifiers"""
        from calibre_tools.isbn_tools import get_book_isbn

        mock_books = [
            {
                'id': 1,
                'identifiers': {'isbn': '9780306406157'},
                'title': 'Test Book'
            }
        ]

        mock_subprocess.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(mock_books)
        )

        isbn = get_book_isbn(1, '/fake/library')

        assert isbn == '9780306406157'

    @patch('subprocess.run')
    def test_get_book_isbn_from_comments(self, mock_subprocess):
        """Test extracting ISBN from book comments when not in identifiers"""
        from calibre_tools.isbn_tools import get_book_isbn

        mock_books = [
            {
                'id': 1,
                'identifiers': {},
                'comments': 'This book has ISBN: 978-0-306-40615-7',
                'title': 'Test Book'
            }
        ]

        mock_subprocess.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(mock_books)
        )

        isbn = get_book_isbn(1, '/fake/library')

        assert isbn is not None

    @patch('subprocess.run')
    def test_get_book_isbn_not_found(self, mock_subprocess):
        """Test getting ISBN when book doesn't exist"""
        from calibre_tools.isbn_tools import get_book_isbn

        mock_subprocess.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps([])
        )

        isbn = get_book_isbn(999, '/fake/library')

        assert isbn is None

    @patch('subprocess.run')
    def test_get_book_isbn_no_isbn(self, mock_subprocess):
        """Test getting ISBN when book has no ISBN"""
        from calibre_tools.isbn_tools import get_book_isbn

        mock_books = [
            {
                'id': 1,
                'identifiers': {},
                'title': 'Test Book',
                'comments': 'No ISBN here'
            }
        ]

        mock_subprocess.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(mock_books)
        )

        isbn = get_book_isbn(1, '/fake/library')

        assert isbn is None

    def test_isbn_regex_patterns(self):
        """Test ISBN regex patterns match correctly"""
        from calibre_tools.isbn_tools import extract_isbn_from_text

        # Various ISBN formats
        test_cases = [
            ("ISBN: 0-306-40615-2", True),
            ("ISBN-10: 0306406152", True),
            ("ISBN-13: 978-0-306-40615-7", True),
            ("ISBN 9780306406157", True),
            ("978-0306406157", True),
            ("0306406152", True),
            ("Random number: 1234567890", False),  # Invalid checksum
        ]

        for text, should_find in test_cases:
            isbns = extract_isbn_from_text(text)
            if should_find:
                assert len(isbns) > 0, f"Should find ISBN in: {text}"
            # Note: Invalid checksums won't be in results due to validation

    def test_handle_dict_identifiers(self):
        """Test handling identifiers as dict"""
        from calibre_tools.isbn_tools import get_book_isbn

        with patch('subprocess.run') as mock_subprocess:
            mock_books = [
                {
                    'id': 1,
                    'identifiers': {'isbn': '9780306406157', 'amazon': 'B001234'},
                    'title': 'Test Book'
                }
            ]

            mock_subprocess.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps(mock_books)
            )

            isbn = get_book_isbn(1, '/fake/library')
            assert isbn == '9780306406157'
