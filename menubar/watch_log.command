#!/bin/bash
# Tail today's daily-enrich log in a Terminal window. Read-only: starts nothing.

REPO="/Users/alexchilton/CAS_NLP_Module3_Calibre_Project"
LOG="$REPO/data/logs/daily-$(date +%Y%m%d).log"

printf '\033]0;calibre daily enrich - log\007'
if [ ! -f "$LOG" ]; then
    echo "no log for today yet: $LOG"
    printf '\nPress return to close. '
    read -r _
    exit 0
fi

echo "tailing $LOG"
echo "ctrl-c to stop"
echo "=================================================="
tail -n 40 -f "$LOG"