#!/bin/bash
#
# Nexora Bank - log rotation helper
# Scheduled maintenance task. Runs as root.
#
# NOTE: this script is NOT writable by the service account. The weakness is
# the directory it sits in, not the file itself.

LOGDIR="/var/log/nexora"
STAMP=$(date -u '+%Y-%m-%dT%H:%M:%SZ')

echo "[$STAMP] rotation sweep" >> "$LOGDIR/maintenance.log"

find "$LOGDIR" -name '*.log' -size +10M -exec truncate -s 0 {} \; 2>/dev/null

exit 0
