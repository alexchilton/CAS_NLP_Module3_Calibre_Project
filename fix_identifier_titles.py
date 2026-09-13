#!/usr/bin/env python3
"""Replace titles that are nothing but a bare ISBN or ASIN with the real title.

Both catalogue scripts are locked to writing the description only, because on
2026-09-06 an ISBN lookup renamed "CUDA for LLMs" to "CUDA for Deep Learning".
That guard is right for a book that already has a title, and wrong for a book
whose title IS the identifier: there is nothing to lose, and 33 books sat in
the library called things like B0FQCGMRC7.

So the guard here is a condition on the CURRENT title rather than a frozen
field set. A book qualifies only if its title matches BARE_IDENTIFIER, which
"CUDA for LLMs" never could. The check is applied twice - once in SQL to pick
candidates, and again immediately before the write, because a run can take
minutes and calibre may have been edited in between.

    python -u fix_identifier_titles.py                 # dry run, shows old -> new
    python -u fix_identifier_titles.py --apply
    python -u fix_identifier_titles.py --limit 5 --apply

CLOSE CALIBRE before --apply: writes go through calibredb.
"""

import argparse
import re
import sqlite3
import subprocess
import sys
import time

import httpx

from calibre_tools.config import DEFAULT_CALIBRE_LIBRARY
from enrich_descriptions import google_key

GOOGLE = "https://www.googleapis.com/books/v1/volumes"
OPENLIB = "https://openlibrary.org/api/books"

# A title that is only an identifier. Two shapes:
#   B0G48HGR81          Amazon ASIN - always B0 plus eight alphanumerics
#   9811625271          ISBN-10 or ISBN-13, dashes and spaces allowed, and the
#   978-0-13-558986-1   ISBN-10 check digit may be X
# Anchored, so a title that merely CONTAINS an identifier is not a candidate.
BARE_IDENTIFIER = re.compile(r"^(?:B0[A-Z0-9]{8}|[\d\-\s]{9,16}[\dXx])$")

# A catalogue that echoes the identifier back as the title has told us nothing,
# and writing it would leave the book looking fixed so no later run revisits it.
MIN_TITLE_CHARS = 3


def is_bare_identifier(title):
    t = (title or "").strip()
    if not BARE_IDENTIFIER.match(t):
        return False
    # The ISBN branch is loose enough to match a stray "2019 - 2020". Require
    # that the digits actually form an ISBN length.
    if not t.upper().startswith("B0"):
        digits = re.sub(r"[^\dXx]", "", t)
        return len(digits) in (10, 13)
    return True


CANDIDATE_SQL = """
    SELECT b.id, b.title,
           (SELECT i.val FROM identifiers i
             WHERE i.book = b.id AND i.type = 'isbn' LIMIT 1) AS isbn
    FROM books b
    ORDER BY b.id DESC
"""


def candidates(db_path, limit=None):
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        rows = [r for r in conn.execute(CANDIDATE_SQL) if is_bare_identifier(r["title"])]
    finally:
        conn.close()
    return rows[:limit] if limit else rows


def live_title(db_path, book_id):
    """The title as it stands right now, for the re-check before writing."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        row = conn.execute("SELECT title FROM books WHERE id = ?", (book_id,)).fetchone()
    finally:
        conn.close()
    return row[0] if row else None


class TitleFetcher:
    """Paced title lookups, with backoff on 429. Mirrors enrich_descriptions."""

    def __init__(self, delay, key=None):
        self.key = key
        self.base_delay = delay
        self.delay = delay
        self.client = httpx.Client(timeout=20, follow_redirects=True)

    def _pace(self):
        time.sleep(self.delay)

    def _backoff(self):
        self.delay = min(self.delay * 2, 60)
        print(f"    rate limited; delay now {self.delay:.1f}s", flush=True)
        time.sleep(self.delay)

    def google(self, isbn):
        params = {"q": f"isbn:{isbn}"}
        if self.key:
            params["key"] = self.key
        for attempt in range(3):
            self._pace()
            r = self.client.get(GOOGLE, params=params)
            if r.status_code == 429:
                self._backoff()
                return None
            if r.status_code == 503:
                time.sleep(2 * (attempt + 1))
                continue
            break
        if r.status_code == 503:
            return None
        r.raise_for_status()
        self.delay = max(self.base_delay, self.delay * 0.8)
        for item in (r.json().get("items") or []):
            info = item.get("volumeInfo", {})
            title = (info.get("title") or "").strip()
            sub = (info.get("subtitle") or "").strip()
            if sub:
                title = f"{title}: {sub}"
            if len(title) >= MIN_TITLE_CHARS and not is_bare_identifier(title):
                return title
        return None

    def openlibrary(self, isbn):
        self._pace()
        params = {"bibkeys": f"ISBN:{isbn}", "format": "json", "jscmd": "data"}
        r = self.client.get(OPENLIB, params=params)
        if r.status_code != 200:
            return None
        data = r.json().get(f"ISBN:{isbn}") or {}
        title = (data.get("title") or "").strip()
        sub = (data.get("subtitle") or "").strip()
        if sub:
            title = f"{title}: {sub}"
        if len(title) >= MIN_TITLE_CHARS and not is_bare_identifier(title):
            return title
        return None

    def find(self, isbn):
        try:
            title = self.google(isbn)
        except (httpx.HTTPError, ValueError) as exc:
            print(f"    google failed: {exc}", flush=True)
            title = None
        if title:
            return title, "google"
        try:
            title = self.openlibrary(isbn)
        except (httpx.HTTPError, ValueError) as exc:
            print(f"    openlibrary failed: {exc}", flush=True)
            title = None
        return (title, "openlibrary") if title else (None, None)


def write_title(book_id, title, library_path):
    result = subprocess.run(
        ["calibredb", "set_metadata", "--library-path", library_path,
         "--field", f"title:{title}", str(book_id)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        # One line, not the whole calibre lecture about concurrent programs.
        first = (result.stderr or "").strip().splitlines()
        print(f"    WRITE FAILED: {first[0] if first else 'unknown error'}", flush=True)
        return False
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="write the titles (default: dry run)")
    ap.add_argument("--limit", type=int, help="only the newest N candidates")
    ap.add_argument("--delay", type=float, default=0.8, help="seconds between lookups")
    ap.add_argument("--library-path", default=str(DEFAULT_CALIBRE_LIBRARY))
    args = ap.parse_args()

    db_path = f"{args.library_path}/metadata.db"
    rows = candidates(db_path, args.limit)
    if not rows:
        print("no titles that are a bare identifier - nothing to do")
        return 0

    print(f"{len(rows)} book(s) titled only by an identifier"
          f"{'' if args.apply else '  (DRY RUN - no writes)'}\n", flush=True)

    fetcher = TitleFetcher(args.delay, google_key())
    found = written = failed = absent = 0

    for n, row in enumerate(rows, 1):
        book_id, title = row["id"], row["title"]
        # Prefer the isbn identifier: a book can be titled by its ASIN while
        # carrying a perfectly good ISBN, which is what 37319 does. Falling
        # back to the title only works when the title is itself an ISBN -
        # stripping non-digits from an ASIN yields "0", which would query
        # nonsense, so those are skipped instead.
        isbn = (row["isbn"] or "").strip()
        if not isbn and not title.strip().upper().startswith("B0"):
            isbn = re.sub(r"[^\dXx]", "", title)
        print(f"[{n}/{len(rows)}] {book_id}  {title}", flush=True)
        if len(re.sub(r"[^\dXx]", "", isbn)) not in (10, 13):
            print("    no usable isbn (asin only)", flush=True)
            absent += 1
            continue

        new_title, source = fetcher.find(isbn)
        if not new_title:
            print("    no catalogue title", flush=True)
            absent += 1
            continue

        found += 1
        print(f"    {source}: {new_title}", flush=True)
        if not args.apply:
            continue

        # Re-check: minutes may have passed since the candidate list was built.
        current = live_title(db_path, book_id)
        if not is_bare_identifier(current):
            print(f"    skipped - title changed to {current!r} since the scan", flush=True)
            continue
        if write_title(book_id, new_title, args.library_path):
            written += 1
        else:
            failed += 1

    print(f"\nchecked {len(rows)} | found {found} | written {written} "
          f"| no title {absent} | write errors {failed}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())