#!/usr/bin/env python3
"""
RaidTheRoot (RTR) - Stage 5 packet capture generator
Owner: Member 3 (Challenge Design B)

Builds a synthetic capture of Nexora Bank internal traffic around the night of
the incident. Roughly 4,000 packets of ordinary activity with a single
command-and-control conversation buried inside it.

Entirely synthetic - crafted with Scapy, never captured from a real network.

Deterministic: the fixed RNG seed and fixed timestamps mean re-running this
produces a byte-identical capture. That is the stage's reset mechanism.

The foothold credential embedded in the exfiltrated blob MUST match the
Stage 6 container. Both read it from the same place:

    STAGE6_USER / STAGE6_PASSWORD   in the repository .env

Usage:
    pip install scapy
    python3 generate.py

Output:
    capture_10.10.20.50.pcap
"""

import os
import random
import base64
import json
import hashlib
from pathlib import Path

from scapy.all import (Ether, IP, TCP, UDP, DNS, DNSQR, DNSRR,
                       Raw, wrpcap)

# --- Configuration ------------------------------------------------------
SEED = 20260920
OUTPUT = "capture_10.10.20.50.pcap"
BASE_TIME = 1758330000.0          # 2026-09-20 02:20:00 UTC, approx

# Hosts
GATEWAY_MAC = "00:1b:44:11:3a:b7"
HOSTS = {
    "10.10.20.17": "00:50:56:a1:4c:22",   # compromised workstation
    "10.10.20.50": "00:50:56:a1:9f:03",   # Ghost staging host  <-- the target
    "10.10.20.11": "00:50:56:a1:2d:91",
    "10.10.20.23": "00:50:56:a1:77:e4",
    "10.10.20.34": "00:50:56:a1:b8:1a",
    "10.10.20.41": "00:50:56:a1:05:cd",
    "10.10.20.58": "00:50:56:a1:e3:60",
}
DNS_SERVER = "10.10.10.5"
INTRANET = "10.10.10.20"
NTP_SERVER = "10.10.10.9"
FILE_SERVER = "10.10.10.31"

# What the solver ultimately recovers
TARGET_HOST = "BANK-CORE-01"
TARGET_IP = "10.10.30.11"
FLAG = "RTR{inside-network_bankcore01}"

C2_IP = "10.10.20.50"
C2_PORT = 4444
VICTIM_IP = "10.10.20.17"

BENIGN_DOMAINS = [
    "intranet.nexorabank.local", "mail.nexorabank.local",
    "updates.nexorabank.local", "sso.nexorabank.local",
    "files.nexorabank.local", "print01.nexorabank.local",
    "ntp.nexorabank.local", "wsus.nexorabank.local",
]

rng = random.Random(SEED)
packets = []


def read_credential():
    """
    Pull the Stage 6 foothold credential from .env so the capture and the
    Stage 6 container never drift apart.
    """
    user, password = "svc_backup", None

    for candidate in (Path(".env"), Path("../.env"), Path("../../.env")):
        if candidate.is_file():
            for line in candidate.read_text().splitlines():
                line = line.strip()
                if line.startswith("STAGE6_USER="):
                    user = line.split("=", 1)[1].strip()
                elif line.startswith("STAGE6_PASSWORD="):
                    password = line.split("=", 1)[1].strip()
            break

    user = os.environ.get("STAGE6_USER", user)
    password = os.environ.get("STAGE6_PASSWORD", password)

    if not password or password == "CHANGE_ME":
        raise SystemExit(
            "STAGE6_PASSWORD not found.\n"
            "Run this from the repository so .env can be read, or export it:\n"
            "    export STAGE6_PASSWORD='...'\n"
            "The value must match the Stage 6 container exactly."
        )
    return user, password


def eth(src_ip, dst_ip):
    """Frame with plausible MACs; anything off-subnet goes via the gateway."""
    src = HOSTS.get(src_ip, GATEWAY_MAC)
    dst = HOSTS.get(dst_ip, GATEWAY_MAC)
    return Ether(src=src, dst=dst)


def add(pkt, when):
    pkt.time = when
    packets.append(pkt)


# ----------------------------------------------------------- background ----

def dns_exchange(client, domain, when):
    sport = rng.randint(40000, 60000)
    txid = rng.randint(1, 65535)
    resolved = f"10.10.10.{rng.randint(20, 90)}"

    q = (eth(client, DNS_SERVER) / IP(src=client, dst=DNS_SERVER) /
         UDP(sport=sport, dport=53) /
         DNS(id=txid, rd=1, qd=DNSQR(qname=domain)))
    add(q, when)

    a = (eth(DNS_SERVER, client) / IP(src=DNS_SERVER, dst=client) /
         UDP(sport=53, dport=sport) /
         DNS(id=txid, qr=1, aa=1, qd=DNSQR(qname=domain),
             an=DNSRR(rrname=domain, ttl=300, rdata=resolved)))
    add(a, when + rng.uniform(0.001, 0.02))


def tcp_session(client, server, dport, request, response, when,
                sport=None, flag_data=True):
    """
    A complete TCP conversation with correct sequence and acknowledgement
    numbers, so Wireshark's Follow TCP Stream reassembles it properly.
    """
    sport = sport or rng.randint(40000, 60000)
    cseq = rng.randint(1000, 500000)
    sseq = rng.randint(1000, 500000)
    t = when

    # handshake
    add(eth(client, server) / IP(src=client, dst=server) /
        TCP(sport=sport, dport=dport, flags="S", seq=cseq), t)
    t += rng.uniform(0.0005, 0.004)

    add(eth(server, client) / IP(src=server, dst=client) /
        TCP(sport=dport, dport=sport, flags="SA", seq=sseq, ack=cseq + 1), t)
    t += rng.uniform(0.0005, 0.004)
    cseq += 1

    add(eth(client, server) / IP(src=client, dst=server) /
        TCP(sport=sport, dport=dport, flags="A", seq=cseq, ack=sseq + 1), t)
    t += rng.uniform(0.001, 0.02)
    sseq += 1

    # request
    if request:
        data = request.encode() if isinstance(request, str) else request
        add(eth(client, server) / IP(src=client, dst=server) /
            TCP(sport=sport, dport=dport, flags="PA", seq=cseq, ack=sseq) /
            Raw(load=data), t)
        cseq += len(data)
        t += rng.uniform(0.002, 0.03)

        add(eth(server, client) / IP(src=server, dst=client) /
            TCP(sport=dport, dport=sport, flags="A", seq=sseq, ack=cseq), t)
        t += rng.uniform(0.002, 0.05)

    # response
    if response:
        data = response.encode() if isinstance(response, str) else response
        add(eth(server, client) / IP(src=server, dst=client) /
            TCP(sport=dport, dport=sport, flags="PA", seq=sseq, ack=cseq) /
            Raw(load=data), t)
        sseq += len(data)
        t += rng.uniform(0.002, 0.03)

        add(eth(client, server) / IP(src=client, dst=server) /
            TCP(sport=sport, dport=dport, flags="A", seq=cseq, ack=sseq), t)
        t += rng.uniform(0.001, 0.02)

    # teardown
    add(eth(client, server) / IP(src=client, dst=server) /
        TCP(sport=sport, dport=dport, flags="FA", seq=cseq, ack=sseq), t)
    t += rng.uniform(0.0005, 0.004)
    add(eth(server, client) / IP(src=server, dst=client) /
        TCP(sport=dport, dport=sport, flags="FA", seq=sseq, ack=cseq + 1), t)
    t += rng.uniform(0.0005, 0.004)
    add(eth(client, server) / IP(src=client, dst=server) /
        TCP(sport=sport, dport=dport, flags="A", seq=cseq + 1, ack=sseq + 1), t)


def http_browse(client, when):
    path = rng.choice(["/", "/notices", "/hr/leave", "/it/servicedesk",
                       "/treasury/daily", "/static/css/main.css",
                       "/static/js/app.js", "/favicon.ico"])
    req = (f"GET {path} HTTP/1.1\r\n"
           f"Host: intranet.nexorabank.local\r\n"
           f"User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)\r\n"
           f"Accept: */*\r\nConnection: keep-alive\r\n\r\n")
    body = "<html><body>Nexora Bank intranet</body></html>"
    resp = (f"HTTP/1.1 200 OK\r\nServer: nginx\r\n"
            f"Content-Type: text/html\r\nContent-Length: {len(body)}\r\n\r\n{body}")
    tcp_session(client, INTRANET, 80, req, resp, when)


def ntp_sync(client, when):
    """
    NTP client/server exchange.

    Built from fixed bytes rather than Scapy's NTP layer: that layer fills
    its timestamp fields from the host clock, which would make the capture
    differ on every run and break the reset guarantee.
    """
    # mode 3 (client), version 4, stratum 0
    client_pkt = bytes([0x23, 0x00, 0x06, 0xec]) + bytes(44)
    # mode 4 (server), version 4, stratum 2
    server_pkt = bytes([0x24, 0x02, 0x06, 0xec]) + bytes(44)

    add(eth(client, NTP_SERVER) / IP(src=client, dst=NTP_SERVER) /
        UDP(sport=123, dport=123) / Raw(load=client_pkt), when)
    add(eth(NTP_SERVER, client) / IP(src=NTP_SERVER, dst=client) /
        UDP(sport=123, dport=123) / Raw(load=server_pkt),
        when + rng.uniform(0.001, 0.01))


def smb_traffic(client, when):
    sport = rng.randint(40000, 60000)
    cseq = rng.randint(1000, 500000)
    add(eth(client, FILE_SERVER) / IP(src=client, dst=FILE_SERVER) /
        TCP(sport=sport, dport=445, flags="S", seq=cseq), when)
    add(eth(FILE_SERVER, client) / IP(src=FILE_SERVER, dst=client) /
        TCP(sport=445, dport=sport, flags="SA", seq=rng.randint(1000, 9999),
            ack=cseq + 1), when + 0.002)


# ----------------------------------------------------------- malicious ----

def beacon(seq_no, when):
    """
    Short check-in to the staging host. Fixed 60-second interval - the
    giveaway. No legitimate service polls on an exact cadence like this.
    """
    payload = f"PING {seq_no:04d} host=WS-TR-017 uid=1f3a9c\n"
    reply = "ACK\n"
    tcp_session(VICTIM_IP, C2_IP, C2_PORT, payload, reply, when)


def exfil(user, password, when):
    """
    The one large transfer. An HTTP POST carrying a base64 configuration blob
    with the next target and the credential to reach it.
    """
    blob = {
        "stage": "lateral",
        "target_host": TARGET_HOST,
        "target_ip": TARGET_IP,
        "svc_user": user,
        "svc_pass": password,
        "method": "ssh",
        "note": "persistence installed, scheduled task active",
        "flag": FLAG,
    }
    encoded = base64.b64encode(json.dumps(blob, indent=2).encode()).decode()

    req = ("POST /stage/config HTTP/1.1\r\n"
           f"Host: {C2_IP}:{C2_PORT}\r\n"
           "User-Agent: nxb-update-agent/2.1\r\n"
           "Content-Type: application/octet-stream\r\n"
           f"Content-Length: {len(encoded)}\r\n"
           "X-Session: 1f3a9c\r\n\r\n"
           f"{encoded}")

    resp = ("HTTP/1.1 200 OK\r\nServer: -\r\n"
            "Content-Length: 18\r\n\r\nstored. standing by")

    tcp_session(VICTIM_IP, C2_IP, C2_PORT, req, resp, when, sport=49871)


def suspicious_dns(when):
    """A couple of odd lookups to reward DNS inspection."""
    for name in ["cdn-sync-eu.net", "update-relay-7.net"]:
        dns_exchange(VICTIM_IP, name, when)
        when += rng.uniform(40, 90)


# ---------------------------------------------------------------- build ----

def main():
    user, password = read_credential()
    print(f"foothold credential: {user} / {'*' * len(password)}")

    clients = [ip for ip in HOSTS if ip not in (C2_IP,)]

    # Background activity across ~75 minutes.
    print("generating background traffic ...")
    t = BASE_TIME
    while t < BASE_TIME + 3600:
        choice = rng.random()
        client = rng.choice(clients)
        if choice < 0.42:
            http_browse(client, t)
        elif choice < 0.72:
            dns_exchange(client, rng.choice(BENIGN_DOMAINS), t)
        elif choice < 0.88:
            smb_traffic(client, t)
        else:
            ntp_sync(client, t)
        t += rng.uniform(4.2, 7.8)

    # The malicious conversation: beacons on a fixed 60s cadence.
    print("embedding C2 beaconing ...")
    beacon_time = BASE_TIME + 600
    n = 0
    while beacon_time < BASE_TIME + 3500:
        n += 1
        beacon(n, beacon_time)
        beacon_time += 900.0           # exact interval, deliberately

    # The single exfiltration, partway through.
    print("embedding exfiltration ...")
    exfil(user, password, BASE_TIME + 2430)
    suspicious_dns(BASE_TIME + 2200)

    packets.sort(key=lambda p: p.time)

    malicious = sum(1 for p in packets
                    if IP in p and C2_IP in (p[IP].src, p[IP].dst))

    wrpcap(OUTPUT, packets)

    digest = hashlib.sha256(open(OUTPUT, "rb").read()).hexdigest()
    size = os.path.getsize(OUTPUT)

    print(f"\nwrote {OUTPUT}")
    print(f"  packets total      {len(packets):,}")
    print(f"  involving {C2_IP}  {malicious}")
    print(f"  beacons            {n}")
    print(f"  size               {size:,} bytes")
    print(f"  sha256             {digest}")
    print(f"\nverify:  python3 solve.py {OUTPUT}")


if __name__ == "__main__":
    main()
