#!/usr/bin/env python3
"""
RaidTheRoot (RTR) - Stage 5 solver
Owner: Member 3 (Challenge Design B)

Self-developed packet capture analyser for "Inside the Network". Works the
same way an analyst would in Wireshark, but scripted so the reasoning is
explicit:

  1. profile the capture - who talks to whom, on what ports
  2. find conversations with a suspiciously regular interval (beaconing)
  3. reassemble the stream carrying the largest payload
  4. decode the base64 blob and pull out the next target and credential

Usage:
    pip install scapy
    python3 solve.py capture_10.10.20.50.pcap
"""

import base64
import json
import re
import sys
from collections import defaultdict
from statistics import mean, pstdev

try:
    from scapy.all import rdpcap, IP, TCP, UDP, DNS, DNSQR, Raw
except ImportError:
    sys.exit("pip install scapy")


def banner(n, text):
    print(f"\n[{n}] {text}")
    print("    " + "-" * 64)


def main():
    if len(sys.argv) != 2:
        sys.exit(f"usage: {sys.argv[0]} <capture.pcap>")

    print(f"reading {sys.argv[1]} ...")
    pkts = rdpcap(sys.argv[1])
    print(f"{len(pkts):,} packets")

    # --- 1. conversation profile -------------------------------------
    banner(1, "profiling conversations by destination port")

    ports = defaultdict(int)
    convs = defaultdict(list)

    for p in pkts:
        if IP not in p:
            continue
        if TCP in p:
            dport = p[TCP].dport
            ports[dport] += 1
            key = (p[IP].src, p[IP].dst, dport)
            convs[key].append(float(p.time))
        elif UDP in p:
            ports[p[UDP].dport] += 1

    common = {80: "HTTP", 443: "HTTPS", 53: "DNS", 123: "NTP",
              445: "SMB", 22: "SSH", 3306: "MySQL"}

    for port, count in sorted(ports.items(), key=lambda kv: -kv[1])[:8]:
        label = common.get(port, "** not a standard service **")
        print(f"    port {port:<6} {count:>6} packets   {label}")

    # --- 2. beacon detection -----------------------------------------
    banner(2, "looking for fixed-interval conversations")

    suspects = []
    for (src, dst, dport), times in convs.items():
        starts = sorted(set(round(t, 1) for t in times))
        # collapse packets belonging to the same short session
        sessions = [starts[0]]
        for t in starts[1:]:
            if t - sessions[-1] > 30:
                sessions.append(t)
        if len(sessions) < 3:
            continue

        gaps = [b - a for a, b in zip(sessions, sessions[1:])]
        if len(gaps) < 2:
            continue

        # Find the dominant interval rather than demanding every gap match.
        # A beaconing implant may also make one-off connections (an upload,
        # a task fetch), so some gaps will not fit the cadence. Cluster the
        # gaps and keep the value the most of them agree on.
        best_interval, best_hits = None, 0
        for candidate in gaps:
            if candidate < 30:
                continue
            hits = sum(1 for g in gaps if abs(g - candidate) <= candidate * 0.10)
            if hits > best_hits:
                best_interval, best_hits = candidate, hits

        # Ordinary user traffic produces gaps that only agree by coincidence,
        # so a handful of matches out of many means nothing. Scheduled
        # software is consistent: demand that most intervals fit the cadence.
        if best_interval and best_hits >= 2 and best_hits / len(gaps) >= 0.5:
            matched = [g for g in gaps if abs(g - best_interval) <= best_interval * 0.10]
            jitter = pstdev(matched) if len(matched) > 1 else 0.0
            suspects.append((src, dst, dport, len(sessions),
                             mean(matched), jitter, best_hits, len(gaps)))

    # Most consistent cadence first.
    suspects.sort(key=lambda s: -(s[6] / s[7]))

    if not suspects:
        print("    none found")
    for src, dst, dport, n, avg, jit, hits, total in suspects:
        print(f"    {src} -> {dst}:{dport}")
        print(f"      {n} sessions, {hits} of {total} intervals agree")
        print(f"      dominant interval {avg:.1f}s, jitter {jit:.2f}s")
        print(f"      a fixed {avg:.0f}s cadence is scheduled, not human")
        if hits < total:
            print(f"      ({total - hits} off-cadence connection(s) - worth a look)")

    if not suspects:
        sys.exit(1)

    c2_src, c2_dst, c2_port = suspects[0][0], suspects[0][1], suspects[0][2]

    # --- 3. odd DNS ---------------------------------------------------
    banner(3, "DNS lookups from the same host")
    seen = set()
    for p in pkts:
        if DNS in p and p[DNS].qr == 0 and IP in p and p[IP].src == c2_src:
            try:
                q = p[DNSQR].qname.decode().rstrip(".")
            except Exception:
                continue
            if q not in seen:
                seen.add(q)
                internal = q.endswith(".nexorabank.local")
                mark = "" if internal else "   <- external, not a bank domain"
                print(f"    {q}{mark}")

    # --- 4. stream reassembly ----------------------------------------
    banner(4, f"reassembling payloads on {c2_dst}:{c2_port}")

    streams = defaultdict(bytes)
    for p in pkts:
        if IP in p and TCP in p and Raw in p:
            if c2_dst in (p[IP].src, p[IP].dst) and \
               c2_port in (p[TCP].sport, p[TCP].dport):
                key = (p[IP].src, p[TCP].sport, p[IP].dst, p[TCP].dport)
                streams[key] += bytes(p[Raw].load)

    biggest = max(streams.items(), key=lambda kv: len(kv[1]))
    (src, sport, dst, dport), data = biggest
    print(f"    largest stream: {src}:{sport} -> {dst}:{dport}  "
          f"({len(data)} bytes)")

    text = data.decode("utf-8", errors="replace")
    head = text.split("\r\n\r\n")[0]
    print("\n    request headers:")
    for line in head.splitlines():
        print(f"      {line}")

    # --- 5. decode the payload ---------------------------------------
    banner(5, "decoding the payload")

    body = text.split("\r\n\r\n", 1)[1] if "\r\n\r\n" in text else text
    candidate = re.sub(r"\s+", "", body)

    try:
        decoded = base64.b64decode(candidate).decode()
    except Exception:
        sys.exit("    payload did not decode as base64")

    print()
    for line in decoded.splitlines():
        print(f"      {line}")

    try:
        blob = json.loads(decoded)
    except json.JSONDecodeError:
        return

    print("\n" + "=" * 68)
    print("  RECOVERED")
    print("=" * 68)
    print(f"  next target : {blob.get('target_host')} ({blob.get('target_ip')})")
    print(f"  credential  : {blob.get('svc_user')} / {blob.get('svc_pass')}")
    print(f"  flag        : {blob.get('flag')}")
    print("=" * 68)
    print("\n  Stage 6:  ssh {}@127.0.0.1 -p 2222\n".format(blob.get("svc_user")))


if __name__ == "__main__":
    main()
