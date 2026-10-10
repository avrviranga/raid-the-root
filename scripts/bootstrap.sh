#!/usr/bin/env bash
#
# RaidTheRoot (RTR) - first-run bootstrap
# Member 1 (Platform & Architecture)
#
# Prepares a fresh machine (Ubuntu / Kali) to run the box:
#   - makes all scripts executable
#   - adds the current user to the docker group (if needed)
#   - adds the challenge hostnames to /etc/hosts
#   - checks docker + compose are installed
#
# Run this ONCE on a new machine, before deploy.sh:
#   chmod +x scripts/bootstrap.sh && ./scripts/bootstrap.sh
#
# If it adds you to the docker group, you must log out and back in (or run
# 'newgrp docker') once - then run ./scripts/deploy.sh.

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

say()  { printf '\n\033[1;34m==>\033[0m %s\n' "$*"; }
ok()   { printf '    \033[0;32m[ok]\033[0m %s\n' "$*"; }
warn() { printf '    \033[0;33m[!]\033[0m %s\n' "$*"; }
act()  { printf '    \033[1;36m[action]\033[0m %s\n' "$*"; }

NEED_RELOGIN=0

# --- 1. scripts executable --------------------------------------------
say "Making scripts executable"
chmod +x scripts/*.sh 2>/dev/null
ok "scripts/*.sh are executable"

# --- 2. docker installed? ---------------------------------------------
say "Checking Docker"
if command -v docker >/dev/null; then
    ok "docker present ($(docker --version | awk '{print $3}' | tr -d ,))"
else
    warn "docker is NOT installed"
    act "install it, then re-run this script:"
    cat <<'EOF'
        # Ubuntu / Kali (Debian-based):
        sudo apt update
        sudo apt install -y docker.io docker-compose-plugin
        sudo systemctl enable --now docker
EOF
    exit 1
fi

if docker compose version >/dev/null 2>&1; then
    ok "compose v2 plugin present"
else
    warn "docker compose v2 plugin missing"
    act "sudo apt install -y docker-compose-plugin"
fi

# --- 3. docker group membership ---------------------------------------
say "Checking docker group access"
if docker ps >/dev/null 2>&1; then
    ok "can talk to docker daemon without sudo"
else
    warn "cannot reach the docker daemon (permission denied)"
    if id -nG "$USER" | grep -qw docker; then
        warn "you ARE in the docker group, but this shell predates it"
        act "run:  newgrp docker    (or log out and back in)"
        NEED_RELOGIN=1
    else
        act "adding $USER to the docker group (needs sudo)"
        if sudo usermod -aG docker "$USER"; then
            ok "added to docker group"
            NEED_RELOGIN=1
        else
            warn "could not modify the docker group - run manually:"
            act "sudo usermod -aG docker \$USER"
        fi
    fi
fi

# --- 4. /etc/hosts entries --------------------------------------------
say "Checking /etc/hosts"
HOSTS="ctf.rtr.local vault-03.rtr.local"
missing=""
for h in $HOSTS; do
    if grep -qE "^[^#]*\b${h//./\\.}\b" /etc/hosts 2>/dev/null; then
        ok "$h already mapped"
    else
        missing="$missing $h"
    fi
done
if [[ -n "$missing" ]]; then
    act "adding hostnames to /etc/hosts (needs sudo)"
    if echo "127.0.0.1 $HOSTS" | sudo tee -a /etc/hosts >/dev/null; then
        ok "added: 127.0.0.1 $HOSTS"
    else
        warn "could not write /etc/hosts - add manually:"
        act "echo '127.0.0.1 $HOSTS' | sudo tee -a /etc/hosts"
    fi
fi

# --- 5. next steps -----------------------------------------------------
say "Bootstrap complete"
if [[ "$NEED_RELOGIN" -eq 1 ]]; then
    cat <<'EOF'

  One more step: your docker group membership needs a fresh session.
  Run ONE of these:

      newgrp docker          # refreshes this terminal
      # or log out and back in, or reboot

  Then deploy:

      ./scripts/deploy.sh
      ./scripts/setup-ctfd.sh
      ./scripts/doctor.sh

EOF
else
    cat <<'EOF'

  Ready to deploy:

      ./scripts/deploy.sh
      ./scripts/setup-ctfd.sh
      ./scripts/doctor.sh

EOF
fi
