# Course Scraper Enhanced

Enhanced course metadata scraper for preparing video courses for Calibre integration.

## Features

### Full Metadata Extraction
- **Title** - Cleaned and normalized
- **Authors/Instructors** - Multiple instructors supported
- **Description** - Full course description
- **Publisher** - Platform name (Udemy, Coursera, etc.)
- **Tags** - Course topics/categories/level
- **Publication Date** - Last updated date (when available)
- **Duration** - Course length (when available)
- **Course URL** - Link to online course page
- **File Path** - Local filesystem path to course directory

### Supported Platforms
1. **Udemy** - Full metadata support
2. **Coursera** - Full metadata support
3. **Pluralsight** - Full metadata support
4. **LinkedIn Learning** - Full metadata support

### Smart Features
- **Platform Auto-Detection** - From directory name keywords
- **Title Cleaning** - Removes platform tags, brackets, "FULL COURSE", etc.
- **DuckDuckGo Search** - Automatically finds course URLs
- **Fallback Strategies** - Uses og:meta tags when scraping fails
- **Extensible** - Easy to add new platforms via strategy pattern

## Usage

### Basic Usage

```python
from course_scraper_enhanced import extract_course_metadata

# Extract metadata from a course directory name
metadata = extract_course_metadata(
    directory_title="The Complete Python Course 2024 [Udemy]",
    file_path="/Users/you/Courses/Udemy/Python2024"
)

if metadata:
    print(f"Title: {metadata.title}")
    print(f"Authors: {', '.join(metadata.authors)}")
    print(f"Platform: {metadata.platform}")
    print(f"Description: {metadata.description[:100]}...")
    print(f"File path: {metadata.file_path}")
```

### Get Dictionary Output

```python
metadata_dict = metadata.to_dict()
# Returns:
# {
#     'title': 'The Complete Python Course 2024',
#     'authors': ['Jose Portilla'],
#     'description': 'Learn Python...',
#     'publisher': 'Udemy',
#     'tags': ['Development', 'Programming Languages', 'Python'],
#     'pubdate': '2024-01-15T00:00:00',
#     'duration': '20h 30m',
#     'course_url': 'https://www.udemy.com/course/complete-python-bootcamp/',
#     'file_path': '/Users/you/Courses/Udemy/Python2024',
#     'platform': 'Udemy'
# }
```

### Batch Processing

```python
import os
from course_scraper_enhanced import extract_course_metadata

courses_dir = "/Users/you/Courses"
results = []

for course_folder in os.listdir(courses_dir):
    full_path = os.path.join(courses_dir, course_folder)
    if os.path.isdir(full_path):
        print(f"Processing: {course_folder}")
        metadata = extract_course_metadata(course_folder, file_path=full_path)
        if metadata:
            results.append(metadata)

print(f"\nSuccessfully processed {len(results)} courses")
```

## Future Calibre Integration

The scraper is designed to prepare metadata for Calibre, but **does not write to the database yet**.

### Proposed Workflow:

1. **Scan course directories** using this scraper
2. **Review extracted metadata**
3. **Add to Calibre** using custom integration:
   - Create virtual "ebook" entries for courses
   - Store file path in custom column
   - Use course URL as identifier
   - Tag with platform and topics

### Custom Calibre Columns Needed:

```python
# Proposed custom columns for courses:
'course_url'      # URL to online course
'course_path'     # Local file system path
'duration'        # Course length
'platform'        # Udemy, Coursera, etc.
'instructor'      # Course instructor(s)
```

## Testing

Comprehensive test suite with 27 tests covering:
- Metadata extraction for all platforms
- Title cleaning logic
- Platform detection
- Edge cases and error handling

```bash
pytest tests/test_course_scraper.py -v
```

All tests use mocked HTML to avoid hitting live websites.

## Architecture

### Strategy Pattern
Each platform has its own metadata scraper function:
- `scrape_udemy_metadata()`
- `scrape_coursera_metadata()`
- `scrape_pluralsight_metadata()`
- `scrape_linkedin_metadata()`

### Configuration
Platform details stored in `PLATFORMS` dict:
```python
PLATFORMS = {
    "udemy.com": {
        "name": "Udemy",
        "metadata_scraper": scrape_udemy_metadata,
        "keywords": ["udemy"]
    },
    # ...
}
```

### Adding New Platforms

1. **Write scraper function:**
```python
def scrape_newplatform_metadata(soup: BeautifulSoup, url: str) -> CourseMetadata:
    metadata = CourseMetadata()
    metadata.platform = "NewPlatform"
    metadata.publisher = "NewPlatform"
    # ... extract title, authors, description, etc.
    return metadata
```

2. **Add to PLATFORMS dict:**
```python
"newplatform.com": {
    "name": "NewPlatform",
    "metadata_scraper": scrape_newplatform_metadata,
    "keywords": ["newplatform"]
}
```

3. **Write tests!**

## Limitations & Notes

### Current Limitations:
- Requires internet connection (DuckDuckGo search + web scraping)
- Selectors may break if platforms update their HTML
- No authentication handling (can't access enrolled-only content)
- Rate limiting not implemented (use delays for batch processing)

### Best Practices:
- Use delays between requests to avoid rate limiting
- Cache results to avoid re-scraping
- Test scrapers periodically as sites change
- Use for personal course library organization only

## Example Output

```
================================================================================
Processing: The Complete 2024 Python Pro Course [Udemy]
================================================================================
  → Cleaned title: The Complete 2024 Python Pro Course
  → Detected platform: Udemy
  → Searching DuckDuckGo for: "The Complete 2024 Python Pro Course" site:udemy.com
  → Found URL: https://www.udemy.com/course/complete-python-bootcamp/
  → Using 'Udemy' metadata scraper...
  → Fetching https://www.udemy.com/course/complete-python-bootcamp/...
  ✓ Successfully extracted metadata
    Title: Complete Python Bootcamp From Zero to Hero in Python
    Authors: Jose Portilla
    Platform: Udemy
    Tags: Development, Programming Languages, Python
```

## Dependencies

- `requests` - HTTP requests
- `beautifulsoup4` - HTML parsing
- `ddgs` - DuckDuckGo search
- `pytest` - Testing (dev dependency)

## License

Part of the Calibre Tools project. See main project LICENSE.
