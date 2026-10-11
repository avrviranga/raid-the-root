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

Docker is not a prerequisite you have to satisfy by hand — `bootstrap.sh`
installs it for you on a fresh Ubuntu or Kali machine (see below).

## Quick start — one command

From a clean clone, the whole box comes up with a single runner that lives in
the repository root:

```bash
git clone <repo-url> raidtheroot
cd raidtheroot

chmod +x run-all.sh
./run-all.sh
```

`run-all.sh` runs every setup step in order and shows a live progress bar:

1. **bootstrap** — install Docker, add you to the `docker` group, add the
   challenge hostnames to `/etc/hosts`
2. **deploy** — bring up the control plane and the Stage 3 / Stage 6 containers
3. **setup-ctfd** — import the six challenges into CTFd
4. **doctor** — fix hosts/scapy and health-check everything
5. **verify-isolation** — run the T-05 / T-06 security checks

If this is the first time Docker is installed on the machine, the runner will
add you to the `docker` group and then stop, because a new group only applies
to a fresh login shell. Activate it and re-run:

```bash
newgrp docker        # refreshes the current terminal
./run-all.sh         # pick up where it left off
```

## Manual setup (step by step)

If you prefer to run the stages yourself, the same steps are available
individually:

```bash
cp .env.template .env        # deploy.sh does this for you if .env is missing
# The template ships with working values; replace any CHANGE_ME if you want
# your own secrets.  Generate strong values with:  openssl rand -hex 24

./scripts/bootstrap.sh       # first run only: Docker, docker group, /etc/hosts
./scripts/deploy.sh          # control plane + live challenge stages
./scripts/setup-ctfd.sh      # import the six challenges (offline, no wizard)
./scripts/doctor.sh          # diagnose + auto-fix common first-run problems
```

If you ran `bootstrap.sh` and it added you to the `docker` group, run
`newgrp docker` (or log out and back in) once before `deploy.sh`.

The challenge hostnames must resolve to localhost. `bootstrap.sh` and
`doctor.sh` add these automatically; to do it by hand:

```
127.0.0.1   ctf.rtr.local
127.0.0.1   vault-03.rtr.local
```

- Linux/macOS: `/etc/hosts`
- Windows: `C:\Windows\System32\drivers\etc\hosts`

### CTFd import

`setup-ctfd.sh` imports the event **offline**, straight into the running CTFd
container (`docker exec … manage.py import_ctf`), so there is no setup wizard
to click through and no CSRF/403 problem. It creates all six challenges with
their flags, point values, progressive hints and — importantly — the
prerequisite chain that enforces stage order.

Log in afterwards with the admin account that ships inside the imported event,
then open <https://ctf.rtr.local>. The self-signed certificate will prompt a
browser warning; this is expected for a local lab.

If the offline import ever fails, the event can still be imported by hand:
`CTFd Admin Panel → Config → Backup → Import → ctfd-config/rtr-event-export.zip`.

## Access points

| What | Where |
|---|---|
| CTFd control plane | <https://ctf.rtr.local> |
| Stage 3 portal (VAULT-03) | <https://vault-03.rtr.local> |
| Stage 6 foothold (BANK-CORE-01) | `ssh svc_backup@10.10.30.11` |

Stage 6 runs on a static address, `10.10.30.11`, on its own isolated subnet, so
the IP recovered in Stage 5 is the real connection point. A localhost fallback
is also exposed for convenience:

```
ssh svc_backup@127.0.0.1 -p 2222
```

Stages 1, 2, 4 and 5 are static forensic artefacts downloaded from their CTFd
challenge pages once the preceding stage has been solved.

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

## Health check / troubleshooting

`doctor.sh` is safe to run at any time. It diagnoses — and, by default, fixes —
the common first-run problems, and reports everything in colour:

```bash
./scripts/doctor.sh          # diagnose + auto-fix
./scripts/doctor.sh --check  # diagnose only, change nothing
```

It checks Docker and the `docker` group, the `.env` file, the `/etc/hosts`
entries, the TLS certificate, every container, CTFd reachability, and that the
Stage 5 PCAP credential matches the Stage 6 container. It auto-installs `scapy`
if it is missing (needed to read the PCAP).

| Symptom | Fix |
|---|---|
| `permission denied` talking to Docker | `newgrp docker` (or log out/in) after bootstrap added you to the group |
| `502 Bad Gateway` on ctf.rtr.local | CTFd is still starting; wait ~30s or `docker compose restart rtr-ctfd` |
| Site won't resolve | hostnames missing from `/etc/hosts` — re-run `doctor.sh` |
| Stage 6 connection refused | rebuild the stage: `./scripts/reset.sh stage6` |
| PCAP / credential mismatch | `doctor.sh` reports it; regenerate with `(cd stage5-forensics && python3 generate.py)` |

## Architecture

```
participant ──HTTPS/443──> Nginx ──┬──> CTFd ──> MariaDB
                                   │      └────> Redis        [rtr-control]
                                   └──> Stage 3 portal        [stage3-net]

participant ──SSH/22─────────────> Stage 6 BANK-CORE-01       [stage6-net]
                                   (10.10.30.11, 2222 on localhost)
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
├── run-all.sh                one-command runner (bootstrap → verify)
├── docker-compose.yml        control plane: nginx, ctfd, mariadb, redis
├── .env.template             secret template (.env is untracked)
├── nginx/nginx.conf          reverse proxy, TLS, rate limiting
├── scripts/
│   ├── bootstrap.sh          first-run machine prep (Docker, group, hosts)
│   ├── deploy.sh             full deployment from clean state
│   ├── setup-ctfd.sh         offline import of the six challenges
│   ├── doctor.sh             diagnose + auto-fix + health check
│   ├── reset.sh              per-stage and full-box recovery
│   └── verify-isolation.sh   T-05 / T-06 verification
├── stage1-osint/             OSINT artefact set
├── stage2-stego/             carrier image + generator
├── stage3-webportal/         Flask portal (live)
├── stage4-crypto/            encrypted artefact + generator
├── stage5-forensics/         synthetic PCAP + Scapy generator
├── stage6-bankcore/          BANK-CORE-01 container (live)
├── ctfd-config/              CTFd event export
└── tests/                    test cases, chain_test.py, results, logs
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
