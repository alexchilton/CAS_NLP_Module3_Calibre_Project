# calibre_mcp/tools/genre_classification.py
import json
import os
from typing import Optional
from calibre_mcp.server import mcp
from calibre_tools.cli_wrapper import get_book_metadata, list_books
from genre_classifier import GenreClassifier


# Lazy-load classifier to avoid loading model during import
_classifier = None


def get_classifier():
    """Lazy-load the genre classifier singleton."""
    global _classifier
    if _classifier is None:
        # Try environment variable first, then fall back to relative path
        model_dir = os.environ.get(
            "GENRE_MODEL_PATH",
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "genre_model")
        )
        _classifier = GenreClassifier(model_dir=model_dir)
    return _classifier


@mcp.tool()
def calibre_predict_genre(
    book_id: int,
    threshold: float = 0.3,
    top_k: int = 5
) -> str:
    """
    Predict genres for a book in your Calibre library using machine learning.

    Uses a fine-tuned transformer model to analyze the book's title and description
    and predict the most likely genres. Works best with books that have descriptions.

    Args:
        book_id: The Calibre book ID
        threshold: Minimum confidence score (0.0-1.0) for a genre to be included. Default: 0.3
        top_k: Maximum number of genres to return. Default: 5

    Returns:
        JSON string with genre predictions including confidence scores

    Example response:
        {
          "book_id": 1,
          "title": "The Hobbit",
          "genres": [
            {"genre": "Fantasy", "confidence": 0.988},
            {"genre": "Children", "confidence": 0.536}
          ]
        }
    """
    # Get book metadata
    metadata = get_book_metadata(book_id)
    title = metadata.get('Title', '')
    description = metadata.get('Comments', '')

    # Get classifier and predict
    classifier = get_classifier()
    predictions = classifier.predict(
        title=title,
        description=description,
        threshold=threshold,
        top_k=top_k
    )

    # Format results
    result = {
        "book_id": book_id,
        "title": title,
        "has_description": bool(description),
        "genres": [
            {
                "genre": genre,
                "confidence": round(confidence, 4)
            }
            for genre, confidence in predictions
        ]
    }

    return json.dumps(result, indent=2)


@mcp.tool()
def calibre_batch_predict_genres(
    limit: int = 10,
    threshold: float = 0.3,
    top_k: int = 3,
    search_term: Optional[str] = None
) -> str:
    """
    Predict genres for multiple books in your Calibre library.

    Processes books in batches to predict genres. Useful for bulk genre tagging.
    Works best with books that have descriptions.

    Args:
        limit: Maximum number of books to process. Default: 10
        threshold: Minimum confidence score (0.0-1.0) for a genre. Default: 0.3
        top_k: Maximum number of genres per book. Default: 3
        search_term: Optional search query to filter books (e.g., "author:Tolkien")

    Returns:
        JSON string with batch predictions

    Example response:
        {
          "total_processed": 3,
          "results": [
            {
              "book_id": 1,
              "title": "The Hobbit",
              "genres": [
                {"genre": "Fantasy", "confidence": 0.988}
              ]
            },
            ...
          ]
        }
    """
    # Get books from Calibre
    books = list_books(limit=limit, search_term=search_term)

    # Get classifier
    classifier = get_classifier()

    # Predict genres for each book
    results = []
    for book in books:
        book_id = book['id']
        title = book.get('title', '')
        description = book.get('comments', '')

        predictions = classifier.predict(
            title=title,
            description=description,
            threshold=threshold,
            top_k=top_k
        )

        results.append({
            "book_id": book_id,
            "title": title,
            "has_description": bool(description),
            "genres": [
                {
                    "genre": genre,
                    "confidence": round(confidence, 4)
                }
                for genre, confidence in predictions
            ]
        })

    # Format batch results
    batch_result = {
        "total_processed": len(results),
        "threshold": threshold,
        "top_k": top_k,
        "results": results
    }

    return json.dumps(batch_result, indent=2)


@mcp.tool()
def calibre_predict_and_tag_genre(
    book_id: int,
    threshold: float = 0.5,
    top_k: int = 3,
    apply: bool = False
) -> str:
    """
    Predict genres and optionally apply them as tags to a book.

    Uses ML to predict genres, then can automatically add them as tags in Calibre.
    Higher threshold (0.5+) recommended when auto-applying to ensure quality.

    Args:
        book_id: The Calibre book ID
        threshold: Minimum confidence score (0.0-1.0). Default: 0.5
        top_k: Maximum number of genres to tag. Default: 3
        apply: If True, automatically apply genres as tags. Default: False

    Returns:
        JSON string with predictions and action taken

    Example response:
        {
          "book_id": 1,
          "title": "The Hobbit",
          "predicted_genres": ["Fantasy", "Children"],
          "action_taken": "tags_updated",
          "message": "Added 2 genre tags to book"
        }
    """
    from calibre_tools.cli_wrapper import set_metadata

    # Get book metadata
    metadata = get_book_metadata(book_id)
    title = metadata.get('Title', '')
    description = metadata.get('Comments', '')
    existing_tags = metadata.get('Tags', '')

    # Predict genres
    classifier = get_classifier()
    predictions = classifier.predict(
        title=title,
        description=description,
        threshold=threshold,
        top_k=top_k
    )

    genre_labels = [genre for genre, _ in predictions]

    result = {
        "book_id": book_id,
        "title": title,
        "predicted_genres": genre_labels,
        "confidence_scores": {
            genre: round(confidence, 4)
            for genre, confidence in predictions
        },
        "existing_tags": existing_tags
    }

    # Apply tags if requested
    if apply:
        # Parse existing tags
        existing_tag_list = [t.strip() for t in existing_tags.split(',')] if existing_tags else []

        # Add new genre tags (avoid duplicates)
        new_tags = list(set(existing_tag_list + genre_labels))
        new_tags_str = ', '.join(new_tags)

        # Update tags in Calibre
        set_metadata(book_id, tags=new_tags_str)

        result['action_taken'] = 'tags_updated'
        result['new_tags'] = new_tags_str
        result['message'] = f"Added {len(genre_labels)} genre tag(s) to book"
    else:
        result['action_taken'] = 'preview_only'
        result['message'] = "Set apply=true to update tags in Calibre"

    return json.dumps(result, indent=2)
