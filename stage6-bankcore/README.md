# Stage 6 — Find the Ghost (Linux / System Security) — Capstone

**Owner:** IT24101430 (Challenge Design B)
**Flag:** `RTR{find-the-ghost_root}`
**Target:** `ssh <user>@127.0.0.1 -p 2222`

## Build and run

```bash
docker compose up -d --build        # reads the foothold credential from ../.env
```

The container is `BANK-CORE-01`, isolated on its own `stage6-net`, publishing
only SSH on 2222.

## CRITICAL — credential synchronisation

The foothold account is created at runtime from `../.env`:

```
STAGE6_USER=svc_backup
STAGE6_PASSWORD=<agreed value>
```

This must be the **same value the Stage 5 capture embeds**, because the capture
is where the participant obtains it. Both read from the same `.env`, so they
stay in sync as long as the file is consistent. If `.env` changes, rebuild this
container *and* regenerate the Stage 5 capture.

The credential is created at runtime, not baked into the image, so it never
appears in the image layers.

## The planted vulnerability

A cron job runs a root-owned maintenance script every minute:

```
* * * * * root /opt/nexora/maintenance/rotate_logs.sh
```

The script itself is `root:root 755` — **the foothold user cannot edit it.**

The weakness is the *directory*. `/opt/nexora/maintenance` is
`svc_ghost:svc_ghost 775`, and the foothold account is a member of the
`svc_ghost` group. Directory write permits renaming the root-owned script
aside and dropping a replacement in its place. cron then executes the
replacement as root.

This is the key teaching point: the file was locked down, but the directory
was not, and on Linux write access to a directory is enough to replace the
files inside it. A common real-world misconfiguration.

## The escalation path

1. SSH in with the recovered credential.
2. `id` — note membership of the `svc_ghost` group.
3. `cat /etc/cron.d/nexora-maintenance` — a root task every minute.
4. `ls -la /opt/nexora/maintenance/` — script is root-owned and not writable.
5. `ls -lad /opt/nexora/maintenance` — the directory IS group-writable.
6. Rename the script aside, write a replacement that reads the root file.
7. Wait up to 60 s for cron.
8. Read the exfiltrated evidence → final flag.

`/opt/nexora/svc/notes.txt` is in-world scenery that points at the writable
directory, for participants who enumerate the filesystem first.

## The capstone reveal

`/root/ghost_identity.txt` (readable only as root) closes the investigation:
the `svc_ghost` account was created on 2026-09-14 02:58 UTC using
**RJewantha's** credentials — the same employee identified in Stage 1, whose
account was reset over the phone at 02:11 that morning. The 03:47 AM transfer
was the first time anyone noticed, not the attack itself.

The participant needs the Stage 1 answer to fully understand the ending, which
is what makes Stage 6 integrate the whole box.

## Solver

`solve.sh` automates the escalation. Member 3's capstone LO3 deliverable.
Run it **on the container** after logging in:

```bash
scp -P 2222 solve.sh <user>@127.0.0.1:/tmp/
ssh <user>@127.0.0.1 -p 2222
bash /tmp/solve.sh
```

## Why the flag proves genuine escalation

The evidence file is `root:root 600`. The foothold user cannot read it
directly. Possession of the flag is therefore proof that code ran as root —
the challenge cannot be shortcut by reading the file from the foothold account.
This is test case T-06.

## Container hardening

Unprivileged, `no-new-privileges`, all capabilities dropped and only the
minimum re-added for sshd and cron. No host volume mounts. 1 GB / 0.5 CPU.

Escalation to root happens *inside* the container by design — that is the
challenge. It does not grant host privilege: `scripts/verify-isolation.sh`
(T-05) confirms the container has no route off its own network, and the
dropped capabilities prevent container escape.

## Reset — rebuild, not restart

The intended solution overwrites a file inside the container, so a restart
would leave the box in a solved state.

```bash
../scripts/reset.sh stage6
```

This runs `down` then `up --force-recreate`, rebuilding from the clean image
and restoring the service account, cron job, directory permissions and
evidence file. Because there are no host volumes, nothing survives the
rebuild. This is test case T-07.
