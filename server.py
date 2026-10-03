#!/usr/bin/env python3
"""Local dev server: serves public/ and proxies the agent calls to LM Studio.

The browser never talks to LM Studio directly, so CORS does not have to be
enabled there and the model choice stays in one place.
"""
import json
import os
import sys
import urllib.error
import urllib.request
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "public")
PORT = int(os.environ.get("PORT", "8734"))
LLM_URL = os.environ.get("LMSTUDIO_URL", "http://localhost:1234").rstrip("/")
# Substring of the model id to prefer among the models LM Studio lists.
LLM_MODEL = os.environ.get("LLM_MODEL", "bonsai")
# "none" skips the model's thinking phase: much faster, and extraction does not need it.
LLM_REASONING = os.environ.get("LLM_REASONING", "none")
MAX_BODY = 256 * 1024


def pick_model():
    with urllib.request.urlopen(LLM_URL + "/v1/models", timeout=4) as r:
        ids = [m["id"] for m in json.load(r).get("data", [])]
    chat = [i for i in ids if "embed" not in i.lower()]
    for i in chat:
        if LLM_MODEL.lower() in i.lower():
            return i
    if not chat:
        raise RuntimeError("LM Studio lists no chat models")
    return chat[0]


class Handler(SimpleHTTPRequestHandler):
    def _json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):
        if self.path == "/api/agent":
            try:
                self._json(200, {"ok": True, "model": pick_model(), "url": LLM_URL})
            except Exception as e:  # LM Studio down, no models loaded
                self._json(200, {"ok": False, "error": str(e)})
            return
        super().do_GET()

    def do_POST(self):
        if self.path != "/api/chat":
            self._json(404, {"error": "not found"})
            return
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0 or n > MAX_BODY:
            self._json(413, {"error": "bad body size"})
            return
        try:
            messages = json.loads(self.rfile.read(n))["messages"]
            payload = {"model": pick_model(), "messages": messages, "stream": True,
                       "temperature": 0.1, "max_tokens": 3000}
            if LLM_REASONING:
                payload["reasoning_effort"] = LLM_REASONING
            req = urllib.request.Request(
                LLM_URL + "/v1/chat/completions", data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"})
            upstream = urllib.request.urlopen(req, timeout=600)
        except urllib.error.HTTPError as e:
            self._json(502, {"error": "LM Studio: %s %s" % (e.code, e.read()[:300].decode("utf8", "replace"))})
            return
        except Exception as e:
            self._json(502, {"error": str(e)})
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.end_headers()
        try:
            with upstream:
                for line in upstream:  # SSE is line-based; forward as it arrives
                    self.wfile.write(line)
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass  # browser pressed Stop

    def log_message(self, fmt, *args):
        if args and "/api/" in str(args[0]):
            sys.stderr.write("%s\n" % (fmt % args))


if __name__ == "__main__":
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), partial(Handler, directory=ROOT))
    print("E34 inspector: http://localhost:%d  (LM Studio: %s, model ~ %s)" % (PORT, LLM_URL, LLM_MODEL))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
