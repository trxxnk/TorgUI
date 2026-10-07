#!/usr/bin/env python3
"""Receiver for scripts/snap.js: the page POSTs lossless PNG frames to http://localhost:8099/<name>.

Usage: python3 scripts/frame_receiver.py [OUT_DIR]   (default: docs/demo-frames)
"""
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "demo-frames")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):  # lets the page load the capture script: eval(await (await fetch('http://localhost:8099/snap.js')).text())
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "snap.js"), "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", "text/javascript; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        name = "".join(c for c in os.path.basename(self.path) if c.isalnum() or c in "-_") or "frame"
        with open(os.path.join(OUT, name + ".png"), "wb") as f:
            f.write(body)
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    HTTPServer(("127.0.0.1", 8099), Handler).serve_forever()
