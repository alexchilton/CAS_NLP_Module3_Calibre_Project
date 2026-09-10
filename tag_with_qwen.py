#!/usr/bin/env python3
"""Assign subject tags to books that have none, using a local model.

Measured 2026-09-07: 17,093 books in this library carry no meaningful subject
tag -- their only tags are placeholders like "Needs Classification" (3,492),
"General" (4,262) or "unknown_source" (5,267). 16,019 of those already have a
description, so the model reads a field that is already in the database and
never opens a file. That is the whole point: no pdftotext, no EPUB unzip.

The vocabulary is CLOSED. The library already has 9,963 distinct tags, 7,958
of them used exactly once, so a model inventing tags freely would make
browsing worse, not better. It picks from the tags this library already uses
often, and anything it returns that is not on that list is discarded.

Two phases, so the slow part can run while calibre is open:

    python -u tag_with_qwen.py --suggest --limit 40      # read-only, resumable
    python -u tag_with_qwen.py --suggest --resume
    python -u tag_with_qwen.py --apply                   # write to calibre

CLOSE CALIBRE before --apply.
"""

import argparse
import json
import os
import re
import sqlite3
import tempfile
import subprocess
import sys
import time

import httpx

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from calibre_tools.config import DEFAULT_CALIBRE_LIBRARY  # noqa: E402

REPO = os.path.dirname(os.path.abspath(__file__))
OUT_FILE = os.path.join(REPO, "qwen-tags.jsonl")

OLLAMA = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
DEFAULT_MODEL = "qwen3-coder:30b-100k"

# A tag has to be in use this often before the model may assign it. Below
# this the tag is one person's passing thought, not a shelf.
MIN_TAG_USES = 50

# Tags that exist and are common but say nothing about the subject: import
# artefacts, workflow markers, publishers, platforms and content ratings.
# The model must not reach for these; several are what we are replacing.
NOT_SUBJECTS = {
    "unknown_source", "general", "unknown", "network import",
    "needs classification", "needs enrichment", "metadata-enriched",
    "metadata-unavailable", "sign in to", "ebook",
    "manning", "pragmatic bookshelf", "udemy", "the great courses",
    "chessbase", "chess training", "online course", "coursera",
    "tools", "applied", "advanced", "modern", "special interest",
    "research", "adult",
}

# Books whose only tags are these still count as unclassified.
PLACEHOLDERS = ("unknown_source", "General", "Unknown", "Network Import",
                "Needs Classification", "Needs Enrichment",
                "metadata-enriched", "metadata-unavailable")

# Enough of the description to classify from. Subject is clear in the first
# paragraph; the rest is detail that costs tokens on every call.
DESC_CHARS = 1200
BATCH = 5           # books per model call, so the vocabulary is sent once per 5
MAX_TAGS = 5

PROMPT = """You are classifying books for a library catalogue.

Choose subject tags for each book from THIS LIST ONLY:
{vocab}

Rules:
- Two to four tags per book. Never more than {max_tags}.
- Copy tags exactly as written above. Do not invent, translate or reword one.
- If nothing on the list fits a book, write NONE for it.
- Reply with one line per book, in the form:  <number>: <tag>, <tag>
- No other text, no explanation, no markdown.

{books}"""


def vocabulary(library_path):
    """The tags this library already uses often, minus the non-subjects."""
    with sqlite3.connect(f"file:{library_path}/metadata.db?mode=ro", uri=True) as con:
        rows = con.execute(
            "SELECT t.name, COUNT(*) c FROM tags t JOIN books_tags_link l ON l.tag=t.id "
            "GROUP BY t.id HAVING c >= ? ORDER BY c DESC", (MIN_TAG_USES,)).fetchall()
    return [name for name, _ in rows if name.strip().lower() not in NOT_SUBJECTS]


def candidates(library_path):
    """Books with no meaningful subject tag.

    A description is preferred but not required. 214 books had neither a
    description nor a tag and could never get one, because they are 200-byte
    placeholder files for Udemy, Pluralsight and chess video courses whose
    scrape returned nothing. Their titles are the course names -- "Golang for
    the Absolute Beginners Hands on Go Programming" -- which is ample to
    classify from. The model is told to answer NONE when it is not.
    """
    marks = ",".join("?" * len(PLACEHOLDERS))
    sql = f"""
        SELECT b.id, b.title,
               (SELECT a.name FROM authors a
                  JOIN books_authors_link ba ON ba.author = a.id
                 WHERE ba.book = b.id LIMIT 1),
               (SELECT c.text FROM comments c WHERE c.book = b.id)
        FROM books b
        WHERE NOT EXISTS (
              SELECT 1 FROM books_tags_link l JOIN tags t ON t.id = l.tag
               WHERE l.book = b.id AND t.name NOT IN ({marks}))
        ORDER BY b.id
    """
    with sqlite3.connect(f"file:{library_path}/metadata.db?mode=ro", uri=True) as con:
        return con.execute(sql, PLACEHOLDERS).fetchall()


def plain(html, limit=DESC_CHARS):
    text = re.sub(r"<[^>]+>", " ", html or "")
    text = re.sub(r"&[a-z]+;|&#\d+;", " ", text)
    return " ".join(text.split())[:limit]


def ask(client, model, vocab, batch):
    """Return {position: [tags]} for one batch of books."""
    lines = []
    for n, (_bid, title, author, desc) in enumerate(batch, 1):
        # A stub course entry has no description. Say so rather than printing
        # "Description: ", which reads like a truncation and invites the model
        # to invent one.
        body = plain(desc)
        lines.append(f"{n}. Title: {title}\n   Author: {author or 'unknown'}\n"
                     + (f"   Description: {body}" if body
                        else "   Description: (none - classify from the title)"))
    prompt = PROMPT.format(vocab="\n".join(vocab), max_tags=MAX_TAGS,
                           books="\n\n".join(lines))
    r = client.post(f"{OLLAMA}/api/chat", json={
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "think": False,
        "options": {"temperature": 0.1, "num_predict": 60 * len(batch) + 60},
    })
    r.raise_for_status()
    reply = r.json().get("message", {}).get("content", "")
    reply = re.sub(r"<think>.*?</think>", "", reply, flags=re.S | re.I)

    # Match tags case-insensitively but always store the library's spelling,
    # so a lowercase reply cannot fork "Python" into a second tag.
    canon = {t.lower(): t for t in vocab}
    out = {}
    for line in reply.splitlines():
        m = re.match(r"\s*\**\s*(\d+)\s*[:.)]\s*(.+)", line)
        if not m:
            continue
        pos = int(m.group(1))
        tags = []
        for piece in re.split(r"[,;]", m.group(2)):
            key = piece.strip().strip("*_`\"'").lower()
            if key in canon and canon[key] not in tags:
                tags.append(canon[key])
        out[pos] = tags[:MAX_TAGS]
    return out


def done_ids():
    seen = set()
    if os.path.exists(OUT_FILE):
        for line in open(OUT_FILE):
            try:
                seen.add(json.loads(line)["id"])
            except Exception:
                pass
    return seen


def do_suggest(args):
    vocab = vocabulary(args.library_path)
    jobs = candidates(args.library_path)
    if args.resume:
        already = done_ids()
        jobs = [j for j in jobs if j[0] not in already]
        print(f"resuming: {len(already)} already done")
    elif os.path.exists(OUT_FILE):
        print(f"{os.path.basename(OUT_FILE)} exists; pass --resume or delete it")
        return 1
    if args.limit:
        jobs = jobs[:args.limit]

    print(f"vocabulary: {len(vocab)} tags used {MIN_TAG_USES}+ times, "
          f"non-subjects removed")
    print(f"{len(jobs)} books to tag with {args.model}, {BATCH} per call")
    print(f"appending to {OUT_FILE}\n", flush=True)

    tagged = empty = errors = 0
    started = time.time()
    with open(OUT_FILE, "a") as out, httpx.Client(timeout=300) as client:
        for start in range(0, len(jobs), BATCH):
            batch = jobs[start:start + BATCH]
            try:
                answers = ask(client, args.model, vocab, batch)
            except Exception as exc:
                answers = {}
                err = type(exc).__name__
                print(f"  batch at {start}: {err}", file=sys.stderr, flush=True)
            else:
                err = None
            for n, (bid, title, _a, _d) in enumerate(batch, 1):
                tags = answers.get(n, [])
                rec = {"id": bid, "title": title, "tags": tags,
                       "error": err or (None if tags else "no usable tags")}
                out.write(json.dumps(rec) + "\n")
                if tags:
                    tagged += 1
                elif err:
                    errors += 1
                else:
                    empty += 1
                print(f"[{start + n}/{len(jobs)}] {bid} {title[:44]:46} "
                      f"{', '.join(tags) if tags else '-- ' + (err or 'no usable tags')}",
                      flush=True)
            out.flush()

    mins = (time.time() - started) / 60
    print(f"\n{len(jobs)} books in {mins:.1f} min | tagged {tagged} | "
          f"no usable tags {empty} | errors {errors}")
    print("run --apply to write them into calibre")
    return 0


def existing_tags(library_path):
    """Current tags per book, so applying adds rather than replaces."""
    with sqlite3.connect(f"file:{library_path}/metadata.db?mode=ro", uri=True) as con:
        rows = con.execute(
            "SELECT l.book, t.name FROM books_tags_link l "
            "JOIN tags t ON t.id = l.tag").fetchall()
    out = {}
    for bid, name in rows:
        out.setdefault(bid, []).append(name)
    return out


def do_apply(args):
    if not os.path.exists(OUT_FILE):
        print(f"no {os.path.basename(OUT_FILE)}; run --suggest first", file=sys.stderr)
        return 1
    recs = {}
    for line in open(OUT_FILE):
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("tags"):
            recs[r["id"]] = r["tags"]

    current = existing_tags(args.library_path)
    payload = {}
    skipped = 0
    for bid, tags in recs.items():
        # Keep everything the book already has. Removing a placeholder is a
        # deletion of your data, so this never does it.
        merged = list(current.get(bid, []))
        added = [t for t in tags if t not in merged]
        if not added:
            skipped += 1
            continue
        payload[str(bid)] = merged + added

    print(f"{len(payload)} books to write, {skipped} already had their tags")
    if not payload:
        return 0

    # One calibre process for the whole map, not one per book. Measured
    # 2026-09-07: calibredb set_metadata cost 3.1s a book, almost all of it
    # process startup and opening a 29,230-book library -- 10.6 hours for
    # 12,312 books. The same two books through here took 1.6s in total.
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                     encoding="utf-8") as fh:
        json.dump({"library": args.library_path, "field": "tags",
                   "values": payload}, fh)
        payload_path = fh.name
    try:
        r = subprocess.run(
            ["calibre-debug", "-e", os.path.join(REPO, "calibre_bulk_set.py"),
             payload_path],
            capture_output=True, text=True)
    finally:
        os.unlink(payload_path)

    if r.returncode != 0:
        print((r.stderr or r.stdout).strip()[-500:], file=sys.stderr)
        print("\nwritten 0 - bulk write failed", file=sys.stderr)
        return 1

    # The script prints one JSON line last; anything before it is calibre's
    # own chatter on startup.
    line = [ln for ln in r.stdout.strip().splitlines() if ln.startswith("{")]
    result = json.loads(line[-1]) if line else {}
    print(f"\nwritten {result.get('written', '?')}, "
          f"already had them {skipped}, "
          f"skipped as deleted {result.get('skipped_missing', 0)}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--suggest", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--library-path", default=DEFAULT_CALIBRE_LIBRARY)
    args = ap.parse_args()
    if args.suggest:
        return do_suggest(args)
    if args.apply:
        return do_apply(args)
    ap.error("give --suggest or --apply")


if __name__ == "__main__":
    sys.exit(main())
