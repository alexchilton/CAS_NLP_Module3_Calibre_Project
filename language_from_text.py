#!/usr/bin/env python3
"""Set the language on books that have none, by reading the book itself.

Measured 2026-09-10: 14,637 of 29,268 books had no language at all, so half
the library was invisible to a language filter.

The description is NOT the source, and that is the whole design decision here.
It looked like the obvious one -- 14,439 of those books have a description and
a detector agrees with the catalogue 98.5% of the time on a random sample. But
that sample is 96% English. On non-English books with a model-generated
description the detector is wrong 75 times in 77, because describe_with_qwen
writes its summaries in English whatever the book is written in. Detecting a
German book's language from an English summary of it cannot work.

So this reads the book's own text, the same extraction describe_with_qwen
uses, and falls back to the description only when no file can be read -- and
then only a catalogue description, never a generated one.

Measured accuracy against the 14,023 books that already carry a language,
on a deliberately hard sample of 150 non-English and 150 English books:

    English      99.3%
    non-English  80.6%
    weighted to the library's real 96/4 split: 98.6%

A confidence threshold does not help: the detector is confidently wrong on the
failures, at every cut from 0.60 to 0.99. The failures are books whose front
matter is in English -- copyright and publisher pages -- which is what the
first 14 pages of a Russian technical book often are. Reading from the middle
of the book would fix it and is the obvious next improvement.

Nothing already set is ever overwritten. This only fills blanks.

    python -u language_from_text.py --scan            # read-only, resumable
    python -u language_from_text.py --scan --resume
    python -u language_from_text.py --apply

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
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from calibre_tools.config import DEFAULT_CALIBRE_LIBRARY  # noqa: E402
import describe_with_qwen as D  # noqa: E402

REPO = os.path.dirname(os.path.abspath(__file__))
SCAN_FILE = os.path.join(REPO, "language-scan.jsonl")

MIN_TEXT = 300          # below this there is not enough to judge
# Restricted to what this library actually contains. Offering the detector 75
# languages it will never see costs accuracy on the ones it will.
LANGS = {
    "ENGLISH": "eng", "GERMAN": "deu", "RUSSIAN": "rus", "SPANISH": "spa",
    "FRENCH": "fra", "ITALIAN": "ita", "ARABIC": "ara", "CHINESE": "zho",
    "CZECH": "ces", "CATALAN": "cat", "ESTONIAN": "est", "PORTUGUESE": "por",
    "DUTCH": "nld", "POLISH": "pol", "SWEDISH": "swe", "DANISH": "dan",
}

CANDIDATE_SQL = """
    SELECT b.id, b.title, d.format, b.path, d.name,
           (SELECT c.text FROM comments c WHERE c.book = b.id)
    FROM books b LEFT JOIN data d ON d.book = b.id
    WHERE NOT EXISTS (SELECT 1 FROM books_languages_link l WHERE l.book = b.id)
"""


def build_detector():
    from lingua import LanguageDetectorBuilder, Language
    langs, iso = [], {}
    for name, code in LANGS.items():
        lang = getattr(Language, name, None)
        if lang is not None:
            langs.append(lang)
            iso[lang] = code
    return (LanguageDetectorBuilder.from_languages(*langs)
            .with_preloaded_language_models().build()), iso


def candidates(library_path):
    """Books with no language, best readable format each."""
    order = {"EPUB": 0, "PDF": 1, "TXT": 2, "ORIGINAL_EPUB": 3,
             "AZW3": 4, "MOBI": 5, "AZW": 6, "ORIGINAL_MOBI": 7, "DJVU": 8}
    best = {}
    with sqlite3.connect(f"file:{library_path}/metadata.db?mode=ro",
                         uri=True) as con:
        for bid, title, fmt, path, name, desc in con.execute(CANDIDATE_SQL):
            rank = order.get(fmt)
            entry = best.get(bid)
            full = (f"{library_path}/{path}/{name}.{fmt.lower()}"
                    if fmt and rank is not None else None)
            if entry is None:
                best[bid] = (rank if rank is not None else 99, fmt, full,
                             title, desc)
            elif rank is not None and rank < entry[0]:
                best[bid] = (rank, fmt, full, title, desc)
    return [(bid, v[1], v[2], v[3], v[4]) for bid, v in best.items()]


def source_text(fmt, path, title, desc):
    """The book's own words, or the least bad substitute.

    A generated description is always English, so using it would label every
    non-English book English. Only a catalogue description is allowed as a
    fallback, and the title comes along because it is in the book's language
    even when nothing else is available.
    """
    if fmt and path:
        text = D.book_text(fmt, path)
        if len(text) >= MIN_TEXT:
            return text, fmt
    if desc and "generated from the book" not in desc:
        plain = " ".join(re.sub(r"<[^>]+>", " ", desc).split())
        if len(plain) >= MIN_TEXT:
            return f"{title}. {plain}", "description"
    return "", "none"


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
    detector, iso = build_detector()
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

    print(f"{len(jobs)} books with no language")
    print(f"appending to {SCAN_FILE}\n", flush=True)

    found = thin = 0
    counts = Counter()
    started = time.time()
    with open(SCAN_FILE, "a") as out:
        for n, (bid, fmt, path, title, desc) in enumerate(jobs, 1):
            text, via = source_text(fmt, path, title, desc)
            code = None
            if text:
                lang = detector.detect_language_of(text)
                code = iso.get(lang) if lang else None
            rec = {"id": bid, "lang": code, "via": via, "title": title}
            out.write(json.dumps(rec) + "\n")
            if code:
                found += 1
                counts[code] += 1
            else:
                thin += 1
            if n % 200 == 0:
                out.flush()
                print(f"  {n}/{len(jobs)}  detected {found}  "
                      f"{dict(counts.most_common(5))}", flush=True)

    mins = (time.time() - started) / 60
    print(f"\nscanned {len(jobs)} in {mins:.1f} min | detected {found} | "
          f"no usable text {thin}")
    print("distribution:", dict(counts.most_common(12)))
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
        if r.get("lang"):
            recs[r["id"]] = r["lang"]

    # Never overwrite, and never write to a book that has gone. Without this
    # the scan file rewrites its whole history on every run.
    with sqlite3.connect(f"file:{args.library_path}/metadata.db?mode=ro",
                         uri=True) as con:
        has = {r[0] for r in con.execute("SELECT book FROM books_languages_link")}
        alive = {r[0] for r in con.execute("SELECT id FROM books")}
    already = len(recs.keys() & has)
    gone = len(recs.keys() - alive)
    payload = {str(b): [c] for b, c in recs.items()
               if b not in has and b in alive}

    print(f"{len(payload)} languages to write "
          f"({already} already set, {gone} no longer in the library)")
    if not payload:
        return 0
    print("distribution:", dict(Counter(v[0] for v in payload.values()).most_common(12)))

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                     encoding="utf-8") as fh:
        json.dump({"library": args.library_path, "field": "languages",
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
    print("\n" + (line[-1] if line else r.stdout.strip()[-200:]))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--library-path", default=DEFAULT_CALIBRE_LIBRARY)
    args = ap.parse_args()
    if args.scan:
        return do_scan(args)
    if args.apply:
        return do_apply(args)
    ap.error("give --scan or --apply")


if __name__ == "__main__":
    sys.exit(main())
