#!/usr/bin/env bash
#
# RaidTheRoot (RTR) - first-run bootstrap
# Member 1 (Platform & Architecture)
#
# Prepares a fresh machine (Ubuntu / Kali) to run the box:
#   - installs Docker Engine + Compose if missing (official repo on Ubuntu)
#   - adds the current user to the docker group
#   - verifies docker works without sudo
#   - installs helper tools the solvers need (sshpass)
#   - adds the challenge hostnames to /etc/hosts
#   - makes all scripts executable
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

# --- helper: install Docker -------------------------------------------
install_docker() {
    # Detect the distribution.
    local id_like="" os_id=""
    if [[ -f /etc/os-release ]]; then
        # shellcheck disable=SC1091
        . /etc/os-release
        os_id="${ID:-}"; id_like="${ID_LIKE:-}"
    fi

    say "Installing Docker Engine"
    read -r -p "    This runs sudo apt operations. Continue? [y/N] " yn
    [[ "$yn" =~ ^[Yy]$ ]] || { warn "skipped Docker install"; return 1; }

    if [[ "$os_id" == "ubuntu" ]]; then
        # Official Docker CE repository for Ubuntu.
        act "adding Docker's official repository (Ubuntu)"
        sudo apt-get update -y
        sudo apt-get install -y ca-certificates curl
        sudo install -m 0755 -d /etc/apt/keyrings
        sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
            -o /etc/apt/keyrings/docker.asc
        sudo chmod a+r /etc/apt/keyrings/docker.asc
        sudo tee /etc/apt/sources.list.d/docker.sources >/dev/null <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
        sudo apt-get update -y
        sudo apt-get install -y docker-ce docker-ce-cli containerd.io \
            docker-buildx-plugin docker-compose-plugin
    else
        # Kali / Debian: the official CE repo has no matching suite, so use
        # the distribution's docker.io package plus the compose plugin.
        act "installing docker.io + compose plugin ($os_id / $id_like)"
        sudo apt-get update -y
        sudo apt-get install -y docker.io docker-compose-plugin || \
            sudo apt-get install -y docker.io docker-compose
    fi

    sudo systemctl enable --now docker 2>/dev/null || true
    command -v docker >/dev/null
}

# --- 2. docker installed? ---------------------------------------------
say "Checking Docker"
if command -v docker >/dev/null; then
    ok "docker present ($(docker --version | awk '{print $3}' | tr -d ,))"
else
    warn "docker is NOT installed"
    if install_docker && command -v docker >/dev/null; then
        ok "docker installed ($(docker --version | awk '{print $3}' | tr -d ,))"
    else
        warn "Docker is still not installed - install it manually, then re-run:"
        cat <<'EOF'
        # Ubuntu (official repo):
        sudo apt-get update && sudo apt-get install -y ca-certificates curl
        sudo install -m 0755 -d /etc/apt/keyrings
        sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
        sudo chmod a+r /etc/apt/keyrings/docker.asc
        echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" | sudo tee /etc/apt/sources.list.d/docker.list
        sudo apt-get update && sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

        # Kali / Debian:
        sudo apt-get update && sudo apt-get install -y docker.io docker-compose-plugin
        sudo systemctl enable --now docker
EOF
        exit 1
    fi
fi

# ensure the daemon is running
if ! sudo systemctl is-active --quiet docker 2>/dev/null; then
    act "starting the docker service"
    sudo systemctl enable --now docker 2>/dev/null || true
fi

if docker compose version >/dev/null 2>&1; then
    ok "compose v2 plugin present ($(docker compose version --short 2>/dev/null))"
else
    warn "docker compose v2 plugin missing"
    act "sudo apt-get install -y docker-compose-plugin"
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

# --- 4. verify docker works (the 'docker ps' test) --------------------
say "Verifying Docker access"
if docker ps >/dev/null 2>&1; then
    ok "docker ps works - no permission denied"
elif id -nG "$USER" | grep -qw docker; then
    warn "docker ps still fails in THIS shell (group not active yet)"
    act "run 'newgrp docker' or re-login, then: docker ps"
else
    warn "docker ps failed - see the docker group step above"
fi

# --- 5. helper tools (sshpass for the Stage 6 solver) -----------------
say "Checking helper tools"
if command -v sshpass >/dev/null; then
    ok "sshpass present"
else
    warn "sshpass not installed (Stage 6 solve.sh uses it for non-interactive SSH)"
    act "installing sshpass (needs sudo)"
    if sudo apt-get install -y sshpass >/dev/null 2>&1 && command -v sshpass >/dev/null; then
        ok "sshpass installed"
    else
        warn "could not auto-install sshpass - install it manually when needed:"
        act "sudo apt-get install -y sshpass"
        warn "(not fatal: solve.sh falls back to 'docker exec' if sshpass is absent)"
    fi
fi

# --- 6. /etc/hosts entries --------------------------------------------
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

# --- 7. next steps -----------------------------------------------------
say "Bootstrap complete"
if [[ "$NEED_RELOGIN" -eq 1 ]]; then
    cat <<'EOF'

  One more step: your docker group membership needs a fresh session.
  Run ONE of these:

      newgrp docker          # refreshes this terminal
      # or log out and back in, or reboot

  Confirm it worked:

      docker ps              # should run with no "permission denied"

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
