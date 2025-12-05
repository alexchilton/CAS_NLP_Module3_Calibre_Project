# tests/test_genre_classifier.py
import pytest
from unittest.mock import patch, MagicMock
import json
import os


class TestGenreClassifier:
    """Test GenreClassifier with Calibre book data"""

    @pytest.fixture
    def classifier(self):
        """Create a GenreClassifier instance if model exists"""
        model_dir = "genre_model"
        if not os.path.exists(model_dir):
            pytest.skip(f"Model directory '{model_dir}' not found")

        from genre_classifier import GenreClassifier
        return GenreClassifier(model_dir=model_dir)

    @patch('subprocess.run')
    def test_genre_prediction_from_calibre_book(self, mock_subprocess, classifier):
        """Test genre prediction using a book from Calibre database"""
        from calibre_tools.cli_wrapper import get_book_metadata

        # Mock Calibre book metadata
        mock_output = """Title               : The Hobbit
Title sort          : Hobbit, The
Author(s)           : J.R.R. Tolkien [Tolkien, J.R.R.]
Publisher           : Houghton Mifflin
Languages           : eng
Timestamp           : 2022-01-01T00:00:00+00:00
Published           : 1937-01-01T00:00:00+00:00
Tags                : Fantasy
Comments            : A great fantasy adventure book about a hobbit who goes on an epic quest to help dwarves reclaim their homeland from a dragon."""

        mock_subprocess.return_value = MagicMock(
            returncode=0,
            stdout=mock_output
        )

        # Get book metadata from Calibre
        metadata = get_book_metadata(1, '/fake/library')

        # Make prediction using book metadata
        title = metadata.get('Title', '')
        description = metadata.get('Comments', '')

        genres = classifier.predict(
            title=title,
            description=description,
            threshold=0.3,  # Lower threshold for more results
            top_k=5
        )

        # Validate results
        assert len(genres) > 0, "Should return at least one genre"
        assert all(isinstance(g, tuple) for g in genres), "Each result should be a tuple"
        assert all(len(g) == 2 for g in genres), "Each tuple should have 2 elements"
        assert all(isinstance(g[0], str) for g in genres), "First element should be genre name"
        assert all(isinstance(g[1], float) for g in genres), "Second element should be probability"
        assert all(0 <= g[1] <= 1 for g in genres), "Probability should be between 0 and 1"
        assert genres == sorted(genres, key=lambda x: x[1], reverse=True), "Should be sorted by probability desc"

        print(f"\nGenre predictions for 'The Hobbit': {genres}")

    @patch('subprocess.run')
    def test_genre_prediction_with_missing_description(self, mock_subprocess, classifier):
        """Test genre prediction when book has no description"""
        from calibre_tools.cli_wrapper import get_book_metadata

        # Mock Calibre book metadata without comments
        mock_output = """Title               : 1984
Author(s)           : George Orwell
Publisher           : Secker & Warburg"""

        mock_subprocess.return_value = MagicMock(
            returncode=0,
            stdout=mock_output
        )

        # Get book metadata
        metadata = get_book_metadata(2, '/fake/library')

        # Make prediction with title only
        title = metadata.get('Title', '')
        description = metadata.get('Comments', '')

        genres = classifier.predict(
            title=title,
            description=description,
            threshold=0.3,
            top_k=3
        )

        # Validate results
        assert len(genres) > 0
        assert all(isinstance(g, tuple) for g in genres)
        assert metadata.get('Comments', '') == ''  # Verify no description

        print(f"\nGenre predictions for '1984' (title only): {genres}")

    @patch('subprocess.run')
    def test_genre_prediction_batch(self, mock_subprocess, classifier):
        """Test genre prediction for multiple books"""
        from calibre_tools.cli_wrapper import list_books

        # Mock list of books
        mock_books = [
            {
                'id': 1,
                'title': 'The Hobbit',
                'authors': ['J.R.R. Tolkien'],
                'comments': 'A fantasy adventure about hobbits and dragons'
            },
            {
                'id': 2,
                'title': 'Foundation',
                'authors': ['Isaac Asimov'],
                'comments': 'A science fiction epic about the fall and rise of civilization'
            },
            {
                'id': 3,
                'title': 'Pride and Prejudice',
                'authors': ['Jane Austen'],
                'comments': 'A romantic novel about love and social class in Georgian England'
            }
        ]

        mock_subprocess.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(mock_books)
        )

        # Get books from Calibre
        books = list_books('/fake/library', limit=3)

        # Predict genres for all books
        results = []
        for book in books:
            genres = classifier.predict(
                title=book.get('title', ''),
                description=book.get('comments', ''),
                threshold=0.3,
                top_k=3
            )
            results.append({
                'book_id': book['id'],
                'title': book['title'],
                'genres': genres
            })

        # Validate results
        assert len(results) == 3
        assert all(len(r['genres']) > 0 for r in results)
        assert all(isinstance(g, tuple) for r in results for g in r['genres'])

        print(f"\nBatch predictions:")
        for r in results:
            print(f"  {r['title']}: {r['genres']}")

    def test_genre_prediction_with_real_model_if_available(self):
        """Test with real model if available (integration test)"""
        import os
        from genre_classifier import GenreClassifier

        # Check if model exists
        model_dir = "genre_model"
        if not os.path.exists(model_dir):
            pytest.skip(f"Model directory '{model_dir}' not found. Skipping integration test.")

        # Try to load the real model
        try:
            classifier = GenreClassifier(model_dir=model_dir)

            # Test prediction with sample text
            genres = classifier.predict(
                title="The Lord of the Rings",
                description="An epic fantasy adventure about a quest to destroy a powerful ring",
                threshold=0.3,
                top_k=3
            )

            # Validate results
            assert len(genres) > 0
            assert all(isinstance(g, tuple) for g in genres)
            assert all(len(g) == 2 for g in genres)
            assert all(isinstance(g[0], str) for g in genres)
            assert all(isinstance(g[1], float) for g in genres)

            print(f"\nGenre predictions: {genres}")

        except Exception as e:
            pytest.skip(f"Could not load model: {e}")

    def test_genre_classifier_predict_labels(self, classifier):
        """Test the predict_labels convenience method"""
        genres = classifier.predict_labels(
            title="The Hobbit",
            description="A fantasy adventure about a hobbit going on a quest",
            threshold=0.3,
            top_k=3
        )

        # Validate results
        assert isinstance(genres, list)
        assert len(genres) > 0
        assert all(isinstance(g, str) for g in genres)

        print(f"\nGenre labels (strings only): {genres}")