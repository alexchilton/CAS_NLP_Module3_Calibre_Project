#!/bin/bash
# Nightly metadata sweep over the calibre library.
#
# Every step is resumable and only touches books that still lack the thing it
# writes, so a normal day is a few minutes. The hours-long runs of 2026-09-06
# and 07 were a one-off backlog, not the steady state.
#
# The ORDER matters and is not arbitrary:
#   1. identifiers  - a book with an ISBN can be looked up
#   2. catalogues   - a real publisher blurb beats a generated one
#   3. the model    - only for what no catalogue carries
#   3b. repair      - adverts and template text the catalogues handed us
#   4. tags         - classified from the description step 2 and 3 wrote
#   5. search index - embeds the descriptions and tags the rest produced
#
# Writes need exclusive access to the library, which a running calibre GUI
# holds. If calibre is open the read-only phases still run and the write
# phases are skipped, so tomorrow picks them up from the same checkpoints.
# The index rebuild is exempt: it only reads.

set -uo pipefail

REPO="/Users/alexchilton/CAS_NLP_Module3_Calibre_Project"
PY="$REPO/venv/bin/python"
LOGDIR="$REPO/data/logs"
LOG="$LOGDIR/daily-$(date +%Y%m%d).log"
SUMMARY="$LOGDIR/daily-latest-summary.txt"

export PYTHONPATH="$REPO"
export PATH="/Applications/calibre.app/Contents/MacOS:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"

mkdir -p "$LOGDIR"
exec >>"$LOG" 2>&1

# A backlog run can outlast the day. Without this, tomorrow's launch starts a
# second copy that competes for the same GPU and appends to the same
# checkpoint files. mkdir is atomic, so it works as a lock; a stale one from a
# crash is cleared by checking whether the recorded pid is still alive.
LOCK="$LOGDIR/daily-enrich.lock"
if ! mkdir "$LOCK" 2>/dev/null; then
    if [ -f "$LOCK/pid" ] && kill -0 "$(cat "$LOCK/pid")" 2>/dev/null; then
        echo "$(date '+%Y-%m-%d %H:%M:%S') still running as pid $(cat "$LOCK/pid") - exiting"
        exit 0
    fi
    echo "$(date '+%Y-%m-%d %H:%M:%S') clearing stale lock"
    rm -rf "$LOCK" && mkdir "$LOCK" || exit 1
fi
echo $$ > "$LOCK/pid"
trap 'rm -rf "$LOCK"' EXIT

echo
echo "================================================================"
echo "daily enrich  $(date '+%Y-%m-%d %H:%M:%S')"
echo "================================================================"

calibre_open() {
    ps -eo args | grep -qE "calibre\.app/Contents/MacOS/calibre$"
}

if calibre_open; then
    WRITES=0
    echo "calibre is OPEN - read-only phases only, writes deferred to tomorrow"
else
    WRITES=1
fi

# Ollama serves the model. Without it the two model phases fail one book at a
# time and fill the log with the same error 500 times, so check once instead.
if curl -sf --max-time 5 "http://127.0.0.1:11434/api/tags" >/dev/null; then
    OLLAMA=1
else
    OLLAMA=0
    echo "ollama is NOT responding on 11434 - skipping the model phases"
fi

step() {          # step "name" command...
    local name="$1"; shift
    echo
    echo "--- $name  $(date '+%H:%M:%S')"
    "$@"
    local rc=$?
    echo "--- $name exit=$rc"
    return $rc
}

# 1. Identifiers ----------------------------------------------------------
if [ "$WRITES" = 1 ]; then
    step "isbn from title" "$PY" -u "$REPO/isbn_from_title.py" --apply
    step "isbn from content (scan)" "$PY" -u "$REPO/isbn_from_content.py" --scan --resume
    step "isbn from content (apply)" "$PY" -u "$REPO/isbn_from_content.py" --apply
else
    step "isbn from content (scan)" "$PY" -u "$REPO/isbn_from_content.py" --scan --resume
fi

# 2. Catalogues -----------------------------------------------------------
# Google's daily quota is the binding constraint. Run before anything else
# competes for it, and accept that a big backlog takes several days.
if [ "$WRITES" = 1 ]; then
    step "catalogue descriptions" "$PY" -u "$REPO/enrich_descriptions.py" --apply --delay 0.8
fi

# 3. Generated descriptions ----------------------------------------------
if [ "$OLLAMA" = 1 ]; then
    step "qwen descriptions (generate)" "$PY" -u "$REPO/describe_with_qwen.py" --generate --resume
    [ "$WRITES" = 1 ] && step "qwen descriptions (apply)" "$PY" -u "$REPO/describe_with_qwen.py" --apply
fi

# 3b. Repair what the catalogues wrote ------------------------------------
# Publisher adverts and template text arrive with new Manning and O'Reilly
# titles, so this is not a one-off. It runs before tags, because a book whose
# junk description is cleared here should not then be classified from it.
if [ "$WRITES" = 1 ]; then
    step "clean descriptions" "$PY" -u "$REPO/clean_descriptions.py" --apply
    step "clean author fields" "$PY" -u "$REPO/clean_author_fields.py" --apply
fi

# 4. Tags -----------------------------------------------------------------
if [ "$OLLAMA" = 1 ]; then
    step "qwen tags (suggest)" "$PY" -u "$REPO/tag_with_qwen.py" --suggest --resume
    [ "$WRITES" = 1 ] && step "qwen tags (apply)" "$PY" -u "$REPO/tag_with_qwen.py" --apply
fi

# 5. Semantic search index ------------------------------------------------
# Last, because it indexes the descriptions and tags the steps above write.
# Rebuilt in full rather than incrementally: 29,230 books took 0.8 minutes on
# MPS, which is cheaper than the bookkeeping to work out what changed.
# Always: this reads the library with calibredb list, which works while
# calibre is open, and embeds locally without ollama. Neither guard applies.
step "semantic index rebuild" env FORCE_REFRESH=1 "$PY" -u -c "
from calibre_tools.semantic_search import get_search_instance
get_search_instance()
print('index rebuilt')
"

# 6. Where the library stands --------------------------------------------
# Yesterday's numbers, kept before this run overwrites them, so the summary
# can say what MOVED rather than only where things stand. A standing total
# tells you nothing about whether the run did anything.
PREV="$LOGDIR/daily-prev-summary.txt"
[ -f "$SUMMARY" ] && cp "$SUMMARY" "$PREV"

DB="/Users/alexchilton/Calibre Library/metadata.db"
ND="NOT EXISTS (SELECT 1 FROM comments c WHERE c.book=b.id AND TRIM(COALESCE(c.text,''))<>'')"
{
    echo
    echo "--- library state  $(date '+%Y-%m-%d %H:%M:%S')"
    sqlite3 "file:$DB?mode=ro&immutable=1" "
      SELECT 'total books            ' || COUNT(*) FROM books;
      SELECT 'no description         ' || COUNT(*) FROM books b WHERE $ND;
      SELECT 'no isbn, no description' || ' ' || COUNT(*) FROM books b WHERE $ND
        AND NOT EXISTS (SELECT 1 FROM identifiers i WHERE i.book=b.id AND i.type='isbn');
      SELECT 'no tags at all         ' || COUNT(*) FROM books b
        WHERE NOT EXISTS (SELECT 1 FROM books_tags_link l WHERE l.book=b.id);
      SELECT 'added in last 24h      ' || COUNT(*) FROM books
        WHERE timestamp >= datetime('now','-1 day');
    " 2>&1 || echo "  (library locked - calibre is open)"
} | tee "$SUMMARY"

# 7. Say what moved -------------------------------------------------------
# The log is thousands of lines; nobody reads it. This is the part that gets
# looked at, so it reports change, failures and skips - not a wall of totals.
CHANGED=""
if [ -f "$PREV" ]; then
    CHANGED=$(awk '
        NR==FNR { if (match($0, /[0-9]+$/)) old[substr($0,1,RSTART-1)] = substr($0,RSTART); next }
        { if (match($0, /[0-9]+$/)) {
            k = substr($0,1,RSTART-1); v = substr($0,RSTART) + 0
            if (k in old && old[k] + 0 != v) {
                d = v - (old[k] + 0)
                printf "%s%s (%+d)\n", k, v, d
            }
          } }
    ' "$PREV" "$SUMMARY")
fi

FAILS=$(grep -c "exit=[1-9]" "$LOG")
# "failed 0" is a step reporting success. Count only a non-zero failure count
# or an actual per-book failure line, or every clean run reports write errors
# it did not have - which is what 2026-09-08 and 09-10 both did.
WRITE_ERRORS=$(grep -cE "WRITE FAILED|^ *[0-9]+: FAILED " "$LOG")

{
    echo
    echo "--- what moved today"
    if [ -n "$CHANGED" ]; then echo "$CHANGED"; else echo "  nothing changed"; fi
    [ "$WRITES" = 0 ] && echo "  WRITES SKIPPED - calibre was open"
    [ "$OLLAMA" = 0 ] && echo "  MODEL PHASES SKIPPED - ollama was down"
    [ "$FAILS" != 0 ] && echo "  $FAILS step(s) exited non-zero - see $LOG"
    [ "$WRITE_ERRORS" != 0 ] && echo "  $WRITE_ERRORS write error(s) - see $LOG"
} | tee -a "$SUMMARY"

# A log file nobody opens is not a report. This puts one line in front of you.
NOTE=$(printf "%s" "${CHANGED:-nothing changed}" | head -4 | tr '\n' ' ')
[ "$WRITES" = 0 ] && NOTE="calibre was open, writes deferred. $NOTE"
osascript -e "display notification \"${NOTE//\"/}\" with title \"calibre daily enrich\"" 2>/dev/null

echo
echo "daily enrich finished $(date '+%Y-%m-%d %H:%M:%S')"
