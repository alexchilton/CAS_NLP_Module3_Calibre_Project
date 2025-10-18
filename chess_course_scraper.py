#!/usr/bin/env python3
"""
Chess course scraper with full metadata extraction for Calibre integration.

Supports:
- Chessable (chessable.com)
- ChessBase (chessbase.com)
- Modern Chess (modern-chess.com)
- TheChessWorld (thechessworld.com)

Extracts:
- Title (cleaned)
- Author/Instructor(s)
- Description
- Publisher (platform name)
- Tags (opening, level, etc.)
- Publication/Update Date
- Course URL
- File path

Does NOT write to Calibre database - just returns structured metadata.
"""

import re
import requests
from bs4 import BeautifulSoup
from typing import Optional, Dict, Any, List
from datetime import datetime
from pathlib import Path
from ddgs import DDGS

# --- Generic Configuration ---
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36'
}

# --- Chess Course Metadata Structure ---
class ChessCourseMetadata:
    """Structured chess course metadata ready for Calibre."""

    def __init__(self):
        self.title: Optional[str] = None
        self.authors: List[str] = []  # Authors/Coaches
        self.description: Optional[str] = None
        self.publisher: Optional[str] = None  # Platform name
        self.tags: List[str] = []  # Opening, level, topics
        self.pubdate: Optional[str] = None  # ISO format
        self.opening: Optional[str] = None  # Chess opening name
        self.level: Optional[str] = None  # Beginner, Intermediate, Advanced
        self.course_url: Optional[str] = None
        self.file_path: Optional[str] = None  # Local course directory/file
        self.platform: Optional[str] = None
        self.content_type: Optional[str] = None  # video, pgn, study, database, ebook, other

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for easy JSON serialization."""
        return {
            'title': self.title,
            'authors': self.authors,
            'description': self.description,
            'publisher': self.publisher,
            'tags': self.tags,
            'pubdate': self.pubdate,
            'opening': self.opening,
            'level': self.level,
            'course_url': self.course_url,
            'file_path': self.file_path,
            'platform': self.platform,
            'content_type': self.content_type
        }

    def __repr__(self):
        return f"ChessCourseMetadata(title='{self.title}', authors={self.authors}, platform='{self.platform}')"


# --- Platform-Specific Metadata Scrapers ---

def scrape_chessable_metadata(soup: BeautifulSoup, url: str) -> ChessCourseMetadata:
    """Extract full metadata from Chessable course page."""
    metadata = ChessCourseMetadata()
    metadata.platform = "Chessable"
    metadata.publisher = "Chessable"
    metadata.course_url = url

    # Title
    title_tag = soup.find('h1', {'class': 'course-title'})
    if not title_tag:
        title_tag = soup.find('h1')
    if not title_tag:
        title_tag = soup.find('meta', property='og:title')
        if title_tag:
            metadata.title = title_tag.get('content')
    else:
        metadata.title = title_tag.get_text(strip=True)

    # Description
    desc_section = soup.find('div', {'class': 'course-description'})
    if desc_section:
        metadata.description = desc_section.get_text(separator='\n', strip=True)
    else:
        meta_desc = soup.find('meta', property='og:description')
        if meta_desc:
            metadata.description = meta_desc.get('content')

    # Authors (look for "by" text or author links)
    author_section = soup.find('div', {'class': 'course-author'})
    if author_section:
        author_links = author_section.find_all('a')
        metadata.authors = [link.get_text(strip=True) for link in author_links]
    else:
        # Try to find "by Author Name" pattern
        by_pattern = soup.find(string=re.compile(r'by\s+', re.IGNORECASE))
        if by_pattern:
            # Extract author name after "by"
            match = re.search(r'by\s+([\w\s]+)', by_pattern, re.IGNORECASE)
            if match:
                metadata.authors = [match.group(1).strip()]

    # Tags/Opening (Chessable often has repertoire tags)
    tags_section = soup.find('div', {'class': 'course-tags'})
    if tags_section:
        tag_links = tags_section.find_all('a')
        metadata.tags = [link.get_text(strip=True) for link in tag_links]

    # Try to extract opening from title
    opening = extract_opening_from_title(metadata.title or "")
    if opening:
        metadata.opening = opening
        if opening not in metadata.tags:
            metadata.tags.append(opening)

    # Level (beginner, intermediate, advanced)
    level = extract_level_from_text(metadata.description or "")
    if level:
        metadata.level = level
        if level not in metadata.tags:
            metadata.tags.append(level)

    return metadata


def scrape_chessbase_metadata(soup: BeautifulSoup, url: str) -> ChessCourseMetadata:
    """Extract full metadata from ChessBase product page."""
    metadata = ChessCourseMetadata()
    metadata.platform = "ChessBase"
    metadata.publisher = "ChessBase"
    metadata.course_url = url

    # Title
    title_tag = soup.find('h1', {'class': 'product-title'})
    if not title_tag:
        title_tag = soup.find('h1')
    if not title_tag:
        title_tag = soup.find('meta', property='og:title')
        if title_tag:
            metadata.title = title_tag.get('content')
    else:
        metadata.title = title_tag.get_text(strip=True)

    # Description
    desc_section = soup.find('div', {'class': 'product-description'})
    if not desc_section:
        desc_section = soup.find('div', {'itemprop': 'description'})
    if desc_section:
        metadata.description = desc_section.get_text(separator='\n', strip=True)
    else:
        meta_desc = soup.find('meta', property='og:description')
        if meta_desc:
            metadata.description = meta_desc.get('content')

    # Authors
    author_tag = soup.find('span', {'itemprop': 'author'})
    if not author_tag:
        author_tag = soup.find('div', {'class': 'product-author'})
    if author_tag:
        metadata.authors = [author_tag.get_text(strip=True)]

    # Try to find author in meta tags
    if not metadata.authors:
        author_meta = soup.find('meta', {'name': 'author'})
        if author_meta:
            metadata.authors = [author_meta.get('content')]

    # Tags from categories or keywords
    keywords_meta = soup.find('meta', {'name': 'keywords'})
    if keywords_meta:
        keywords = keywords_meta.get('content', '').split(',')
        metadata.tags = [kw.strip() for kw in keywords if kw.strip()]

    # Extract opening and level
    opening = extract_opening_from_title(metadata.title or "")
    if opening:
        metadata.opening = opening
        if opening not in metadata.tags:
            metadata.tags.append(opening)

    level = extract_level_from_text(metadata.description or "")
    if level:
        metadata.level = level
        if level not in metadata.tags:
            metadata.tags.append(level)

    return metadata


def scrape_modernchess_metadata(soup: BeautifulSoup, url: str) -> ChessCourseMetadata:
    """Extract full metadata from Modern Chess course page."""
    metadata = ChessCourseMetadata()
    metadata.platform = "Modern Chess"
    metadata.publisher = "Modern Chess"
    metadata.course_url = url

    # Title
    title_tag = soup.find('h1')
    if not title_tag:
        title_tag = soup.find('meta', property='og:title')
        if title_tag:
            metadata.title = title_tag.get('content')
    else:
        metadata.title = title_tag.get_text(strip=True)

    # Description
    meta_desc = soup.find('meta', property='og:description')
    if meta_desc:
        metadata.description = meta_desc.get('content')
    else:
        desc_section = soup.find('div', {'class': 'course-description'})
        if desc_section:
            metadata.description = desc_section.get_text(separator='\n', strip=True)

    # Authors (instructor)
    instructor_section = soup.find('div', {'class': 'instructor'})
    if instructor_section:
        name_tag = instructor_section.find('h3')
        if name_tag:
            metadata.authors = [name_tag.get_text(strip=True)]

    # Tags (course categories/topics)
    category_section = soup.find('div', {'class': 'course-categories'})
    if category_section:
        category_links = category_section.find_all('a')
        metadata.tags = [link.get_text(strip=True) for link in category_links]

    # Extract opening and level
    opening = extract_opening_from_title(metadata.title or "")
    if opening:
        metadata.opening = opening
        if opening not in metadata.tags:
            metadata.tags.append(opening)

    level = extract_level_from_text(metadata.description or "")
    if level:
        metadata.level = level
        if level not in metadata.tags:
            metadata.tags.append(level)

    return metadata


def scrape_thechessworld_metadata(soup: BeautifulSoup, url: str) -> ChessCourseMetadata:
    """Extract full metadata from TheChessWorld course page."""
    metadata = ChessCourseMetadata()
    metadata.platform = "TheChessWorld"
    metadata.publisher = "TheChessWorld"
    metadata.course_url = url

    # Title
    title_tag = soup.find('h1')
    if not title_tag:
        title_tag = soup.find('meta', property='og:title')
        if title_tag:
            metadata.title = title_tag.get('content')
    else:
        metadata.title = title_tag.get_text(strip=True)

    # Description
    meta_desc = soup.find('meta', property='og:description')
    if meta_desc:
        metadata.description = meta_desc.get('content')
    else:
        desc_section = soup.find('div', {'class': 'entry-content'})
        if desc_section:
            metadata.description = desc_section.get_text(separator='\n', strip=True)

    # Authors (look for author meta or byline)
    author_meta = soup.find('meta', {'name': 'author'})
    if author_meta:
        metadata.authors = [author_meta.get('content')]
    else:
        author_section = soup.find('span', {'class': 'author'})
        if author_section:
            metadata.authors = [author_section.get_text(strip=True)]

    # Tags from post categories
    category_section = soup.find('div', {'class': 'post-categories'})
    if category_section:
        category_links = category_section.find_all('a')
        metadata.tags = [link.get_text(strip=True) for link in category_links]

    # Extract opening and level
    opening = extract_opening_from_title(metadata.title or "")
    if opening:
        metadata.opening = opening
        if opening not in metadata.tags:
            metadata.tags.append(opening)

    level = extract_level_from_text(metadata.description or "")
    if level:
        metadata.level = level
        if level not in metadata.tags:
            metadata.tags.append(level)

    return metadata


# --- Chess-Specific Helper Functions ---

CHESS_OPENINGS = [
    # Common openings
    "Sicilian", "French", "Caro-Kann", "Pirc", "Scandinavian",
    "King's Indian", "Queen's Gambit", "London System", "English",
    "Ruy Lopez", "Italian", "Scotch", "Vienna", "Alekhine",
    "Nimzo-Indian", "Bogo-Indian", "Catalan", "Grunfeld", "Benoni",
    "Dutch", "Slav", "Semi-Slav", "Tarrasch", "Chigorin",
    "King's Gambit", "Queen's Gambit Accepted", "Queen's Gambit Declined",
    "Petroff", "Philidor", "Budapest", "Benko", "Najdorf",
    "Dragon", "Sveshnikov", "Taimanov", "Kan", "Accelerated Dragon",
    "Maroczy", "Smith-Morra", "Grand Prix Attack", "Rossolimo",
]


def extract_opening_from_title(title: str) -> Optional[str]:
    """Extract chess opening name from title."""
    if not title:
        return None

    title_lower = title.lower()
    for opening in CHESS_OPENINGS:
        if opening.lower() in title_lower:
            return opening

    return None


def extract_level_from_text(text: str) -> Optional[str]:
    """Extract skill level from text (beginner, intermediate, advanced, etc.)."""
    if not text:
        return None

    text_lower = text.lower()

    # Check for level keywords
    if any(word in text_lower for word in ['beginner', 'basics', 'introduction', 'getting started']):
        return "Beginner"
    elif any(word in text_lower for word in ['advanced', 'expert', 'master']):
        return "Advanced"
    elif any(word in text_lower for word in ['intermediate', 'improving']):
        return "Intermediate"

    return None


def detect_content_type(file_path: Optional[str], course_url: Optional[str] = None) -> str:
    """
    Detect content type based on file path and/or URL.

    Returns:
        - "video" for directories with video files (mp4, mov, avi, mkv, etc.)
        - "pgn" for .pgn files
        - "study" for Lichess study URLs
        - "database" for ChessBase database files (.cbh, .cbv)
        - "ebook" for PDF/EPUB files
        - "other" for unknown types
    """
    # Check URL patterns first
    if course_url:
        if 'lichess.org/study' in course_url:
            return "study"

    # No file path provided
    if not file_path:
        return "other"

    path = Path(file_path)

    # Single file - check extension
    if path.is_file():
        suffix = path.suffix.lower()
        if suffix == '.pgn':
            return "pgn"
        elif suffix in ['.cbh', '.cbv']:
            return "database"
        elif suffix in ['.pdf', '.epub', '.mobi']:
            return "ebook"
        elif suffix in ['.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv']:
            return "video"
        else:
            return "other"

    # Directory - scan for content types
    elif path.is_dir():
        try:
            files = list(path.iterdir())

            # Check for video files
            video_extensions = {'.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv', '.m4v'}
            has_video = any(f.suffix.lower() in video_extensions for f in files if f.is_file())
            if has_video:
                return "video"

            # Check for PGN files
            has_pgn = any(f.suffix.lower() == '.pgn' for f in files if f.is_file())
            if has_pgn:
                return "pgn"

            # Check for ChessBase database
            has_database = any(f.suffix.lower() in {'.cbh', '.cbv'} for f in files if f.is_file())
            if has_database:
                return "database"

            # Check for ebooks
            has_ebook = any(f.suffix.lower() in {'.pdf', '.epub', '.mobi'} for f in files if f.is_file())
            if has_ebook:
                return "ebook"

        except (OSError, PermissionError):
            pass

    return "other"


# --- Strategy Pattern Configuration ---
PLATFORMS: Dict[str, Dict[str, Any]] = {
    "chessable.com": {
        "name": "Chessable",
        "metadata_scraper": scrape_chessable_metadata,
        "keywords": ["chessable"]
    },
    "chessbase.com": {
        "name": "ChessBase",
        "metadata_scraper": scrape_chessbase_metadata,
        "keywords": ["chessbase"]
    },
    "modern-chess.com": {
        "name": "Modern Chess",
        "metadata_scraper": scrape_modernchess_metadata,
        "keywords": ["modern chess", "modern-chess"]
    },
    "thechessworld.com": {
        "name": "TheChessWorld",
        "metadata_scraper": scrape_thechessworld_metadata,
        "keywords": ["thechessworld", "the chess world"]
    }
}


# --- Helper Functions ---

def get_platform_from_url(url: str) -> Optional[Dict[str, Any]]:
    """Determines the platform configuration based on the URL's domain."""
    for domain, platform_config in PLATFORMS.items():
        if domain in url:
            return platform_config
    return None


def detect_platform_from_title(title: str) -> Optional[Dict[str, Any]]:
    """Detects the platform from keywords in the title."""
    lower_title = title.lower()
    for domain, platform_config in PLATFORMS.items():
        for keyword in platform_config['keywords']:
            if keyword in lower_title:
                return platform_config
    return None


def clean_title(directory_title: str) -> str:
    """Cleans up the directory name for better search results and Calibre title."""
    platform_keywords = '|'.join([kw for p in PLATFORMS.values() for kw in p['keywords']])
    cleaned = re.sub(rf'\[.*?\]|\(.*?\)|\s?-\s?COURSE|\s?({platform_keywords})', '',
                     directory_title, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r'[_.\-]', ' ', cleaned).strip()

    # Remove common junk patterns in chess course names
    cleaned = re.sub(r'\s+\d{4}$', '', cleaned)  # Remove year at end
    cleaned = re.sub(r'^\d+\.\s*', '', cleaned)  # Remove leading numbers

    return cleaned


def find_course_url(title_query: str, target_domains: Optional[List[str]] = None) -> Optional[str]:
    """Uses DuckDuckGo Search to find the first valid course page URL from a supported platform."""
    if target_domains:
        domain_query = " OR ".join([f"site:{domain}" for domain in target_domains])
    else:
        domain_query = " OR ".join([f"site:{domain}" for domain in PLATFORMS.keys()])

    search_query = f'"{title_query}" {domain_query}'

    print(f"  → Searching DuckDuckGo for: {search_query}")

    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(search_query, max_results=5))
            for result in results:
                url = result['href']
                if any(domain in url for domain in PLATFORMS.keys()):
                    print(f"  → Found URL: {url}")
                    return url
        print("  → No valid URL found in search results.")
        return None
    except Exception as e:
        print(f"  ✗ Error during DuckDuckGo search: {e}")
        return None


def scrape_course_metadata(url: str, scraper_func) -> Optional[ChessCourseMetadata]:
    """Fetches the page and uses the provided metadata scraper function."""
    try:
        print(f"  → Fetching {url}...")
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        metadata = scraper_func(soup, url)
        return metadata

    except requests.exceptions.RequestException as e:
        print(f"  ✗ Error fetching URL {url}: {e}")
        return None


def extract_chess_course_metadata(directory_title: str, file_path: Optional[str] = None) -> Optional[ChessCourseMetadata]:
    """
    Main function to extract full chess course metadata from a directory name.

    Args:
        directory_title: Course directory name (e.g., "Sicilian Defense Course [Chessable]")
        file_path: Optional local file system path to the course directory

    Returns:
        ChessCourseMetadata object or None if extraction failed
    """
    print(f"\n{'='*80}")
    print(f"Processing: {directory_title}")
    print(f"{'='*80}")

    # Clean title for search and Calibre
    cleaned_title = clean_title(directory_title)
    print(f"  → Cleaned title: {cleaned_title}")

    # Detect platform
    platform = detect_platform_from_title(directory_title)
    target_domains = [domain for domain, p in PLATFORMS.items() if p == platform] if platform else None

    if platform:
        print(f"  → Detected platform: {platform['name']}")

    # Find course URL
    course_url = find_course_url(cleaned_title, target_domains=target_domains)
    if not course_url:
        print("  ✗ Could not locate the course page URL.")
        return None

    # Get platform from URL
    platform_from_url = get_platform_from_url(course_url)
    if not platform_from_url:
        print(f"  ✗ URL does not belong to a supported platform: {course_url}")
        return None

    # Scrape full metadata
    print(f"  → Using '{platform_from_url['name']}' metadata scraper...")
    scraper = platform_from_url['metadata_scraper']
    metadata = scrape_course_metadata(course_url, scraper)

    if not metadata:
        print("  ✗ Failed to extract metadata")
        return None

    # Use cleaned title if scraping didn't find one
    if not metadata.title:
        metadata.title = cleaned_title

    # Set file path if provided
    if file_path:
        metadata.file_path = str(Path(file_path).resolve())

    # Detect content type
    content_type = detect_content_type(file_path, course_url)
    metadata.content_type = content_type

    print(f"  ✓ Successfully extracted metadata")
    print(f"    Title: {metadata.title}")
    print(f"    Authors: {', '.join(metadata.authors) if metadata.authors else 'None'}")
    print(f"    Platform: {metadata.platform}")
    print(f"    Content Type: {metadata.content_type}")
    print(f"    Opening: {metadata.opening or 'None'}")
    print(f"    Level: {metadata.level or 'None'}")
    print(f"    Tags: {', '.join(metadata.tags) if metadata.tags else 'None'}")

    return metadata


# --- Test Execution ---
if __name__ == "__main__":
    TEST_CASES = [
        ("Sicilian Defense Accelerated Dragon [Chessable]",
         "/Users/alexchilton/Chess/Chessable/SicilianDragon"),
        ("King's Indian Defense - ChessBase",
         "/Users/alexchilton/Chess/ChessBase/KingsIndian"),
        ("London System Complete Course (Modern Chess)",
         "/Users/alexchilton/Chess/ModernChess/LondonSystem"),
        ("French Defense Winawer [TheChessWorld]",
         "/Users/alexchilton/Chess/TheChessWorld/FrenchWinawer"),
    ]

    results = []
    for title, path in TEST_CASES:
        metadata = extract_chess_course_metadata(title, file_path=path)
        if metadata:
            results.append(metadata)
            print(f"\n{'-'*80}")
            print("METADATA SUMMARY:")
            print(f"{'-'*80}")
            for key, value in metadata.to_dict().items():
                if value:
                    print(f"{key:15s}: {value}")

    print(f"\n\n{'='*80}")
    print(f"FINAL SUMMARY: {len(results)}/{len(TEST_CASES)} courses successfully processed")
    print(f"{'='*80}\n")
