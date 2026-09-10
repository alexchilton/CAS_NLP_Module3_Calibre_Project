#!/usr/bin/env python3
"""Strip publisher adverts and model asides out of stored descriptions.

Measured 2026-09-10 on a 29,268-book library: 302 descriptions were shared by
1,261 books. Most of that sharing is correct -- 177 New Scientist issues and 98
Economist issues really do share a description of the publication. The rest was
not a description at all.

Two kinds of damage, and they need opposite treatment:

CLEAR -- the whole field is junk, so blanking it is an improvement, and the
rest of the pipeline will then fill it:

    "Stay ahead of what's next in tech with predictions from 1,500+ business
     leaders, insiders, and Pluralsight Authors."   (182 books, an advert
     filed as the description of Docker and Kubernetes titles)

    "BOOK MARKETING DESCRIPTION HERE. (This can be supplied by the author, but
     otherwise the Consumer Short Text from the Marketing tab in the PDB works
     here...)"                                       (16 books, a publisher's
     internal template, shipped as the blurb)

TRIM -- a real description with something stapled to it. Blanking these would
throw away good text:

    "...in-depth analysis and commentary on world events. This is a
     periodical/magazine issue and does not require metadata enrichment."
     (428 books: the first sentence describes the magazine, the second is the
     model talking about its own task)

    "Get the eBook free when you register your print book at Manning."
     as a leading line, with the real blurb underneath (6 books)

These arrive with every new Manning and O'Reilly title, so this runs in the
daily chain rather than being a one-off.

    python -u clean_descriptions.py            # dry run
    python -u clean_descriptions.py --apply

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
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from calibre_tools.config import DEFAULT_CALIBRE_LIBRARY  # noqa: E402

REPO = os.path.dirname(os.path.abspath(__file__))

# The whole field is one of these and nothing else. The length guard matters:
# some books quote the advert and then describe themselves properly, and those
# are trimmed below rather than cleared.
WHOLLY_JUNK = (
    "stay ahead of what",
    "book marketing description here",
)
JUNK_MAX_CHARS = 700

# An advert glued to the front of a real description.
LEADING_AD = re.compile(
    r"^\s*(?:<p>)?\s*Get the eBook free when you register your print book"
    r"[^.]*\.\s*(?:</p>)?\s*", re.I)

# The model commenting on its own task, always as a final sentence.
# The trailing tags matter: a description stored as "<p>...enrichment.</p>"
# ends with markup, not with the sentence, so anchoring on $ alone silently
# matches nothing. Closing tags are consumed and put back by the caller.
TRAILING_META = re.compile(
    r"(?:(?<=[.!?])\s+|\A)[^.!?<]*\b(?:does not require metadata|"
    r"no metadata (?:is )?required|not require metadata enrichment)\b"
    r"[^.!?<]*[.!?]?\s*(?P<tail>(?:</[a-z][^>]*>\s*)*)$", re.I)

# Below this a trimmed description is not worth keeping, so clear it instead
# and let the pipeline write a real one.
MIN_KEEP = 150


def plain(html):
    return " ".join(re.sub(r"<[^>]+>", " ", html or "").split())


def repair(html):
    """Return (action, new_value). action is 'clear', 'trim' or None."""
    body = plain(html)
    low = body.lower()
    if any(m in low for m in WHOLLY_JUNK) and len(body) < JUNK_MAX_CHARS:
        return "clear", ""

    new = LEADING_AD.sub("", html)
    new = TRAILING_META.sub(lambda m: m.group("tail"), new).strip()
    if new == (html or "").strip():
        return None, None
    return ("trim", new) if len(plain(new)) >= MIN_KEEP else ("clear", "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--library-path", default=DEFAULT_CALIBRE_LIBRARY)
    args = ap.parse_args()

    with sqlite3.connect(f"file:{args.library_path}/metadata.db?mode=ro",
                         uri=True) as con:
        rows = con.execute(
            "SELECT book, text FROM comments "
            "WHERE TRIM(COALESCE(text,'')) <> ''").fetchall()

    payload, kinds, samples = {}, Counter(), {}
    for bid, html in rows:
        action, new = repair(html)
        if not action:
            continue
        payload[str(bid)] = new
        kinds[action] += 1
        samples.setdefault(action, [])
        if len(samples[action]) < 2:
            samples[action].append((bid, plain(html)[:70],
                                    plain(new)[:70] or "(blank)"))

    print(f"{len(payload)} descriptions to repair "
          f"({kinds['clear']} cleared, {kinds['trim']} trimmed)")
    for action in samples:
        for bid, before, after in samples[action]:
            print(f"  {action:6} {bid}\n      {before}\n   -> {after}")
    if not payload:
        return 0
    if not args.apply:
        print("\ndry run - nothing written. Add --apply.")
        return 0

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                     encoding="utf-8") as fh:
        json.dump({"library": args.library_path, "field": "comments",
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


if __name__ == "__main__":
    sys.exit(main())
