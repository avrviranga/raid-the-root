# RaidTheRoot (RTR) - Ghost of the Vault

A six-stage Capture The Flag Play Box simulating the investigation of an
insider-originated breach at Nexora Bank, a fictional digital bank.

IE3132 Penetration Testing — Assignment 02
Sri Lanka Institute of Information Technology

| Member | Student ID | Responsibility |
|---|---|---|
| Algiriya Vitharanage R.V. | IT24100446 | CTF Platform & Architecture |
| Jayashan D H J | IT24101430 | Challenge Design B (Stages 4-6) |
| Chandler S. R | IT24102116 | Integration, Testing & Documentation |
| Hansika H A S | IT24103666 | Challenge Design A (Stages 1-3) |

---

## Requirements

- Docker Engine 24.x with the Compose v2 plugin
- `openssl` (certificate generation)
- 4 vCPU / 8 GB RAM / 40 GB disk recommended
- Linux host (tested on Ubuntu 22.04 LTS and Kali 2026.x)

## Setup

```bash
git clone <repo-url> raidtheroot
cd raidtheroot

cp .env.template .env
# Edit .env and replace every CHANGE_ME value.
# Generate strong values with:  openssl rand -hex 24

./scripts/deploy.sh
```

Then add the challenge hostnames to your hosts file:

```
127.0.0.1   ctf.rtr.local
127.0.0.1   vault-03.rtr.local
```

- Linux/macOS: `/etc/hosts`
- Windows: `C:\Windows\System32\drivers\etc\hosts`

### First run

Open <https://ctf.rtr.local> and complete the CTFd setup wizard (the
self-signed certificate will prompt a browser warning — this is expected for
a local lab). Then import the event configuration:

```
CTFd Admin Panel → Config → Backup → Import
    ctfd-config/rtr-event-export.zip
```

This creates all six challenges with their flags, point values, progressive
hints and — importantly — the prerequisite chain that enforces stage order.

## Access points

| What | Where |
|---|---|
| CTFd control plane | <https://ctf.rtr.local> |
| Stage 3 portal (VAULT-03) | <https://vault-03.rtr.local> |
| Stage 6 foothold (BANK-CORE-01) | `ssh <STAGE6_USER>@127.0.0.1 -p 2222` |

Stages 1, 2, 4 and 5 are static forensic artefacts downloaded from their
CTFd challenge pages once the preceding stage has been solved.

## Reset and recovery

```bash
./scripts/reset.sh stage3      # restart the portal (non-destructive)
./scripts/reset.sh stage6      # REBUILD — required after any solve
./scripts/reset.sh all         # reset both live stages
./scripts/reset.sh platform    # full redeploy (destroys CTFd data)
```

Stage 6 must be **rebuilt**, not restarted: the intended solution overwrites a
scheduled script inside the container, so only a force-recreate restores the
planted service account, cron job, directory permissions and root-owned
evidence file.

Static stages (1, 2, 4, 5) are reset by re-uploading the master artefact from
this repository, or by re-running that stage's generator script — all
generators use fixed seeds and produce byte-identical output.

## Verifying isolation

```bash
./scripts/verify-isolation.sh
```

Executes test cases T-05 (network isolation) and T-06 (flag containment) and
reports pass/fail. Every check asserts that a connection **must fail**: a
reachable target means a compromised challenge could pivot to another stage or
to the control plane.

## Architecture

```
participant ──HTTPS/443──> Nginx ──┬──> CTFd ──> MariaDB
                                   │      └────> Redis        [rtr-control]
                                   └──> Stage 3 portal        [stage3-net]

participant ──SSH/2222───────────> Stage 6 BANK-CORE-01       [stage6-net]
```

One isolated bridge network per live challenge. Only Nginx spans more than one
network. Challenge containers have no route to each other or to the control
plane, so full compromise of Stage 6 — which is the intended outcome — yields
no other stage's flag and cannot reach the database where flags are stored.

Challenge containers run unprivileged, drop all Linux capabilities except the
minimum the intended escalation path requires, mount no host volumes, and
carry explicit CPU and memory limits.

## Repository layout

```
raidtheroot/
├── docker-compose.yml        control plane: nginx, ctfd, mariadb, redis
├── .env.template             secret template (.env is untracked)
├── nginx/nginx.conf          reverse proxy, TLS, rate limiting
├── scripts/
│   ├── deploy.sh             full deployment from clean state
│   ├── reset.sh              per-stage and full-box recovery
│   └── verify-isolation.sh   T-05 / T-06 verification
├── stage1-osint/             OSINT artefact set
├── stage2-stego/             carrier image + generator
├── stage3-webportal/         Flask portal (live)
├── stage4-crypto/            encrypted artefact + generator
├── stage5-forensics/         synthetic PCAP + Scapy generator
├── stage6-bankcore/          BANK-CORE-01 container (live)
├── ctfd-config/              CTFd event export
└── tests/                    test cases, results, logs
```

## Ethical scope

All targets are synthetic and were created by the group for this CTF. Scenario
personal data is fabricated; Nexora Bank does not correspond to any real
institution. No third-party production system, real personal data or
unauthorised target is involved. The box binds only to localhost and is not
reachable from any institutional network segment.

## Acknowledgements

CTFd · Docker · Nginx · MariaDB · Redis · Flask · Pillow · PyCryptodome ·
Scapy · Wireshark · CyberChef · OWASP Top 10 · MITRE ATT&CK
