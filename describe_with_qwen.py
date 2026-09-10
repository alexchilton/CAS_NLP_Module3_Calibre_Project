#!/usr/bin/env python3
"""Write descriptions for books no catalogue has, using a local model.

Roughly 1,300 books in this library have no description and no recoverable
ISBN. They are chess course material, self-published study guides, lecture
notes and summaries -- Google Books and Open Library will never carry them.
The book's own front matter is the only source that exists, so a local model
reads that and writes the description.

The result is a summary, not a publisher blurb, so every generated
description carries a visible marker line. Find them later with the calibre
search:  comments:"generated from the book"

Two phases, so the slow part can run while calibre is open:

    python -u describe_with_qwen.py --generate            # read + model, resumable
    python -u describe_with_qwen.py --generate --resume
    python -u describe_with_qwen.py --apply               # write to calibre

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
import zipfile
from pathlib import Path

import httpx

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from calibre_tools.config import DEFAULT_CALIBRE_LIBRARY  # noqa: E402

REPO = Path(__file__).resolve().parent
OUT_FILE = REPO / "qwen-descriptions.jsonl"

OLLAMA = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
# Measured 2026-09-06: qwen3-coder:30b-100k took 8s a book against
# 38s for the dense qwen3.8:27b, at comparable quality. It is MoE,
# so only ~3B parameters activate per token.
DEFAULT_MODEL = "qwen3-coder:30b-100k"
PDFTOTEXT = "/opt/homebrew/bin/pdftotext"

# Kindle and scanned formats that no python library here can open. calibre
# converts all of them. Measured 2026-09-10: 58 books had a file and no
# description solely because it was one of these -- 20% of everything still
# undescribed. Conversion costs about 6 seconds a book against 0.1 for
# pdftotext, so these rank last and are only reached when nothing else exists.
EBOOK_CONVERT = "/Applications/calibre.app/Contents/MacOS/ebook-convert"
CONVERTIBLE = ("MOBI", "AZW3", "AZW", "DJVU", "LRF", "ORIGINAL_MOBI")

# Enough front matter to cover a title page, blurb, preface and contents,
# without feeding a whole book to the model.
PDF_PAGES = 14
MAX_CHARS = 9000
MIN_CHARS = 400        # below this there is nothing to summarise

MARKER = ("<p><em>Description generated from the book's own text by a local "
          "model, not from a publisher or catalogue.</em></p>")

PROMPT = """Below is the opening of a book: title page, preface, contents.

Write a description of this book for a library catalogue.

Rules:
- Three or four sentences. No more.
- Say what the book covers and who it is for.
- Plain prose. No markdown, no headings, no bullet points.
- Use only what the text supports. If it names a topic, say so; if it does
  not, do not invent one.
- Do not begin with "This book". Do not mention the extract or these rules.
- If the text is too damaged or sparse to describe, reply with exactly:
  INSUFFICIENT

--- book text ---
{text}
--- end ---"""


def pdf_text(path):
    r = subprocess.run([PDFTOTEXT, "-f", "1", "-l", str(PDF_PAGES), path, "-"],
                       capture_output=True, text=True, timeout=120)
    return r.stdout


def epub_text(path):
    parts = []
    with zipfile.ZipFile(path) as z:
        names = [n for n in z.namelist()
                 if n.lower().endswith((".xhtml", ".html", ".htm"))]
        for name in names[:25]:
            try:
                raw = z.read(name).decode("utf-8", "replace")
            except Exception:
                continue
            parts.append(re.sub(r"<[^>]+>", " ", raw))
            if sum(len(p) for p in parts) > MAX_CHARS:
                break
    return "\n".join(parts)


def txt_text(path):
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read(MAX_CHARS * 2)


def converted_text(path):
    """Let calibre open what we cannot, by converting to plain text.

    The whole book is converted, not just the front matter, because
    ebook-convert has no page range. Only the first slice is read back, which
    is the same front matter the other readers extract.
    """
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "out.txt")
        try:
            r = subprocess.run([EBOOK_CONVERT, path, out],
                               capture_output=True, timeout=300)
        except subprocess.TimeoutExpired:
            return ""
        if r.returncode != 0 or not os.path.isfile(out):
            return ""
        return txt_text(out)


def book_text(fmt, path):
    if not os.path.isfile(path):
        return ""
    if fmt == "PDF":
        raw = pdf_text(path)
    elif fmt in ("EPUB", "ORIGINAL_EPUB"):
        raw = epub_text(path)
    elif fmt == "TXT":
        raw = txt_text(path)
    elif fmt in CONVERTIBLE:
        raw = converted_text(path)
    else:
        return ""
    # Collapse the whitespace that PDF extraction leaves behind, so the
    # character budget carries words rather than blank space.
    return re.sub(r"[ \t]+", " ", re.sub(r"\n{3,}", "\n\n", raw)).strip()[:MAX_CHARS]


def clean(reply):
    """Strip reasoning blocks and markdown the model may add anyway."""
    reply = re.sub(r"<think>.*?</think>", "", reply, flags=re.S | re.I)
    reply = re.sub(r"^\s*(#+ .*|```.*)$", "", reply, flags=re.M)
    reply = re.sub(r"\*\*(.+?)\*\*", r"\1", reply)
    reply = " ".join(reply.split()).strip()
    # The model routinely writes a complete description and then appends the
    # refusal token anyway. Only a bare INSUFFICIENT is a refusal; a trailing
    # one is noise, and stripping it leaves the description intact. A reply
    # that was nothing but the token becomes empty, which the caller treats
    # as a refusal. Measured 2026-09-06: 5 of 15 sampled "declines" were
    # full descriptions with this token stuck on the end.
    reply = re.sub(r"\s*\bINSUFFICIENT\b[\s.]*$", "", reply).strip()
    # The model often writes a good description and then appends a remark
    # about the source: "Note: The text provided appears to be a partial
    # excerpt...". Measured 2026-09-10: 63 of 1,639 stored descriptions ended
    # that way. It is always trailing and always after a marker, so cutting at
    # the marker keeps the description and drops the commentary.
    # The marker must START a sentence. Without that, "musical notation and
    # the Note: symbol" would be cut in half.
    reply = re.split(r"(?:(?<=[.!?])\s+|\A|\n|---+\s*)(?:Note:|NB:|\(Note:)",
                     reply, maxsplit=1)[0]
    return reply.strip().rstrip("-—–").strip()


def describe(client, model, text, title, author):
    header = f"Catalogue title: {title}\nCatalogue author: {author or 'unknown'}\n\n"
    r = client.post(f"{OLLAMA}/api/chat", json={
        "model": model,
        "messages": [{"role": "user", "content": PROMPT.format(text=header + text)}],
        "stream": False,
        "think": False,
        "options": {"temperature": 0.3, "num_predict": 300},
    })
    r.raise_for_status()
    return clean(r.json().get("message", {}).get("content", ""))


def candidates(library_path):
    """Books with no description, best readable format each."""
    # Cheapest and cleanest reader first; the convertible formats cost about
    # 6 seconds each, so they are only used when a book has nothing else.
    order = {"EPUB": 0, "PDF": 1, "TXT": 2, "ORIGINAL_EPUB": 3,
             "AZW3": 4, "MOBI": 5, "AZW": 6, "ORIGINAL_MOBI": 7, "LRF": 8,
             "DJVU": 9}
    sql = """
        SELECT b.id, d.format, b.path, d.name, b.title,
               (SELECT a.name FROM authors a JOIN books_authors_link l
                ON l.author = a.id AND l.book = b.id LIMIT 1)
        FROM books b JOIN data d ON d.book = b.id
        WHERE NOT EXISTS (SELECT 1 FROM comments c
                          WHERE c.book = b.id AND TRIM(COALESCE(c.text,'')) <> '')
        -- Having an ISBN used to disqualify a book here, on the grounds that
        -- Google Books would carry a real publisher blurb for it. That has now
        -- been tested: three catalogue passes over 2,853 books, the last of
        -- them (2026-09-07) with the Google quota intact for 848 of 856 books,
        -- leaving 440 marked genuinely absent from both catalogues. An ISBN no
        -- longer predicts a blurb exists, so the book's own text is the only
        -- source left. Run this AFTER enrich_descriptions.py, never before.
    """
    best = {}
    with sqlite3.connect(f"file:{library_path}/metadata.db?mode=ro", uri=True) as con:
        for bid, fmt, path, name, title, author in con.execute(sql):
            if fmt not in order:
                continue
            rank = order[fmt]
            if bid not in best or rank < best[bid][0]:
                best[bid] = (rank, fmt,
                             f"{library_path}/{path}/{name}.{fmt.lower()}",
                             title, author)
    return [(b, f, p, t, a) for b, (_, f, p, t, a) in best.items()]


def done_ids():
    if not OUT_FILE.exists():
        return set()
    seen = set()
    for line in open(OUT_FILE):
        try:
            seen.add(json.loads(line)["id"])
        except Exception:
            continue
    return seen


def do_generate(args):
    jobs = candidates(args.library_path)
    if args.resume:
        already = done_ids()
        jobs = [j for j in jobs if j[0] not in already]
        print(f"resuming: {len(already)} already done")
    elif OUT_FILE.exists():
        print(f"{OUT_FILE.name} exists; pass --resume or delete it")
        return 1
    if args.limit:
        jobs = jobs[:args.limit]

    print(f"{len(jobs)} books to describe with {args.model}")
    print(f"appending to {OUT_FILE}\n", flush=True)

    written = thin = refused = errors = 0
    started = time.time()
    with open(OUT_FILE, "a") as out, httpx.Client(timeout=300) as client:
        for n, (bid, fmt, path, title, author) in enumerate(jobs, 1):
            rec = {"id": bid, "fmt": fmt, "title": title, "desc": None, "error": None}
            try:
                text = book_text(fmt, path)
                if len(text) < MIN_CHARS:
                    rec["error"] = "too little text"
                    thin += 1
                else:
                    desc = describe(client, args.model, text, title, author)
                    if not desc or len(desc) < 80:
                        rec["error"] = "model declined"
                        refused += 1
                    else:
                        rec["desc"] = desc
                        written += 1
            except Exception as exc:
                rec["error"] = f"{type(exc).__name__}"
                errors += 1
            out.write(json.dumps(rec) + "\n")
            out.flush()
            if rec["desc"]:
                print(f"[{n}/{len(jobs)}] {bid} {title[:44]}\n    {rec['desc'][:110]}...",
                      flush=True)
            else:
                print(f"[{n}/{len(jobs)}] {bid} {title[:44]}  -- {rec['error']}", flush=True)

    mins = (time.time() - started) / 60
    print(f"\n{len(jobs)} books in {mins:.1f} min | described {written} | "
          f"too little text {thin} | model declined {refused} | errors {errors}")
    print("run --apply to write them into calibre")
    return 0


def do_apply(args):
    if not OUT_FILE.exists():
        print(f"no {OUT_FILE.name}; run --generate first", file=sys.stderr)
        return 1
    recs = {}
    for line in open(OUT_FILE):
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("desc"):
            recs[r["id"]] = r["desc"]

    # The checkpoint file only grows, so without this every run rewrites every
    # description it has ever generated. Measured 2026-09-07: that was already
    # 1,089 redundant calibredb calls, ~20 minutes, and it gets worse daily.
    with sqlite3.connect(f"file:{args.library_path}/metadata.db?mode=ro", uri=True) as con:
        have = {r[0] for r in con.execute(
            "SELECT book FROM comments WHERE TRIM(COALESCE(text,'')) <> ''")}
        alive = {r[0] for r in con.execute("SELECT id FROM books")}
    skipped = len(recs.keys() & have)
    # A book deleted since its description was generated stays in the
    # checkpoint file forever, so without this it fails on every future run.
    # Book 36402 did exactly that, once a day, from 2026-09-07.
    gone = len(recs.keys() - have - alive)
    recs = {bid: d for bid, d in recs.items() if bid not in have and bid in alive}

    print(f"{len(recs)} generated descriptions to write "
          f"({skipped} already described, {gone} no longer in the library)")
    written = failed = 0
    for bid, desc in recs.items():
        html = f"<p>{desc}</p>\n{MARKER}"
        r = subprocess.run(
            ["calibredb", "set_metadata", "--library-path", args.library_path,
             "--field", f"comments:{html}", str(bid)],
            capture_output=True, text=True)
        if r.returncode == 0:
            written += 1
        else:
            failed += 1
            print(f"  {bid}: FAILED {(r.stderr or r.stdout).strip()[-80:]}",
                  file=sys.stderr)
        if (written + failed) % 50 == 0:
            print(f"  {written + failed}/{len(recs)}", flush=True)
    print(f"\nwritten {written}, failed {failed}")
    print('find them in calibre with:  comments:"generated from the book"')
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--generate", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--library-path", default=DEFAULT_CALIBRE_LIBRARY)
    args = ap.parse_args()
    if args.generate:
        return do_generate(args)
    if args.apply:
        return do_apply(args)
    ap.error("give --generate or --apply")


if __name__ == "__main__":
    sys.exit(main())
