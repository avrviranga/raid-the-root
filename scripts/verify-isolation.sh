#!/usr/bin/env bash
#
# RaidTheRoot (RTR) - isolation verification
# IT24102116 (Platform & Architecture)
#
# Self-developed verification tool. Executes test cases T-05 (network
# isolation) and T-06 (flag containment).
#
# Every check below is written as "this connection MUST fail". A reachable
# target is a FAIL, because it would mean a compromised challenge container
# can pivot to another stage or to the control plane.
#
# Usage: ./scripts/verify-isolation.sh

set -uo pipefail

PASS=0
FAIL=0

hdr()  { printf '\n\033[1;34m== %s\033[0m\n' "$*"; }
pass() { printf '  \033[0;32mPASS\033[0m  %s\n' "$*"; PASS=$((PASS+1)); }
fail() { printf '  \033[0;31mFAIL\033[0m  %s\n' "$*"; FAIL=$((FAIL+1)); }
note() { printf '  \033[0;33mSKIP\033[0m  %s\n' "$*"; }

running() { docker ps --format '{{.Names}}' | grep -qx "$1"; }

# Attempt a TCP connection FROM a container TO host:port.
# Uses bash /dev/tcp so no extra tooling is needed inside the image.
# Returns 0 if the connection succeeded (which, for isolation, is bad).
reaches() {
    local from="$1" host="$2" port="$3"
    docker exec "$from" timeout 3 bash -c \
        "exec 3<>/dev/tcp/${host}/${port}" >/dev/null 2>&1
}

must_not_reach() {
    local from="$1" host="$2" port="$3" label="$4"
    if reaches "$from" "$host" "$port"; then
        fail "$label  -- REACHABLE, isolation broken"
    else
        pass "$label  -- blocked"
    fi
}

echo "RaidTheRoot isolation verification"
echo "Run at: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"

# ---------------------------------------------------------------- T-05 ----
hdr "T-05  Network isolation"

if running rtr-stage6; then
    must_not_reach rtr-stage6 rtr-stage3 5000 "stage6 -> stage3 (other challenge)"
    must_not_reach rtr-stage6 rtr-ctfd   8000 "stage6 -> CTFd control plane"
    must_not_reach rtr-stage6 rtr-db     3306 "stage6 -> MariaDB (flag store)"
    must_not_reach rtr-stage6 rtr-cache  6379 "stage6 -> Redis"
    # Docker's default host gateway inside a bridge network.
    must_not_reach rtr-stage6 172.17.0.1 22  "stage6 -> host SSH"
else
    note "rtr-stage6 not running - Stage 6 checks skipped"
fi

if running rtr-stage3; then
    must_not_reach rtr-stage3 rtr-stage6 22   "stage3 -> stage6 (other challenge)"
    must_not_reach rtr-stage3 rtr-db     3306 "stage3 -> MariaDB (flag store)"
    must_not_reach rtr-stage3 rtr-ctfd   8000 "stage3 -> CTFd control plane"
else
    note "rtr-stage3 not running - Stage 3 checks skipped"
fi

# ---------------------------------------------------------------- T-06 ----
hdr "T-06  Flag containment"

# A fully compromised challenge box must expose ONLY its own flag.
check_flags() {
    local container="$1" allowed="$2"
    running "$container" || { note "$container not running"; return; }

    local found
    found=$(docker exec "$container" \
        grep -rIoh 'RTR{[a-zA-Z0-9_-]*}' / 2>/dev/null \
        | sort -u || true)

    if [[ -z "$found" ]]; then
        note "$container: no flag strings found on disk"
        return
    fi

    local leaked=0
    while read -r flag; do
        [[ -z "$flag" ]] && continue
        if [[ "$flag" == *"$allowed"* ]]; then
            pass "$container holds its own flag only: $flag"
        else
            fail "$container LEAKS another stage's flag: $flag"
            leaked=1
        fi
    done <<< "$found"
    [[ $leaked -eq 0 ]] || true
}

check_flags rtr-stage3 "back-door"
check_flags rtr-stage6 "find-the-ghost"

# ------------------------------------------------- privilege posture ------
hdr "Container privilege posture"

for c in rtr-stage3 rtr-stage6; do
    running "$c" || { note "$c not running"; continue; }

    priv=$(docker inspect -f '{{.HostConfig.Privileged}}' "$c")
    [[ "$priv" == "false" ]] \
        && pass "$c is unprivileged" \
        || fail "$c runs PRIVILEGED"

    mounts=$(docker inspect -f '{{len .Mounts}}' "$c")
    [[ "$mounts" == "0" ]] \
        && pass "$c has no host volume mounts" \
        || fail "$c has $mounts host mount(s)"

    mem=$(docker inspect -f '{{.HostConfig.Memory}}' "$c")
    [[ "$mem" != "0" ]] \
        && pass "$c memory limit set ($((mem/1024/1024))MB)" \
        || fail "$c has NO memory limit"
done

# ---------------------------------------------------------------- done ----
hdr "Result"
printf '  passed: %d   failed: %d\n\n' "$PASS" "$FAIL"
[[ $FAIL -eq 0 ]] || exit 1
