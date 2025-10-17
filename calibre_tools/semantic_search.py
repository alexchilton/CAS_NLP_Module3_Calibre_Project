# calibre_tools/semantic_search.py
import os
import pickle
import json
import subprocess
import time
import re
from datetime import datetime, timedelta
from sentence_transformers import SentenceTransformer
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from calibre_tools.config import (
    DEFAULT_CALIBRE_LIBRARY,
    DEFAULT_EMBEDDING_FILE,
    DEFAULT_METADATA_FILE,
    DEFAULT_MODEL_NAME,
    DEFAULT_DEVICE,
    CACHE_EXPIRY_DAYS,
    FORCE_REFRESH,
)

class CalibreSemanticSearch:
    def __init__(
        self, 
        library_path=DEFAULT_CALIBRE_LIBRARY,
        embedding_file=DEFAULT_EMBEDDING_FILE,
        metadata_file=DEFAULT_METADATA_FILE,
        model_name=DEFAULT_MODEL_NAME,
        device=DEFAULT_DEVICE,
    ):
        self.library_path = os.path.expanduser(library_path)
        self.embedding_file = embedding_file
        self.metadata_file = metadata_file
        self.model_name = model_name
        self.device = device
        
        # Load or create data
        self.load_or_create_data()
    
    def load_or_create_data(self):
        """Load existing data or create new embeddings if needed"""
        # Model will be loaded lazily when needed
        self.model = None

        # Check if we need to refresh the data
        refresh_needed = self._check_refresh_needed()

        if refresh_needed:
            # Extract metadata from Calibre
            books = self._get_calibre_metadata()

            # Save metadata
            with open(self.metadata_file, 'w') as f:
                json.dump(books, f)

            # Prepare searchable texts and metadata
            self.searchable_texts, self.book_metadata = self._prepare_metadata_for_embedding(books)

            # Generate embeddings (this will load the model)
            self.embeddings_dict = self._create_embeddings()
        else:
            # Load cached data
            print("Loading cached metadata and embeddings...")
            with open(self.metadata_file, 'r') as f:
                books = json.load(f)

            # Prepare metadata
            self.searchable_texts, self.book_metadata = self._prepare_metadata_for_embedding(books)

            # Load embeddings
            with open(self.embedding_file, 'rb') as f:
                self.embeddings_dict = pickle.load(f)

            # Model will be loaded lazily on first search
    
    def _check_refresh_needed(self):
        """Check if we need to refresh the cache"""
        if FORCE_REFRESH:
            return True
        
        # Check if files exist
        if not os.path.exists(self.metadata_file) or not os.path.exists(self.embedding_file):
            return True
        
        # Check if files are older than cache expiry
        metadata_time = datetime.fromtimestamp(os.path.getmtime(self.metadata_file))
        if datetime.now() - metadata_time > timedelta(days=CACHE_EXPIRY_DAYS):
            return True
        
        return False
    
    def _get_calibre_metadata(self):
        """Extract metadata from Calibre using the CLI"""
        print(f"Extracting metadata from Calibre library: {self.library_path}")
        
        cmd = [
            'calibredb', 'list',
            '--library-path', self.library_path,
            '--for-machine'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise Exception(f"Failed to read Calibre library: {result.stderr}")
        
        books = json.loads(result.stdout)
        print(f"Found {len(books)} books in library")
        
        return books
    
    def _prepare_metadata_for_embedding(self, books):
        """Prepare book metadata for embedding"""
        searchable_texts = {}
        book_metadata = {}
        
        print("Preparing metadata for embedding...")
        for book in books:
            book_id = str(book['id'])
            searchable_texts[book_id] = self._create_searchable_text(book)
            book_metadata[book_id] = book
        
        return searchable_texts, book_metadata
    
    def _create_searchable_text(self, book):
        """Combine relevant metadata fields into searchable text"""
        parts = []
        
        # Title (include twice for emphasis)
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
        
        # Tags/Genres
        if book.get('tags'):
            tags = ', '.join(book['tags']) if isinstance(book['tags'], list) else book['tags']
            parts.append(f"Tags: {tags}")
        
        # Publisher
        if book.get('publisher'):
            parts.append(f"Publisher: {book['publisher']}")
        
        # Description/Comments
        if book.get('comments'):
            # Strip HTML tags
            clean_comments = re.sub(r'<[^>]+>', '', book['comments'])
            parts.append(f"Description: {clean_comments}")
            parts.append(clean_comments)  # Include twice for emphasis
        
        return " | ".join(parts)
    
    def _load_model(self):
        """Lazy load the model only when needed"""
        if self.model is None:
            print(f"Loading embedding model {self.model_name} on {self.device}...")
            self.model = SentenceTransformer(self.model_name, device=self.device)

    def _create_embeddings(self):
        """Create embeddings for all books"""
        self._load_model()

        print("Generating embeddings for book metadata...")

        book_ids = list(self.searchable_texts.keys())
        texts_to_embed = list(self.searchable_texts.values())

        # Generate embeddings
        embeddings = self.model.encode(
            texts_to_embed,
            batch_size=32,
            show_progress_bar=True,
            convert_to_numpy=True
        )

        # Map book IDs to embeddings
        embeddings_dict = {book_id: emb for book_id, emb in zip(book_ids, embeddings)}

        # Save embeddings
        with open(self.embedding_file, 'wb') as f:
            pickle.dump(embeddings_dict, f)

        return embeddings_dict
    
    def search(self, query, top_n=10):
        """Perform semantic search on book metadata"""
        # Load model if not already loaded
        self._load_model()

        # Embed the query
        query_embedding = self.model.encode(query, convert_to_numpy=True).reshape(1, -1)

        # Calculate similarities efficiently (vectorized)
        book_ids = list(self.embeddings_dict.keys())
        all_embeddings = np.vstack([self.embeddings_dict[book_id] for book_id in book_ids])

        # Compute all similarities at once (much faster)
        similarities = cosine_similarity(query_embedding, all_embeddings)[0]

        # Get indices of top N results
        top_indices = np.argsort(similarities)[::-1][:top_n]

        # Return top N with full metadata
        results = []
        for idx in top_indices:
            book_id = book_ids[idx]
            results.append({
                'score': float(similarities[idx]),
                'metadata': self.book_metadata[book_id]
            })

        return results

# Singleton instance for easy access
_instance = None

def get_search_instance(**kwargs):
    global _instance
    if _instance is None:
        _instance = CalibreSemanticSearch(**kwargs)
    return _instance

def search(query, top_n=10, **kwargs):
    """Convenience function for searching"""
    searcher = get_search_instance(**kwargs)
    return searcher.search(query, top_n=top_n)