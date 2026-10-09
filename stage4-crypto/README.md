# Stage 4 — The Locked Vault (Cryptography)

**Owner:** IT24101430 (Challenge Design B)
**Flag:** `RTR{locked-vault_decrypted}`

## Files

| File | Role |
|---|---|
| `generate.py` | Produces `vault_backup.enc`. Deterministic — the reset mechanism. |
| `solve.py` | Decryption and cryptanalysis (Member 3's LO3 deliverable) |
| `vault_backup.enc` | Ciphertext — **served by Stage 3**, not uploaded to CTFd |

```bash
python3 generate.py
cp vault_backup.enc ../stage3-webportal/app/static/
```

Expected SHA-256: `5966c099ea2ab0838a6ded1212f2b1d9178b0521723f6c8f97a868d3a2a4c7ce`

## The scheme

Repeating-key XOR. The key is the Stage 1 username in lowercase:
`rjewantha`.

This is what makes Stage 4 the first challenge requiring evidence from two
**non-adjacent** stages: the ciphertext and cipher family come from Stage 3,
but the key comes from Stage 1. A participant who skipped ahead cannot solve
it even with the file in hand.

## Why this is the right weakness to teach

The lesson is that cryptographic failure usually comes from key management,
not algorithm choice. XOR itself is not broken — a one-time pad is XOR. What
breaks here is reusing a short, guessable key derived from a public username.

`solve.py` demonstrates both sides:

```bash
python3 solve.py vault_backup.enc rjewantha   # intended path
python3 solve.py vault_backup.enc             # no key: cryptanalysis
```

The second mode detects key length by normalised Hamming distance between
blocks, then solves each key byte independently as a single-byte XOR using
letter-frequency scoring. On a 234-byte ciphertext with a 9-byte key the
statistics are thin, which is itself worth explaining: the scheme is weak in
principle, and having the key from Stage 1 is what makes it reliably solvable.

## Recovered plaintext

```
NEXT LOCATION: 10.10.20.50 : 4444
They think I'm outside. I'm already inside.
RTR{locked-vault_decrypted}
```

## Dependencies

**In:** `vault_backup.enc` + `X-Cipher-Hint: repeating-key-xor` from Stage 3;
username from Stage 1.
**Out:** `10.10.20.50:4444` → Stage 5 (identifies the correct capture file and
the display filter).

## Solvable with standard tooling

CyberChef: *From Hex* is unnecessary — load the raw file, apply **XOR** with
key `rjewantha` as UTF-8. One operation. Participants are not required to use
`solve.py`.

## Reset

Re-run `generate.py`. Output is byte-identical: same plaintext, same key, no
randomness in the scheme.
