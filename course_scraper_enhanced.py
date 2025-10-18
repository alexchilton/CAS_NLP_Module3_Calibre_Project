#!/usr/bin/env python3
"""
Enhanced course scraper with full metadata extraction for Calibre integration.

Extracts:
- Title (cleaned)
- Author/Instructor(s)
- Description
- Publisher (platform name)
- Tags/Topics
- Publication/Update Date
- Duration
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

# --- Course Metadata Structure ---
class CourseMetadata:
    """Structured course metadata ready for Calibre."""

    def __init__(self):
        self.title: Optional[str] = None
        self.authors: List[str] = []  # Instructors
        self.description: Optional[str] = None
        self.publisher: Optional[str] = None  # Platform name
        self.tags: List[str] = []  # Topics/categories
        self.pubdate: Optional[str] = None  # ISO format
        self.duration: Optional[str] = None  # e.g., "10h 30m"
        self.course_url: Optional[str] = None
        self.file_path: Optional[str] = None  # Local course directory
        self.platform: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for easy JSON serialization."""
        return {
            'title': self.title,
            'authors': self.authors,
            'description': self.description,
            'publisher': self.publisher,
            'tags': self.tags,
            'pubdate': self.pubdate,
            'duration': self.duration,
            'course_url': self.course_url,
            'file_path': self.file_path,
            'platform': self.platform
        }

    def __repr__(self):
        return f"CourseMetadata(title='{self.title}', authors={self.authors}, platform='{self.platform}')"


# --- Platform-Specific Metadata Scrapers ---

def scrape_udemy_metadata(soup: BeautifulSoup, url: str) -> CourseMetadata:
    """Extract full metadata from Udemy course page."""
    metadata = CourseMetadata()
    metadata.platform = "Udemy"
    metadata.publisher = "Udemy"
    metadata.course_url = url

    # Title
    title_tag = soup.find('h1', {'data-purpose': 'lead-title'})
    if not title_tag:
        title_tag = soup.find('meta', property='og:title')
        if title_tag:
            metadata.title = title_tag.get('content')
    else:
        metadata.title = title_tag.get_text(strip=True)

    # Description
    desc_section = soup.find('div', {'class': 'styles--description--AfVWV'})
    if desc_section:
        metadata.description = desc_section.get_text(separator='\n', strip=True)
    else:
        # Fallback to meta description
        meta_desc = soup.find('meta', property='og:description')
        if meta_desc:
            metadata.description = meta_desc.get('content')

    # Authors/Instructors
    instructor_links = soup.find_all('a', {'data-purpose': 'instructor-url'})
    if instructor_links:
        metadata.authors = [link.get_text(strip=True) for link in instructor_links]

    # Tags/Topics (from breadcrumbs or categories)
    breadcrumbs = soup.find('nav', {'aria-label': 'Breadcrumb'})
    if breadcrumbs:
        links = breadcrumbs.find_all('a')
        metadata.tags = [link.get_text(strip=True) for link in links if link.get_text(strip=True)]

    # Duration
    duration_span = soup.find('span', {'data-purpose': 'video-content-length'})
    if duration_span:
        metadata.duration = duration_span.get_text(strip=True)

    # Last updated date
    last_updated = soup.find('div', {'data-purpose': 'last-update-date'})
    if last_updated:
        date_text = last_updated.get_text(strip=True)
        # Extract date (format varies)
        date_match = re.search(r'(\d{1,2}/\d{4})', date_text)
        if date_match:
            try:
                date_obj = datetime.strptime(date_match.group(1), '%m/%Y')
                metadata.pubdate = date_obj.isoformat()
            except:
                pass

    return metadata


def scrape_coursera_metadata(soup: BeautifulSoup, url: str) -> CourseMetadata:
    """Extract full metadata from Coursera course page."""
    metadata = CourseMetadata()
    metadata.platform = "Coursera"
    metadata.publisher = "Coursera"
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
    desc_section = soup.find('div', {'class': 'content-inner'})
    if desc_section:
        metadata.description = desc_section.get_text(separator='\n', strip=True)
    else:
        meta_desc = soup.find('meta', property='og:description')
        if meta_desc:
            metadata.description = meta_desc.get('content')

    # Instructors
    instructor_sections = soup.find_all('h3', string=re.compile('Instructor', re.IGNORECASE))
    for section in instructor_sections:
        parent = section.find_parent('div')
        if parent:
            names = parent.find_all('a')
            metadata.authors.extend([name.get_text(strip=True) for name in names])

    # Tags (from skills or topics)
    skills_section = soup.find('div', {'class': 'skills'})
    if skills_section:
        skill_tags = skills_section.find_all('span')
        metadata.tags = [tag.get_text(strip=True) for tag in skill_tags]

    return metadata


def scrape_pluralsight_metadata(soup: BeautifulSoup, url: str) -> CourseMetadata:
    """Extract full metadata from Pluralsight course page."""
    metadata = CourseMetadata()
    metadata.platform = "Pluralsight"
    metadata.publisher = "Pluralsight"
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
        desc_section = soup.find('div', {'class': 'course-description-text'})
        if desc_section:
            metadata.description = desc_section.get_text(separator='\n', strip=True)

    # Authors
    author_tag = soup.find('a', {'class': 'author-name'})
    if author_tag:
        metadata.authors = [author_tag.get_text(strip=True)]

    # Duration
    duration_tag = soup.find('div', string=re.compile('Duration', re.IGNORECASE))
    if duration_tag:
        parent = duration_tag.find_parent('div')
        if parent:
            duration_text = parent.get_text(strip=True)
            metadata.duration = duration_text.replace('Duration', '').strip()

    # Level/Tags
    level_tag = soup.find('div', string=re.compile('Level', re.IGNORECASE))
    if level_tag:
        parent = level_tag.find_parent('div')
        if parent:
            level = parent.get_text(strip=True).replace('Level', '').strip()
            metadata.tags.append(level)

    return metadata


def scrape_linkedin_metadata(soup: BeautifulSoup, url: str) -> CourseMetadata:
    """Extract full metadata from LinkedIn Learning course page."""
    metadata = CourseMetadata()
    metadata.platform = "LinkedIn Learning"
    metadata.publisher = "LinkedIn Learning"
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
        desc_section = soup.find('section', {'class': 'show-more-less-html'})
        if desc_section:
            content_div = desc_section.find('div', {'class': 'show-more-less-html__markup'})
            if content_div:
                metadata.description = content_div.get_text(separator='\n', strip=True)

    # Instructors
    instructor_section = soup.find('div', {'class': 'instructor-info'})
    if instructor_section:
        name_tag = instructor_section.find('a')
        if name_tag:
            metadata.authors = [name_tag.get_text(strip=True)]

    return metadata


# --- Strategy Pattern Configuration ---
PLATFORMS: Dict[str, Dict[str, Any]] = {
    "udemy.com": {
        "name": "Udemy",
        "metadata_scraper": scrape_udemy_metadata,
        "keywords": ["udemy"]
    },
    "coursera.org": {
        "name": "Coursera",
        "metadata_scraper": scrape_coursera_metadata,
        "keywords": ["coursera"]
    },
    "pluralsight.com": {
        "name": "Pluralsight",
        "metadata_scraper": scrape_pluralsight_metadata,
        "keywords": ["pluralsight"]
    },
    "linkedin.com": {
        "name": "LinkedIn Learning",
        "metadata_scraper": scrape_linkedin_metadata,
        "keywords": ["linkedin"]
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
    cleaned = re.sub(rf'\[.*?\]|\(.*?\)|\s?-\s?FULL\s?COURSE|\s?({platform_keywords})', '',
                     directory_title, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r'[_.\-]', ' ', cleaned).strip()
    return cleaned


def find_course_url(title_query: str, target_domains: Optional[List[str]] = None) -> Optional[str]:
    """Uses DuckDuckGo Search to find the first valid course page URL from a supported platform."""
    if target_domains:
        domain_query = " OR ".join([f"site:{domain}" for domain in target_domains])
    else:
        domain_query = " OR ".join([f"site:{domain}" for domain in PLATFORMS.keys()])

    search_query = f'"{title_query}" {domain_query}'

    if not target_domains or "pluralsight.com" in target_domains:
        search_query += " -inurl:paths"

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


def scrape_course_metadata(url: str, scraper_func) -> Optional[CourseMetadata]:
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


def extract_course_metadata(directory_title: str, file_path: Optional[str] = None) -> Optional[CourseMetadata]:
    """
    Main function to extract full course metadata from a directory name.

    Args:
        directory_title: Course directory name (e.g., "Python Course [Udemy]")
        file_path: Optional local file system path to the course directory

    Returns:
        CourseMetadata object or None if extraction failed
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

    print(f"  ✓ Successfully extracted metadata")
    print(f"    Title: {metadata.title}")
    print(f"    Authors: {', '.join(metadata.authors) if metadata.authors else 'None'}")
    print(f"    Platform: {metadata.platform}")
    print(f"    Tags: {', '.join(metadata.tags) if metadata.tags else 'None'}")

    return metadata


# --- Test Execution ---
if __name__ == "__main__":
    TEST_CASES = [
        ("The Complete 2024 Python Pro Course - From Zero to Expert [Udemy]",
         "/Users/alexchilton/Courses/Udemy/Python2024"),
        ("IBM Data Science Professional Certificate (Coursera)",
         "/Users/alexchilton/Courses/Coursera/IBMDataScience"),
        ("React 18: Getting Started [Pluralsight]",
         "/Users/alexchilton/Courses/Pluralsight/React18"),
        ("Learning Python (LinkedIn)",
         "/Users/alexchilton/Courses/LinkedIn/PythonBasics"),
    ]

    results = []
    for title, path in TEST_CASES:
        metadata = extract_course_metadata(title, file_path=path)
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
