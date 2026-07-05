#!/bin/bash
# watchdog.sh — alert if edgar-synth heartbeat goes stale (silent failure = missed filings).
# Cron (every 5 min, weekdays, market window):  */5 6-22 * * 1-5 /full/path/to/watchdog.sh
# NOTE: absolute paths everywhere — cron PATH is minimal (your morning-briefing lesson).

DIR="$(cd "$(dirname "$0")" && pwd)"
HEARTBEAT="$DIR/heartbeat"
MAX_AGE=180   # seconds; loop touches heartbeat every cycle

if [ ! -f "$HEARTBEAT" ]; then
    /usr/bin/osascript -e 'display notification "heartbeat file missing — watcher not running" with title "EDGAR-SYNTH DOWN" sound name "Basso"'
    exit 1
fi

NOW=$(/bin/date +%s)
MOD=$(/usr/bin/stat -f %m "$HEARTBEAT")
AGE=$((NOW - MOD))

if [ "$AGE" -gt "$MAX_AGE" ]; then
    /usr/bin/osascript -e "display notification \"heartbeat ${AGE}s stale — check edgar_synth.log\" with title \"EDGAR-SYNTH STALLED\" sound name \"Basso\""
    exit 1
fi
exit 0
