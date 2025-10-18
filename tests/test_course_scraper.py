"""
Tests for course_scraper_enhanced.py

Note: These tests use mocked HTTP responses to avoid hitting live websites.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from bs4 import BeautifulSoup
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from course_scraper_enhanced import (
    CourseMetadata,
    clean_title,
    detect_platform_from_title,
    get_platform_from_url,
    scrape_udemy_metadata,
    scrape_coursera_metadata,
    scrape_pluralsight_metadata,
    scrape_linkedin_metadata,
    PLATFORMS
)


class TestCourseMetadata:
    """Test CourseMetadata data structure."""

    def test_initialization(self):
        """Test that CourseMetadata initializes with None/empty values."""
        metadata = CourseMetadata()
        assert metadata.title is None
        assert metadata.authors == []
        assert metadata.description is None
        assert metadata.publisher is None
        assert metadata.tags == []
        assert metadata.pubdate is None
        assert metadata.duration is None
        assert metadata.course_url is None
        assert metadata.file_path is None
        assert metadata.platform is None

    def test_to_dict(self):
        """Test conversion to dictionary."""
        metadata = CourseMetadata()
        metadata.title = "Test Course"
        metadata.authors = ["John Doe"]
        metadata.publisher = "Udemy"

        result = metadata.to_dict()
        assert result['title'] == "Test Course"
        assert result['authors'] == ["John Doe"]
        assert result['publisher'] == "Udemy"
        assert 'description' in result
        assert 'tags' in result

    def test_repr(self):
        """Test string representation."""
        metadata = CourseMetadata()
        metadata.title = "Python Course"
        metadata.authors = ["Jane Smith"]
        metadata.platform = "Coursera"

        repr_str = repr(metadata)
        assert "Python Course" in repr_str
        assert "Coursera" in repr_str


class TestTitleCleaning:
    """Test title cleaning functions."""

    def test_clean_title_removes_platform_keywords(self):
        """Test removal of platform keywords."""
        assert clean_title("Python Course [Udemy]") == "Python Course"
        assert clean_title("Data Science (Coursera)") == "Data Science"
        assert clean_title("React [Pluralsight]") == "React"

    def test_clean_title_removes_full_course(self):
        """Test removal of 'FULL COURSE' text."""
        assert clean_title("Python - FULL COURSE") == "Python"
        assert clean_title("Data Science-FULL COURSE") == "Data Science"

    def test_clean_title_replaces_separators(self):
        """Test replacement of underscores, dots, dashes with spaces."""
        assert clean_title("Python_Course") == "Python Course"
        assert clean_title("Data.Science") == "Data Science"
        assert clean_title("Machine-Learning") == "Machine Learning"

    def test_clean_title_complex_example(self):
        """Test complex title cleaning."""
        title = "The_Complete.2024-Python-Pro-Course [Udemy] - FULL COURSE"
        cleaned = clean_title(title)
        assert "[Udemy]" not in cleaned
        assert "FULL COURSE" not in cleaned
        assert "_" not in cleaned
        assert "." not in cleaned


class TestPlatformDetection:
    """Test platform detection functions."""

    def test_detect_platform_from_title_udemy(self):
        """Test Udemy detection from title."""
        platform = detect_platform_from_title("Python Course [Udemy]")
        assert platform is not None
        assert platform['name'] == "Udemy"

    def test_detect_platform_from_title_coursera(self):
        """Test Coursera detection from title."""
        platform = detect_platform_from_title("Data Science (Coursera)")
        assert platform is not None
        assert platform['name'] == "Coursera"

    def test_detect_platform_from_title_pluralsight(self):
        """Test Pluralsight detection from title."""
        platform = detect_platform_from_title("React [Pluralsight]")
        assert platform is not None
        assert platform['name'] == "Pluralsight"

    def test_detect_platform_from_title_linkedin(self):
        """Test LinkedIn Learning detection from title."""
        platform = detect_platform_from_title("Python (LinkedIn)")
        assert platform is not None
        assert platform['name'] == "LinkedIn Learning"

    def test_detect_platform_from_title_none(self):
        """Test no platform detected."""
        platform = detect_platform_from_title("Generic Course Title")
        assert platform is None

    def test_get_platform_from_url_udemy(self):
        """Test Udemy detection from URL."""
        url = "https://www.udemy.com/course/python-bootcamp/"
        platform = get_platform_from_url(url)
        assert platform is not None
        assert platform['name'] == "Udemy"

    def test_get_platform_from_url_coursera(self):
        """Test Coursera detection from URL."""
        url = "https://www.coursera.org/learn/machine-learning"
        platform = get_platform_from_url(url)
        assert platform is not None
        assert platform['name'] == "Coursera"

    def test_get_platform_from_url_none(self):
        """Test no platform detected from URL."""
        url = "https://www.example.com/course"
        platform = get_platform_from_url(url)
        assert platform is None


class TestUdemyMetadataScraper:
    """Test Udemy metadata scraping."""

    def test_scrape_udemy_metadata_basic(self):
        """Test basic Udemy metadata extraction."""
        html = """
        <html>
            <head>
                <meta property="og:title" content="Python Bootcamp">
                <meta property="og:description" content="Learn Python from scratch">
            </head>
            <body>
                <h1 data-purpose="lead-title">Python Bootcamp</h1>
                <div class="styles--description--AfVWV">
                    Complete Python course for beginners
                </div>
                <a data-purpose="instructor-url">John Doe</a>
                <a data-purpose="instructor-url">Jane Smith</a>
            </body>
        </html>
        """
        soup = BeautifulSoup(html, 'html.parser')
        metadata = scrape_udemy_metadata(soup, "https://www.udemy.com/course/python")

        assert metadata.title == "Python Bootcamp"
        assert metadata.description == "Complete Python course for beginners"
        assert len(metadata.authors) == 2
        assert "John Doe" in metadata.authors
        assert "Jane Smith" in metadata.authors
        assert metadata.platform == "Udemy"
        assert metadata.publisher == "Udemy"

    def test_scrape_udemy_metadata_fallback_title(self):
        """Test Udemy title fallback to og:title."""
        html = """
        <html>
            <head>
                <meta property="og:title" content="React Course">
            </head>
            <body>
                <div class="styles--description--AfVWV">React from scratch</div>
            </body>
        </html>
        """
        soup = BeautifulSoup(html, 'html.parser')
        metadata = scrape_udemy_metadata(soup, "https://www.udemy.com/course/react")

        assert metadata.title == "React Course"

    def test_scrape_udemy_metadata_no_instructors(self):
        """Test Udemy with no instructors found."""
        html = """
        <html>
            <body>
                <h1 data-purpose="lead-title">Course Title</h1>
            </body>
        </html>
        """
        soup = BeautifulSoup(html, 'html.parser')
        metadata = scrape_udemy_metadata(soup, "https://www.udemy.com/course/test")

        assert metadata.authors == []


class TestCourseraMetadataScraper:
    """Test Coursera metadata scraping."""

    def test_scrape_coursera_metadata_basic(self):
        """Test basic Coursera metadata extraction."""
        html = """
        <html>
            <head>
                <meta property="og:title" content="Machine Learning">
                <meta property="og:description" content="Learn ML">
            </head>
            <body>
                <h1>Machine Learning Specialization</h1>
                <div class="content-inner">
                    Comprehensive ML course
                </div>
                <div>
                    <h3>Instructors</h3>
                    <a>Andrew Ng</a>
                </div>
            </body>
        </html>
        """
        soup = BeautifulSoup(html, 'html.parser')
        metadata = scrape_coursera_metadata(soup, "https://www.coursera.org/learn/ml")

        assert metadata.title == "Machine Learning Specialization"
        assert metadata.description == "Comprehensive ML course"
        assert "Andrew Ng" in metadata.authors
        assert metadata.platform == "Coursera"


class TestPluralsightMetadataScraper:
    """Test Pluralsight metadata scraping."""

    def test_scrape_pluralsight_metadata_basic(self):
        """Test basic Pluralsight metadata extraction."""
        html = """
        <html>
            <head>
                <meta property="og:description" content="Learn React 18">
            </head>
            <body>
                <h1>React 18 Fundamentals</h1>
                <a class="author-name">Jane Developer</a>
                <div>Level: Intermediate</div>
            </body>
        </html>
        """
        soup = BeautifulSoup(html, 'html.parser')
        metadata = scrape_pluralsight_metadata(soup, "https://www.pluralsight.com/courses/react")

        assert metadata.title == "React 18 Fundamentals"
        assert metadata.description == "Learn React 18"
        assert "Jane Developer" in metadata.authors
        assert metadata.platform == "Pluralsight"


class TestLinkedInMetadataScraper:
    """Test LinkedIn Learning metadata scraping."""

    def test_scrape_linkedin_metadata_basic(self):
        """Test basic LinkedIn Learning metadata extraction."""
        html = """
        <html>
            <head>
                <meta property="og:title" content="Python Essential Training">
                <meta property="og:description" content="Master Python basics">
            </head>
            <body>
                <h1>Python Essential Training</h1>
                <div class="instructor-info">
                    <a>Bill Weinman</a>
                </div>
            </body>
        </html>
        """
        soup = BeautifulSoup(html, 'html.parser')
        metadata = scrape_linkedin_metadata(soup, "https://www.linkedin.com/learning/python")

        assert metadata.title == "Python Essential Training"
        assert metadata.description == "Master Python basics"
        assert "Bill Weinman" in metadata.authors
        assert metadata.platform == "LinkedIn Learning"


class TestPlatformsConfiguration:
    """Test PLATFORMS configuration."""

    def test_platforms_has_all_required_fields(self):
        """Test that all platforms have required configuration fields."""
        for domain, config in PLATFORMS.items():
            assert 'name' in config
            assert 'metadata_scraper' in config
            assert 'keywords' in config
            assert isinstance(config['keywords'], list)
            assert len(config['keywords']) > 0

    def test_platforms_scrapers_are_callable(self):
        """Test that all metadata scrapers are callable."""
        for domain, config in PLATFORMS.items():
            assert callable(config['metadata_scraper'])


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_clean_title_empty_string(self):
        """Test cleaning empty string."""
        assert clean_title("") == ""

    def test_clean_title_only_whitespace(self):
        """Test cleaning whitespace-only string."""
        result = clean_title("   ")
        assert result.strip() == ""

    def test_detect_platform_case_insensitive(self):
        """Test platform detection is case insensitive."""
        platform1 = detect_platform_from_title("Course [UDEMY]")
        platform2 = detect_platform_from_title("Course [udemy]")
        platform3 = detect_platform_from_title("Course [Udemy]")

        assert platform1 == platform2 == platform3
        assert platform1 is not None

    def test_metadata_to_dict_handles_none_values(self):
        """Test to_dict handles None values properly."""
        metadata = CourseMetadata()
        result = metadata.to_dict()

        assert 'title' in result
        assert result['title'] is None
        assert 'authors' in result
        assert result['authors'] == []


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
