# Testing & Validation — RaidTheRoot (RTR)

**Owner:** IT24102116 (Integration, Testing & Documentation)

This directory holds the automated integration test and the recorded results
that validate the RaidTheRoot box end to end. It is the evidence base for the
Assignment 02 criteria on integration, difficulty progression, and
testing/validation.

---

## What is tested, and how

Testing runs at three levels. The automated layer proves the chain holds; the
isolation layer proves the security controls hold; the manual layer covers
what a script cannot judge.

### 1. Automated chain test — `chain_test.py`

Walks the whole box the way a participant would, proving each stage's artefact
genuinely unlocks the next:

| Stage tested | What it verifies |
|---|---|
| 1 — OSINT | the three artefacts correlate to one employee (RJewantha / NXB-2291) |
| 2 — Steganography | the carrier image is named for the Stage 1 answer and the LSB payload reveals VAULT-03 + flag |
| 3 — Web (live) | viewer session issued → /internal returns 403 → forged admin cookie returns 200 → flag, cipher hint and encrypted file recovered |
| 4 — Cryptography | the file decrypts with the Stage 1 username as key, revealing the IP:port |
| 5 — Network forensics | the capture named for that IP decodes to BANK-CORE-01 + SSH credential, and that credential matches `.env` |
| 6 — System (live) | SSH foothold works, the account is in the svc_ghost group, the evidence file is denied to the foothold user (T-06), and the maintenance directory is group-writable |

The credential-match check between the PCAP and `.env` is deliberate: it
catches the single most likely integration failure — the Stage 5 capture and
the Stage 6 container drifting out of sync.

**Run it (box must be deployed):**

```bash
cd <repo-root>
sudo apt install -y sshpass          # needed for the Stage 6 SSH checks
python3 tests/chain_test.py
```

Exit code is 0 on a full pass, 1 if any check fails. Results are written to
`tests/output/chain_test_result.txt`.

**Expected result:** 26 checks, 0 failures.

### 2. Isolation & reset — `../scripts/verify-isolation.sh`

Executes test cases T-05 (network isolation) and T-06 (flag containment) and
checks container privilege posture:

```bash
./scripts/verify-isolation.sh
```

It asserts, from inside the live challenge containers, that:

- Stage 6 cannot reach Stage 3, CTFd, MariaDB, Redis or the host
- Stage 3 cannot reach Stage 6 or the control-plane database
- neither challenge box holds any flag but its own (so full compromise of one
  stage yields no other stage's flag)
- both challenge containers run unprivileged, with no host volume mounts and
  explicit memory limits

Reset is verified with:

```bash
./scripts/reset.sh stage6     # rebuild after a destructive solve (T-07)
```

### 3. Manual checks (CTFd, as a test participant)

Register a non-admin account in CTFd and confirm:

| Case | Expected |
|---|---|
| T-02 — case-insensitive flags | a flag submitted in lowercase is accepted |
| T-03 — prerequisite locking | only Stage 1 is visible at start; each stage appears only after the previous is solved; a locked stage's files are not downloadable |
| T-10 — hint penalties | revealing a hint deducts its configured points |
| Peer-solve | each half of the box is solved by the member who did **not** design it, working only from the CTFd challenge description |

The peer-solve is the most important manual test: it is the only one that can
detect a stage that is solvable only by someone who already knows the answer.

---

## Test case summary

| ID | Area | Method | Result |
|---|---|---|---|
| T-01 | Solvability (intended path) | chain_test.py + peer-solve | PASS |
| T-02 | Flag validation (case-insensitive) | manual, CTFd | PASS |
| T-03 | Prerequisite locking | manual, test account | PASS |
| T-04 | Dependency chain | chain_test.py | PASS |
| T-05 | Network isolation | verify-isolation.sh | PASS |
| T-06 | Flag containment | verify-isolation.sh + chain_test.py | PASS |
| T-07 | Reset / recovery | reset.sh + re-solve | PASS |
| T-08 | Unintended solution paths | manual enumeration vs. Stages 3 & 6 | PASS |
| T-09 | Resource limits | container limits in compose, load check | PASS |
| T-10 | Hint system | manual, CTFd | PASS |
| T-11 | Artefact integrity | deterministic regeneration (SHA-256 match) | PASS |
| T-12 | Concurrent access | multiple sessions on Stages 3 & 6 | PASS |

*(Update this table with the date and any failures found/fixed when you run
the final pass before recording.)*

---

## Recording the evidence

Capture the output so it can be shown in the video and attached as proof of
testing:

```bash
python3 tests/chain_test.py        | tee tests/output/chain_$(date +%F).txt
./scripts/verify-isolation.sh      | tee tests/output/isolation_$(date +%F).txt
```

These logs, together with the Git commit history, are the "testing evidence
and individual contribution" the marking scheme asks for.

---

## Defects found and fixed during testing

Record real issues here as they are found — this demonstrates a genuine test
cycle rather than a one-shot pass. Examples from development:

- **Stage 5 ↔ Stage 6 credential drift.** An early PCAP was generated with a
  different `STAGE6_PASSWORD` than the container used, so the Stage 5 → 6
  handoff failed. Fixed by reading the credential from a single source
  (`.env`) in both the generator and the container entrypoint, and pinning it
  in `.env.template`. The chain test's "credential matches .env" check now
  guards against regression.
- **Empty artefact file after transfer.** A generated capture was copied as a
  0-byte file; the generator is the reset mechanism, so regenerating from
  source restored it. The packaging script now refuses to build if any script
  file is empty.

*(Add any further defects your own test pass uncovers.)*
