# Calibre Tools

A comprehensive set of tools for interacting with your Calibre library, including semantic search, duplicate detection, ISBN tools, and MCP integration for Claude.

[![Tests](https://img.shields.io/badge/tests-79%20passed-brightgreen)]()
[![Coverage](https://img.shields.io/badge/coverage-75%25-yellow)]()
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)]()

## ✨ Features

- 🔍 **Semantic Search**: Find books using natural language queries powered by sentence transformers
- 📖 **Complete Metadata**: Get full book details including descriptions, publisher, ISBN, formats
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
- ✅ **79 tests** - All passing
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

### Available Tools

- `calibre_semantic_search` - Search using natural language
- `calibre_get_book_details` - Get complete metadata for a specific book
- `calibre_find_duplicates` - Find duplicate books
- `calibre_isbn_extract_from_text` - Extract ISBNs from text
- `calibre_isbn_validate` - Validate ISBN
- `calibre_isbn_find_books` - Find books by ISBN
- `calibre_list_books` - List books with filters
- `calibre_search_library` - Search using Calibre syntax
- `calibre_add_book` - Add book to library
- And more...

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
│   └── cli_wrapper.py          # Calibre CLI wrappers
│
├── calibre_mcp/                # MCP integration
│   ├── __init__.py
│   ├── app.py                  # MCP server entry point
│   ├── server.py               # MCP server instance
│   └── tools/                  # MCP tool definitions
│       ├── __init__.py
│       ├── semantic_search.py
│       ├── book_details.py
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
│       └── test_cli_wrapper.py # 24 tests
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
    convert_book,
    search_library
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

# Search
books = search_library("author:tolkien AND tags:fantasy")
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
