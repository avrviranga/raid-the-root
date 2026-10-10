#!/usr/bin/env bash
#
# RaidTheRoot (RTR) - reset / recovery script
# IT24100446 (Platform & Architecture)
#
# Usage:
#   ./scripts/reset.sh stage3     restart the Stage 3 portal (non-destructive)
#   ./scripts/reset.sh stage6     REBUILD Stage 6 (required - solve is destructive)
#   ./scripts/reset.sh all        reset both live stages
#   ./scripts/reset.sh platform   full redeploy, DESTROYS CTFd data
#
# Static-artefact stages (1, 2, 4, 5) are reset by re-uploading the master
# artefact from the repository to the CTFd challenge entry, or by re-running
# that stage's generator script (fixed seeds produce byte-identical output).

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

say() { printf '\n\033[1;34m==>\033[0m %s\n' "$*"; }
ok()  { printf '    \033[0;32m[ok]\033[0m %s\n' "$*"; }

reset_stage3() {
    say "Resetting Stage 3 (The Back Door)"
    # The Flask app holds no persistent state and mounts no volumes, so a
    # restart fully restores the original condition.
    docker compose -f stage3-webportal/docker-compose.yml restart
    ok "stage3 restarted from clean image state"
}

reset_stage6() {
    say "Resetting Stage 6 (Find the Ghost)"
    # A rebuild is MANDATORY here: the intended solution modifies files inside
    # the container (the participant overwrites the scheduled script). Only a
    # force-recreate restores svc_ghost, the cron job, the directory
    # permissions and the root-owned evidence file to their declared state.
    docker compose -f stage6-bankcore/docker-compose.yml down
    docker compose -f stage6-bankcore/docker-compose.yml up -d --force-recreate --build
    ok "stage6 rebuilt from clean image"
}

reset_platform() {
    say "FULL PLATFORM RESET"
    printf '    This destroys the CTFd database (accounts, scores, submissions).\n'
    read -r -p '    Type YES to continue: ' confirm
    [[ "$confirm" == "YES" ]] || { echo "    aborted"; exit 1; }

    docker compose -f stage3-webportal/docker-compose.yml down 2>/dev/null || true
    docker compose -f stage6-bankcore/docker-compose.yml down 2>/dev/null || true
    docker compose down -v
    ok "all stacks and volumes removed"
    ./scripts/deploy.sh
}

case "${1:-}" in
    stage3)   reset_stage3 ;;
    stage6)   reset_stage6 ;;
    all)      reset_stage3; reset_stage6 ;;
    platform) reset_platform ;;
    *)
        cat <<EOF
Usage: $0 {stage3|stage6|all|platform}

  stage3     restart the Stage 3 portal        (fast, non-destructive)
  stage6     rebuild Stage 6 from clean image  (required after any solve)
  all        reset both live stages
  platform   full redeploy - DESTROYS CTFd data
EOF
        exit 1 ;;
esac
