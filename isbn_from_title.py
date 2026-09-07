#!/usr/bin/env python3
"""Recover ISBNs that are sitting in book titles and store them as identifiers.

Libgen and similar downloads often leave the ISBN in the title -- "... (ISBN
0821802682)(399s).djvu" -- while the identifier field stays empty, so the
identifier-based enrichment never sees the book. This finds those, checksum-
validates the candidate so bare libgen IDs are rejected, and writes a real
isbn identifier.

    python -u isbn_from_title.py              # dry run, prints what it would set
    python -u isbn_from_title.py --apply      # write the identifiers
    python -u isbn_from_title.py --apply --limit 5

CLOSE CALIBRE before --apply: writes go through calibredb.
"""

import argparse
import re
import sqlite3
import subprocess
import sys

from calibre_tools.config import DEFAULT_CALIBRE_LIBRARY
from calibre_tools.isbn_tools import validate_isbn

# ISBN-13 starts 978/979; ISBN-10 is 9 digits plus a check character.
# Separators are allowed inside, and the lookarounds stop us biting a chunk
# out of a longer digit run such as a libgen id.
ISBN_PATTERN = re.compile(r'(?<!\d)(97[89][\d-]{10,16}|\d[\d-]{8,12}[\dXx])(?!\d)')

# Amazon ASINs are B followed by nine alphanumerics. Requiring a digit among
# them keeps ordinary capitalised words out.
ASIN_PATTERN = re.compile(r'\b(B[0-9A-Z]{9})\b')

CANDIDATE_SQL = """
    SELECT b.id, b.title
    FROM books b
    WHERE NOT EXISTS (
            SELECT 1 FROM identifiers i
            WHERE i.book = b.id AND i.type IN ('isbn', 'amazon', 'asin'))
      AND (b.title GLOB '*[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]*'
           OR b.title GLOB '*B[0-9A-Z][0-9A-Z][0-9A-Z][0-9A-Z][0-9A-Z][0-9A-Z][0-9A-Z][0-9A-Z][0-9A-Z]*')
"""


def identifier_in(title):
    """Return (type, value) for the first usable identifier in title, or None.

    ISBN wins over ASIN: it is checksum-verifiable, so a match is certain,
    and more metadata sources index it.
    """
    for match in ISBN_PATTERN.finditer(title):
        candidate = match.group(0).replace("-", "")
        if validate_isbn(candidate):
            return "isbn", candidate

    for match in ASIN_PATTERN.finditer(title):
        candidate = match.group(1)
        if any(c.isdigit() for c in candidate[1:]):
            return "amazon", candidate

    return None


def set_identifier(book_id, id_type, value, library_path):
    result = subprocess.run(
        ["calibredb", "set_metadata", "--library-path", library_path,
         "--field", f"identifiers:{id_type}:{value}", str(book_id)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout).strip().splitlines()[-1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write the identifiers")
    ap.add_argument("--limit", type=int, help="stop after this many books")
    ap.add_argument("--missing-description", action="store_true",
                    help="only books that also have no description")
    ap.add_argument("--library-path", default=DEFAULT_CALIBRE_LIBRARY)
    args = ap.parse_args()

    sql = CANDIDATE_SQL
    if args.missing_description:
        sql += ("      AND NOT EXISTS (SELECT 1 FROM comments c "
                "WHERE c.book = b.id AND TRIM(COALESCE(c.text,'')) <> '')\n")

    db = f"{args.library_path}/metadata.db"
    with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as con:
        rows = con.execute(sql).fetchall()

    found = [(bid, ident, title) for bid, title in rows
             if (ident := identifier_in(title))]
    if args.limit:
        found = found[:args.limit]

    by_type = {}
    for _, (id_type, _), _ in found:
        by_type[id_type] = by_type.get(id_type, 0) + 1

    print(f"scanned {len(rows)} candidate titles")
    print(f"{len(found)} carry a usable identifier: "
          + (", ".join(f"{n} {t}" for t, n in sorted(by_type.items())) or "none") + "\n")

    applied = failed = 0
    for bid, (id_type, value), title in found:
        print(f"  {bid:>6}  {id_type:<7} {value:<14} {title[:60]}")
        if args.apply:
            try:
                set_identifier(bid, id_type, value, args.library_path)
                applied += 1
            except Exception as exc:
                failed += 1
                print(f"          FAILED: {exc}", file=sys.stderr)

    if args.apply:
        print(f"\napplied {applied}, failed {failed}")
        print("run enrich_by_identifier_sql.py next to fetch their descriptions")
    else:
        print("\ndry run - nothing written. Add --apply to set these identifiers.")


if __name__ == "__main__":
    main()