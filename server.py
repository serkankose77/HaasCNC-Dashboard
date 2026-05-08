#!/usr/bin/env python3
"""
SE Havacılık · Multi-Machine MTConnect Dashboard Server
=======================================================
Serves dashboard.html on http://localhost:8000 and proxies MTConnect
agent requests for multiple Haas machines configured below.

Routes:
    GET /                       -> dashboard.html
    GET /api/machines           -> JSON list of configured machines
    GET /mtc/<id>/<endpoint>    -> proxied to machine[id]
                                   e.g. /mtc/vf6/current
                                        /mtc/st10/probe
                                        /mtc/umc400/sample?from=123

Usage:
    python3 server.py
    Open http://localhost:8000

Requirements: Python 3.8+ (stdlib only)
"""

import http.server
import socketserver
import urllib.request
import urllib.error
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

# ---- Configuration ----------------------------------------------------------
# Machine list (host IPs, names, mill/lathe type) lives in machines.json next
# to this file. Copy machines.example.json -> machines.json and edit with your
# shop-floor IPs. machines.json is gitignored so real IPs never enter source.
LISTEN_HOST  = "0.0.0.0"
LISTEN_PORT  = 8000
TIMEOUT      = 5     # saniye — LAN tezgahları için 5sn yeterli; offline ise hızlı 502 döner
CONFIG_FILE  = "machines.json"
EXAMPLE_FILE = "machines.example.json"
# -----------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent


def load_machines():
    """Load machine config from machines.json. Hard-fail with a helpful
    message if it doesn't exist — prevents accidentally running with the
    placeholder IPs from machines.example.json."""
    cfg = SCRIPT_DIR / CONFIG_FILE
    if not cfg.exists():
        example = SCRIPT_DIR / EXAMPLE_FILE
        hint = (
            f"\n   cp {EXAMPLE_FILE} {CONFIG_FILE}  &&  edit {CONFIG_FILE}"
            if example.exists()
            else f"\n   create {CONFIG_FILE} with your machine list"
        )
        sys.stderr.write(
            f"ERROR: {cfg} not found.{hint}\n"
        )
        sys.exit(1)
    try:
        with cfg.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        sys.stderr.write(f"ERROR: {cfg} is not valid JSON: {e}\n")
        sys.exit(1)


MACHINES = load_machines()


class DashboardHandler(http.server.SimpleHTTPRequestHandler):

    def log_message(self, fmt, *args):
        msg = fmt % args
        if " 200 " not in msg and " 304 " not in msg:
            sys.stderr.write(f"[{self.address_string()}] {msg}\n")

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path in ("", "/"):
            self.path = "/dashboard.html"
            return super().do_GET()

        if path == "/api/machines":
            return self._send_machines()

        if path.startswith("/mtc/"):
            return self._proxy_mtconnect(parsed)

        return super().do_GET()

    def _send_machines(self):
        payload = [
            {
                "id":    mid,
                "name":  m["name"],
                "model": m["model"],
                "type":  m.get("type", "mill"),
            }
            for mid, m in MACHINES.items()
        ]
        data = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _proxy_mtconnect(self, parsed):
        rest = parsed.path[len("/mtc/"):]
        parts = rest.split("/", 1)
        machine_id = parts[0] if parts else ""

        if machine_id not in MACHINES:
            self.send_error(404, f"Unknown machine '{machine_id}'")
            return

        sub_path = parts[1] if len(parts) > 1 else ""
        m = MACHINES[machine_id]
        target = f"http://{m['host']}:{m['port']}/{sub_path}"
        if parsed.query:
            target += f"?{parsed.query}"

        try:
            req = urllib.request.Request(
                target,
                headers={
                    "Accept":     "application/xml",
                    "User-Agent": "se-mtc-dashboard/1.2",
                },
            )
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                body = resp.read()
                ctype = resp.headers.get("Content-Type", "application/xml")

            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        except urllib.error.HTTPError as e:
            self.send_error(e.code, f"Upstream HTTP {e.code}: {e.reason}")
        except urllib.error.URLError as e:
            self.send_error(502, f"{m['host']}:{m['port']} - {e.reason}")
        except TimeoutError:
            self.send_error(504, f"Timeout {m['host']}")
        except Exception as e:
            self.send_error(500, f"Proxy error: {e}")


class ThreadedServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads      = True
    allow_reuse_address = True


def main():
    os.chdir(SCRIPT_DIR)
    if not (SCRIPT_DIR / "dashboard.html").exists():
        sys.stderr.write(
            f"ERROR: dashboard.html not found in {SCRIPT_DIR}\n"
            "Place dashboard.html next to server.py and try again.\n"
        )
        sys.exit(1)

    print("=" * 70)
    print("  SE Havacılık · MTConnect Dashboard")
    print("=" * 70)
    for mid, m in MACHINES.items():
        kind = m.get("type", "mill")
        print(f"   [{mid:8s}]  {m['name']:14s}  {kind:6s}  ->  {m['host']}:{m['port']}")
    print("-" * 70)
    print(f"   Dashboard:  http://localhost:{LISTEN_PORT}")
    print(f"   API:        /api/machines")
    print(f"   Proxy:      /mtc/<id>/<endpoint>")
    print("=" * 70)
    print("   Ctrl+C to stop\n")

    try:
        with ThreadedServer((LISTEN_HOST, LISTEN_PORT), DashboardHandler) as httpd:
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")


if __name__ == "__main__":
    main()
