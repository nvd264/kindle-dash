#!/usr/bin/env python3
"""Serve the dashboard PNG to the Kindle over the LAN, re-rendering every 5 min.

The public-repo GH Actions cron is heavily delayed (runs ~hourly at best), so
the PC is the fast source of updates. The Kindle (dash.sh) fetches this first
and falls back to the GitHub Pages URL when unreachable, e.g. away from home.

Run with the venv python so render.py's Pillow import works:
    .venv/bin/python pc/dashboard.py
Ctrl-C stops it.
"""
import ipaddress
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out" / "dash.png"
LAN_IP = "192.168.1.170"  # must match dash.sh's LAN_URL
TTL = 300  # seconds, matches the Kindle's INTERVAL
lock = threading.Lock()


def image_bytes():
    with lock:  # one render at a time even if the Kindle and a browser hit it together
        stale = not OUT.exists() or time.time() - OUT.stat().st_mtime > TTL
        if stale:
            try:
                subprocess.run([sys.executable, str(ROOT / "render.py"), str(OUT)], check=True, cwd=ROOT)
            except subprocess.CalledProcessError:
                # API down: serve the last good frame instead of erroring out
                if not OUT.exists():
                    raise
    return OUT.read_bytes()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if not ipaddress.ip_address(self.client_address[0]).is_private:
            return self.send_error(403)
        try:
            body = image_bytes()
        except Exception as e:
            return self.send_error(500, str(e))
        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass  # one request per 5 min; keep the terminal quiet


if __name__ == "__main__":
    print(f"Serving {OUT} at http://{LAN_IP}:8766/dash.png (re-render every {TTL}s, Ctrl-C to stop)")
    ThreadingHTTPServer((LAN_IP, 8766), Handler).serve_forever()
