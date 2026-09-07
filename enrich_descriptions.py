#!/usr/bin/env python3
"""Fill in missing book descriptions from Google Books and Open Library.

Written because calibre 7.11's own Google source calls the GData feed
(books.google.com/books/feeds/volumes) that Google retired, so its identifier
lookups cannot succeed, and its Amazon source scrapes a search engine that
blocks it. This talks to the current APIs directly.

Deliberate differences from enrich_by_identifier_sql.py:

  * Only the description is written. Nothing can rewrite a title or author.
  * A network failure is never recorded as "no metadata exists". Books are
    left untouched so a later run can retry them.
  * Requests are paced, with backoff on HTTP 429, rather than fired flat out.
  * Newest books first: they are far likelier to carry a publisher blurb.

    python -u enrich_descriptions.py --limit 20             # dry run
    python -u enrich_descriptions.py --limit 20 --apply
    python -u enrich_descriptions.py --apply --delay 2.0    # whole candidate set

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

GOOGLE = "https://www.googleapis.com/books/v1/volumes"
OPENLIB = "https://openlibrary.org/api/books"

# A Google Books API key lifts the anonymous per-IP throttle, which 500-odd
# lookups exhaust almost immediately. Read at run time so the key stays in
# .env and never in this repo.
ENV_FILE = "/Users/alexchilton/PycharmProjects/iwb_agent1/mcp_jira_conf/.env"


def google_key():
    try:
        with open(ENV_FILE, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line.startswith("#") or "=" not in line:
                    continue
                name, _, value = line.partition("=")
                if name.strip() == "books_api":
                    return value.strip().strip("\"'")
    except OSError:
        pass
    return None

# Publisher boilerplate that says nothing about the book. Writing one would
# leave the book looking described, so no later run would revisit it.
JUNK_MARKERS = ("register your print book", "get the ebook free")
MIN_CHARS = 150

CANDIDATE_SQL = """
    SELECT b.id, b.title, i.val, b.pubdate
    FROM books b
    JOIN identifiers i ON i.book = b.id AND i.type = 'isbn'
    WHERE NOT EXISTS (
        SELECT 1 FROM comments c
        WHERE c.book = b.id AND TRIM(COALESCE(c.text, '')) <> '')
    {unavailable_clause}
    -- Newest first. Measured 2026-09-06 on this library: books published
    -- 2018-2030 yielded a usable description 7 times in 13, books from
    -- 1901-1984 only 1 time in 12. Publishers write blurbs for current
    -- titles; nobody wrote one for a 1969 chess book.
    -- calibre stores an unknown publication date as year 0101, so those sort
    -- to the end rather than polluting the front.
    ORDER BY CAST(SUBSTR(b.pubdate, 1, 4) AS INTEGER) < 1900, b.pubdate DESC
"""

# Books an earlier run gave up on. Catalogues do fill in over time, so these
# are worth a retry now and then, but not on every run.
EXCLUDE_UNAVAILABLE = """
      AND NOT EXISTS (
        SELECT 1 FROM books_tags_link l JOIN tags t ON t.id = l.tag
        WHERE l.book = b.id AND t.name = 'metadata-unavailable')
"""


def usable(text):
    """True if text reads like a real description rather than boilerplate."""
    plain = re.sub(r"<[^>]+>", "", text or "").strip()
    if len(plain) < MIN_CHARS:
        return False
    lowered = plain.lower()
    return not any(m in lowered for m in JUNK_MARKERS)


class Fetcher:
    """Paced lookups across both catalogues, with backoff on 429."""

    def __init__(self, delay, key=None):
        self.key = key
        self.base_delay = delay
        self.delay = delay
        self.client = httpx.Client(timeout=20, follow_redirects=True)
        self.throttled = 0
        self.consulted = True
        # A source that has cut us off stays cut off for a while. Asking it
        # once per book just pays the backoff over and over.
        self.consecutive_429 = {}
        self.disabled = set()

    def _pace(self):
        time.sleep(self.delay)

    def _backoff(self):
        self.throttled += 1
        self.consulted = False          # this source never actually answered
        self.delay = min(self.delay * 2, 60)
        print(f"    rate limited; delay now {self.delay:.1f}s", flush=True)
        time.sleep(self.delay)

    def _recover(self):
        # Ease back towards the requested pace after a clean response.
        self.delay = max(self.base_delay, self.delay * 0.8)

    def google(self, isbn):
        params = {"q": f"isbn:{isbn}"}
        if self.key:
            params["key"] = self.key

        # Google returns a transient 503 fairly often; a short retry recovers
        # it, whereas treating it as failure loses the book for the whole run.
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
            raise httpx.HTTPError("503 after 3 attempts")
        r.raise_for_status()
        self._recover()
        for item in (r.json().get("items") or []):
            desc = (item.get("volumeInfo", {}).get("description") or "").strip()
            if usable(desc):
                return desc
        return None

    @staticmethod
    def _plain(field):
        """Open Library returns descriptions as a string or {type, value}."""
        if isinstance(field, dict):
            field = field.get("value", "")
        return (field or "").strip()

    def openlibrary(self, isbn):
        """Edition record first, then the work it belongs to.

        The description usually lives on the work, not the edition, and the
        /api/books endpoint returns neither - only excerpts and notes.
        """
        self._pace()
        r = self.client.get(f"https://openlibrary.org/isbn/{isbn}.json")
        if r.status_code == 429:
            self._backoff()
            return None
        if r.status_code == 404:
            return None
        r.raise_for_status()
        self._recover()
        edition = r.json()

        for works in (edition.get("works") or [])[:1]:
            self._pace()
            w = self.client.get(f"https://openlibrary.org{works['key']}.json")
            if w.status_code == 429:
                self._backoff()
                break
            if w.status_code == 200:
                self._recover()
                text = self._plain(w.json().get("description"))
                if usable(text):
                    return text

        text = self._plain(edition.get("description"))
        if usable(text):
            return text
        for excerpt in (edition.get("excerpts") or []):
            text = self._plain(excerpt.get("text"))
            if usable(text):
                return text
        return None

    def description(self, isbn):
        """Return (description, source).

        source is the catalogue that answered, "absent" when every catalogue
        was reached and none had the book, or "inconclusive" when at least one
        could not be consulted. Only "absent" is a real negative.
        """
        reached_all = True
        for name, fn in (("google", self.google), ("openlibrary", self.openlibrary)):
            if name in self.disabled:
                reached_all = False
                continue
            self.consulted = True
            try:
                found = fn(isbn)
            except Exception as exc:
                print(f"    {name} error: {type(exc).__name__}", flush=True)
                reached_all = False
                continue
            if not self.consulted:      # rate limited, so it never answered
                reached_all = False
                self.consecutive_429[name] = self.consecutive_429.get(name, 0) + 1
                if self.consecutive_429[name] >= 5:
                    self.disabled.add(name)
                    self.delay = self.base_delay
                    print(f"    {name} disabled for this run after 5 straight "
                          f"rate limits", flush=True)
                continue
            self.consecutive_429[name] = 0
            if found:
                return found, name
        return None, "absent" if reached_all else "inconclusive"


def set_description(book_id, text, library_path):
    result = subprocess.run(
        ["calibredb", "set_metadata", "--library-path", library_path,
         "--field", f"comments:{text}", str(book_id)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout).strip().splitlines()[-1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write the descriptions")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--delay", type=float, default=1.5,
                    help="seconds between requests (default 1.5)")
    ap.add_argument("--include-unavailable", action="store_true",
                    help="also retry books tagged metadata-unavailable; "
                         "catalogues do fill in over time")
    ap.add_argument("--library-path", default=DEFAULT_CALIBRE_LIBRARY)
    args = ap.parse_args()

    sql = CANDIDATE_SQL.format(
        unavailable_clause="" if args.include_unavailable else EXCLUDE_UNAVAILABLE)
    with sqlite3.connect(f"file:{args.library_path}/metadata.db?mode=ro", uri=True) as con:
        rows = con.execute(sql).fetchall()
    if args.limit:
        rows = rows[:args.limit]

    print(f"{len(rows)} books with an ISBN and no description, oldest first"
          + (" (including metadata-unavailable)" if args.include_unavailable else ""))
    print(f"pacing: {args.delay}s between requests\n", flush=True)

    found = written = missing = unclear = failed = 0
    started = time.time()
    key = google_key()
    print("google books key: " + ("loaded" if key else "NOT FOUND, anonymous quota"),
          flush=True)
    fetcher = Fetcher(args.delay, key)

    for n, (book_id, title, isbn, pubdate) in enumerate(rows, 1):
        year = (pubdate or "????")[:4]
        print(f"[{n}/{len(rows)}] {book_id} {year} {title[:58]}", flush=True)
        text, source = fetcher.description(isbn)
        if not text:
            if source == "absent":
                missing += 1
                print("    not in either catalogue", flush=True)
            else:
                unclear += 1
                print("    INCONCLUSIVE - a source could not be reached, retry later",
                      flush=True)
            continue
        found += 1
        print(f"    {source}: {len(text)} chars", flush=True)
        if args.apply:
            try:
                set_description(book_id, text, args.library_path)
                written += 1
            except Exception as exc:
                failed += 1
                print(f"    WRITE FAILED: {exc}", file=sys.stderr, flush=True)

    mins = (time.time() - started) / 60
    print(f"\nchecked {len(rows)} in {mins:.1f} min | found {found} | "
          f"written {written} | genuinely absent {missing} | inconclusive {unclear} | "
          f"write errors {failed} | rate-limit pauses {fetcher.throttled}")
    if not args.apply:
        print("dry run - nothing written. Add --apply.")


if __name__ == "__main__":
    main()