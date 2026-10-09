# Stage 2 — The Ghost File (Steganography)

**Owner:** IT24103666 (Challenge Design A)
**Flag:** `RTR{ghost-file_vault03}`

## Files

| File | Role |
|---|---|
| `generate.py` | Builds the carrier image. Deterministic — this *is* the reset mechanism. |
| `solve.py` | Self-developed LSB extractor (Member 2's LO3 deliverable) |
| `RJewantha_backup.png` | The artefact uploaded to CTFd |

```bash
pip install pillow
python3 generate.py               # rebuild the artefact
python3 solve.py RJewantha_backup.png   # extract the payload
```

Expected SHA-256: `59a67f51119964b0944738f72d56150987560ec63b2335b04ff38e8d333f3dd9`

## Dependency on Stage 1

The filename encodes the Stage 1 answer. A participant who has not solved
Stage 1 does not know which file to request from the index, so possession of
the previous artefact — not just its flag string — is required to begin.

**If the Stage 1 username ever changes, rename this file to match.**

## How the concealment works

The payload is written into the least significant bit of each colour channel,
row-major, R then G then B. That is the layout `zsteg` reports as
`b1,rgb,lsb,xy` — the first thing any solver tries — so the stage is solvable
with standard tooling while `solve.py` shows the extraction written out
manually.

Changing the LSB of a channel shifts its value by at most 1/255, which is
invisible. The carrier renders as an ordinary scanned Treasury statement.

Payload:

```
You are looking in the wrong place.
SERVER: VAULT-03
RTR{ghost-file_vault03}
```

Terminated with four null bytes so the extractor knows where to stop.

## The decoy

PNG text chunks carry plausible scanner metadata, including:

```
Source: ARCHIVE-07
```

`ARCHIVE-07` does not exist anywhere in the box. A participant who runs only
`exiftool`, finds a hostname, and tries to reach it wastes time and learns the
intended lesson: metadata-level concealment and pixel-level concealment are
different things, and finding *a* string is not finding *the* string.

The `Creation Time` chunk reads `2026:09:14 02:47:11` — the same night as the
Stage 1 lockout ticket, reinforcing that the compromise predates the transfer.

## Expected solution path

1. Note the filename convention and locate the image matching the Stage 1
   username.
2. Run `exiftool` — find `ARCHIVE-07`, which leads nowhere.
3. Run `zsteg -a` or an equivalent LSB extraction.
4. Read the recovered message: hostname `VAULT-03` plus the flag.
5. Submit the flag; add `vault-03.rtr.local` to the hosts file for Stage 3.

## Verification before release

```bash
exiftool RJewantha_backup.png     # shows only the decoy
zsteg -a RJewantha_backup.png     # reveals the payload
python3 solve.py RJewantha_backup.png
```

Confirm the image opens normally in an image viewer with no visible artefact.

## Reset

Re-upload this file to the CTFd challenge, or re-run `generate.py` — the fixed
RNG seed (`20260914`) and pinned PNG compression level produce byte-identical
output, verified by comparing SHA-256 across runs.

## Dependency produced

`VAULT-03` → Stage 3. The hostname must match the `server_name` in
`nginx/nginx.conf` (`vault-03.rtr.local`).
