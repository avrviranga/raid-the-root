#!/usr/bin/env python3
"""
RaidTheRoot (RTR) - Stage 4 artefact generator
Owner: Member 3 (Challenge Design B)

Produces vault_backup.enc, the encrypted file served by the Stage 3 portal.

Scheme: repeating-key XOR. The key is the Stage 1 username in lowercase, so
the file cannot be decrypted without having solved Stage 1 - this is what
makes Stage 4 depend on two non-adjacent earlier stages.

Deterministic: same input always produces the same ciphertext. This is the
stage's reset mechanism.

Usage:
    python3 generate.py
Output:
    vault_backup.enc
"""

import hashlib
import os

# Key material: the Stage 1 answer, lowercased.
# If the Stage 1 username changes, this must change with it.
KEY = b"rjewantha"

OUTPUT = "vault_backup.enc"

PLAINTEXT = """\
NEXORA BANK - TREASURY OPERATIONS
INTERNAL VAULT BACKUP / RESTRICTED
==================================

NEXT LOCATION: 10.10.20.50 : 4444

They think I'm outside.
I'm already inside.

RTR{locked-vault_decrypted}

-- end of record --
"""


def xor_repeating(data: bytes, key: bytes) -> bytes:
    """Repeating-key XOR. Symmetric: the same call decrypts."""
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))


def main():
    plain = PLAINTEXT.encode("utf-8")
    cipher = xor_repeating(plain, KEY)

    with open(OUTPUT, "wb") as fh:
        fh.write(cipher)

    digest = hashlib.sha256(cipher).hexdigest()
    print(f"wrote {OUTPUT}  ({len(cipher)} bytes)")
    print(f"sha256 {digest}")
    print(f"key    {KEY.decode()}  (Stage 1 username, lowercased)")

    # Sanity check: round-trip must recover the plaintext exactly.
    assert xor_repeating(cipher, KEY) == plain, "round-trip failed"
    print("\nround-trip verified")

    print("\nCopy this file to the Stage 3 portal so it can be served:")
    print("  cp vault_backup.enc ../stage3-webportal/app/static/")


if __name__ == "__main__":
    main()
