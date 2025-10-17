"""
Semantic Search for Calibre Library using Metadata
Searches books based on title, author, description, tags, series, and publisher
"""

import warnings
warnings.filterwarnings("ignore")

import os
import pickle
import subprocess
import json
from sentence_transformers import SentenceTransformer
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from tqdm import tqdm

# --- Configuration ---
CALIBRE_LIBRARY_PATH = os.path.expanduser("~/calibre_semantic_test")
EMBEDDING_FILE = 'calibre_book_embeddings.pkl'
METADATA_FILE = 'calibre_metadata.json'

# --- Step 1: Extract Metadata from Calibre ---

def get_calibre_metadata(library_path):
    """
    Extracts metadata from Calibre database using calibredb CLI.
    Returns a dictionary of book_id -> metadata
    """
    print(f"Extracting metadata from Calibre library: {library_path}")

    # Get metadata in JSON format
    cmd = [
        'calibredb', 'list',
        '--library-path', library_path,
        '--for-machine'
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise Exception(f"Failed to read Calibre library: {result.stderr}")

    books = json.loads(result.stdout)
    print(f"Found {len(books)} books in library")

    return books

def create_searchable_text(book):
    """
    Combines relevant metadata fields into a single searchable text.
    This is what we'll embed for semantic search.
    """
    parts = []

    # Title (most important, include it twice for emphasis)
    if book.get('title'):
        parts.append(f"Title: {book['title']}")
        parts.append(book['title'])

    # Authors
    if book.get('authors'):
        authors = ', '.join(book['authors']) if isinstance(book['authors'], list) else book['authors']
        parts.append(f"Authors: {authors}")

    # Series
    if book.get('series'):
        parts.append(f"Series: {book['series']}")

    # Tags/Genres (very important for semantic search)
    if book.get('tags'):
        tags = ', '.join(book['tags']) if isinstance(book['tags'], list) else book['tags']
        parts.append(f"Tags: {tags}")

    # Publisher
    if book.get('publisher'):
        parts.append(f"Publisher: {book['publisher']}")

    # Description/Comments (most descriptive, include prominently)
    if book.get('comments'):
        # Strip HTML tags if present
        import re
        clean_comments = re.sub(r'<[^>]+>', '', book['comments'])
        parts.append(f"Description: {clean_comments}")
        parts.append(clean_comments)  # Include twice for emphasis

    return " | ".join(parts)

def prepare_metadata_for_embedding(books):
    """
    Prepares book metadata for embedding.
    Returns: dict of book_id -> searchable_text and dict of book_id -> full_metadata
    """
    searchable_texts = {}
    book_metadata = {}

    print("Preparing metadata for embedding...")
    for book in tqdm(books):
        book_id = str(book['id'])
        searchable_texts[book_id] = create_searchable_text(book)
        book_metadata[book_id] = book

    return searchable_texts, book_metadata

# --- Step 2: Load or Generate Embeddings ---

def load_or_create_embeddings(searchable_texts, model):
    """
    Loads existing embeddings or creates new ones.
    """
    if os.path.exists(EMBEDDING_FILE):
        print("Loading existing embeddings from disk...")
        with open(EMBEDDING_FILE, 'rb') as f:
            embeddings_dict = pickle.load(f)
        print("Embeddings loaded.")
        return embeddings_dict

    print("Generating embeddings for book metadata...")
    book_ids = list(searchable_texts.keys())
    texts_to_embed = list(searchable_texts.values())

    # Generate embeddings
    embeddings = model.encode(
        texts_to_embed,
        batch_size=32,
        show_progress_bar=True,
        convert_to_numpy=True
    )

    # Map book IDs to embeddings
    embeddings_dict = {book_id: emb for book_id, emb in zip(book_ids, embeddings)}

    # Save embeddings
    with open(EMBEDDING_FILE, 'wb') as f:
        pickle.dump(embeddings_dict, f)
    print(f"Embeddings saved to '{EMBEDDING_FILE}'")

    return embeddings_dict

# --- Step 3: Search Functions ---

def semantic_search(query, embeddings_dict, book_metadata, model, top_n=10):
    """
    Performs semantic search on the book metadata.
    """
    # Embed the query
    query_embedding = model.encode(query, convert_to_numpy=True).reshape(1, -1)

    # Calculate similarities
    similarities = {}
    for book_id, book_embedding in embeddings_dict.items():
        book_embedding = book_embedding.reshape(1, -1)
        similarity = cosine_similarity(query_embedding, book_embedding)[0][0]
        similarities[book_id] = similarity

    # Sort by similarity
    sorted_results = sorted(similarities.items(), key=lambda x: x[1], reverse=True)

    # Return top N with full metadata
    results = []
    for book_id, score in sorted_results[:top_n]:
        results.append({
            'score': score,
            'metadata': book_metadata[book_id]
        })

    return results

def display_results(results):
    """
    Displays search results in a readable format.
    """
    print("\n" + "="*80)
    print("SEARCH RESULTS")
    print("="*80)

    for i, result in enumerate(results, 1):
        book = result['metadata']
        score = result['score']

        print(f"\n{i}. [{score:.4f}] {book.get('title', 'Unknown Title')}")

        # Authors
        if book.get('authors'):
            authors = ', '.join(book['authors']) if isinstance(book['authors'], list) else book['authors']
            print(f"   Authors: {authors}")

        # Series
        if book.get('series'):
            series_info = book['series']
            if book.get('series_index'):
                series_info += f" #{book['series_index']}"
            print(f"   Series: {series_info}")

        # Tags
        if book.get('tags'):
            tags = ', '.join(book['tags']) if isinstance(book['tags'], list) else book['tags']
            print(f"   Tags: {tags}")

        # Publisher and date
        pub_info = []
        if book.get('publisher'):
            pub_info.append(book['publisher'])
        if book.get('pubdate'):
            pub_info.append(str(book['pubdate']))
        if pub_info:
            print(f"   Published: {', '.join(pub_info)}")

        # Rating
        if book.get('rating'):
            stars = '★' * int(book['rating']) + '☆' * (5 - int(book['rating']))
            print(f"   Rating: {stars}")

        # Description preview
        if book.get('comments'):
            import re
            clean_comments = re.sub(r'<[^>]+>', '', book['comments'])
            preview = clean_comments[:200] + "..." if len(clean_comments) > 200 else clean_comments
            print(f"   Description: {preview}")

        print(f"   Calibre ID: {book['id']}")
        print("-" * 80)

# --- Main Execution ---

def main():
    print("Calibre Semantic Search System")
    print("="*80 + "\n")

    # Step 1: Load metadata
    if os.path.exists(METADATA_FILE):
        print("Loading cached metadata...")
        with open(METADATA_FILE, 'r') as f:
            books = json.load(f)
    else:
        books = get_calibre_metadata(CALIBRE_LIBRARY_PATH)
        # Cache metadata
        with open(METADATA_FILE, 'w') as f:
            json.dump(books, f)

    searchable_texts, book_metadata = prepare_metadata_for_embedding(books)

    # Step 2: Initialize model
    print("\nLoading embedding model...")
    model = SentenceTransformer('all-MiniLM-L6-v2', device="cpu")  # Fast, good model
    # For better quality (but slower): 'sentence-transformers/all-mpnet-base-v2'
    # For GPU: change device to "cuda"
    print("Model loaded.\n")

    # Step 3: Load or create embeddings
    embeddings_dict = load_or_create_embeddings(searchable_texts, model)

    print("\n" + "="*80)
    print("Ready to search! Enter queries to find similar books.")
    print("="*80 + "\n")

    # Step 4: Interactive search loop
    while True:
        query = input("\nEnter search query (or 'exit' to quit): ").strip()

        if query.lower() in ['exit', 'quit', 'q']:
            print("Goodbye!")
            break

        if not query:
            continue

        # Perform search
        results = semantic_search(query, embeddings_dict, book_metadata, model, top_n=10)

        # Display results
        display_results(results)

if __name__ == "__main__":
    main()