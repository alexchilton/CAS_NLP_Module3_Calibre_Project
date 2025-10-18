# Calibre Tools

A comprehensive set of tools for interacting with your Calibre library, including semantic search, duplicate detection, ISBN tools, and MCP integration for Claude.

[![Tests](https://img.shields.io/badge/tests-86%20passed-brightgreen)]()
[![Coverage](https://img.shields.io/badge/coverage-75%25-yellow)]()
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)]()

## ✨ Features

- 🔍 **Semantic Search**: Find books using natural language queries powered by sentence transformers
- 📖 **Complete Metadata**: Get full book details including descriptions, publisher, ISBN, formats
- 🚀 **Batch Enrichment**: Automatically find and enrich books missing metadata from online sources
- 🌐 **Online Metadata Fetching**: Query Amazon, Goodreads, Google Books for rich metadata
- 🔄 **Duplicate Detection**: Find duplicate books by title, author, ISBN, or content similarity
- 📚 **ISBN Tools**: Extract, validate, and search for ISBN-10 and ISBN-13
- 🛠️ **Calibre CLI Integration**: Python wrappers for all common Calibre operations
- 🤖 **MCP Integration**: Use tools directly in Claude Desktop via Model Context Protocol
- ⚡ **Performance Optimized**: Lazy loading, caching, and MPS support for Apple Silicon

---

## 📦 Installation

### Prerequisites
- Python 3.11+
- Calibre installed and in PATH
- (Optional) PyTorch for semantic search

### Install from source
```bash
git clone https://github.com/yourusername/calibre-tools.git
cd calibre-tools
pip install -e .
```

### Install dependencies
```bash
# Core dependencies
pip install sentence-transformers scikit-learn numpy

# Testing dependencies
pip install pytest pytest-cov

# MCP dependencies
pip install mcp
```

---

## 🚀 Quick Start

### Python API

```python
from calibre_tools import semantic_search, isbn_tools, duplicate_finder

# Semantic search
results = semantic_search.search("fantasy novels with dragons", top_n=5)
for result in results:
    print(f"{result['metadata']['title']} (Score: {result['score']:.2f})")

# Validate ISBN
is_valid = isbn_tools.validate_isbn("978-0-547-92822-7")
print(f"ISBN valid: {is_valid}")

# Find duplicates
duplicates = duplicate_finder.find_all_duplicates()
print(f"Found {len(duplicates['exact_matches'])} exact duplicates")
```

### Command Line

```python
# Using Python directly
python -c "from calibre_tools.semantic_search import search; print(search('sci-fi', 3))"

# Or use the manual test script (see below)
python manual_test.py
```

---

## 🧪 Testing

### Automated Tests (pytest)

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=calibre_tools --cov-report=html

# Run specific test file
pytest tests/calibre_tools/test_isbn_tools.py

# Run specific test
pytest tests/calibre_tools/test_isbn_tools.py::TestISBNTools::test_validate_isbn10_valid -v

# View coverage report
open htmlcov/index.html
```

**Test Results:**
- ✅ **86 tests** - All passing
- ⚡ **~3 seconds** - Fast execution
- 📊 **75% coverage** - High code coverage
- 🎯 **100% calibre_tools** - Core modules fully tested

### Manual/Interactive Testing

For testing with your actual Calibre library:

```bash
python manual_test.py
```

This launches an interactive menu where you can:

**CLI Wrapper Tests:**
1. List books (with search, sort, limit)
2. Add books with metadata ⚠️
3. Remove books ⚠️
4. Set metadata ⚠️
5. Search library

**ISBN Tools:**
6. Validate ISBNs
7. Extract ISBNs from text
8. Extract ISBNs from files
9. Find books by ISBN

**Duplicate Finder:**
10. Find all duplicates (exact, similar, ISBN)

**Semantic Search:**
11. Natural language search

**Features:**
- ✅ Safe by default - warns before modifications
- ✅ Interactive prompts for destructive operations
- ✅ Pretty-printed JSON output
- ✅ Test with real Calibre data
- ✅ Quick test mode for common operations

**Example Session:**
```
$ python manual_test.py

Options:
  1. Interactive menu
  2. Quick test
  3. Exit

Enter choice: 1

Using Calibre library: ~/Calibre Library

SELECT A TEST:
============================================================
CLI WRAPPER:
  1. List books
  ...

Enter choice: 1

============================================================
  LIST BOOKS
============================================================
Getting first 5 books from library...

Found 5 books:
[
  {
    "id": 1,
    "title": "The Hobbit",
    "authors": ["J.R.R. Tolkien"],
    ...
  }
]
```

---

## 🔧 Configuration

Configuration is handled via environment variables and `calibre_tools/config.py`:

### Environment Variables

```bash
# Calibre library path
export CALIBRE_LIBRARY_PATH="~/Calibre Library"

# Force cache refresh
export FORCE_REFRESH=1

# Cache expiry (days)
export CACHE_EXPIRY_DAYS=7

# Force CUDA (otherwise auto-detects MPS on Mac)
export USE_CUDA=1
```

### Device Detection

The system automatically detects the best available device:
1. **CUDA** - If `USE_CUDA=1` and CUDA available
2. **MPS** - If on Mac with Apple Silicon (with fallback)
3. **CPU** - Default fallback

### Cache Settings

Embeddings are cached in `~/.calibre_tools/`:
- `embeddings.pkl` - Book embeddings
- `metadata.json` - Book metadata

Cache is refreshed when:
- Files don't exist
- Files older than `CACHE_EXPIRY_DAYS`
- `FORCE_REFRESH=1` set

---

## 🤖 MCP Integration for Claude

### Setup

1. Start the MCP server:
```bash
python -m calibre_mcp.app
```

2. Configure Claude Desktop (add to `claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "calibre": {
      "command": "python",
      "args": ["-m", "calibre_mcp.app"],
      "env": {
        "CALIBRE_LIBRARY_PATH": "/path/to/Calibre Library"
      }
    }
  }
}
```

### Available Tools (22 total)

**Search & Discovery:**
- `calibre_semantic_search` - Search using natural language
- `calibre_list_books` - List books with filters
- `calibre_search_library` - Search using Calibre syntax
- `calibre_get_book_details` - Get complete metadata for a specific book
- `calibre_sql` - Execute read-only SQL queries on Calibre's metadata.db

**Metadata Enrichment:**
- `calibre_fetch_metadata_by_identifier` - Fetch metadata using ASIN, ISBN, or Goodreads ID
- `calibre_fetch_metadata_by_title` - Fetch metadata by title/author
- `calibre_enrich_book_metadata` - Auto-detect identifiers and enrich (with preview)
- `calibre_apply_metadata_updates` - Apply suggested metadata updates
- `calibre_find_books_needing_enrichment` - Find books with ISBNs missing metadata
- `calibre_batch_enrich_books` - Batch process multiple books
- `calibre_enrich_identifier_titles` - Find and enrich books where title is an ISBN/ASIN

**Duplicate Detection:**
- `calibre_find_duplicates` - Find duplicate books by title, author, ISBN

**ISBN Tools:**
- `calibre_isbn_extract_from_text` - Extract ISBNs from text
- `calibre_isbn_validate` - Validate ISBN
- `calibre_isbn_find_books` - Find books by ISBN

**Library Management:**
- `calibre_add_book` - Add book to library
- `calibre_remove_book` - Remove book from library
- `calibre_set_book_metadata` - Update book metadata (title, authors, isbn, tags, publisher, comments, pubdate, series, rating, language)
- `calibre_bulk_update_comments` - Bulk update comments/description for multiple books
- `calibre_convert_format` - Convert book formats
- `calibre_export_book` - Export book files

### Example Workflow: Batch Enrichment in Claude Desktop

Here's how to use the metadata enrichment tools to automatically enrich books missing metadata:

**1. Find books needing enrichment:**
```
You: "Find 10 books with ISBNs that are missing descriptions"
→ Uses calibre_find_books_needing_enrichment
→ Returns list of books with IDs, titles, ISBNs
```

**2. Enrich a single book (automatic identifier detection):**
```
You: "Enrich book ID 1762"
→ Uses calibre_enrich_book_metadata
→ Auto-detects ISBN/ASIN from title or identifiers field
→ Fetches metadata from Amazon/Goodreads/Google Books
→ Shows existing metadata vs. suggested updates
```

**3. Apply updates selectively:**
```
You: "Update the publisher and series for book 1762"
→ Uses calibre_apply_metadata_updates(1762, "Publisher,Series")
→ Applies only the specified fields
→ Returns confirmation of updates
```

**4. Batch process multiple books:**
```
You: "Batch enrich 20 books with ISBNs missing metadata"
→ Uses calibre_batch_enrich_books(20)
→ Processes up to 20 books automatically
→ Returns summary: total processed, successful, failed
→ Shows detailed results for each book
```

**Key Features:**
- ✅ **Auto-detection** - Finds ASIN/ISBN in title or identifiers field
- ✅ **Preview before applying** - See suggested changes before updating
- ✅ **Selective updates** - Choose which fields to update
- ✅ **Batch processing** - Enrich 10-50 books at once
- ✅ **Focus on ISBNs** - More reliable than ASINs for metadata fetching

### Example Workflow: Bulk Update Comments for Magazines

The `calibre_bulk_update_comments` tool is perfect for adding generic descriptions to groups of books (e.g., magazines, periodicals) to prevent them from being picked up by metadata enrichment tools:

**1. Find magazine/periodical IDs:**
```
You: "Find all books with 'The Economist' in the title"
→ Uses calibre_search_library or calibre_list_books
→ Returns list of book IDs
```

**2. Bulk update comments:**
```
You: "Update the comments for books [1234, 1235, 1236, ...] with the text 'This is a periodical/magazine issue and does not require metadata enrichment.'"
→ Uses calibre_bulk_update_comments
→ Updates all books at once
→ Returns success/failure count and detailed results
```

**Example Response:**
```json
{
  "success_count": 290,
  "failure_count": 0,
  "total": 290,
  "updated_ids": [1234, 1235, 1236, ...],
  "errors": null
}
```

**Use Cases:**
- 📰 **Magazines** - Mark periodicals to exclude from enrichment
- 📚 **Series** - Add uniform descriptions to book series
- 🏷️ **Categorization** - Bulk categorize books by type
- 🚫 **Exclusion** - Mark books to skip in automated processing

---

## 📁 Project Structure

```
.
├── calibre_tools/              # Core functionality
│   ├── __init__.py
│   ├── config.py               # Configuration & device detection
│   ├── semantic_search.py      # Semantic search with embeddings
│   ├── duplicate_finder.py     # Duplicate detection algorithms
│   ├── isbn_tools.py           # ISBN extraction & validation
│   ├── cli_wrapper.py          # Calibre CLI wrappers (get_book_metadata, fetch_ebook_metadata)
│   └── batch_enrichment.py     # Batch enrichment tools (NEW)
│
├── calibre_mcp/                # MCP integration
│   ├── __init__.py
│   ├── app.py                  # MCP server entry point
│   ├── server.py               # MCP server instance
│   └── tools/                  # MCP tool definitions
│       ├── __init__.py
│       ├── semantic_search.py
│       ├── book_details.py     # calibre_get_book_details (NEW)
│       ├── metadata_enrichment.py  # 6 enrichment tools (NEW)
│       ├── duplicate_finder.py
│       ├── isbn_tools.py
│       └── calibre_cli.py
│
├── tests/                      # Comprehensive test suite
│   ├── conftest.py             # Shared fixtures
│   └── calibre_tools/
│       ├── test_config.py      # 9 tests
│       ├── test_semantic_search.py  # 14 tests
│       ├── test_duplicate_finder.py # 13 tests
│       ├── test_isbn_tools.py  # 19 tests
│       └── test_cli_wrapper.py # 31 tests (10 new tests)
│
├── manual_test.py              # Interactive testing script
├── pytest.ini                  # Pytest configuration
├── .coveragerc                 # Coverage configuration
├── TEST_RESULTS.md             # Detailed test documentation
└── README.md                   # This file
```

---

## 📖 API Documentation

### Semantic Search

```python
from calibre_tools.semantic_search import search, CalibreSemanticSearch

# Quick search
results = search("epic fantasy adventure", top_n=5)

# Advanced usage
searcher = CalibreSemanticSearch(
    library_path="~/Calibre Library",
    model_name="all-MiniLM-L6-v2",
    device="mps"  # or "cuda", "cpu"
)
results = searcher.search("query", top_n=10)
```

### Duplicate Finder

```python
from calibre_tools.duplicate_finder import (
    find_all_duplicates,
    find_exact_duplicates,
    find_similar_titles,
    find_isbn_duplicates
)

# Find all types
results = find_all_duplicates(library_path="~/Calibre Library")

# Find specific types
exact = find_exact_duplicates(books, fields=['title', 'authors'])
similar = find_similar_titles(books, similarity_threshold=0.85)
isbn = find_isbn_duplicates(books)
```

### ISBN Tools

```python
from calibre_tools.isbn_tools import (
    validate_isbn,
    validate_isbn10,
    validate_isbn13,
    extract_isbn_from_text,
    extract_isbn_from_file,
    find_books_by_isbn,
    get_book_isbn
)

# Validate
is_valid = validate_isbn("978-0-547-92822-7")

# Extract
isbns = extract_isbn_from_text("ISBN: 978-0-547-92822-7")
isbns = extract_isbn_from_file("book.epub")

# Find books
books = find_books_by_isbn("9780547928227")
```

### CLI Wrapper

```python
from calibre_tools.cli_wrapper import (
    list_books,
    add_book,
    remove_book,
    set_metadata,
    bulk_update_comments,
    convert_book,
    search_library,
    fetch_ebook_metadata,
    get_book_metadata
)

# List with filters
books = list_books(
    library_path="~/Calibre Library",
    search_term="tolkien",
    sort_by="title",
    limit=10
)

# Add book
book_id = add_book(
    "book.epub",
    title="My Book",
    authors="Author Name",
    isbn="9780547928227"
)

# Update single book metadata
set_metadata(
    book_id=1762,
    library_path="~/Calibre Library",
    publisher="Publisher Name",
    comments="Book description",
    tags="fiction,fantasy"
)

# Bulk update comments for multiple books
results = bulk_update_comments(
    book_ids=[1234, 1235, 1236],
    comment_text="This is a periodical/magazine issue.",
    library_path="~/Calibre Library"
)
print(f"Updated {results['success_count']} books")

# Search
books = search_library("author:tolkien AND tags:fantasy")

# Fetch metadata from online sources
metadata = fetch_ebook_metadata(isbn="9780547928227", timeout=30)
# Or by ASIN
metadata = fetch_ebook_metadata(identifiers=["amazon:B004XFYWNY"])

# Get full book details from Calibre
details = get_book_metadata(book_id=1762)
```

### Batch Enrichment

```python
from calibre_tools.batch_enrichment import (
    find_books_needing_enrichment,
    enrich_single_book,
    batch_enrich_books
)

# Find books with ISBNs that are missing descriptions
candidates = find_books_needing_enrichment(
    limit=10,
    require_isbn=True,
    missing_fields=['comments', 'publisher']
)

print(f"Found {len(candidates)} books needing enrichment")
for book in candidates:
    print(f"  {book['id']}: {book['title']} (ISBN: {book['isbn']})")

# Enrich a single book
result = enrich_single_book(book_id=1679)
if result['success']:
    print(f"Fetched metadata: {result['fetched_metadata']}")

    # Apply updates
    from calibre_tools.cli_wrapper import set_metadata
    set_metadata(
        book_id=1679,
        publisher=result['fetched_metadata']['Publisher'],
        comments=result['fetched_metadata']['Comments']
    )

# Batch process multiple books
results = batch_enrich_books(limit=10, find_candidates=True)
print(f"Processed: {results['total_processed']}")
print(f"Successful: {results['successful']}")
print(f"Failed: {results['failed']}")

for r in results['results']:
    if r['success']:
        print(f"✓ Book {r['book_id']}: Enriched with {r['identifier_used']}")
    else:
        print(f"✗ Book {r['book_id']}: {r['error']}")
```

---

## 🐛 Troubleshooting

### Common Issues

**"calibredb not found"**
- Ensure Calibre is installed and in your PATH
- On Mac: `/Applications/calibre.app/Contents/MacOS/calibredb`

**MPS not working on Mac**
- Check PyTorch version: `python -c "import torch; print(torch.backends.mps.is_available())"`
- System falls back to CPU automatically

**Slow first search**
- First run downloads embedding model (~90MB)
- Subsequent searches use cached embeddings

**Import errors**
- Ensure all dependencies installed: `pip install -r requirements.txt`

### Debug Mode

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

---

## 🤝 Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Write tests for new features
4. Ensure all tests pass: `pytest`
5. Submit a pull request

---

## 📄 License

MIT License - see LICENSE file for details

---

## 🙏 Acknowledgments

- Calibre - Amazing ebook management software
- sentence-transformers - Semantic search models
- MCP - Model Context Protocol by Anthropic

---

## 📞 Support

- Issues: [GitHub Issues](https://github.com/yourusername/calibre-tools/issues)
- Documentation: See `TEST_RESULTS.md` for detailed test documentation

---

**Built with ❤️ for the Calibre community**
