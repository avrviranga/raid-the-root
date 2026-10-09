#!/usr/bin/env python3
"""
RaidTheRoot (RTR) - Stage 2 carrier image generator
Owner: Member 2 (Challenge Design A)

Builds the Stage 2 artefact: an image that looks like a scanned Nexora Bank
statement, carrying a hidden message in the least significant bits of its
pixel data, plus deliberately misleading PNG text metadata.

Deterministic: a fixed RNG seed means re-running this produces a
byte-identical image, which is the stage's reset mechanism.

Usage:
    pip install pillow
    python3 generate.py

Output:
    RJewantha_backup.png
"""

import random
from PIL import Image, ImageDraw, ImageFont
from PIL.PngImagePlugin import PngInfo

# --- Configuration ------------------------------------------------------
SEED = 20260914                 # ticket 4469 date - keeps output reproducible
OUTPUT = "RJewantha_backup.png"
WIDTH, HEIGHT = 900, 1180

# The payload recovered by LSB analysis. The hostname here is what unlocks
# Stage 3; the flag is what the participant submits.
PAYLOAD = (
    "You are looking in the wrong place.\n"
    "SERVER: VAULT-03\n"
    "RTR{ghost-file_vault03}\n"
)

# Deliberately misleading metadata. A participant who runs only exiftool
# finds ARCHIVE-07, which does not exist, and goes nowhere.
DECOY_METADATA = {
    "Software":    "Nexora DocScan 4.2",
    "Author":      "scanner-03.nexorabank.local",
    "Creation Time": "2026:09:14 02:47:11",
    "Source":      "ARCHIVE-07",
    "Comment":     "Routine statement archive. No further processing required.",
}


def build_document(rng):
    """Draw something that reads as a scanned bank statement."""
    img = Image.new("RGB", (WIDTH, HEIGHT), (252, 252, 250))
    d = ImageDraw.Draw(img)

    try:
        h1 = ImageFont.truetype("DejaVuSerif-Bold.ttf", 30)
        h2 = ImageFont.truetype("DejaVuSerif.ttf", 15)
        body = ImageFont.truetype("DejaVuSans.ttf", 13)
        mono = ImageFont.truetype("DejaVuSansMono.ttf", 12)
    except OSError:
        h1 = h2 = body = mono = ImageFont.load_default()

    ink = (28, 32, 44)
    grey = (105, 112, 125)

    # Header
    d.text((60, 58), "NEXORA BANK", font=h1, fill=(11, 37, 69))
    d.text((60, 98), "Treasury Operations - Account Statement",
           font=h2, fill=grey)
    d.line([(60, 128), (WIDTH - 60, 128)], fill=(11, 37, 69), width=2)

    # Account block
    y = 160
    for label, value in [
        ("Account holder", "NEXORA BANK N.V. - TREASURY OPERATIONS"),
        ("Statement ref",  "NXB-TR-2026-0914-0031"),
        ("Period",         "01 Sep 2026 - 14 Sep 2026"),
        ("Currency",       "EUR"),
        ("Issued",         "14 Sep 2026 02:47 UTC"),
    ]:
        d.text((60, y), f"{label}", font=body, fill=grey)
        d.text((230, y), value, font=body, fill=ink)
        y += 26

    # Transaction table
    y += 24
    d.rectangle([(60, y), (WIDTH - 60, y + 28)], fill=(238, 242, 247))
    for x, head in [(72, "DATE"), (190, "REFERENCE"),
                    (430, "DESCRIPTION"), (700, "AMOUNT")]:
        d.text((x, y + 8), head, font=mono, fill=(11, 37, 69))
    y += 28

    rows = [
        ("02 Sep", "TRF-88213904", "Interbank settlement",      "  1,240,000.00"),
        ("04 Sep", "TRF-88214551", "FX position adjustment",    "   -318,750.00"),
        ("06 Sep", "TRF-88215330", "Interbank settlement",      "    902,400.00"),
        ("08 Sep", "TRF-88216102", "Liquidity buffer transfer", "  2,100,000.00"),
        ("09 Sep", "TRF-88216847", "FX position adjustment",    "   -145,280.00"),
        ("11 Sep", "TRF-88217593", "Interbank settlement",      "    763,910.00"),
        ("12 Sep", "TRF-88218226", "Custody fee settlement",    "    -42,118.60"),
        ("13 Sep", "TRF-88219014", "Liquidity buffer transfer", "  1,875,000.00"),
        ("14 Sep", "TRF-88219770", "Interbank settlement",      "    651,220.00"),
    ]
    for i, (date, ref, desc, amt) in enumerate(rows):
        if i % 2:
            d.rectangle([(60, y), (WIDTH - 60, y + 26)], fill=(250, 251, 253))
        d.text((72, y + 7),  date, font=mono, fill=ink)
        d.text((190, y + 7), ref,  font=mono, fill=ink)
        d.text((430, y + 7), desc, font=body, fill=ink)
        d.text((700, y + 7), amt,  font=mono, fill=ink)
        y += 26

    d.line([(60, y + 6), (WIDTH - 60, y + 6)], fill=(200, 208, 218), width=1)
    d.text((430, y + 18), "Closing balance", font=body, fill=grey)
    d.text((700, y + 18), "  6,826,381.40", font=mono, fill=ink)

    # Footer
    d.text((60, HEIGHT - 110),
           "This statement is generated automatically. Retain for your records.",
           font=body, fill=grey)
    d.text((60, HEIGHT - 86),
           "Nexora Bank N.V. - Registered office: Amsterdam",
           font=body, fill=grey)
    d.text((60, HEIGHT - 50), "scanner-03 / batch 0914-A",
           font=mono, fill=(170, 176, 186))

    # Light scanner noise so it reads as a scan rather than a clean render.
    px = img.load()
    for _ in range(int(WIDTH * HEIGHT * 0.012)):
        x, yy = rng.randrange(WIDTH), rng.randrange(HEIGHT)
        r, g, b = px[x, yy]
        n = rng.randint(-7, 7)
        px[x, yy] = (max(0, min(255, r + n)),
                     max(0, min(255, g + n)),
                     max(0, min(255, b + n)))

    return img


def embed_lsb(img, message):
    """
    Write `message` into the least significant bit of each colour channel,
    row-major, R then G then B. This is the layout zsteg reports as
    b1,rgb,lsb,xy - the standard first thing a solver tries.
    """
    data = message.encode("utf-8") + b"\x00" * 4   # null terminator
    bits = [(byte >> i) & 1 for byte in data for i in range(7, -1, -1)]

    capacity = img.width * img.height * 3
    if len(bits) > capacity:
        raise ValueError(f"payload needs {len(bits)} bits, image holds {capacity}")

    px = img.load()
    idx = 0
    for y in range(img.height):
        for x in range(img.width):
            if idx >= len(bits):
                return img
            channels = list(px[x, y])
            for c in range(3):
                if idx < len(bits):
                    channels[c] = (channels[c] & 0xFE) | bits[idx]
                    idx += 1
            px[x, y] = tuple(channels)
    return img


def main():
    rng = random.Random(SEED)

    print("building carrier document ...")
    img = build_document(rng)

    print(f"embedding {len(PAYLOAD)} byte payload into LSB plane ...")
    img = embed_lsb(img, PAYLOAD)

    meta = PngInfo()
    for key, value in DECOY_METADATA.items():
        meta.add_text(key, value)

    # compress_level fixed so output stays byte-identical between runs
    img.save(OUTPUT, "PNG", pnginfo=meta, compress_level=6, optimize=False)

    import hashlib, os
    digest = hashlib.sha256(open(OUTPUT, "rb").read()).hexdigest()
    print(f"\nwrote {OUTPUT}  ({os.path.getsize(OUTPUT):,} bytes)")
    print(f"sha256 {digest}")
    print("\nverify with:  zsteg -a RJewantha_backup.png")
    print("or:           python3 solve.py RJewantha_backup.png")


if __name__ == "__main__":
    main()
