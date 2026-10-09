# Stage 5 — Inside the Network (Network Forensics)

**Owner:** IT24101430 (Challenge Design B)
**Flag:** `RTR{inside-network_bankcore01}`

## Files

| File | Role |
|---|---|
| `generate.py` | Builds the capture with Scapy. Deterministic — the reset mechanism. |
| `solve.py` | Packet analyser (Member 3's LO3 deliverable) |
| `capture_10.10.20.50.pcap` | The artefact uploaded to CTFd |

```bash
pip install scapy
python3 generate.py                        # run from the repo so .env is read
python3 solve.py capture_10.10.20.50.pcap
```

## CRITICAL — credential synchronisation

The capture embeds the Stage 6 foothold credential. `generate.py` reads it
from the repository `.env`:

```
STAGE6_USER=svc_backup
STAGE6_PASSWORD=<agreed value>
```

**All four members must use the same value**, and Stage 6's container must be
built with it. If `.env` changes, regenerate this capture or the Stage 5 → 6
handoff breaks. The capture is the only place a participant can obtain the
password, so a mismatch makes Stage 6 unsolvable.

## Capture profile

| | |
|---|---|
| Total packets | 3,400 |
| Involving `10.10.20.50` | 50 (1.5%) |
| Beacon sessions | 4, exactly 900 s apart |
| Exfiltration | 1 HTTP POST, 533 byte stream |
| Window | ~60 minutes |
| Size | 336 KB |

Background traffic: intranet HTTP, internal DNS, NTP and SMB across six
workstations. Entirely synthetic — crafted packet by packet, never captured
from any real network.

## What is hidden in it

**The beacon.** `10.10.20.17 → 10.10.20.50:4444`, four sessions at an exact
900-second cadence. Port 4444 is not a standard service, and no legitimate
application polls on a perfectly fixed interval. Each check-in carries
`PING <seq> host=WS-TR-017 uid=1f3a9c`.

**The exfiltration.** One HTTP POST to `/stage/config` with a base64 body
decoding to:

```json
{
  "target_host": "BANK-CORE-01",
  "target_ip": "10.10.30.11",
  "svc_user": "svc_backup",
  "svc_pass": "<from .env>",
  "method": "ssh",
  "flag": "RTR{inside-network_bankcore01}"
}
```

**Two external DNS lookups** from the same host — `cdn-sync-eu.net` and
`update-relay-7.net` — among otherwise entirely `.nexorabank.local` queries.
Supporting evidence, not required to solve.

## Expected solution path

1. Match the capture filename to the IP recovered in Stage 4.
2. Open in Wireshark. `Statistics → Conversations` shows port 4444 against a
   backdrop of 80/53/123/445.
3. Filter `tcp.port == 4444` and note the fixed interval between sessions.
4. Follow the TCP stream on the largest conversation.
5. Base64-decode the POST body.
6. Record the hostname and credential; submit the flag.

Useful filters:

```
tcp.port == 4444
ip.addr == 10.10.20.50
dns.qry.name && !(dns.qry.name contains "nexorabank")
```

## Note on the solver

`solve.py` detects beaconing by clustering inter-session gaps and keeping the
interval that the **majority** of them agree on. An earlier version demanded
near-zero jitter across every gap, which failed as soon as the implant made
one off-cadence connection (the upload) — and a looser version produced false
positives from ordinary user traffic that happened to cluster.

Requiring that most intervals fit, rather than all or merely some, is what
separates scheduled software from human browsing. Worth explaining on camera:
it is a real detection-engineering tradeoff, not an arbitrary threshold.

## Reset

Re-run `generate.py`. Fixed RNG seed (`20260920`), fixed base timestamp and
fixed NTP payloads produce a byte-identical file — verified by comparing
SHA-256 across runs.

Expected SHA-256 (with the test credential):
`87126f5c9840600dc634154a5fff35558b22102d86d87ae1e027cedf852ca866`

This changes when `STAGE6_PASSWORD` changes, which is expected — record your
group's value alongside this file.

## Dependencies

**In:** `10.10.20.50:4444` from Stage 4 — identifies the capture and the filter.
**Out:** `BANK-CORE-01` + SSH credential → Stage 6.
