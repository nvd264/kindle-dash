#!/usr/bin/env python3
"""Kindle as a second screen: serve a Hyprland headless monitor as a grayscale PNG.

Run it, move windows onto monitor "kindle", then start "Second screen" on the Kindle.
Ctrl-C removes the virtual monitor.
"""
import atexit
import ipaddress
import signal
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

NAME, PORT = "kindle", 8765


def sh(*cmd, data=None):
    return subprocess.run(cmd, input=data, capture_output=True, check=True).stdout


def frame():
    raw = sh("grim", "-t", "ppm", "-o", NAME, "-")
    mean = float(sh("magick", "ppm:-", "-sample", "64x64!", "-colorspace", "Gray", "-format", "%[fx:mean]", "info:", data=raw))
    # e-ink reads best dark-on-light, so flip dark themes
    flip = ["-negate"] if mean < 0.5 else []
    return sh("magick", "ppm:-", "-colorspace", "Gray", *flip, "-define", "png:compression-level=1", "png:-", data=raw)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if not ipaddress.ip_address(self.client_address[0]).is_private:
            return self.send_error(403)
        try:
            body = frame()
        except subprocess.CalledProcessError as e:
            return self.send_error(500, e.stderr.decode()[:200])
        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass  # one request per second would flood the terminal


if __name__ == "__main__":
    sh("hyprctl", "output", "create", "headless", NAME)
    atexit.register(sh, "hyprctl", "output", "remove", NAME)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))  # so atexit also runs on kill
    # PW4 panel in portrait; 2x scale keeps text readable at 300ppi
    sh("hyprctl", "eval", f'hl.monitor({{ output = "{NAME}", mode = "1072x1448@1", position = "auto", scale = 2 }})')
    print(f"Move windows to monitor '{NAME}'. Serving http://0.0.0.0:{PORT}/ (Ctrl-C to stop)")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
