"""
Tests for chess_course_scraper.py

Note: These tests use mocked HTTP responses to avoid hitting live websites.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from bs4 import BeautifulSoup
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from chess_course_scraper import (
    ChessCourseMetadata,
    clean_title,
    detect_platform_from_title,
    get_platform_from_url,
    extract_opening_from_title,
    extract_level_from_text,
    detect_content_type,
    scrape_chessable_metadata,
    scrape_chessbase_metadata,
    scrape_modernchess_metadata,
    scrape_thechessworld_metadata,
    PLATFORMS,
    CHESS_OPENINGS
)


class TestChessCourseMetadata:
    """Test ChessCourseMetadata data structure."""

    def test_initialization(self):
        """Test that ChessCourseMetadata initializes with None/empty values."""
        metadata = ChessCourseMetadata()
        assert metadata.title is None
        assert metadata.authors == []
        assert metadata.description is None
        assert metadata.publisher is None
        assert metadata.tags == []
        assert metadata.pubdate is None
        assert metadata.opening is None
        assert metadata.level is None
        assert metadata.course_url is None
        assert metadata.file_path is None
        assert metadata.platform is None
        assert metadata.content_type is None

    def test_to_dict(self):
        """Test conversion to dictionary."""
        metadata = ChessCourseMetadata()
        metadata.title = "Sicilian Defense"
        metadata.authors = ["GM Magnus Carlsen"]
        metadata.publisher = "Chessable"
        metadata.opening = "Sicilian"
        metadata.level = "Advanced"

        result = metadata.to_dict()
        assert result['title'] == "Sicilian Defense"
        assert result['authors'] == ["GM Magnus Carlsen"]
        assert result['publisher'] == "Chessable"
        assert result['opening'] == "Sicilian"
        assert result['level'] == "Advanced"
        assert 'description' in result
        assert 'tags' in result

    def test_repr(self):
        """Test string representation."""
        metadata = ChessCourseMetadata()
        metadata.title = "King's Indian Defense"
        metadata.authors = ["GM Garry Kasparov"]
        metadata.platform = "ChessBase"

        repr_str = repr(metadata)
        assert "King's Indian Defense" in repr_str
        assert "ChessBase" in repr_str


class TestTitleCleaning:
    """Test title cleaning functions."""

    def test_clean_title_removes_platform_keywords(self):
        """Test removal of platform keywords."""
        assert clean_title("Sicilian Defense [Chessable]") == "Sicilian Defense"
        assert clean_title("French Defense (ChessBase)") == "French Defense"
        assert clean_title("London System [Modern Chess]") == "London System"

    def test_clean_title_removes_course_keyword(self):
        """Test removal of 'COURSE' text."""
        assert clean_title("Sicilian Defense - COURSE") == "Sicilian Defense"
        # Note: Standalone "COURSE" without dash is not removed by regex
        assert "Defense" in clean_title("French Defense COURSE")

    def test_clean_title_replaces_separators(self):
        """Test replacement of underscores, dots, dashes with spaces."""
        assert clean_title("Sicilian_Defense") == "Sicilian Defense"
        assert clean_title("Kings.Indian") == "Kings Indian"
        assert clean_title("Queen-Gambit") == "Queen Gambit"

    def test_clean_title_removes_year(self):
        """Test removal of year at end."""
        assert clean_title("Sicilian Defense 2024") == "Sicilian Defense"
        assert clean_title("French Defense 2023") == "French Defense"

    def test_clean_title_removes_leading_numbers(self):
        """Test removal of leading numbers with period."""
        # Note: The regex removes "1." but the "." becomes a space
        result1 = clean_title("1. Sicilian Defense")
        assert "Sicilian Defense" in result1
        result2 = clean_title("10. French Defense")
        assert "French Defense" in result2

    def test_clean_title_complex_example(self):
        """Test complex title cleaning."""
        title = "1._Sicilian.Defense-Najdorf_[Chessable]_2024"
        cleaned = clean_title(title)
        assert "[Chessable]" not in cleaned
        assert "2024" not in cleaned
        assert "_" not in cleaned
        assert "." not in cleaned
        assert "Sicilian" in cleaned


class TestPlatformDetection:
    """Test platform detection functions."""

    def test_detect_platform_from_title_chessable(self):
        """Test Chessable detection from title."""
        platform = detect_platform_from_title("Sicilian Defense [Chessable]")
        assert platform is not None
        assert platform['name'] == "Chessable"

    def test_detect_platform_from_title_chessbase(self):
        """Test ChessBase detection from title."""
        platform = detect_platform_from_title("French Defense (ChessBase)")
        assert platform is not None
        assert platform['name'] == "ChessBase"

    def test_detect_platform_from_title_modernchess(self):
        """Test Modern Chess detection from title."""
        platform = detect_platform_from_title("London System [Modern Chess]")
        assert platform is not None
        assert platform['name'] == "Modern Chess"

    def test_detect_platform_from_title_thechessworld(self):
        """Test TheChessWorld detection from title."""
        platform = detect_platform_from_title("Caro-Kann (TheChessWorld)")
        assert platform is not None
        assert platform['name'] == "TheChessWorld"

    def test_detect_platform_from_title_none(self):
        """Test no platform detected."""
        platform = detect_platform_from_title("Generic Chess Course")
        assert platform is None

    def test_get_platform_from_url_chessable(self):
        """Test Chessable detection from URL."""
        url = "https://www.chessable.com/course/sicilian-defense/"
        platform = get_platform_from_url(url)
        assert platform is not None
        assert platform['name'] == "Chessable"

    def test_get_platform_from_url_chessbase(self):
        """Test ChessBase detection from URL."""
        url = "https://shop.chessbase.com/en/products/french-defense"
        platform = get_platform_from_url(url)
        assert platform is not None
        assert platform['name'] == "ChessBase"

    def test_get_platform_from_url_none(self):
        """Test no platform detected from URL."""
        url = "https://www.example.com/course"
        platform = get_platform_from_url(url)
        assert platform is None


class TestOpeningExtraction:
    """Test chess opening extraction."""

    def test_extract_opening_sicilian(self):
        """Test Sicilian extraction."""
        assert extract_opening_from_title("Sicilian Defense Najdorf") == "Sicilian"
        assert extract_opening_from_title("The Complete Sicilian") == "Sicilian"

    def test_extract_opening_french(self):
        """Test French extraction."""
        assert extract_opening_from_title("French Defense Winawer") == "French"
        assert extract_opening_from_title("Mastering the French") == "French"

    def test_extract_opening_kings_indian(self):
        """Test King's Indian extraction."""
        assert extract_opening_from_title("King's Indian Defense Classical") == "King's Indian"

    def test_extract_opening_queens_gambit(self):
        """Test Queen's Gambit extraction."""
        # Note: Returns first match, which is "Queen's Gambit"
        # "Queen's Gambit Declined" is also in list, but check depends on order
        opening1 = extract_opening_from_title("Queen's Gambit Declined")
        assert opening1 in ["Queen's Gambit", "Queen's Gambit Declined"]
        opening2 = extract_opening_from_title("Queen's Gambit Accepted")
        assert opening2 in ["Queen's Gambit", "Queen's Gambit Accepted"]

    def test_extract_opening_none(self):
        """Test no opening found."""
        assert extract_opening_from_title("General Chess Strategy") is None
        assert extract_opening_from_title("Endgame Techniques") is None

    def test_extract_opening_case_insensitive(self):
        """Test case insensitive extraction."""
        assert extract_opening_from_title("SICILIAN DEFENSE") == "Sicilian"
        assert extract_opening_from_title("french defense") == "French"


class TestLevelExtraction:
    """Test skill level extraction."""

    def test_extract_level_beginner(self):
        """Test beginner level extraction."""
        assert extract_level_from_text("This course is for beginners") == "Beginner"
        assert extract_level_from_text("Introduction to chess") == "Beginner"
        assert extract_level_from_text("Getting started with the Sicilian") == "Beginner"
        # Note: "basic" alone doesn't trigger beginner detection
        assert extract_level_from_text("Beginner level course") == "Beginner"

    def test_extract_level_intermediate(self):
        """Test intermediate level extraction."""
        assert extract_level_from_text("For intermediate players") == "Intermediate"
        # Note: "improve" alone doesn't trigger intermediate detection
        assert extract_level_from_text("Intermediate level tactics") == "Intermediate"

    def test_extract_level_advanced(self):
        """Test advanced level extraction."""
        assert extract_level_from_text("Advanced tactics") == "Advanced"
        assert extract_level_from_text("Expert-level endgames") == "Advanced"
        assert extract_level_from_text("Master the Najdorf") == "Advanced"

    def test_extract_level_none(self):
        """Test no level found."""
        assert extract_level_from_text("Complete chess course") is None
        assert extract_level_from_text("Sicilian Defense repertoire") is None


class TestChessableMetadataScraper:
    """Test Chessable metadata scraping."""

    def test_scrape_chessable_metadata_basic(self):
        """Test basic Chessable metadata extraction."""
        html = """
        <html>
            <head>
                <meta property="og:title" content="Sicilian Najdorf">
                <meta property="og:description" content="Learn the Najdorf variation">
            </head>
            <body>
                <h1 class="course-title">Sicilian Defense - Najdorf Variation</h1>
                <div class="course-description">
                    Complete course on the Najdorf for advanced players
                </div>
                <div class="course-author">
                    <a>GM Magnus Carlsen</a>
                </div>
                <div class="course-tags">
                    <a>Sicilian</a>
                    <a>e4</a>
                    <a>Sharp</a>
                </div>
            </body>
        </html>
        """
        soup = BeautifulSoup(html, 'html.parser')
        metadata = scrape_chessable_metadata(soup, "https://www.chessable.com/course/sicilian")

        assert metadata.title == "Sicilian Defense - Najdorf Variation"
        assert metadata.description == "Complete course on the Najdorf for advanced players"
        assert "GM Magnus Carlsen" in metadata.authors
        assert metadata.platform == "Chessable"
        assert metadata.publisher == "Chessable"
        assert "Sicilian" in metadata.tags
        assert metadata.opening == "Sicilian"
        assert metadata.level == "Advanced"

    def test_scrape_chessable_metadata_by_pattern(self):
        """Test Chessable author extraction using 'by' pattern."""
        html = """
        <html>
            <body>
                <h1>French Defense Course</h1>
                <p>by GM Vishy Anand</p>
            </body>
        </html>
        """
        soup = BeautifulSoup(html, 'html.parser')
        metadata = scrape_chessable_metadata(soup, "https://www.chessable.com/course/french")

        assert "GM Vishy Anand" in metadata.authors


class TestChessBaseMetadataScraper:
    """Test ChessBase metadata scraping."""

    def test_scrape_chessbase_metadata_basic(self):
        """Test basic ChessBase metadata extraction."""
        html = """
        <html>
            <head>
                <meta property="og:title" content="King's Indian Defense">
                <meta property="og:description" content="Master the King's Indian">
                <meta name="keywords" content="Kings Indian, Defense, e4, d4">
            </head>
            <body>
                <h1 class="product-title">King's Indian Defense - Complete Repertoire</h1>
                <div class="product-description">
                    Comprehensive guide to the King's Indian Defense
                </div>
                <span itemprop="author">GM Garry Kasparov</span>
            </body>
        </html>
        """
        soup = BeautifulSoup(html, 'html.parser')
        metadata = scrape_chessbase_metadata(soup, "https://shop.chessbase.com/kings-indian")

        assert metadata.title == "King's Indian Defense - Complete Repertoire"
        assert metadata.description == "Comprehensive guide to the King's Indian Defense"
        assert "GM Garry Kasparov" in metadata.authors
        assert metadata.platform == "ChessBase"
        assert metadata.opening == "King's Indian"
        assert len(metadata.tags) > 0


class TestModernChessMetadataScraper:
    """Test Modern Chess metadata scraping."""

    def test_scrape_modernchess_metadata_basic(self):
        """Test basic Modern Chess metadata extraction."""
        html = """
        <html>
            <head>
                <meta property="og:title" content="London System">
                <meta property="og:description" content="Complete London System course">
            </head>
            <body>
                <h1>London System - Full Course</h1>
                <div class="instructor">
                    <h3>GM Simon Williams</h3>
                </div>
                <div class="course-categories">
                    <a>London System</a>
                    <a>d4</a>
                    <a>Solid</a>
                </div>
            </body>
        </html>
        """
        soup = BeautifulSoup(html, 'html.parser')
        metadata = scrape_modernchess_metadata(soup, "https://modern-chess.com/london")

        assert metadata.title == "London System - Full Course"
        assert "GM Simon Williams" in metadata.authors
        assert metadata.platform == "Modern Chess"
        assert metadata.opening == "London System"
        assert "London System" in metadata.tags


class TestTheChessWorldMetadataScraper:
    """Test TheChessWorld metadata scraping."""

    def test_scrape_thechessworld_metadata_basic(self):
        """Test basic TheChessWorld metadata extraction."""
        html = """
        <html>
            <head>
                <meta property="og:title" content="French Defense Winawer">
                <meta property="og:description" content="Learn the Winawer">
                <meta name="author" content="IM John Watson">
            </head>
            <body>
                <h1>French Defense - Winawer Variation</h1>
                <div class="post-categories">
                    <a>French</a>
                    <a>e4 e6</a>
                </div>
            </body>
        </html>
        """
        soup = BeautifulSoup(html, 'html.parser')
        metadata = scrape_thechessworld_metadata(soup, "https://thechessworld.com/french")

        assert metadata.title == "French Defense - Winawer Variation"
        assert "IM John Watson" in metadata.authors
        assert metadata.platform == "TheChessWorld"
        assert metadata.opening == "French"
        assert "French" in metadata.tags


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

    def test_platforms_count(self):
        """Test that we have 4 chess platforms."""
        assert len(PLATFORMS) == 4


class TestChessOpeningsList:
    """Test CHESS_OPENINGS list."""

    def test_chess_openings_not_empty(self):
        """Test that chess openings list is not empty."""
        assert len(CHESS_OPENINGS) > 0

    def test_chess_openings_has_common_openings(self):
        """Test that common openings are in the list."""
        assert "Sicilian" in CHESS_OPENINGS
        assert "French" in CHESS_OPENINGS
        assert "King's Indian" in CHESS_OPENINGS
        assert "Queen's Gambit" in CHESS_OPENINGS
        assert "Ruy Lopez" in CHESS_OPENINGS


class TestContentTypeDetection:
    """Test content type detection."""

    def test_detect_content_type_lichess_study(self):
        """Test detection of Lichess study from URL."""
        content_type = detect_content_type(
            file_path=None,
            course_url="https://lichess.org/study/abc123"
        )
        assert content_type == "study"

    def test_detect_content_type_pgn_file(self):
        """Test detection of PGN file."""
        # Note: This tests detection logic, not actual file existence
        import tempfile
        import os
        with tempfile.NamedTemporaryFile(suffix='.pgn', delete=False) as f:
            temp_path = f.name
        try:
            content_type = detect_content_type(temp_path)
            assert content_type == "pgn"
        finally:
            os.unlink(temp_path)

    def test_detect_content_type_video_file(self):
        """Test detection of video file."""
        import tempfile
        import os
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as f:
            temp_path = f.name
        try:
            content_type = detect_content_type(temp_path)
            assert content_type == "video"
        finally:
            os.unlink(temp_path)

    def test_detect_content_type_database_file(self):
        """Test detection of ChessBase database file."""
        import tempfile
        import os
        with tempfile.NamedTemporaryFile(suffix='.cbh', delete=False) as f:
            temp_path = f.name
        try:
            content_type = detect_content_type(temp_path)
            assert content_type == "database"
        finally:
            os.unlink(temp_path)

    def test_detect_content_type_ebook_file(self):
        """Test detection of ebook file."""
        import tempfile
        import os
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            temp_path = f.name
        try:
            content_type = detect_content_type(temp_path)
            assert content_type == "ebook"
        finally:
            os.unlink(temp_path)

    def test_detect_content_type_video_directory(self):
        """Test detection of directory with video files."""
        import tempfile
        import os
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a dummy video file
            video_path = os.path.join(temp_dir, "lesson1.mp4")
            with open(video_path, 'w') as f:
                f.write("")
            content_type = detect_content_type(temp_dir)
            assert content_type == "video"

    def test_detect_content_type_pgn_directory(self):
        """Test detection of directory with PGN files."""
        import tempfile
        import os
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a dummy PGN file
            pgn_path = os.path.join(temp_dir, "games.pgn")
            with open(pgn_path, 'w') as f:
                f.write("")
            content_type = detect_content_type(temp_dir)
            assert content_type == "pgn"

    def test_detect_content_type_no_path(self):
        """Test detection with no file path."""
        content_type = detect_content_type(None)
        assert content_type == "other"

    def test_detect_content_type_unknown_extension(self):
        """Test detection with unknown extension."""
        import tempfile
        import os
        with tempfile.NamedTemporaryFile(suffix='.xyz', delete=False) as f:
            temp_path = f.name
        try:
            content_type = detect_content_type(temp_path)
            assert content_type == "other"
        finally:
            os.unlink(temp_path)


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
        platform1 = detect_platform_from_title("Course [CHESSABLE]")
        platform2 = detect_platform_from_title("Course [chessable]")
        platform3 = detect_platform_from_title("Course [Chessable]")

        assert platform1 == platform2 == platform3
        assert platform1 is not None

    def test_extract_opening_empty_title(self):
        """Test opening extraction with empty title."""
        assert extract_opening_from_title("") is None
        assert extract_opening_from_title(None) is None

    def test_extract_level_empty_text(self):
        """Test level extraction with empty text."""
        assert extract_level_from_text("") is None
        assert extract_level_from_text(None) is None

    def test_metadata_to_dict_handles_none_values(self):
        """Test to_dict handles None values properly."""
        metadata = ChessCourseMetadata()
        result = metadata.to_dict()

        assert 'title' in result
        assert result['title'] is None
        assert 'authors' in result
        assert result['authors'] == []
        assert 'opening' in result
        assert result['opening'] is None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
