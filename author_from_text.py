#!/usr/bin/env python3
"""Recover the author of books filed under "Unknown", by reading the book.

Measured 2026-09-10: 7,765 of 29,268 books have no author, 7,754 of which have
a readable file whose title page names one.

Validated against 25 books whose author calibre already knows:

    matched 18 | missed 0 | said unknown 7

Nothing wrong in 25. The model either names the author or says UNKNOWN, which
is the property that makes this safe to run unattended -- a wrong author is
much worse than no author, because it is invisible. It also tends to find
co-authors calibre had lost: "Dan Jurafsky" came back as "Daniel Jurafsky &
James H. Martin", which is the correct pair.

Applying an author makes calibre RENAME THE BOOK'S FOLDER on disk. That is
normal calibre behaviour and it is safe, but it is thousands of directory
moves, so --scan is read-only and the write is a separate deliberate step.

    python -u author_from_text.py --scan            # read-only, resumable
    python -u author_from_text.py --scan --resume
    python -u author_from_text.py --apply

CLOSE CALIBRE before --apply.
"""

import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import time

import httpx

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from calibre_tools.config import DEFAULT_CALIBRE_LIBRARY  # noqa: E402
import describe_with_qwen as D  # noqa: E402

REPO = os.path.dirname(os.path.abspath(__file__))
SCAN_FILE = os.path.join(REPO, "author-scan.jsonl")

UNKNOWN = ("Unknown", "Unknown Author", "", "Anonymous")
FRONT_CHARS = 6000      # title and copyright pages; the rest is not evidence
MAX_AUTHORS = 6

# The copyright page names the publisher more prominently than the author, so
# that is what the model reaches for when the author is not stated. The prompt
# says not to; this makes it so. A real person is not called "Packt
# Publishing", and filing 200 books under one imprint is worse than Unknown
# because it looks deliberate.
IMPRINT_WORDS = {
    "publishing", "publications", "publisher", "publishers", "press",
    "media", "books", "book", "editions", "verlag", "ltd", "limited",
    "inc", "llc", "gmbh", "co", "company", "group", "house", "imprint",
    "academy", "institute", "university", "college", "school", "series",
    "edition", "team", "staff", "editors", "editor", "translated",
    "association", "society", "council", "committee", "department",
}

PROMPT = """Below is the opening of a book: cover page, title page, copyright page.

Who wrote it? Reply with the author's name and nothing else.
If several authors, separate with " & ". If the text does not clearly name an
author, reply with exactly: UNKNOWN

Do not reply with a publisher, an imprint, an editor, a translator, or the
title of the book.

--- book text ---
{text}
--- end ---"""


def candidates(library_path):
    """Books with no author, best readable format each."""
    order = {"EPUB": 0, "PDF": 1, "TXT": 2, "ORIGINAL_EPUB": 3,
             "AZW3": 4, "MOBI": 5, "AZW": 6, "ORIGINAL_MOBI": 7, "DJVU": 8}
    marks = ",".join("?" * len(UNKNOWN))
    sql = f"""
        SELECT b.id, d.format, b.path, d.name, b.title
        FROM books b
        JOIN books_authors_link ba ON ba.book = b.id
        JOIN authors a ON a.id = ba.author
        JOIN data d ON d.book = b.id
        WHERE a.name IN ({marks})
    """
    best = {}
    with sqlite3.connect(f"file:{library_path}/metadata.db?mode=ro",
                         uri=True) as con:
        for bid, fmt, path, name, title in con.execute(sql, UNKNOWN):
            rank = order.get(fmt)
            if rank is None:
                continue
            if bid not in best or rank < best[bid][0]:
                best[bid] = (rank, fmt,
                             f"{library_path}/{path}/{name}.{fmt.lower()}",
                             title)
    return [(bid, v[1], v[2], v[3]) for bid, v in best.items()]


# Academic credentials only. A generational suffix is part of the name --
# "Francis X. Govers III" is what the man is called, and stripping it would be
# an error, not a tidy-up.
CREDENTIAL_SUFFIX = re.compile(
    r",?\s*\b(ph\.?\s?d|m\.?d|m\.?sc|m\.?a|b\.?sc|mba|msee|pmp|cissp|"
    r"cpa|p\.?e)\b\.?\s*$", re.I)


def tidy(name):
    """Trim a title page's decoration off a name."""
    n = re.sub(r"\s+", " ", (name or "")).strip(" ,.;")
    return CREDENTIAL_SUFFIX.sub("", n).strip(" ,")


def plausible(names, title):
    """Reject anything that is not a person's name.

    The model is well behaved on this task, but the cost of a wrong author is
    high and silent, so the output is checked rather than trusted.
    """
    if not names or len(names) > MAX_AUTHORS:
        return False
    title_words = {w for w in re.sub(r"[^a-z ]", " ", (title or "").lower()).split()
                   if len(w) > 3}
    for n in names:
        n = n.strip()
        if not (3 <= len(n) <= 60):
            return False
        if "(" in n or ")" in n or "@" in n or "/" in n:
            return False
        letters = [c for c in n if c.isalpha()]
        if not letters:
            return False
        # Catalogue-card artefacts: "SMITH, JOHN (JOHN.)"
        if sum(c.isupper() for c in letters) / len(letters) > 0.7:
            return False
        if sum(c.isdigit() for c in n) > 2:
            return False
        # An echo of the title is not an author.
        words = {w for w in re.sub(r"[^a-z ]", " ", n.lower()).split() if len(w) > 3}
        if words and words <= title_words:
            return False
        if {w.strip(".,") for w in n.lower().split()} & IMPRINT_WORDS:
            return False
    return True


def ask(client, model, text, title):
    r = client.post(f"{D.OLLAMA}/api/chat", json={
        "model": model,
        "messages": [{"role": "user",
                      "content": PROMPT.format(text=text[:FRONT_CHARS])}],
        "stream": False,
        "think": False,
        "options": {"temperature": 0.0, "num_predict": 40},
    })
    r.raise_for_status()
    reply = D.clean(r.json().get("message", {}).get("content", ""))
    if not reply or reply.upper().startswith("UNKNOWN") or "UNKNOWN" in reply.upper():
        return None
    names = [tidy(n) for n in re.split(r"\s*&\s*|\s*;\s*", reply) if n.strip()]
    names = [n for n in names if n]
    return names if plausible(names, title) else None


def done_ids():
    seen = set()
    if os.path.exists(SCAN_FILE):
        for line in open(SCAN_FILE):
            try:
                seen.add(json.loads(line)["id"])
            except Exception:
                pass
    return seen


def do_scan(args):
    jobs = candidates(args.library_path)
    if args.resume:
        already = done_ids()
        jobs = [j for j in jobs if j[0] not in already]
        print(f"resuming: {len(already)} already scanned")
    elif os.path.exists(SCAN_FILE):
        print(f"{os.path.basename(SCAN_FILE)} exists; pass --resume or delete it")
        return 1
    if args.limit:
        jobs = jobs[:args.limit]

    print(f"{len(jobs)} books with no author, reading with {args.model}")
    print(f"appending to {SCAN_FILE}\n", flush=True)

    found = unknown = thin = errors = 0
    started = time.time()
    with open(SCAN_FILE, "a") as out, httpx.Client(timeout=300) as client:
        for n, (bid, fmt, path, title) in enumerate(jobs, 1):
            rec = {"id": bid, "title": title, "authors": None, "note": None}
            try:
                text = D.book_text(fmt, path)
                if len(text) < D.MIN_CHARS:
                    rec["note"] = "too little text"
                    thin += 1
                else:
                    names = ask(client, args.model, text, title)
                    if names:
                        rec["authors"] = names
                        found += 1
                    else:
                        rec["note"] = "no author named"
                        unknown += 1
            except Exception as exc:
                rec["note"] = type(exc).__name__
                errors += 1
            out.write(json.dumps(rec) + "\n")
            out.flush()
            mark = " & ".join(rec["authors"]) if rec["authors"] else "-- " + rec["note"]
            print(f"[{n}/{len(jobs)}] {bid} {title[:42]:44} {mark}", flush=True)

    mins = (time.time() - started) / 60
    print(f"\n{len(jobs)} books in {mins:.1f} min | found {found} | "
          f"no author named {unknown} | too little text {thin} | errors {errors}")
    print("run --apply to write them into calibre")
    return 0


def do_apply(args):
    if not os.path.exists(SCAN_FILE):
        print(f"no {os.path.basename(SCAN_FILE)}; run --scan first", file=sys.stderr)
        return 1
    recs = {}
    for line in open(SCAN_FILE):
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("authors"):
            # Tidy at write time as well as at scan time: records written
            # before tidy() existed still carry "Val Andrei Fajardo, PhD".
            names = [n for n in (tidy(a) for a in r["authors"]) if n]
            if names:
                recs[r["id"]] = names

    # Only books still filed under Unknown. If you have since named an author
    # yourself, yours wins; this never overwrites a real one.
    marks = ",".join("?" * len(UNKNOWN))
    with sqlite3.connect(f"file:{args.library_path}/metadata.db?mode=ro",
                         uri=True) as con:
        still_unknown = {r[0] for r in con.execute(
            f"""SELECT ba.book FROM books_authors_link ba JOIN authors a
                ON a.id = ba.author WHERE a.name IN ({marks})""", UNKNOWN)}
        alive = {r[0] for r in con.execute("SELECT id FROM books")}

    named = len(recs.keys() - still_unknown)
    gone = len(recs.keys() - alive)
    payload = {str(b): v for b, v in recs.items()
               if b in still_unknown and b in alive}

    print(f"{len(payload)} authors to write "
          f"({named} already have an author, {gone} no longer in the library)")
    if not payload:
        return 0
    print("calibre will rename these books' folders on disk.", flush=True)

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                     encoding="utf-8") as fh:
        json.dump({"library": args.library_path, "field": "authors",
                   "values": payload}, fh)
        path = fh.name
    try:
        r = subprocess.run(
            ["calibre-debug", "-e", os.path.join(REPO, "calibre_bulk_set.py"), path],
            capture_output=True, text=True)
    finally:
        os.unlink(path)
    if r.returncode != 0:
        print((r.stderr or r.stdout).strip()[-500:], file=sys.stderr)
        return 1
    line = [ln for ln in r.stdout.strip().splitlines() if ln.startswith("{")]
    print("\n" + (line[-1] if line else r.stdout.strip()[-300:]))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--model", default=D.DEFAULT_MODEL)
    ap.add_argument("--library-path", default=DEFAULT_CALIBRE_LIBRARY)
    args = ap.parse_args()
    if args.scan:
        return do_scan(args)
    if args.apply:
        return do_apply(args)
    ap.error("give --scan or --apply")


if __name__ == "__main__":
    sys.exit(main())
