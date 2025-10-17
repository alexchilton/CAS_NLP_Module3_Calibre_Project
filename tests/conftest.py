# tests/conftest.py
"""
Pytest configuration and shared fixtures
"""

import pytest
import tempfile
import shutil
import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture(scope="session")
def temp_calibre_library():
    """
    Create a temporary Calibre library directory for testing
    """
    temp_dir = tempfile.mkdtemp(prefix="calibre_test_")
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def temp_dir():
    """
    Create a temporary directory for test files
    """
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def sample_books():
    """
    Sample book data for testing
    """
    return [
        {
            'id': 1,
            'title': 'The Hobbit',
            'authors': ['J.R.R. Tolkien'],
            'tags': ['fantasy', 'adventure'],
            'series': 'Middle Earth',
            'publisher': 'Allen & Unwin',
            'comments': '<p>A great fantasy novel about a hobbit\'s adventure</p>',
            'isbn': '9780547928227',
            'identifiers': {'isbn': '9780547928227'},
            'timestamp': '2020-01-01T00:00:00+00:00',
            'formats': ['EPUB', 'PDF']
        },
        {
            'id': 2,
            'title': 'Foundation',
            'authors': ['Isaac Asimov'],
            'tags': ['sci-fi', 'space'],
            'series': 'Foundation Series',
            'publisher': 'Gnome Press',
            'comments': '<p>Classic science fiction about the fall of galactic empire</p>',
            'isbn': '9780553293357',
            'identifiers': {'isbn': '9780553293357'},
            'timestamp': '2020-01-02T00:00:00+00:00',
            'formats': ['EPUB']
        },
        {
            'id': 3,
            'title': '1984',
            'authors': ['George Orwell'],
            'tags': ['dystopian', 'classic'],
            'series': None,
            'publisher': 'Secker & Warburg',
            'comments': '<p>Dystopian social science fiction novel</p>',
            'isbn': '9780451524935',
            'identifiers': {'isbn': '9780451524935'},
            'timestamp': '2020-01-03T00:00:00+00:00',
            'formats': ['EPUB', 'MOBI']
        }
    ]


@pytest.fixture
def sample_isbns():
    """
    Sample ISBN data for testing
    """
    return {
        'valid_isbn10': ['0306406152', '043942089X', '0451524934'],
        'invalid_isbn10': ['0306406153', '1234567890'],
        'valid_isbn13': ['9780306406157', '9780547928227', '9780451524935'],
        'invalid_isbn13': ['9780306406158', '1234567890123']
    }


@pytest.fixture(autouse=True)
def reset_singleton():
    """
    Reset singleton instances between tests
    """
    # Reset semantic search singleton
    import calibre_tools.semantic_search as ss
    ss._instance = None

    yield

    # Clean up after test
    ss._instance = None


@pytest.fixture
def mock_calibre_command():
    """
    Mock successful Calibre CLI commands
    """
    from unittest.mock import MagicMock
    import json

    def _mock_command(stdout_data=None, returncode=0, stderr=""):
        if stdout_data is None:
            stdout_data = []

        return MagicMock(
            returncode=returncode,
            stdout=json.dumps(stdout_data) if isinstance(stdout_data, (list, dict)) else stdout_data,
            stderr=stderr
        )

    return _mock_command


@pytest.fixture
def mock_sentence_transformer():
    """
    Mock SentenceTransformer model for testing
    """
    from unittest.mock import MagicMock
    import numpy as np

    mock_model = MagicMock()
    mock_model.encode.return_value = np.random.rand(384)  # Standard embedding size

    return mock_model


# Pytest configuration hooks

def pytest_configure(config):
    """
    Pytest configuration hook
    """
    # Add custom markers
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "slow: Slow running tests")


def pytest_collection_modifyitems(config, items):
    """
    Modify test collection to add markers automatically
    """
    for item in items:
        # Add 'unit' marker to all tests by default
        if not any(mark.name in ['integration', 'slow'] for mark in item.iter_markers()):
            item.add_marker(pytest.mark.unit)


# Test utilities

class MockCalibreDB:
    """
    Mock CalibreDB for testing without actual Calibre installation
    """

    def __init__(self, books=None):
        self.books = books or []

    def list(self, search=None, sort_by=None, limit=None):
        results = self.books

        if search:
            # Simple search implementation
            results = [b for b in results if search.lower() in str(b).lower()]

        if sort_by:
            results = sorted(results, key=lambda x: x.get(sort_by, ''))

        if limit:
            results = results[:limit]

        return results

    def add(self, file_path, **metadata):
        new_id = max([b['id'] for b in self.books], default=0) + 1
        new_book = {'id': new_id, **metadata}
        self.books.append(new_book)
        return new_id

    def remove(self, book_id):
        self.books = [b for b in self.books if b['id'] != book_id]

    def set_metadata(self, book_id, **metadata):
        for book in self.books:
            if book['id'] == book_id:
                book.update(metadata)
                return True
        return False
