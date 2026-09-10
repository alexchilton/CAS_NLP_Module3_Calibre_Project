#!/usr/bin/env python3
"""Replace a title that is nothing but an ISBN or ASIN with the real one.

isbn_from_title.py lifts the identifier out of such a title, and
enrich_descriptions.py then fetches a description with it -- but deliberately
writes only the description, never a title, because enrich_by_identifier_sql.py
once rewrote "CUDA for LLMs" into "CUDA for Deep Learning". That caution is
right in general and pointless here: a title like "1806109018" carries no
information at all, so there is nothing to protect.

The safety rule is therefore narrow and mechanical, not a judgement call:

  * the current title must be a bare code -- digits with an optional X check
    digit, or an Amazon ASIN. A title with a letter or a space in it is never
    touched. This is what keeps "Swordheart", whose kobo id happens to be
    "swordheart", out of the candidate set.
  * that code must equal one of the book's own identifiers.
  * the catalogue must return a title that is not itself a bare code.

The author is set at the same time, but ONLY when it is currently Unknown.
A book that already names an author keeps it.

    python -u title_from_identifier.py            # dry run
    python -u title_from_identifier.py --apply

CLOSE CALIBRE before --apply.
"""

import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys
import time

import httpx

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from calibre_tools.config import DEFAULT_CALIBRE_LIBRARY  # noqa: E402
from enrich_descriptions import GOOGLE, google_key  # noqa: E402

REPO = os.path.dirname(os.path.abspath(__file__))

# A bare code and nothing else. No spaces, no letters except a trailing X on
# an ISBN-10 or the leading B of an ASIN.
BARE_ISBN = re.compile(r"^\d{9,13}[Xx]?$")
BARE_ASIN = re.compile(r"^B[0-9A-Z]{9}$")

UNKNOWN_AUTHORS = {"unknown", "unknown author", "", "anonymous"}


def usable_author(name):
    """Reject the catalogue-record artefacts Google returns for some books.

    Measured 2026-09-10 on this set: one of ten hits came back as
    "GEORGE. CHRYSOCHOIDIS HANTZARAS (GEORGE.)" -- a library card entry, not a
    name. Writing that over "Unknown" makes the record worse, not better, so
    the book keeps Unknown and stays visible as something to fix.
    """
    n = (name or "").strip()
    if not n or "(" in n:
        return False
    letters = [c for c in n if c.isalpha()]
    return bool(letters) and sum(c.isupper() for c in letters) / len(letters) < 0.7


def is_bare_code(title):
    t = (title or "").strip()
    return bool(BARE_ISBN.match(t) or BARE_ASIN.match(t))


CANDIDATE_SQL = """
    SELECT b.id, b.title, i.type, i.val,
           (SELECT a.name FROM authors a
              JOIN books_authors_link ba ON ba.author = a.id
             WHERE ba.book = b.id LIMIT 1)
    FROM books b JOIN identifiers i ON i.book = b.id
    ORDER BY b.id DESC
"""


def lookup(client, key, isbn):
    """Return (title, authors) from Google Books, or (None, None)."""
    params = {"q": f"isbn:{isbn}"}
    if key:
        params["key"] = key
    r = client.get(GOOGLE, params=params)
    if r.status_code != 200:
        return None, None
    for item in (r.json().get("items") or []):
        info = item.get("volumeInfo", {})
        title = (info.get("title") or "").strip()
        sub = (info.get("subtitle") or "").strip()
        if not title or is_bare_code(title):
            continue
        if sub and sub.lower() not in title.lower():
            title = f"{title}: {sub}"
        return title, info.get("authors") or []
    return None, None


def set_fields(book_id, title, authors, library_path):
    cmd = ["calibredb", "set_metadata", "--library-path", library_path,
           "--field", f"title:{title}"]
    if authors:
        cmd += ["--field", "authors:" + " & ".join(authors)]
    cmd.append(str(book_id))
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).strip().splitlines()[-1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--delay", type=float, default=0.8)
    ap.add_argument("--library-path", default=DEFAULT_CALIBRE_LIBRARY)
    args = ap.parse_args()

    with sqlite3.connect(f"file:{args.library_path}/metadata.db?mode=ro",
                         uri=True) as con:
        rows = con.execute(CANDIDATE_SQL).fetchall()

    jobs = []
    seen = set()
    for bid, title, _itype, val, author in rows:
        if bid in seen or not is_bare_code(title):
            continue
        if title.strip().upper() != (val or "").strip().upper():
            continue
        seen.add(bid)
        jobs.append((bid, title, val, author))

    print(f"{len(jobs)} books whose title is nothing but their identifier")
    key = google_key()
    print("google books key: " + ("loaded" if key else "NOT FOUND"), flush=True)

    found = written = absent = failed = 0
    with httpx.Client(timeout=20, follow_redirects=True) as client:
        for n, (bid, title, val, author) in enumerate(jobs, 1):
            time.sleep(args.delay)
            try:
                new_title, authors = lookup(client, key, val)
            except Exception as exc:
                print(f"[{n}/{len(jobs)}] {bid} {title}  -- {type(exc).__name__}",
                      flush=True)
                continue
            if not new_title:
                absent += 1
                print(f"[{n}/{len(jobs)}] {bid} {title}  -- not in Google Books",
                      flush=True)
                continue
            found += 1
            # Only fill an author that is missing. A book that names one keeps it.
            keep_author = (author or "").strip().lower() not in UNKNOWN_AUTHORS
            show_authors = [] if keep_author else [a for a in authors if usable_author(a)]
            print(f"[{n}/{len(jobs)}] {bid} {title}\n"
                  f"    -> {new_title}"
                  + (f"\n    -> authors: {', '.join(show_authors)}"
                     if show_authors else
                     f"    (author kept: {author})"), flush=True)
            if args.apply:
                try:
                    set_fields(bid, new_title, show_authors, args.library_path)
                    written += 1
                except Exception as exc:
                    failed += 1
                    print(f"    WRITE FAILED: {exc}", file=sys.stderr, flush=True)

    print(f"\n{len(jobs)} checked | found {found} | written {written} | "
          f"not in catalogue {absent} | write errors {failed}")
    if not args.apply:
        print("dry run - nothing written. Add --apply.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
