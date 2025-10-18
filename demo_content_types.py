#!/usr/bin/env python3
"""
Demo script showing content type detection for chess courses.
"""

from chess_course_scraper import detect_content_type

# Example scenarios
examples = [
    # Lichess study (online)
    {
        "description": "Lichess study (online)",
        "file_path": None,
        "course_url": "https://lichess.org/study/abc123"
    },
    # Video course directory
    {
        "description": "Video course directory",
        "file_path": "/Users/you/Chess/Courses/Sicilian_Videos",
        "course_url": None
    },
    # PGN file
    {
        "description": "PGN games collection",
        "file_path": "/Users/you/Chess/Games/my_games.pgn",
        "course_url": None
    },
    # ChessBase database
    {
        "description": "ChessBase database",
        "file_path": "/Users/you/Chess/Databases/mega2024.cbh",
        "course_url": None
    },
    # Chess ebook
    {
        "description": "Chess ebook (PDF)",
        "file_path": "/Users/you/Chess/Books/sicilian_defense.pdf",
        "course_url": None
    },
]

print("Chess Course Content Type Detection Demo")
print("=" * 80)
print()

for example in examples:
    print(f"📁 {example['description']}")

    if example['file_path']:
        print(f"   Path: {example['file_path']}")
    if example['course_url']:
        print(f"   URL: {example['course_url']}")

    # Detect content type
    content_type = detect_content_type(
        file_path=example['file_path'],
        course_url=example['course_url']
    )

    # Content type emoji mapping
    emoji_map = {
        "video": "🎥",
        "pgn": "♟️",
        "study": "📚",
        "database": "💾",
        "ebook": "📖",
        "other": "❓"
    }

    emoji = emoji_map.get(content_type, "❓")
    print(f"   {emoji} Content Type: {content_type}")
    print()

print("=" * 80)
print("\nContent Type Categories:")
print("  🎥 video    - Directories with MP4, MOV, AVI, MKV files")
print("  ♟️  pgn      - PGN game files or directories with PGN files")
print("  📚 study    - Lichess online studies")
print("  💾 database - ChessBase .cbh/.cbv database files")
print("  📖 ebook    - PDF, EPUB, MOBI chess books")
print("  ❓ other    - Unknown or unrecognized format")
