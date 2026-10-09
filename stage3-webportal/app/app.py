#!/usr/bin/env python3
"""
VAULT-03 - Nexora Bank internal document portal
RaidTheRoot (RTR) Stage 3 challenge
Owner: Member 2 (Challenge Design A)

INTENTIONALLY VULNERABLE. Built for the RaidTheRoot CTF and isolated on its
own Docker network. Not for deployment anywhere else.

The planted weakness is a broken access control: the portal issues a session
cookie containing the user's role as client-side data, then trusts that value
on the server without verifying it against anything. A participant who decodes
the cookie, changes the role and re-sends it is granted administrative access.

This maps to OWASP A01:2021 Broken Access Control.
"""

import base64
import json
import os

from flask import (Flask, Response, make_response, render_template,
                   request, send_from_directory)

app = Flask(__name__)

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

FLAG = "RTR{back-door_access-granted}"

# Identifies the cipher family used in Stage 4 without revealing the key.
CIPHER_HINT = "repeating-key-xor"

DOCUMENTS = [
    ("NXB-TR-2026-0914-0031", "Treasury settlement statement", "14 Sep 2026", "Released"),
    ("NXB-TR-2026-0908-0027", "Liquidity buffer reconciliation", "08 Sep 2026", "Released"),
    ("NXB-CP-2026-0903-0119", "Counterparty exposure summary", "03 Sep 2026", "Released"),
    ("NXB-TR-2026-0829-0014", "FX position daily close", "29 Aug 2026", "Released"),
    ("NXB-AU-2026-0821-0006", "Internal audit control sample", "21 Aug 2026", "Restricted"),
    ("NXB-TR-2026-0815-0098", "Treasury settlement statement", "15 Aug 2026", "Released"),
]


def issue_session(role="viewer", user="guest"):
    """
    Build the session cookie.

    THE FLAW: the role travels to the client inside the cookie and is read
    back verbatim. There is no signature, no MAC, and no server-side session
    store, so the client is free to rewrite it.
    """
    payload = {"user": user, "role": role, "portal": "VAULT-03"}
    return base64.b64encode(json.dumps(payload).encode()).decode()


def read_session(raw):
    """Decode the session cookie. Returns None when absent or malformed."""
    if not raw:
        return None
    try:
        return json.loads(base64.b64decode(raw).decode())
    except Exception:
        return None


@app.after_request
def banner(resp):
    resp.headers["Server"] = "NexoraPortal/1.4"
    return resp


@app.route("/")
def index():
    session = read_session(request.cookies.get("nxb_session"))
    resp = make_response(render_template("index.html",
                                         documents=DOCUMENTS,
                                         session=session))
    if not session:
        # Every visitor is handed a viewer session on arrival.
        resp.set_cookie("nxb_session", issue_session(), path="/")
    return resp


@app.route("/documents")
def documents():
    return render_template("index.html",
                           documents=DOCUMENTS,
                           session=read_session(request.cookies.get("nxb_session")))


@app.route("/health")
def health():
    return {"status": "ok", "portal": "VAULT-03"}


@app.route("/robots.txt")
def robots():
    return Response("User-agent: *\nDisallow: /internal\n",
                    mimetype="text/plain")


@app.route("/internal")
def internal():
    """
    Staging console. Ghost used this to hold data before moving it out.

    Not linked from the navigation. Reachable by directory enumeration or by
    reading the commented-out call in static/js/portal.js.
    """
    session = read_session(request.cookies.get("nxb_session"))

    if not session:
        return Response(
            json.dumps({"error": "no session", "hint": "visit / first"}, indent=2),
            status=401, mimetype="application/json")

    # THE FLAW, exercised: the role is taken straight from the cookie.
    # Nothing checks it against a server-side record of who this user is.
    if session.get("role") != "administrator":
        return Response(
            json.dumps({
                "error": "insufficient role",
                "required_role": "administrator",
                "your_role": session.get("role"),
                "portal": "VAULT-03",
            }, indent=2),
            status=403, mimetype="application/json")

    resp = make_response(render_template("internal.html",
                                         flag=FLAG,
                                         session=session))
    # Stage 4 needs this. Identifies the cipher family, not the key.
    resp.headers["X-Cipher-Hint"] = CIPHER_HINT
    return resp


@app.route("/internal/download/<path:filename>")
def internal_download(filename):
    """Serving the staged file, behind the same broken check."""
    session = read_session(request.cookies.get("nxb_session"))
    if not session or session.get("role") != "administrator":
        return Response(
            json.dumps({"error": "insufficient role"}, indent=2),
            status=403, mimetype="application/json")

    if filename != "vault_backup.enc":
        return Response(json.dumps({"error": "not found"}), status=404,
                        mimetype="application/json")

    resp = make_response(send_from_directory(STATIC_DIR, filename,
                                             as_attachment=True))
    resp.headers["X-Cipher-Hint"] = CIPHER_HINT
    return resp


@app.errorhandler(404)
def not_found(_):
    return Response(json.dumps({"error": "not found", "portal": "VAULT-03"},
                               indent=2),
                    status=404, mimetype="application/json")


if __name__ == "__main__":
    # debug stays off: a traceback page would hand over the source.
    app.run(host="0.0.0.0", port=5000, debug=False)
