# tests/calibre_tools/test_semantic_search.py
import os
import json
import pickle
import pytest
import tempfile
import shutil
from unittest.mock import patch, MagicMock, mock_open
from datetime import datetime, timedelta
import numpy as np


class TestCalibreSemanticSearch:
    """Test semantic search functionality"""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test files"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def mock_books(self):
        """Sample book data for testing"""
        return [
            {
                'id': 1,
                'title': 'The Hobbit',
                'authors': ['J.R.R. Tolkien'],
                'tags': ['fantasy', 'adventure'],
                'series': 'Middle Earth',
                'publisher': 'Allen & Unwin',
                'comments': '<p>A great fantasy novel</p>'
            },
            {
                'id': 2,
                'title': 'Foundation',
                'authors': ['Isaac Asimov'],
                'tags': ['sci-fi', 'space'],
                'series': 'Foundation Series',
                'publisher': 'Gnome Press',
                'comments': '<p>Classic science fiction</p>'
            }
        ]

    @pytest.fixture
    def mock_embeddings(self):
        """Sample embeddings for testing"""
        return {
            '1': np.random.rand(384),
            '2': np.random.rand(384)
        }

    def test_create_searchable_text(self, mock_books):
        """Test creating searchable text from book metadata"""
        from calibre_tools.semantic_search import CalibreSemanticSearch

        with patch.object(CalibreSemanticSearch, 'load_or_create_data'):
            searcher = CalibreSemanticSearch()
            text = searcher._create_searchable_text(mock_books[0])

            assert 'The Hobbit' in text
            assert 'J.R.R. Tolkien' in text
            assert 'fantasy' in text
            assert 'Middle Earth' in text
            assert 'great fantasy novel' in text  # HTML stripped

    def test_prepare_metadata_for_embedding(self, mock_books):
        """Test preparing metadata for embedding"""
        from calibre_tools.semantic_search import CalibreSemanticSearch

        with patch.object(CalibreSemanticSearch, 'load_or_create_data'):
            searcher = CalibreSemanticSearch()
            texts, metadata = searcher._prepare_metadata_for_embedding(mock_books)

            assert '1' in texts
            assert '2' in texts
            assert '1' in metadata
            assert '2' in metadata
            assert metadata['1']['title'] == 'The Hobbit'

    def test_check_refresh_needed_no_files(self, temp_dir):
        """Test refresh is needed when files don't exist"""
        from calibre_tools.semantic_search import CalibreSemanticSearch

        with patch.object(CalibreSemanticSearch, 'load_or_create_data'):
            searcher = CalibreSemanticSearch()
            searcher.metadata_file = os.path.join(temp_dir, 'metadata.json')
            searcher.embedding_file = os.path.join(temp_dir, 'embeddings.pkl')

            assert searcher._check_refresh_needed() is True

    def test_check_refresh_needed_with_cache(self, temp_dir):
        """Test refresh not needed when cache is fresh"""
        from calibre_tools.semantic_search import CalibreSemanticSearch

        metadata_file = os.path.join(temp_dir, 'metadata.json')
        embedding_file = os.path.join(temp_dir, 'embeddings.pkl')

        # Create fresh files
        with open(metadata_file, 'w') as f:
            json.dump({}, f)
        with open(embedding_file, 'wb') as f:
            pickle.dump({}, f)

        with patch.object(CalibreSemanticSearch, 'load_or_create_data'):
            with patch('calibre_tools.semantic_search.FORCE_REFRESH', False):
                with patch('calibre_tools.semantic_search.CACHE_EXPIRY_DAYS', 7):
                    searcher = CalibreSemanticSearch()
                    searcher.metadata_file = metadata_file
                    searcher.embedding_file = embedding_file

                    assert searcher._check_refresh_needed() is False

    def test_check_refresh_needed_expired_cache(self, temp_dir):
        """Test refresh is needed when cache is expired"""
        from calibre_tools.semantic_search import CalibreSemanticSearch

        metadata_file = os.path.join(temp_dir, 'metadata.json')
        embedding_file = os.path.join(temp_dir, 'embeddings.pkl')

        # Create old files
        with open(metadata_file, 'w') as f:
            json.dump({}, f)
        with open(embedding_file, 'wb') as f:
            pickle.dump({}, f)

        # Set file time to 10 days ago
        old_time = (datetime.now() - timedelta(days=10)).timestamp()
        os.utime(metadata_file, (old_time, old_time))

        with patch.object(CalibreSemanticSearch, 'load_or_create_data'):
            with patch('calibre_tools.semantic_search.CACHE_EXPIRY_DAYS', 7):
                searcher = CalibreSemanticSearch()
                searcher.metadata_file = metadata_file
                searcher.embedding_file = embedding_file

                assert searcher._check_refresh_needed() is True

    @patch('subprocess.run')
    def test_get_calibre_metadata(self, mock_subprocess, mock_books):
        """Test extracting metadata from Calibre"""
        from calibre_tools.semantic_search import CalibreSemanticSearch

        mock_subprocess.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(mock_books)
        )

        with patch.object(CalibreSemanticSearch, 'load_or_create_data'):
            searcher = CalibreSemanticSearch()
            books = searcher._get_calibre_metadata()

            assert len(books) == 2
            assert books[0]['title'] == 'The Hobbit'

    @patch('subprocess.run')
    def test_get_calibre_metadata_failure(self, mock_subprocess):
        """Test handling Calibre CLI failure"""
        from calibre_tools.semantic_search import CalibreSemanticSearch

        mock_subprocess.return_value = MagicMock(
            returncode=1,
            stderr='Error: Library not found'
        )

        with patch.object(CalibreSemanticSearch, 'load_or_create_data'):
            searcher = CalibreSemanticSearch()

            with pytest.raises(Exception, match='Failed to read Calibre library'):
                searcher._get_calibre_metadata()

    def test_lazy_model_loading(self):
        """Test that model is loaded lazily"""
        from calibre_tools.semantic_search import CalibreSemanticSearch

        with patch.object(CalibreSemanticSearch, 'load_or_create_data'):
            searcher = CalibreSemanticSearch()
            searcher.model = None

            assert searcher.model is None

            # Mock model loading
            with patch('calibre_tools.semantic_search.SentenceTransformer') as mock_st:
                searcher._load_model()
                mock_st.assert_called_once()
                assert searcher.model is not None

    def test_search_with_mock_data(self, mock_books, mock_embeddings):
        """Test search functionality with mock data"""
        from calibre_tools.semantic_search import CalibreSemanticSearch

        with patch.object(CalibreSemanticSearch, 'load_or_create_data'):
            searcher = CalibreSemanticSearch()
            searcher.embeddings_dict = mock_embeddings
            searcher.book_metadata = {
                '1': mock_books[0],
                '2': mock_books[1]
            }

            # Mock model
            mock_model = MagicMock()
            mock_model.encode.return_value = np.random.rand(384)
            searcher.model = mock_model

            results = searcher.search('fantasy adventure', top_n=2)

            assert len(results) == 2
            assert 'score' in results[0]
            assert 'metadata' in results[0]
            assert results[0]['metadata']['id'] in [1, 2]

    def test_vectorized_similarity_calculation(self, mock_embeddings):
        """Test that similarity calculation is vectorized"""
        from calibre_tools.semantic_search import CalibreSemanticSearch

        with patch.object(CalibreSemanticSearch, 'load_or_create_data'):
            searcher = CalibreSemanticSearch()
            searcher.embeddings_dict = mock_embeddings
            searcher.book_metadata = {'1': {}, '2': {}}

            # Mock model
            mock_model = MagicMock()
            query_embedding = np.random.rand(384)
            mock_model.encode.return_value = query_embedding
            searcher.model = mock_model

            with patch('calibre_tools.semantic_search.cosine_similarity') as mock_cosine:
                mock_cosine.return_value = np.array([[0.9, 0.7]])

                results = searcher.search('test query', top_n=2)

                # Should call cosine_similarity once with all embeddings
                assert mock_cosine.call_count == 1
                call_args = mock_cosine.call_args[0]
                assert call_args[1].shape[0] == 2  # Both embeddings

    def test_singleton_instance(self):
        """Test singleton pattern for search instance"""
        from calibre_tools.semantic_search import get_search_instance

        with patch('calibre_tools.semantic_search.CalibreSemanticSearch') as mock_class:
            instance1 = get_search_instance()
            instance2 = get_search_instance()

            # Should only create instance once
            assert mock_class.call_count == 1
            assert instance1 is instance2

    def test_convenience_search_function(self):
        """Test convenience search function"""
        from calibre_tools.semantic_search import search

        with patch('calibre_tools.semantic_search.get_search_instance') as mock_get:
            mock_searcher = MagicMock()
            mock_searcher.search.return_value = [{'score': 0.9, 'metadata': {}}]
            mock_get.return_value = mock_searcher

            results = search('test query', top_n=5)

            mock_searcher.search.assert_called_once_with('test query', top_n=5)
            assert len(results) == 1
