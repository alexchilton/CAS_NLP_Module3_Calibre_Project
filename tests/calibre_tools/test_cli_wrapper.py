# tests/calibre_tools/test_cli_wrapper.py
import pytest
from unittest.mock import patch, MagicMock
import json


class TestCalibreCLI:
    """Test Calibre CLI wrapper functionality"""

    @patch('subprocess.run')
    def test_list_books(self, mock_subprocess):
        """Test listing books"""
        from calibre_tools.cli_wrapper import list_books

        mock_books = [
            {'id': 1, 'title': 'The Hobbit', 'authors': ['J.R.R. Tolkien']},
            {'id': 2, 'title': 'Foundation', 'authors': ['Isaac Asimov']}
        ]

        mock_subprocess.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(mock_books)
        )

        books = list_books('/fake/library')

        assert len(books) == 2
        assert books[0]['title'] == 'The Hobbit'

        # Check command was constructed correctly
        call_args = mock_subprocess.call_args[0][0]
        assert 'calibredb' in call_args
        assert 'list' in call_args
        assert '--for-machine' in call_args

    @patch('subprocess.run')
    def test_list_books_with_search(self, mock_subprocess):
        """Test listing books with search term"""
        from calibre_tools.cli_wrapper import list_books

        mock_subprocess.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps([])
        )

        list_books('/fake/library', search_term='Tolkien')

        call_args = mock_subprocess.call_args[0][0]
        assert '--search' in call_args
        assert 'Tolkien' in call_args

    @patch('subprocess.run')
    def test_list_books_with_sort(self, mock_subprocess):
        """Test listing books with sorting"""
        from calibre_tools.cli_wrapper import list_books

        mock_subprocess.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps([])
        )

        list_books('/fake/library', sort_by='title')

        call_args = mock_subprocess.call_args[0][0]
        assert '--sort-by' in call_args
        assert 'title' in call_args

    @patch('subprocess.run')
    def test_list_books_with_limit(self, mock_subprocess):
        """Test listing books with limit"""
        from calibre_tools.cli_wrapper import list_books

        mock_subprocess.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps([])
        )

        list_books('/fake/library', limit=10)

        call_args = mock_subprocess.call_args[0][0]
        assert '--limit' in call_args
        assert '10' in call_args

    @patch('subprocess.run')
    def test_list_books_failure(self, mock_subprocess):
        """Test handling list_books failure"""
        from calibre_tools.cli_wrapper import list_books

        mock_subprocess.return_value = MagicMock(
            returncode=1,
            stderr='Error: Library not found'
        )

        with pytest.raises(Exception, match='Failed to list books'):
            list_books('/fake/library')

    @patch('subprocess.run')
    def test_add_book(self, mock_subprocess):
        """Test adding a book"""
        from calibre_tools.cli_wrapper import add_book

        mock_subprocess.return_value = MagicMock(
            returncode=0,
            stdout='Added book ids: 42'
        )

        book_id = add_book('/fake/book.epub', '/fake/library')

        assert book_id == 42

        call_args = mock_subprocess.call_args[0][0]
        assert 'calibredb' in call_args
        assert 'add' in call_args
        assert '/fake/book.epub' in call_args

    @patch('subprocess.run')
    def test_add_book_with_metadata(self, mock_subprocess):
        """Test adding a book with metadata"""
        from calibre_tools.cli_wrapper import add_book

        mock_subprocess.return_value = MagicMock(
            returncode=0,
            stdout='Added book ids: 42'
        )

        book_id = add_book(
            '/fake/book.epub',
            '/fake/library',
            title='Test Book',
            authors='Test Author',
            isbn='9780306406157'
        )

        assert book_id == 42

        call_args = mock_subprocess.call_args[0][0]
        assert '--title' in call_args
        assert 'Test Book' in call_args
        assert '--authors' in call_args
        assert 'Test Author' in call_args

    @patch('subprocess.run')
    def test_add_book_failure(self, mock_subprocess):
        """Test handling add_book failure"""
        from calibre_tools.cli_wrapper import add_book

        mock_subprocess.return_value = MagicMock(
            returncode=1,
            stderr='Error: File not found'
        )

        with pytest.raises(Exception, match='Failed to add book'):
            add_book('/fake/book.epub', '/fake/library')

    @patch('subprocess.run')
    def test_add_book_no_id_in_output(self, mock_subprocess):
        """Test add_book when ID not in output"""
        from calibre_tools.cli_wrapper import add_book

        mock_subprocess.return_value = MagicMock(
            returncode=0,
            stdout='Book added successfully'
        )

        book_id = add_book('/fake/book.epub', '/fake/library')

        assert book_id is None

    @patch('subprocess.run')
    def test_remove_book(self, mock_subprocess):
        """Test removing a book"""
        from calibre_tools.cli_wrapper import remove_book

        mock_subprocess.return_value = MagicMock(returncode=0)

        result = remove_book(42, '/fake/library')

        assert result is True

        call_args = mock_subprocess.call_args[0][0]
        assert 'calibredb' in call_args
        assert 'remove' in call_args
        assert '42' in call_args

    @patch('subprocess.run')
    def test_remove_book_permanent(self, mock_subprocess):
        """Test permanently removing a book"""
        from calibre_tools.cli_wrapper import remove_book

        mock_subprocess.return_value = MagicMock(returncode=0)

        remove_book(42, '/fake/library', permanent=True)

        call_args = mock_subprocess.call_args[0][0]
        assert '--permanent' in call_args

    @patch('subprocess.run')
    def test_remove_book_failure(self, mock_subprocess):
        """Test handling remove_book failure"""
        from calibre_tools.cli_wrapper import remove_book

        mock_subprocess.return_value = MagicMock(
            returncode=1,
            stderr='Error: Book not found'
        )

        with pytest.raises(Exception, match='Failed to remove book'):
            remove_book(42, '/fake/library')

    @patch('subprocess.run')
    def test_set_metadata(self, mock_subprocess):
        """Test setting book metadata"""
        from calibre_tools.cli_wrapper import set_metadata

        mock_subprocess.return_value = MagicMock(returncode=0)

        result = set_metadata(
            42,
            '/fake/library',
            title='New Title',
            authors='New Author',
            tags='fiction,adventure'
        )

        assert result is True

        call_args = mock_subprocess.call_args[0][0]
        assert 'calibredb' in call_args
        assert 'set_metadata' in call_args
        assert '42' in call_args
        assert '--field' in call_args

    @patch('subprocess.run')
    def test_set_metadata_with_none_values(self, mock_subprocess):
        """Test set_metadata ignores None values"""
        from calibre_tools.cli_wrapper import set_metadata

        mock_subprocess.return_value = MagicMock(returncode=0)

        set_metadata(
            42,
            '/fake/library',
            title='New Title',
            authors=None  # Should be ignored
        )

        call_args = mock_subprocess.call_args[0][0]
        call_str = ' '.join(call_args)

        assert 'title:New Title' in call_str
        assert 'authors' not in call_str

    @patch('subprocess.run')
    def test_set_metadata_failure(self, mock_subprocess):
        """Test handling set_metadata failure"""
        from calibre_tools.cli_wrapper import set_metadata

        mock_subprocess.return_value = MagicMock(
            returncode=1,
            stderr='Error: Book not found'
        )

        with pytest.raises(Exception, match='Failed to set metadata'):
            set_metadata(42, '/fake/library', title='New Title')

    @patch('subprocess.run')
    def test_convert_book(self, mock_subprocess):
        """Test converting a book"""
        from calibre_tools.cli_wrapper import convert_book

        mock_subprocess.return_value = MagicMock(
            returncode=0,
            stdout='/output/path/book.epub'
        )

        output_path = convert_book(42, 'epub', '/fake/library')

        assert output_path == '/output/path/book.epub'

        call_args = mock_subprocess.call_args[0][0]
        assert 'calibredb' in call_args
        assert 'export' in call_args
        assert '--format' in call_args
        assert 'epub' in call_args

    @patch('subprocess.run')
    def test_convert_book_failure(self, mock_subprocess):
        """Test handling convert_book failure"""
        from calibre_tools.cli_wrapper import convert_book

        mock_subprocess.return_value = MagicMock(
            returncode=1,
            stderr='Error: Conversion failed'
        )

        with pytest.raises(Exception, match='Failed to convert book'):
            convert_book(42, 'epub', '/fake/library')

    @patch('subprocess.run')
    def test_search_library(self, mock_subprocess):
        """Test searching the library"""
        from calibre_tools.cli_wrapper import search_library

        mock_books = [
            {'id': 1, 'title': 'The Hobbit', 'authors': ['J.R.R. Tolkien']}
        ]

        mock_subprocess.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(mock_books)
        )

        books = search_library('author:Tolkien', '/fake/library')

        assert len(books) == 1
        assert books[0]['title'] == 'The Hobbit'

        call_args = mock_subprocess.call_args[0][0]
        assert '--search' in call_args
        assert 'author:Tolkien' in call_args

    @patch('subprocess.run')
    def test_search_library_failure(self, mock_subprocess):
        """Test handling search_library failure"""
        from calibre_tools.cli_wrapper import search_library

        mock_subprocess.return_value = MagicMock(
            returncode=1,
            stderr='Error: Invalid search query'
        )

        with pytest.raises(Exception, match='Failed to search library'):
            search_library('invalid query', '/fake/library')

    @patch('subprocess.run')
    def test_default_library_path(self, mock_subprocess):
        """Test that default library path is used"""
        from calibre_tools.cli_wrapper import list_books

        mock_subprocess.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps([])
        )

        # Don't provide library_path, should use default
        list_books()

        call_args = mock_subprocess.call_args[0][0]
        assert '--library-path' in call_args

    @patch('os.path.expanduser')
    @patch('subprocess.run')
    def test_file_path_expansion(self, mock_subprocess, mock_expanduser):
        """Test that file paths are expanded"""
        from calibre_tools.cli_wrapper import add_book

        mock_expanduser.return_value = '/home/user/book.epub'
        mock_subprocess.return_value = MagicMock(
            returncode=0,
            stdout='Added book ids: 42'
        )

        add_book('~/book.epub', '/fake/library')

        mock_expanduser.assert_called_once_with('~/book.epub')
        call_args = mock_subprocess.call_args[0][0]
        assert '/home/user/book.epub' in call_args

    @patch('subprocess.run')
    def test_get_book_metadata(self, mock_subprocess):
        """Test getting detailed book metadata"""
        from calibre_tools.cli_wrapper import get_book_metadata

        mock_output = """Title               : The Hobbit
Title sort          : Hobbit, The
Author(s)           : J.R.R. Tolkien [Tolkien, J.R.R.]
Publisher           : Houghton Mifflin
Languages           : eng
Timestamp           : 2022-01-01T00:00:00+00:00
Published           : 1937-01-01T00:00:00+00:00
Comments            : A great fantasy adventure book"""

        mock_subprocess.return_value = MagicMock(
            returncode=0,
            stdout=mock_output
        )

        metadata = get_book_metadata(1, '/fake/library')

        assert metadata['Title'] == 'The Hobbit'
        assert metadata['Publisher'] == 'Houghton Mifflin'
        assert 'Comments' in metadata

        call_args = mock_subprocess.call_args[0][0]
        assert 'calibredb' in call_args
        assert 'show_metadata' in call_args
        assert '1' in call_args

    @patch('subprocess.run')
    def test_get_book_metadata_as_opf(self, mock_subprocess):
        """Test getting book metadata as OPF XML"""
        from calibre_tools.cli_wrapper import get_book_metadata

        mock_xml = '<?xml version="1.0"?><package>...</package>'

        mock_subprocess.return_value = MagicMock(
            returncode=0,
            stdout=mock_xml
        )

        xml_output = get_book_metadata(1, '/fake/library', as_opf=True)

        assert xml_output == mock_xml
        call_args = mock_subprocess.call_args[0][0]
        assert '--as-opf' in call_args

    @patch('subprocess.run')
    def test_get_book_metadata_failure(self, mock_subprocess):
        """Test handling get_book_metadata failure"""
        from calibre_tools.cli_wrapper import get_book_metadata

        mock_subprocess.return_value = MagicMock(
            returncode=1,
            stderr='Error: Book not found'
        )

        with pytest.raises(Exception, match='Failed to get book metadata'):
            get_book_metadata(999, '/fake/library')
