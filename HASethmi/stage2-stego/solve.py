#!/usr/bin/env python3
"""
RaidTheRoot (RTR) - Stage 2 solver
Owner: Member 2 (Challenge Design A)

Self-developed solver for "The Ghost File". Extracts the message concealed in
the least significant bits of a carrier image without relying on zsteg, and
shows why the PNG text metadata is a dead end.

This is the manual equivalent of what zsteg does for b1,rgb,lsb,xy - written
out so the extraction logic is explicit rather than hidden behind a tool.

Usage:
    python3 solve.py RJewantha_backup.png
"""

import sys
from PIL import Image


def read_metadata(img):
    """PNG tEXt chunks - what exiftool would show."""
    return dict(img.info)


def extract_lsb(img, max_bytes=512):
    """
    Walk the image row-major, pulling the LSB of R, G and B from each pixel
    and reassembling them into bytes MSB-first. Stop at the null terminator.
    """
    px = img.load()
    bits = []

    for y in range(img.height):
        for x in range(img.width):
            for channel in px[x, y][:3]:
                bits.append(channel & 1)
            if len(bits) >= max_bytes * 8:
                break
        if len(bits) >= max_bytes * 8:
            break

    out = bytearray()
    for i in range(0, len(bits) - 7, 8):
        byte = 0
        for bit in bits[i:i + 8]:
            byte = (byte << 1) | bit
        if byte == 0:                      # terminator
            break
        out.append(byte)

    return bytes(out)


def main():
    if len(sys.argv) != 2:
        sys.exit(f"usage: {sys.argv[0]} <carrier.png>")

    img = Image.open(sys.argv[1]).convert("RGB")

    print("=" * 62)
    print("  STEP 1 - metadata inspection (the obvious first move)")
    print("=" * 62)
    meta = read_metadata(img)
    if meta:
        for k, v in meta.items():
            print(f"  {k:16} {v}")
        print("\n  Nothing here resolves. 'Source: ARCHIVE-07' looks like a")
        print("  lead but no such host exists. The metadata is a decoy.")
    else:
        print("  (no text chunks)")

    print()
    print("=" * 62)
    print("  STEP 2 - least significant bit extraction")
    print("=" * 62)
    payload = extract_lsb(img)

    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        print("  no readable payload in the LSB plane")
        sys.exit(1)

    print()
    for line in text.rstrip().splitlines():
        print(f"    {line}")
    print()

    for line in text.splitlines():
        if line.startswith("SERVER:"):
            host = line.split(":", 1)[1].strip()
            print(f"  -> next target: {host}")
        if line.startswith("RTR{"):
            print(f"  -> flag: {line.strip()}")
    print()


if __name__ == "__main__":
    main()
