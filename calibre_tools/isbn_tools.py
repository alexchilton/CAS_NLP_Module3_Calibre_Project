# calibre_tools/isbn_tools.py
import re
import subprocess
import json
from pathlib import Path
import os
from calibre_tools.config import DEFAULT_CALIBRE_LIBRARY

# Regular expressions for finding ISBNs
ISBN10_REGEX = r'(?:ISBN(?:-10)?:?\s*)?(\d{1,5}[-\s]?\d{1,7}[-\s]?\d{1,7}[-\s]?[\dX])'
ISBN13_REGEX = r'(?:ISBN(?:-13)?:?\s*)?(97[89][-\s]?\d{1,5}[-\s]?\d{1,7}[-\s]?\d{1,7}[-\s]?\d)'
ISBN_REGEX = fr'({ISBN10_REGEX}|{ISBN13_REGEX})'

def validate_isbn10(isbn):
    """Validate an ISBN-10 string"""
    # Remove hyphens and spaces
    isbn = re.sub(r'[-\s]', '', isbn)
    
    # Check length and format
    if not re.match(r'^\d{9}[\dX]$', isbn):
        return False
    
    # Calculate checksum
    digits = [int(d) if d != 'X' else 10 for d in isbn]
    checksum = sum((10 - i) * d for i, d in enumerate(digits))
    
    return checksum % 11 == 0

def validate_isbn13(isbn):
    """Validate an ISBN-13 string"""
    # Remove hyphens and spaces
    isbn = re.sub(r'[-\s]', '', isbn)
    
    # Check length and format
    if not re.match(r'^97[89]\d{10}$', isbn):
        return False
    
    # Calculate checksum
    digits = [int(d) for d in isbn]
    checksum = sum(d * (1 if i % 2 == 0 else 3) for i, d in enumerate(digits[:-1]))
    check_digit = (10 - (checksum % 10)) % 10
    
    return check_digit == digits[-1]

def validate_isbn(isbn):
    """Validate an ISBN string (either ISBN-10 or ISBN-13)"""
    # Remove hyphens and spaces
    isbn = re.sub(r'[-\s]', '', isbn)
    
    if len(isbn) == 10:
        return validate_isbn10(isbn)
    elif len(isbn) == 13:
        return validate_isbn13(isbn)
    
    return False

def extract_isbn_from_text(text):
    """Extract ISBN numbers from text"""
    if not text:
        return []
    
    # Find all potential ISBNs
    matches = []
    
    # Look for ISBN-10
    isbn10_matches = re.finditer(ISBN10_REGEX, text, re.IGNORECASE)
    for match in isbn10_matches:
        isbn = re.sub(r'[-\s]', '', match.group(1))
        if validate_isbn10(isbn):
            matches.append(isbn)
    
    # Look for ISBN-13
    isbn13_matches = re.finditer(ISBN13_REGEX, text, re.IGNORECASE)
    for match in isbn13_matches:
        isbn = re.sub(r'[-\s]', '', match.group(1))
        if validate_isbn13(isbn):
            matches.append(isbn)
    
    return matches

def extract_isbn_from_file(file_path):
    """Extract ISBN from ebook metadata using Calibre CLI"""
    file_path = os.path.expanduser(file_path)
    
    # Check if file exists
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    # Use calibredb to extract metadata
    cmd = [
        'ebook-meta',
        file_path
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        raise Exception(f"Failed to extract metadata: {result.stderr}")
    
    output = result.stdout
    
    # Extract ISBN from metadata
    isbns = extract_isbn_from_text(output)
    
    # Also look for identifiers line
    id_match = re.search(r'Identifiers\s*:\s*(.+)', output)
    if id_match:
        id_line = id_match.group(1)
        # Look for isbn:xxx pattern
        isbn_in_id = re.search(r'isbn:([^\s,]+)', id_line, re.IGNORECASE)
        if isbn_in_id:
            isbn = isbn_in_id.group(1).strip()
            if validate_isbn(isbn) and isbn not in isbns:
                isbns.append(isbn)
    
    return isbns

def find_books_by_isbn(isbn, library_path=DEFAULT_CALIBRE_LIBRARY):
    """Find books with a specific ISBN in the library"""
    # Normalize ISBN
    isbn = re.sub(r'[-\s]', '', isbn)
    
    cmd = [
        'calibredb', 'list',
        '--library-path', library_path,
        '--for-machine',
        '--search', f'identifiers:isbn:{isbn}'
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        raise Exception(f"Failed to search Calibre library: {result.stderr}")
    
    books = json.loads(result.stdout)
    return books

def get_book_isbn(book_id, library_path=DEFAULT_CALIBRE_LIBRARY):
    """Get ISBN for a specific book in the library"""
    cmd = [
        'calibredb', 'list',
        '--library-path', library_path,
        '--for-machine',
        '--search', f'id:{book_id}'
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        raise Exception(f"Failed to search Calibre library: {result.stderr}")
    
    books = json.loads(result.stdout)
    
    if not books:
        return None
    
    book = books[0]
    
    # Check for ISBN in identifiers
    identifiers = book.get('identifiers', {})
    if isinstance(identifiers, dict) and 'isbn' in identifiers:
        return identifiers['isbn']
    
    # If not found, try to extract from other metadata
    isbns = []
    
    # Check title
    if 'title' in book:
        isbns.extend(extract_isbn_from_text(book['title']))
    
    # Check comments
    if 'comments' in book:
        isbns.extend(extract_isbn_from_text(book['comments']))
    
    return isbns[0] if isbns else None