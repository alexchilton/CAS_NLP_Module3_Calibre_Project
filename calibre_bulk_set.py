#!/usr/bin/env python
"""Set one metadata field on many books in a single library session.

Run under calibre's own interpreter, which is the only one that has these
imports:

    calibre-debug -e calibre_bulk_set.py <payload.json>

The payload is {"library": "...", "field": "tags", "values": {"123": [...]}}.

Why this exists: calibredb set_metadata boots a calibre process, opens the
library, writes one field and exits, once per book. Measured 2026-09-07 on a
29,230-book library, that is 3.1 seconds per book -- 10.6 hours for 12,312
books, and essentially all of it is startup. Cache.set_field takes the whole
map at once, so the library is opened once instead of 12,312 times.
"""

import json
import sys

from calibre.db.cache import Cache
from calibre.db.backend import DB


def main():
    if len(sys.argv) < 2:
        print("usage: calibre-debug -e calibre_bulk_set.py <payload.json>",
              file=sys.stderr)
        return 2

    with open(sys.argv[1], encoding="utf-8") as fh:
        payload = json.load(fh)

    library = payload["library"]
    field = payload["field"]
    # JSON object keys are strings; calibre keys books by int.
    values = {int(k): v for k, v in payload["values"].items()}

    cache = Cache(DB(library))
    cache.init()

    # A book deleted since the values were generated would abort the whole
    # write. Drop those instead, and say how many, rather than losing the run.
    known = cache.all_book_ids()
    missing = [bid for bid in values if bid not in known]
    for bid in missing:
        del values[bid]

    if field == "tags":
        values = {bid: tuple(v) for bid, v in values.items()}

    changed = cache.set_field(field, values)

    print(json.dumps({
        "requested": len(values) + len(missing),
        "written": len(changed),
        "skipped_missing": len(missing),
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
