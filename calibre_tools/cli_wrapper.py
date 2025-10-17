# calibre_tools/cli_wrapper.py
import subprocess
import json
import os
import re
from pathlib import Path
from calibre_tools.config import DEFAULT_CALIBRE_LIBRARY

def list_books(library_path=DEFAULT_CALIBRE_LIBRARY, search_term=None, sort_by=None, limit=None):
    """List books in the Calibre library"""
    cmd = [
        'calibredb', 'list',
        '--library-path', library_path,
        '--for-machine'
    ]
    
    if search_term:
        cmd.extend(['--search', search_term])
    
    if sort_by:
        cmd.extend(['--sort-by', sort_by])
    
    if limit:
        cmd.extend(['--limit', str(limit)])
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        raise Exception(f"Failed to list books: {result.stderr}")
    
    books = json.loads(result.stdout)
    return books

def add_book(file_path, library_path=DEFAULT_CALIBRE_LIBRARY, **metadata):
    """Add a book to the Calibre library with metadata"""
    cmd = [
        'calibredb', 'add',
        '--library-path', library_path,
        '--with-library', library_path
    ]
    
    # Add metadata
    for key, value in metadata.items():
        if value:
            cmd.extend([f'--{key}', value])
    
    # Add file path
    cmd.append(os.path.expanduser(file_path))
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        raise Exception(f"Failed to add book: {result.stderr}")
    
    # Extract book ID from output
    match = re.search(r'Added book ids: (\d+)', result.stdout)
    if match:
        return int(match.group(1))
    
    return None

def remove_book(book_id, library_path=DEFAULT_CALIBRE_LIBRARY, permanent=False):
    """Remove a book from the Calibre library"""
    cmd = [
        'calibredb', 'remove',
        '--library-path', library_path
    ]
    
    if permanent:
        cmd.append('--permanent')
    
    # Add book ID
    cmd.append(str(book_id))
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        raise Exception(f"Failed to remove book: {result.stderr}")
    
    return True

def set_metadata(book_id, library_path=DEFAULT_CALIBRE_LIBRARY, **metadata):
    """Set metadata for a book in the Calibre library"""
    cmd = [
        'calibredb', 'set_metadata',
        '--library-path', library_path
    ]
    
    # Add field metadata
    for key, value in metadata.items():
        if value is not None:
            cmd.extend([f'--field', f'{key}:{value}'])
    
    # Add book ID
    cmd.append(str(book_id))
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        raise Exception(f"Failed to set metadata: {result.stderr}")
    
    return True

def convert_book(book_id, output_format, library_path=DEFAULT_CALIBRE_LIBRARY):
    """Convert a book to another format"""
    cmd = [
        'calibredb', 'export',
        '--library-path', library_path,
        '--format', output_format
    ]
    
    # Add book ID
    cmd.append(str(book_id))
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        raise Exception(f"Failed to convert book: {result.stderr}")
    
    return result.stdout.strip()  # Returns the path to the converted file

def search_library(query, library_path=DEFAULT_CALIBRE_LIBRARY):
    """Search the Calibre library using the built-in search functionality"""
    cmd = [
        'calibredb', 'list',
        '--library-path', library_path,
        '--for-machine',
        '--search', query
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise Exception(f"Failed to search library: {result.stderr}")

    books = json.loads(result.stdout)
    return books

def get_book_metadata(book_id, library_path=DEFAULT_CALIBRE_LIBRARY, as_opf=False):
    """Get detailed metadata for a specific book

    Args:
        book_id: The Calibre book ID
        library_path: Path to the Calibre library
        as_opf: If True, return OPF XML format; if False, return parsed text

    Returns:
        If as_opf=True: XML string
        If as_opf=False: Dictionary with parsed metadata
    """
    cmd = [
        'calibredb', 'show_metadata',
        '--library-path', library_path,
        str(book_id)
    ]

    if as_opf:
        cmd.append('--as-opf')

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise Exception(f"Failed to get book metadata: {result.stderr}")

    if as_opf:
        return result.stdout

    # Parse the text output into a dictionary
    metadata = {}
    lines = result.stdout.strip().split('\n')

    for line in lines:
        if ':' in line:
            key, value = line.split(':', 1)
            key = key.strip()
            value = value.strip()

            # Handle multi-value fields
            if key in metadata:
                if isinstance(metadata[key], list):
                    metadata[key].append(value)
                else:
                    metadata[key] = [metadata[key], value]
            else:
                metadata[key] = value

    return metadata

def fetch_ebook_metadata(title=None, authors=None, isbn=None, identifiers=None,
                        as_opf=False, timeout=30, allowed_plugins=None):
    """Fetch book metadata from online sources (Amazon, Goodreads, Google Books, etc.)

    Args:
        title: Book title
        authors: Book author(s)
        isbn: Book ISBN
        identifiers: List of identifiers in format "source:value"
                    (e.g., ["amazon:B004XFYWNY", "goodreads:39799149"])
        as_opf: If True, return OPF XML format; if False, return parsed text
        timeout: Timeout in seconds (default: 30)
        allowed_plugins: List of plugin names to use (default: all)
                        Options: Goodreads, Google, Google Images, Amazon.com,
                        Edelweiss, Open Library, Big Book Search

    Returns:
        If as_opf=True: XML string
        If as_opf=False: Dictionary with parsed metadata

    Examples:
        # Search by ASIN (Amazon ID)
        metadata = fetch_ebook_metadata(identifiers=["amazon:B004XFYWNY"])

        # Search by ISBN
        metadata = fetch_ebook_metadata(isbn="9780547928227")

        # Search by title and author
        metadata = fetch_ebook_metadata(title="The Hobbit", authors="J.R.R. Tolkien")

        # Use specific plugins only
        metadata = fetch_ebook_metadata(
            identifiers=["amazon:B004XFYWNY"],
            allowed_plugins=["Amazon.com", "Goodreads"]
        )
    """
    if not any([title, authors, isbn, identifiers]):
        raise ValueError("Must specify at least one of: title, authors, isbn, or identifiers")

    cmd = ['fetch-ebook-metadata']

    # Add search criteria
    if title:
        cmd.extend(['--title', title])
    if authors:
        cmd.extend(['--authors', authors])
    if isbn:
        cmd.extend(['--isbn', isbn])
    if identifiers:
        for identifier in identifiers:
            cmd.extend(['--identifier', identifier])

    # Add options
    if as_opf:
        cmd.append('--opf')

    cmd.extend(['--timeout', str(timeout)])

    if allowed_plugins:
        for plugin in allowed_plugins:
            cmd.extend(['--allowed-plugin', plugin])

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise Exception(f"Failed to fetch ebook metadata: {result.stderr}")

    if as_opf:
        return result.stdout

    # Parse the text output into a dictionary
    metadata = {}
    lines = result.stdout.strip().split('\n')

    for line in lines:
        if ':' in line:
            key, value = line.split(':', 1)
            key = key.strip()
            value = value.strip()

            # Handle multi-value fields
            if key in metadata:
                if isinstance(metadata[key], list):
                    metadata[key].append(value)
                else:
                    metadata[key] = [metadata[key], value]
            else:
                metadata[key] = value

    return metadata