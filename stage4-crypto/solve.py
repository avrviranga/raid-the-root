#!/usr/bin/env python3
"""
RaidTheRoot (RTR) - Stage 4 solver
Owner: Member 3 (Challenge Design B)

Self-developed solver for "The Locked Vault". Recovers the plaintext from
vault_backup.enc given the cipher family named by the Stage 3 response header
and the username recovered in Stage 1.

Two modes:

  with a key      - direct decryption, the intended path
  without a key   - key-length detection by Hamming distance, then
                    per-byte frequency analysis, to show the scheme is weak
                    even if Stage 1 were unavailable

Usage:
    python3 solve.py vault_backup.enc rjewantha   # intended path
    python3 solve.py vault_backup.enc            # analytical path
"""

import sys
from itertools import combinations


def xor_repeating(data: bytes, key: bytes) -> bytes:
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))


# ---------------------------------------------------------------- analysis --

def hamming(a: bytes, b: bytes) -> int:
    return sum(bin(x ^ y).count("1") for x, y in zip(a, b))


def guess_key_length(data: bytes, lo=2, hi=20):
    """
    Classic repeating-key XOR key-length detection. Blocks that are one key
    length apart share the same keystream, so their normalised Hamming
    distance is lower than for a wrong length.
    """
    scores = []
    for klen in range(lo, min(hi, len(data) // 4) + 1):
        blocks = [data[i * klen:(i + 1) * klen] for i in range(4)]
        pairs = list(combinations(blocks, 2))
        dist = sum(hamming(x, y) for x, y in pairs) / len(pairs) / klen
        scores.append((dist, klen))
    scores.sort()
    return [k for _, k in scores[:3]]


def score_english(bs: bytes) -> float:
    """Crude printable-ASCII and letter-frequency score."""
    common = b"ETAOIN SHRDLU etaoinshrdlu"
    s = 0.0
    for b in bs:
        if b in common:
            s += 2
        elif 32 <= b <= 126 or b in (10, 13):
            s += 1
        else:
            s -= 5
    return s / max(len(bs), 1)


def crack_key(data: bytes, klen: int) -> bytes:
    """Solve each key byte independently as a single-byte XOR."""
    key = bytearray()
    for pos in range(klen):
        column = data[pos::klen]
        best, best_score = 0, float("-inf")
        for candidate in range(256):
            sc = score_english(bytes(c ^ candidate for c in column))
            if sc > best_score:
                best, best_score = candidate, sc
        key.append(best)
    return bytes(key)


# -------------------------------------------------------------------- main --

def report(plain: bytes):
    print("\n" + "=" * 66)
    print("  RECOVERED PLAINTEXT")
    print("=" * 66 + "\n")
    text = plain.decode("utf-8", errors="replace")
    for line in text.splitlines():
        print(f"    {line}")
    print()

    for line in text.splitlines():
        if "NEXT LOCATION" in line:
            print(f"  -> next target: {line.split(':', 1)[1].strip()}")
        if line.strip().startswith("RTR{"):
            print(f"  -> flag: {line.strip()}")
    print()


def main():
    if len(sys.argv) < 2:
        sys.exit(f"usage: {sys.argv[0]} <vault_backup.enc> [key]")

    data = open(sys.argv[1], "rb").read()
    print(f"ciphertext: {len(data)} bytes")

    if len(sys.argv) >= 3:
        key = sys.argv[2].encode()
        print(f"key:        {key.decode()}  (supplied)")
        print("\nStage 3 named the cipher family. Stage 1 supplied the key.")
        report(xor_repeating(data, key))
        return

    # No key given - demonstrate that the scheme does not protect anything.
    print("no key supplied - running cryptanalysis\n")

    candidates = guess_key_length(data)
    print(f"likely key lengths (Hamming distance): {candidates}")

    for klen in candidates:
        key = crack_key(data, klen)
        plain = xor_repeating(data, key)
        if b"RTR{" in plain:
            print(f"\nrecovered key: {key.decode(errors='replace')}  (length {klen})")
            report(plain)
            return

    print("\ncryptanalysis did not converge - supply the Stage 1 username as the key")


if __name__ == "__main__":
    main()
