#!/usr/bin/env bash
#
# RaidTheRoot (RTR) - deployment script
# IT24100446 (Platform & Architecture)
#
# Brings up the control plane and both live challenge stages from a clean
# state. Safe to re-run.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

say()  { printf '\n\033[1;34m==>\033[0m %s\n' "$*"; }
ok()   { printf '    \033[0;32m[ok]\033[0m %s\n' "$*"; }
die()  { printf '\n\033[0;31m[!]\033[0m %s\n' "$*" >&2; exit 1; }
warn() { printf '    \033[0;33m[!]\033[0m %s\n' "$*"; }

# --- 1. Preconditions --------------------------------------------------
say "Checking prerequisites"
command -v docker >/dev/null || die "docker not found"
docker compose version >/dev/null 2>&1 || die "docker compose v2 plugin not found"
ok "docker $(docker --version | awk '{print $3}' | tr -d ,)"

#[[ -f .env ]] || die ".env not found. Run: cp .env.template .env  then edit it."
# shellcheck disable=SC1091
if [[ ! -f .env ]]; then
    warn ".env not found - creating it from .env.template"
    cp .env.template .env
    ok ".env created from template"
fi
set -a; source .env; set +a
for var in DB_ROOT_PASSWORD DB_PASSWORD CTFD_SECRET_KEY STAGE6_PASSWORD; do
    [[ "${!var:-CHANGE_ME}" == "CHANGE_ME" || -z "${!var:-}" ]] \
        && die "$var is unset or still CHANGE_ME in .env"
done
ok ".env populated"

# --- 2. TLS certificate ------------------------------------------------
say "Ensuring TLS certificate"
if [[ ! -f nginx/certs/rtr.crt ]]; then
    mkdir -p nginx/certs
    openssl req -x509 -nodes -newkey rsa:2048 -days 365 \
        -keyout nginx/certs/rtr.key \
        -out    nginx/certs/rtr.crt \
        -subj "/C=LK/O=RaidTheRoot CTF/CN=ctf.rtr.local" \
        -addext "subjectAltName=DNS:ctf.rtr.local,DNS:vault-03.rtr.local" \
        2>/dev/null
    ok "self-signed certificate generated (365 days)"
else
    ok "certificate already present"
fi

# --- 3. Control plane --------------------------------------------------
say "Starting control plane (CTFd, MariaDB, Redis, Nginx)"
docker compose up -d
ok "control plane containers started"

printf '    waiting for CTFd'
for _ in $(seq 1 60); do
    if docker compose exec -T rtr-ctfd \
         python -c "import socket;socket.create_connection(('127.0.0.1',8000),1)" \
         >/dev/null 2>&1; then
        printf '\n'; ok "CTFd is listening"; break
    fi
    printf '.'; sleep 2
done

# --- 4. Live challenge stages -----------------------------------------
say "Starting live challenge stages"
for stage in stage3-webportal stage6-bankcore; do
    if [[ -f "$stage/docker-compose.yml" ]]; then
        docker compose -f "$stage/docker-compose.yml" up -d --build
        ok "$stage started"
    else
        printf '    \033[0;33m[skip]\033[0m %s not built yet\n' "$stage"
    fi
done

# --- 5. Summary --------------------------------------------------------
say "Deployment complete"
cat <<EOF

  Add these to your /etc/hosts (or C:\\Windows\\System32\\drivers\\etc\\hosts):

      127.0.0.1   ctf.rtr.local
      127.0.0.1   vault-03.rtr.local

  Control plane : https://ctf.rtr.local
  Stage 3 portal: https://vault-03.rtr.local
  Stage 6 SSH   : ssh ${STAGE6_USER}@127.0.0.1 -p 2222

  Next: run scripts/verify-isolation.sh to confirm segmentation holds.

EOF
docker compose ps
