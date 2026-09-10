#!/usr/bin/env python3
"""Repair author fields that hold scrape artefacts instead of names.

Measured 2026-09-10 on a 29,268-book library: 2,459 books carry an author that
is mechanically, unambiguously not a name. The largest group by far is 2,077
books scraped from Udemy, filed under strings like

    Created byJose Portilla|Pierian Training
    Created byPaul Chin| PhD
    Created byPaulo Dichone | Software Engineer| AWS Cloud Practitioner

The instructor's name is right there. This needs no model: strip the glued-on
"Created by", split on the pipe, drop the parts that are job titles or
credentials, and keep what is left. Where only an organisation remains
("Created byPackt Publishing") the organisation is kept, because "Packt
Publishing" is still better than "Created byPackt Publishing".

The other groups are filenames (copyright-2023-manning-publications.html, 266
books), placeholders (AUTHOR NAMES HERE, 17), bare domains and strings with no
letters at all. Those hold no name to recover, so they are reset to Unknown --
which is what they mean, and which makes them visible to author_from_text.

Nothing that could be a real name is touched. "HELEN H. DURRANT" is shouty,
not wrong, and books with such authors are left exactly as they are.

    python -u clean_author_fields.py            # dry run
    python -u clean_author_fields.py --apply

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

# A part that ENDS in a role word is a job title, not a name. It has to be
# the ending, not a containment: "Paulo Dichone" must survive while
# "AWS Cloud Practitioner" must not, and both sit in the same byline.
ROLE_END = re.compile(
    r"\b(engineer|developer|architect|scientist|analyst|instructor|trainer|"
    r"consultant|coach|expert|practitioner|specialist|professional|"
    r"entrepreneur|founder|ceo|cto|mentor|educator|teacher)s?\s*$", re.I)
CREDENTIAL = re.compile(
    r"^\s*(ph\.?\s?d|m\.?sc|m\.?d|mba|b\.?sc|bs|ms|msee|pmp|cissp|pe|cpa|"
    r"prof(essor)?|dr)\.?\s*$", re.I)

# Words that make a part an organisation. Kept only when no person is present,
# because "Packt Publishing" beats "Created byPackt Publishing" but loses to a
# named instructor standing next to it.
ORG_WORD = re.compile(
    r"\b(inc|llc|ltd|limited|gmbh|corp|co|company|team|academy|training|"
    r"careers|publishing|publications|press|school|institute|university|"
    r"college|group|media|labs?|studios?|solutions|systems|technologies|"
    r"education|educational|learning|courses?|tutorials?|bridging)\b\.?",
    re.I)

# A value that cannot be repaired because it holds no name at all.
FILENAME = re.compile(r"\.(html?|pdf|epubs?|mobi|txt|azw3?)$", re.I)
DOMAIN = re.compile(r"^[\w-]+\.(im|com|net|org|io|co|de|ai)$", re.I)
PLACEHOLDERS = {"AUTHOR NAMES HERE", "AUTHOR NAME HERE", "N/A", "NONE",
                "NULL", "TBD", "UNTITLED"}

UNKNOWN = "Unknown"


def looks_like_person(part):
    """Two to four capitalised words, the shape of a name."""
    words = part.split()
    if not 1 < len(words) <= 4:
        return False
    return all(w[:1].isupper() or not w[:1].isalpha() for w in words)


def repair_created_by(value):
    """"Created byJose Portilla|Pierian Training" -> "Jose Portilla"."""
    body = re.sub(r"^\s*created\s*by\s*", "", value, flags=re.I)
    raw = [p.strip(" ,|") for p in body.split("|") if p.strip(" ,|")]
    parts = [p for p in raw
             if not CREDENTIAL.match(p) and not ROLE_END.search(p)]
    if not parts:
        # Every part reads as a role: "Created byIntellezy Trainers",
        # "Created byExperts". There is no name to find, but dropping the
        # glued-on prefix still leaves something a person can read.
        parts = raw[:1]
    if not parts:
        return None
    people = [p for p in parts
              if looks_like_person(p) and not ORG_WORD.search(p)]
    # Prefer the people. Fall back to whatever is left, which will be an
    # organisation -- still an improvement on the glued-together original.
    chosen = people or parts[:1]
    # De-duplicate while keeping order: several Udemy bylines repeat the team
    # name in two spellings.
    seen, out = set(), []
    for p in chosen:
        if p.lower() not in seen:
            seen.add(p.lower())
            out.append(p)
    return out[:4] or None


def classify(value):
    """Return (kind, new_value_list_or_None)."""
    s = (value or "").strip()
    if not s or s == UNKNOWN:
        return None, None
    if re.match(r"^\s*created\s*by", s, re.I):
        return "created-by", repair_created_by(s)
    if FILENAME.search(s):
        return "filename", [UNKNOWN]
    if s.upper() in PLACEHOLDERS:
        return "placeholder", [UNKNOWN]
    if DOMAIN.match(s):
        return "domain", [UNKNOWN]
    if not re.search(r"[A-Za-z]", s):
        return "no letters", [UNKNOWN]
    return None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--library-path", default=DEFAULT_CALIBRE_LIBRARY)
    args = ap.parse_args()

    with sqlite3.connect(f"file:{args.library_path}/metadata.db?mode=ro",
                         uri=True) as con:
        rows = con.execute(
            """SELECT ba.book, a.name FROM books_authors_link ba
               JOIN authors a ON a.id = ba.author""").fetchall()

    by_book = {}
    for bid, name in rows:
        by_book.setdefault(bid, []).append(name)

    payload, kinds, samples = {}, Counter(), {}
    for bid, names in by_book.items():
        new, changed = [], False
        for name in names:
            kind, repl = classify(name)
            if kind and repl:
                changed = True
                kinds[kind] += 1
                samples.setdefault(kind, [])
                if len(samples[kind]) < 3:
                    samples[kind].append((name, " & ".join(repl)))
                new.extend(repl)
            else:
                new.append(name)
        if not changed:
            continue
        # Drop Unknown if a real name survived alongside it.
        real = [n for n in new if n != UNKNOWN]
        final, seen = [], set()
        for n in (real or [UNKNOWN]):
            if n.lower() not in seen:
                seen.add(n.lower())
                final.append(n)
        if final != names:
            payload[str(bid)] = final

    print(f"{len(payload)} books with a repairable author field\n")
    for kind in kinds:
        print(f"  {kind:12} {kinds[kind]:5} values")
        for before, after in samples[kind]:
            print(f"      {before[:58]:60} ->  {after[:44]}")
    if not args.apply:
        print("\ndry run - nothing written. Add --apply.")
        return 0

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


if __name__ == "__main__":
    sys.exit(main())
