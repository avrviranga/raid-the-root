#!/usr/bin/env bash
#
# RaidTheRoot (RTR) - automated CTFd event import
# IT24100446 (Platform & Architecture)
#
# Optional convenience script. Runs AFTER deploy.sh.
#
#
# Usage:
#   ./scripts/setup-ctfd.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

say()  { printf '\n\033[1;34m==>\033[0m %s\n' "$*"; }
ok()   { printf '    \033[0;32m[ok]\033[0m %s\n' "$*"; }
warn() { printf '    \033[0;33m[!]\033[0m %s\n' "$*"; }
die()  { printf '\n\033[0;31m[x]\033[0m %s\n' "$*" >&2; exit 1; }

CONTAINER="rtr-ctfd"
EXPORT_ZIP="ctfd-config/rtr-event-export.zip"
CTF_URL="https://ctf.rtr.local"

# --- preconditions -----------------------------------------------------
command -v docker >/dev/null || die "docker not found"
docker ps --format '{{.Names}}' | grep -qx "$CONTAINER" \
    || die "$CONTAINER is not running - run ./scripts/deploy.sh first"
[[ -f "$EXPORT_ZIP" ]] \
    || die "$EXPORT_ZIP not found - export the event from CTFd first"

# --- wait for CTFd to be ready ----------------------------------------
say "Waiting for CTFd to be ready"
for _ in $(seq 1 30); do
    if docker exec "$CONTAINER" \
         python -c "import socket;socket.create_connection(('127.0.0.1',8000),1)" \
         >/dev/null 2>&1; then
        ok "CTFd is up"; break
    fi
    sleep 2
done

# --- copy the export into the container -------------------------------
say "Copying export into the container"
docker cp "$EXPORT_ZIP" "$CONTAINER:/tmp/rtr-event-export.zip"
ok "copied to /tmp/rtr-event-export.zip"

# --- import via CTFd's own manage command -----------------------------
say "Importing event (this wipes and restores the CTFd database)"
if docker exec -w /opt/CTFd "$CONTAINER" \
     python manage.py import_ctf /tmp/rtr-event-export.zip 2>&1 | tee /tmp/rtr_import.log
then
    ok "import command completed"
else
    warn "import_ctf reported an error (see above)"
    warn "fall back to the manual browser import - see README Path B"
    exit 1
fi

# CTFd caches in Redis; restart the app so the restored data is served clean.
say "Restarting CTFd to clear cache"
docker restart "$CONTAINER" >/dev/null
for _ in $(seq 1 30); do
    if docker exec "$CONTAINER" \
         python -c "import socket;socket.create_connection(('127.0.0.1',8000),1)" \
         >/dev/null 2>&1; then
        ok "CTFd back up"; break
    fi
    sleep 2
done

# --- verify ------------------------------------------------------------
say "Verifying"
count="$(docker exec "$CONTAINER" python -c "
from CTFd import create_app
app = create_app()
with app.app_context():
    from CTFd.models import Challenges
    print(Challenges.query.count())
" 2>/dev/null | tail -1 || echo 0)"

if [[ "${count:-0}" -ge 6 ]]; then
    ok "$count challenges present"
    say "Done - event imported"
    echo "    Open $CTF_URL"
    echo "    Log in with the ADMIN account from the exported event"
    echo "    (the credentials used when the box was first built, NOT .env)"
else
    warn "expected >= 6 challenges, found ${count:-unknown}"
    warn "verify in the admin panel, or use the manual browser import"
fi
