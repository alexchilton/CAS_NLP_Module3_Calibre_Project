# calibre_tools/duplicate_finder.py
import re
import difflib
from collections import defaultdict
from calibre_tools.config import DEFAULT_CALIBRE_LIBRARY
import subprocess
import json

def get_calibre_metadata(library_path=DEFAULT_CALIBRE_LIBRARY):
    """Extract metadata from Calibre using the CLI"""
    cmd = [
        'calibredb', 'list',
        '--library-path', library_path,
        '--for-machine'
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        raise Exception(f"Failed to read Calibre library: {result.stderr}")
    
    books = json.loads(result.stdout)
    return books

def normalize_string(s):
    """Normalize a string for comparison"""
    if not s:
        return ""
    # Convert to lowercase
    s = s.lower()
    # Remove punctuation
    s = re.sub(r'[^\w\s]', '', s)
    # Remove extra whitespace
    s = re.sub(r'\s+', ' ', s).strip()
    return s

def find_exact_duplicates(books, fields=None):
    """Find books with exact matches on specified fields"""
    if fields is None:
        fields = ["title", "authors"]
    
    # Group books by the specified fields
    groups = defaultdict(list)
    
    for book in books:
        # Create a tuple of the normalized field values
        key_parts = []
        for field in fields:
            if field in book:
                # Handle lists (e.g., authors)
                if isinstance(book[field], list):
                    value = tuple(sorted([normalize_string(v) for v in book[field]]))
                else:
                    value = normalize_string(book[field])
                key_parts.append(value)
            else:
                key_parts.append(None)
        
        # Create a hashable key
        key = tuple(key_parts)
        groups[key].append(book)
    
    # Return groups with more than one book
    duplicates = {k: v for k, v in groups.items() if len(v) > 1}
    return duplicates

def find_similar_titles(books, similarity_threshold=0.85):
    """Find books with similar titles using fuzzy matching"""
    # Group books by author to reduce comparisons
    author_groups = defaultdict(list)
    
    for book in books:
        authors = tuple(sorted(book.get("authors", []))) if isinstance(book.get("authors"), list) else book.get("authors", "")
        author_groups[authors].append(book)
    
    # Find similar titles within each author group
    similar_groups = []
    
    for author, author_books in author_groups.items():
        # Skip if only one book by this author
        if len(author_books) < 2:
            continue
        
        # Compare each pair of books
        for i, book1 in enumerate(author_books):
            group = [book1]
            
            for j, book2 in enumerate(author_books):
                if i == j:
                    continue
                
                title1 = normalize_string(book1.get("title", ""))
                title2 = normalize_string(book2.get("title", ""))
                
                # Skip empty titles
                if not title1 or not title2:
                    continue
                
                # Calculate similarity ratio
                similarity = difflib.SequenceMatcher(None, title1, title2).ratio()
                
                if similarity >= similarity_threshold:
                    group.append(book2)
            
            # If we found similar books, add the group
            if len(group) > 1:
                similar_groups.append(group)
    
    return similar_groups

def find_isbn_duplicates(books):
    """Find books with identical ISBNs"""
    # Group books by ISBN
    isbn_groups = defaultdict(list)
    
    for book in books:
        # Check different ISBN fields
        for isbn_field in ["isbn", "identifiers"]:
            if isbn_field in book:
                if isbn_field == "isbn" and book[isbn_field]:
                    isbn_groups[book[isbn_field]].append(book)
                elif isbn_field == "identifiers" and isinstance(book[isbn_field], dict):
                    # Handle the 'identifiers' structure which may contain ISBN
                    for id_type, id_value in book[isbn_field].items():
                        if "isbn" in id_type.lower() and id_value:
                            isbn_groups[id_value].append(book)
    
    # Return groups with more than one book
    duplicates = {k: v for k, v in isbn_groups.items() if len(v) > 1}
    return duplicates

def find_all_duplicates(library_path=DEFAULT_CALIBRE_LIBRARY):
    """Find all types of duplicates in the library"""
    books = get_calibre_metadata(library_path)
    
    results = {
        "exact_matches": find_exact_duplicates(books, fields=["title", "authors"]),
        "similar_titles": find_similar_titles(books),
        "isbn_duplicates": find_isbn_duplicates(books),
    }
    
    return results

def format_duplicate_results(results):
    """Format duplicate results for display"""
    output = []
    
    # Format exact matches
    if results["exact_matches"]:
        output.append("## Exact Title/Author Matches")
        for key, books in results["exact_matches"].items():
            title, authors = key[0], key[1]
            output.append(f"\n### {title} by {authors}")
            for book in books:
                formats = ", ".join(book.get("formats", []))
                output.append(f"- ID: {book['id']} | Format: {formats} | Added: {book.get('timestamp')}")
    
    # Format similar titles
    if results["similar_titles"]:
        output.append("\n## Similar Titles by Same Author")
        for i, group in enumerate(results["similar_titles"], 1):
            output.append(f"\n### Group {i}")
            for book in group:
                title = book.get("title", "Unknown")
                authors = ", ".join(book.get("authors", [])) if isinstance(book.get("authors"), list) else book.get("authors", "Unknown")
                output.append(f"- ID: {book['id']} | {title} by {authors}")
    
    # Format ISBN duplicates
    if results["isbn_duplicates"]:
        output.append("\n## ISBN Duplicates")
        for isbn, books in results["isbn_duplicates"].items():
            output.append(f"\n### ISBN: {isbn}")
            for book in books:
                title = book.get("title", "Unknown")
                authors = ", ".join(book.get("authors", [])) if isinstance(book.get("authors"), list) else book.get("authors", "Unknown")
                output.append(f"- ID: {book['id']} | {title} by {authors}")
    
    return "\n".join(output)