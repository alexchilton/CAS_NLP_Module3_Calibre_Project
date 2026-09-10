#!/usr/bin/env python3
"""Recover ISBNs by reading the text of the book files, headless.

calibre's "Extract ISBN" plugin does this well but is a GUI action, so it
cannot run while calibre is closed. This is the same idea from the command
line. The repo's own extract_isbn_from_file only reads the embedded metadata
block, which yielded 0 ISBNs out of 20 books on this library; reading the
actual text yielded 8 out of the same 20.

Two phases, because writing needs calibre closed AND nothing else writing:

    python -u isbn_from_content.py --scan               # read only, resumable
    python -u isbn_from_content.py --scan --resume      # continue after a stop
    python -u isbn_from_content.py --apply              # write what was found

Scan results are appended to isbn-scan.jsonl as they are produced, so a crash
or a Ctrl-C costs only the book in flight.
"""

import argparse
import collections
import json
import multiprocessing as mp
import os
import re
import sqlite3
import subprocess
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from calibre_tools.isbn_tools import extract_isbn_from_text  # noqa: E402
from calibre_tools.config import DEFAULT_CALIBRE_LIBRARY      # noqa: E402

REPO = Path(__file__).resolve().parent
SCAN_FILE = REPO / "isbn-scan.jsonl"

PDFTOTEXT = "/opt/homebrew/bin/pdftotext"
EBOOK_CONVERT = "/Applications/calibre.app/Contents/MacOS/ebook-convert"

# Read only the front matter. The copyright page is always near the start,
# and scanning a 900-page PDF in full is both slow and a source of false hits
# from bibliographies.
PDF_PAGES = 12
EPUB_PARTS = 20

# Placeholders that pass the checksum. 0123456789 turned up in a real book on
# the first sample run.
DUMMY_ISBNS = {"0123456789", "1234567890", "9781234567897", "9780000000002"}

# The plugin restricts ISBN-13 to these prefixes; anything else is a
# coincidence rather than a book number.
VALID_13_PREFIXES = ("977", "978", "979")

# An ISBN found in several unrelated books is a constant the regex mistook
# for one. The threshold differs by length: a repeated ISBN-13 is usually the
# same title filed twice, but ISBN-10's weak checksum means a repeat is far
# more likely to be a number like 4294967277 recurring in technical text.
REPEAT_LIMIT_13 = 4
REPEAT_LIMIT_10 = 2

NATIVE = {"EPUB", "PDF", "TXT"}
CONVERTIBLE = {"MOBI", "AZW3", "AZW", "DJVU", "LIT", "PDB", "RTF", "HTMLZ", "ORIGINAL_EPUB"}


def plausible(isbn):
    if isbn in DUMMY_ISBNS:
        return False
    if len(isbn) == 13 and not isbn.startswith(VALID_13_PREFIXES):
        return False
    if len(isbn) == 10 and isbn.startswith(("97", "21474836")):
        # 97... at length 10 is an ISBN-13 that lost its last three digits;
        # 2147483648 is 2**31 and appears in any book about integers.
        return False
    # A run of one repeated digit is a placeholder, not a book.
    return len(set(isbn[:-1])) > 2


def first_isbn(text):
    """Prefer a 13-digit ISBN; fall back to a 10-digit one.

    ISBN-10's check digit is weak - roughly 1 in 11 random 10-digit numbers
    passes - so technical books full of constants throw false positives. The
    first scan of this library matched 2147483648 (2**31) in 15 different
    books. ISBN-13 carries the 978/979 prefix as well as its checksum, so it
    is far harder to hit by accident.
    """
    found = [i for i in extract_isbn_from_text(text or "") if plausible(i)]
    for isbn in found:
        if len(isbn) == 13:
            return isbn
    return found[0] if found else None


def from_pdf(path):
    r = subprocess.run([PDFTOTEXT, "-f", "1", "-l", str(PDF_PAGES), path, "-"],
                       capture_output=True, text=True, timeout=120)
    return first_isbn(r.stdout)


def from_epub(path):
    with zipfile.ZipFile(path) as z:
        names = [n for n in z.namelist()
                 if n.lower().endswith((".opf", ".xhtml", ".html", ".htm", ".ncx"))]
        for name in names[:EPUB_PARTS]:
            try:
                raw = z.read(name).decode("utf-8", "replace")
            except Exception:
                continue
            found = first_isbn(re.sub(r"<[^>]+>", " ", raw))
            if found:
                return found
    return None


def from_txt(path):
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return first_isbn(fh.read(200_000))


def from_convert(path):
    """Last resort: let calibre turn it into text. Slow, so used sparingly."""
    out = f"/tmp/isbn_scan_{os.getpid()}.txt"
    try:
        r = subprocess.run([EBOOK_CONVERT, path, out],
                           capture_output=True, text=True, timeout=180)
        if r.returncode != 0 or not os.path.exists(out):
            return None
        with open(out, "r", encoding="utf-8", errors="replace") as fh:
            return first_isbn(fh.read(200_000))
    finally:
        if os.path.exists(out):
            os.remove(out)


def scan_one(job):
    """Runs in a worker process. Returns a result dict, never raises."""
    book_id, fmt, path = job
    try:
        if not os.path.isfile(path):
            return {"id": book_id, "isbn": None, "error": "missing file"}
        if fmt == "PDF":
            isbn = from_pdf(path)
        elif fmt in ("EPUB", "ORIGINAL_EPUB"):
            isbn = from_epub(path)
        elif fmt == "TXT":
            isbn = from_txt(path)
        else:
            isbn = from_convert(path)
        return {"id": book_id, "isbn": isbn, "fmt": fmt, "error": None}
    except subprocess.TimeoutExpired:
        return {"id": book_id, "isbn": None, "fmt": fmt, "error": "timeout"}
    except Exception as exc:
        return {"id": book_id, "isbn": None, "fmt": fmt, "error": type(exc).__name__}


def candidates(library_path):
    """Books with no description and no ISBN, best readable format each."""
    order = {f: i for i, f in enumerate(
        ["EPUB", "PDF", "TXT", "ORIGINAL_EPUB", "AZW3", "MOBI", "AZW", "DJVU"])}
    sql = """
        SELECT b.id, d.format, b.path, d.name
        FROM books b JOIN data d ON d.book = b.id
        WHERE NOT EXISTS (SELECT 1 FROM comments c
                          WHERE c.book = b.id AND TRIM(COALESCE(c.text,'')) <> '')
          AND NOT EXISTS (SELECT 1 FROM identifiers i
                          WHERE i.book = b.id AND i.type = 'isbn')
    """
    best = {}
    with sqlite3.connect(f"file:{library_path}/metadata.db?mode=ro", uri=True) as con:
        for book_id, fmt, path, name in con.execute(sql):
            if fmt not in NATIVE and fmt not in CONVERTIBLE:
                continue
            rank = order.get(fmt, 99)
            if book_id not in best or rank < best[book_id][0]:
                full = f"{library_path}/{path}/{name}.{fmt.lower()}"
                best[book_id] = (rank, fmt, full)
    return [(bid, fmt, path) for bid, (_, fmt, path) in best.items()]


def done_ids():
    if not SCAN_FILE.exists():
        return set()
    seen = set()
    with open(SCAN_FILE) as fh:
        for line in fh:
            try:
                seen.add(json.loads(line)["id"])
            except Exception:
                continue
    return seen


def do_scan(args):
    jobs = candidates(args.library_path)
    if args.resume:
        already = done_ids()
        jobs = [j for j in jobs if j[0] not in already]
        print(f"resuming: {len(already)} already scanned")
    elif SCAN_FILE.exists():
        print(f"{SCAN_FILE.name} exists; pass --resume to continue it, "
              f"or delete it to start over")
        return 1
    if args.limit:
        jobs = jobs[:args.limit]

    print(f"scanning {len(jobs)} books with {args.workers} workers")
    print(f"appending to {SCAN_FILE}\n", flush=True)

    found = errors = 0
    with open(SCAN_FILE, "a") as out, mp.Pool(args.workers) as pool:
        for n, res in enumerate(pool.imap_unordered(scan_one, jobs, chunksize=4), 1):
            out.write(json.dumps(res) + "\n")
            out.flush()                      # every book, so a crash costs one
            if res["isbn"]:
                found += 1
            if res["error"]:
                errors += 1
            if n % 25 == 0 or n == len(jobs):
                print(f"  {n}/{len(jobs)}  found {found}  errors {errors}", flush=True)

    print(f"\nscanned {len(jobs)} | ISBNs found {found} | errors {errors}")
    print("run with --apply to write these identifiers (calibre must be closed)")
    return 0


def do_apply(args):
    if not SCAN_FILE.exists():
        print(f"no {SCAN_FILE.name}; run --scan first", file=sys.stderr)
        return 1
    results = {}
    with open(SCAN_FILE) as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("isbn"):
                results[r["id"]] = r["isbn"]

    # An ISBN that turns up in several unrelated books is a constant the
    # regex mistook for one, not a book number. Genuine duplicates exist
    # (the same title filed twice), so allow a few before rejecting.
    counts = collections.Counter(results.values())
    suspect = {i for i, n in counts.items()
               if n >= (REPEAT_LIMIT_13 if len(i) == 13 else REPEAT_LIMIT_10)}
    if suspect:
        dropped = [b for b, i in results.items() if i in suspect]
        print(f"dropping {len(dropped)} books on {len(suspect)} repeated "
              f"ISBNs: {sorted(suspect)}")
        results = {b: i for b, i in results.items() if i not in suspect}

    # The scan file only grows, so without this every run rewrites every ISBN
    # it has ever recovered. Measured 2026-09-10: 925 books, ~15 minutes, on
    # every daily run since 09-08, all of it writing values already present.
    with sqlite3.connect(f"file:{args.library_path}/metadata.db?mode=ro",
                         uri=True) as con:
        have = {bid: val for bid, val in con.execute(
            "SELECT book, val FROM identifiers WHERE type = 'isbn'")}
        alive = {r[0] for r in con.execute("SELECT id FROM books")}

    unchanged = sum(1 for b, i in results.items() if have.get(b) == i)
    gone = sum(1 for b in results if b not in alive)
    results = {b: i for b, i in results.items()
               if b in alive and have.get(b) != i}

    print(f"{len(results)} books need their recovered ISBN written "
          f"({unchanged} already have it, {gone} no longer in the library)")
    written = failed = 0
    for book_id, isbn in results.items():
        r = subprocess.run(
            ["calibredb", "set_metadata", "--library-path", args.library_path,
             "--field", f"identifiers:isbn:{isbn}", str(book_id)],
            capture_output=True, text=True)
        if r.returncode == 0:
            written += 1
        else:
            failed += 1
            print(f"  {book_id}: FAILED {(r.stderr or r.stdout).strip()[-80:]}",
                  file=sys.stderr)
        if (written + failed) % 50 == 0:
            print(f"  {written + failed}/{len(results)} written {written}", flush=True)
    print(f"\nwritten {written}, failed {failed}")
    print("run enrich_descriptions.py next to fetch descriptions for them")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan", action="store_true", help="read files, find ISBNs")
    ap.add_argument("--apply", action="store_true", help="write what --scan found")
    ap.add_argument("--resume", action="store_true", help="continue an interrupted scan")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--library-path", default=DEFAULT_CALIBRE_LIBRARY)
    args = ap.parse_args()
    if args.scan:
        return do_scan(args)
    if args.apply:
        return do_apply(args)
    ap.error("give --scan or --apply")


if __name__ == "__main__":
    sys.exit(main())
