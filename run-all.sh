#!/usr/bin/env bash
#
# RaidTheRoot (RTR) - one-shot runner
# IT24100446 (Platform & Architecture)
#
# Lives in the REPOSITORY ROOT (raid-the-root/), NOT in scripts/.
# Runs the whole setup in order, with a live status bar:
#
#   1. bootstrap        - install Docker, docker group, /etc/hosts
#   2. deploy           - control plane + Stage 3 / Stage 6 containers
#   3. setup-ctfd       - import the six challenges into CTFd
#   4. doctor           - fix hosts/scapy, health-check everything
#   5. verify-isolation - T-05 / T-06 security checks
#
# Usage (from the repo root):
#   chmod +x run-all.sh && ./run-all.sh

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

# --- colours (ANSI-C quoting so they print directly) ------------------
C_RESET=$'\033[0m'
C_CYAN=$'\033[1;36m'
C_BLUE=$'\033[1;34m'
C_RED=$'\033[1;31m'
C_GRN=$'\033[1;32m'
C_YEL=$'\033[1;33m'
C_DIM=$'\033[2m'
C_BLINK=$'\033[5m'

TOTAL=5

ok()   { printf '   %s[ok]%s %s\n'  "$C_GRN" "$C_RESET" "$*"; }
warn() { printf '   %s[!]%s %s\n'   "$C_YEL" "$C_RESET" "$*"; }
die()  { printf '\n%s[x]%s %s\n'    "$C_RED" "$C_RESET" "$*" >&2; exit 1; }

# --- RaidTheRoot banner + blinking status ------------------------------
banner() {
    printf '%s' "$C_CYAN"
    cat <<'LOGO'

   ██████╗ ████████╗██████╗
   ██╔══██╗╚══██╔══╝██╔══██╗
   ██████╔╝   ██║   ██████╔╝
   ██╔══██╗   ██║   ██╔══██╗
   ██║  ██║   ██║   ██║  ██║
   ╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝
LOGO
    printf '%s' "$C_RESET"
    printf '   %sRaidTheRoot%s  %s//%s  Ghost of the Vault\n' \
        "$C_CYAN" "$C_RESET" "$C_DIM" "$C_RESET"
    printf '   %s%s● THREAT ACTIVE%s   %stracing the Ghost ...%s\n\n' \
        "$C_RED" "$C_BLINK" "$C_RESET" "$C_DIM" "$C_RESET"
}

# --- status bar for step N of TOTAL ------------------------------------
status_bar() {
    local step="$1" label="$2"
    local width=28
    local filled=$(( step * width / TOTAL ))
    local empty=$(( width - filled ))
    local bar=""
    local i
    for (( i=0; i<filled; i++ )); do bar+="█"; done
    for (( i=0; i<empty;  i++ )); do bar+="░"; done
    local pct=$(( step * 100 / TOTAL ))

    printf '\n%s┌─ STEP %d/%d ─ %s%s\n' "$C_BLUE" "$step" "$TOTAL" "$label" "$C_RESET"
    printf '%s│%s %s%s%s %3d%%  (%d/%d)\n' \
        "$C_BLUE" "$C_RESET" "$C_CYAN" "$bar" "$C_RESET" "$pct" "$step" "$TOTAL"
    printf '%s└%s\n' "$C_BLUE" "$C_RESET"
}

# ======================================================================
clear 2>/dev/null || true
banner

[[ -d scripts ]] || die "run this from the repo root - scripts/ not found here"
chmod +x scripts/*.sh 2>/dev/null

# ------------------------------------------------- 1. bootstrap -------
status_bar 1 "bootstrap  (Docker, docker group, hosts)"
./scripts/bootstrap.sh

if ! docker ps >/dev/null 2>&1; then
    warn "the docker group is not active in this shell yet"
    printf '\n   Activate it, then re-run %s./run-all.sh%s:\n\n' "$C_CYAN" "$C_RESET"
    printf '       %snewgrp docker%s     # refreshes this terminal\n' "$C_GRN" "$C_RESET"
    printf '       # or log out and back in, or reboot\n\n'
    exit 0
fi
ok "docker is reachable - continuing"

# ------------------------------------------------- 2. deploy ---------
status_bar 2 "deploy  (control plane + challenge stages)"
./scripts/deploy.sh || die "deploy failed - fix the error above and re-run"

# ------------------------------------------------- 3. setup-ctfd -----
status_bar 3 "setup-ctfd  (import the six challenges)"
if ./scripts/setup-ctfd.sh; then
    ok "challenges imported"
else
    warn "setup-ctfd failed - use the manual browser import (README Path B)"
fi

# ------------------------------------------------- 4. doctor --------
status_bar 4 "doctor  (hosts, scapy, health checks)"
./scripts/doctor.sh || true

# ------------------------------------------------- 5. isolation -----
status_bar 5 "verify-isolation  (T-05 / T-06 security checks)"
if ./scripts/verify-isolation.sh; then
    ok "isolation verified"
else
    warn "isolation checks reported a failure - review the output above"
fi

# ------------------------------------------------- done -------------
printf '\n%s%s' "$C_GRN" "$C_BLINK"
printf '   ●●●  RAIDTHEROOT IS LIVE  ●●●'
printf '%s\n\n' "$C_RESET"

printf '   Open   %shttps://ctf.rtr.local%s   (accept the self-signed cert)\n' "$C_CYAN" "$C_RESET"
printf '   Log in with the admin account from the imported event.\n\n'
printf '   Stage 3 portal : %shttps://vault-03.rtr.local%s\n' "$C_CYAN" "$C_RESET"
printf '   Stage 6 SSH    : %sssh svc_backup@10.10.30.11%s   (or 127.0.0.1 -p 2222)\n\n' "$C_CYAN" "$C_RESET"
