#!/bin/bash
# The Terminal-visible face of daily_enrich.sh.
#
# daily_enrich.sh redirects its own stdout into the dated log (exec >>"$LOG"),
# so running it in a Terminal window shows nothing at all. This starts it and
# tails that log alongside, so the window shows the run as it happens.

REPO="/Users/alexchilton/CAS_NLP_Module3_Calibre_Project"
LOGDIR="$REPO/data/logs"
LOG="$LOGDIR/daily-$(date +%Y%m%d).log"
SUMMARY="$LOGDIR/daily-latest-summary.txt"

mkdir -p "$LOGDIR"
touch "$LOG"

printf '\033]0;calibre daily enrich\007'
echo "=================================================="
echo "calibre daily enrich   $(date '+%Y-%m-%d %H:%M:%S')"
echo "log: $LOG"
echo "=================================================="
echo

# -n 0 so the window shows THIS run, not the whole day's backlog.
tail -f -n 0 "$LOG" &
TAILPID=$!

"$REPO/daily_enrich.sh"
RC=$?

sleep 1                      # let tail flush the last lines the script wrote
kill "$TAILPID" 2>/dev/null
wait "$TAILPID" 2>/dev/null

echo
echo "=================================================="
[ -f "$SUMMARY" ] && cat "$SUMMARY"
echo
echo "daily_enrich.sh exit=$RC"
echo "=================================================="
printf '\nPress return to close this window. '
read -r _