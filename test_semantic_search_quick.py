#!/usr/bin/env python3
"""Quick test of semantic search functionality"""

from calibre_tools.semantic_search import search

print("=" * 60)
print("TESTING SEMANTIC SEARCH")
print("=" * 60)

# Test search
query = "fantasy adventure with dragons"
print(f"\nSearching for: '{query}'")
print("This will:")
print("  1. Load the embedding model (first time only)")
print("  2. Extract metadata from Calibre library")
print("  3. Create embeddings for books")
print("  4. Search and rank by similarity")
print("\n" + "-" * 60)

try:
    results = search(query, top_n=5)

    print(f"\nFound {len(results)} results:\n")

    for i, result in enumerate(results, 1):
        metadata = result['metadata']
        score = result['score']

        # Handle authors - could be list or string
        authors = metadata.get('authors', ['Unknown'])
        if isinstance(authors, list):
            authors_str = ', '.join(authors)
        else:
            authors_str = authors

        print(f"{i}. {metadata['title']}")
        print(f"   Author(s): {authors_str}")
        print(f"   Score: {score:.4f}")
        print(f"   ID: {metadata['id']}")
        print()

except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("=" * 60)
print("TEST COMPLETE")
print("=" * 60)
