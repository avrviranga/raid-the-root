#!/usr/bin/env bash
#
# RaidTheRoot (RTR) - setup helper & doctor
# IT24100446 (Platform & Architecture)
#
# Handles the machine-specific setup the deploy script cannot (the /etc/hosts
# entry), and diagnoses the common first-run problems. Safe to run repeatedly.
#
# Usage:
#   ./scripts/doctor.sh          # diagnose + auto-fix what it safely can
#   ./scripts/doctor.sh --check  # diagnose only, change nothing

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

CHECK_ONLY=0
[[ "${1:-}" == "--check" ]] && CHECK_ONLY=1

ok()   { printf '  \033[0;32m[ok]\033[0m   %s\n' "$*"; }
warn() { printf '  \033[0;33m[warn]\033[0m %s\n' "$*"; }
bad()  { printf '  \033[0;31m[fail]\033[0m %s\n' "$*"; }
fix()  { printf '  \033[1;34m[fix]\033[0m  %s\n' "$*"; }
hdr()  { printf '\n\033[1m== %s\033[0m\n' "$*"; }

HOSTS="ctf.rtr.local vault-03.rtr.local"

# ---------------------------------------------------------------- docker
hdr "Docker"
if command -v docker >/dev/null; then
    ok "docker present ($(docker --version | awk '{print $3}' | tr -d ,))"
else
    bad "docker not installed - install Docker Engine + compose plugin"
fi
if docker compose version >/dev/null 2>&1; then
    ok "compose v2 plugin present"
else
    bad "docker compose v2 plugin missing"
fi
if docker ps >/dev/null 2>&1; then
    ok "docker daemon reachable without sudo"
else
    warn "cannot talk to docker daemon - add yourself to the docker group:"
    fix "sudo usermod -aG docker \$USER   then log out/in (or: newgrp docker)"
fi

# ---------------------------------------------------------------- .env
hdr ".env"
if [[ -f .env ]]; then
    ok ".env present"
    if grep -q "CHANGE_ME" .env; then
        bad ".env still contains CHANGE_ME placeholders"
        fix "edit .env and set real values (see .env.template)"
    else
        ok "no CHANGE_ME placeholders"
    fi
else
    warn ".env missing"
    if [[ "$CHECK_ONLY" -eq 0 && -f .env.template ]]; then
        cp .env.template .env
        fix "created .env from .env.template"
        grep -q "CHANGE_ME" .env && bad "...but it has CHANGE_ME - edit it before deploying"
    else
        fix "run: cp .env.template .env   then edit it"
    fi
fi

# ---------------------------------------------------------------- hosts
hdr "/etc/hosts name resolution"
missing=""
for h in $HOSTS; do
    if grep -qE "^[^#]*\b${h//./\\.}\b" /etc/hosts 2>/dev/null; then
        ok "$h is mapped"
    else
        warn "$h not in /etc/hosts"
        missing="$missing $h"
    fi
done
if [[ -n "$missing" ]]; then
    if [[ "$CHECK_ONLY" -eq 0 ]]; then
        line="127.0.0.1  $HOSTS"
        if echo "$line" | sudo tee -a /etc/hosts >/dev/null 2>&1; then
            fix "added: $line"
        else
            bad "could not write /etc/hosts (need sudo)"
            fix "run manually: echo '$line' | sudo tee -a /etc/hosts"
        fi
    else
        fix "add: echo '127.0.0.1  $HOSTS' | sudo tee -a /etc/hosts"
    fi
fi

# ---------------------------------------------------------------- certs
hdr "TLS certificate"
if [[ -f nginx/certs/rtr.crt && -f nginx/certs/rtr.key ]]; then
    ok "certificate present"
else
    warn "certificate missing - deploy.sh generates it on next run"
fi

# ---------------------------------------------------------------- containers
hdr "Containers"
need="rtr-ctfd rtr-db rtr-cache rtr-proxy"
up=0
for c in $need; do
    if docker ps --format '{{.Names}}' 2>/dev/null | grep -qx "$c"; then
        ok "$c running"; up=$((up+1))
    else
        warn "$c not running"
    fi
done
for c in rtr-stage3 rtr-stage6; do
    if docker ps --format '{{.Names}}' 2>/dev/null | grep -qx "$c"; then
        ok "$c running"
    else
        warn "$c not running (challenge stage)"
    fi
done
if [[ "$up" -lt 4 ]]; then
    fix "bring the stack up: ./scripts/deploy.sh"
fi

# ---------------------------------------------------------------- reachability
hdr "CTFd reachability"
if command -v curl >/dev/null; then
    code="$(curl -sko /dev/null -w '%{http_code}' --connect-timeout 5 https://ctf.rtr.local/ 2>/dev/null || echo 000)"
    case "$code" in
        200|302) ok "https://ctf.rtr.local responds ($code)";;
        502)     bad "502 Bad Gateway - CTFd container up but not answering yet"
                 fix "wait 30s, or: docker compose restart rtr-ctfd";;
        000)     bad "no response - containers down, or hosts entry missing"
                 fix "check the Containers and /etc/hosts sections above";;
        *)       warn "unexpected HTTP $code";;
    esac
else
    warn "curl not installed - cannot test reachability"
fi

# ---------------------------------------------------------------- stage5/6 sync
hdr "Stage 5 / Stage 6 credential sync"
pcap="stage5-forensics/capture_10.10.20.50.pcap"
if [[ -f "$pcap" && -f .env ]] && command -v python3 >/dev/null; then
    env_pass="$(grep -E '^STAGE6_PASSWORD=' .env | cut -d= -f2-)"
    pcap_pass="$(python3 - "$pcap" <<'PY' 2>/dev/null
import sys,base64,json,re
try:
    from scapy.all import rdpcap, IP, TCP, Raw
except Exception:
    sys.exit(0)
pkts=rdpcap(sys.argv[1]); s={}
for p in pkts:
    if IP in p and TCP in p and Raw in p and 4444 in (p[TCP].sport,p[TCP].dport):
        k=(p[IP].src,p[TCP].sport); s[k]=s.get(k,b'')+bytes(p[Raw].load)
for d in s.values():
    t=d.decode('utf-8','replace')
    if '\r\n\r\n' in t:
        b=re.sub(r'\s+','',t.split('\r\n\r\n',1)[1])
        try: print(json.loads(base64.b64decode(b))['svc_pass']); break
        except Exception: pass
PY
)"
    if [[ -z "$pcap_pass" ]]; then
        warn "could not read PCAP password (scapy missing?) - skipping"
    elif [[ "$env_pass" == "$pcap_pass" ]]; then
        ok "PCAP credential matches .env"
    else
        bad "MISMATCH: .env has '$env_pass' but PCAP has '$pcap_pass'"
        fix "regenerate the PCAP so it matches, then re-upload to CTFd:"
        fix "  (cd stage5-forensics && python3 generate.py)"
    fi
else
    warn "cannot check (missing pcap, .env, or python3)"
fi

# ---------------------------------------------------------------- summary
hdr "Done"
if [[ "$CHECK_ONLY" -eq 1 ]]; then
    echo "  diagnosis only - re-run without --check to auto-fix hosts and .env"
else
    echo "  re-run ./scripts/doctor.sh after deploy.sh to confirm everything is green"
fi
