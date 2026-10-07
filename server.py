#!/usr/bin/env python3
"""Local dev server: serves public/ and proxies the agent calls to LM Studio.

The browser never talks to LM Studio directly, so CORS does not have to be
enabled there and the model choice stays in one place.
"""
import json
import os
import re
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


# Only the numeric offer id is taken from the user's link; the request always goes to api.av.by.
AV_LINK = re.compile(r"^https?://(?:[a-z0-9-]+\.)?av\.by/(?:[^?#]*/)?(\d{6,12})/?(?:[?#].*)?$", re.I)
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"


def fetch_listing(url):
    m = AV_LINK.match(url.strip())
    if not m:
        return {"ok": False, "error": "bad_url"}
    req = urllib.request.Request("https://api.av.by/offers/" + m.group(1),
                                 headers={"User-Agent": UA, "Accept": "application/json"})
    d = None
    for _ in range(2):  # av.by answers 502 now and then; one retry is enough
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                d = json.load(r)
            break
        except urllib.error.HTTPError as e:
            if e.code in (404, 410):
                return {"ok": False, "error": "not_found"}
        except Exception:
            pass
    if not isinstance(d, dict):
        return {"ok": False, "error": "unavailable"}
    p = {x.get("name"): x.get("value") for x in d.get("properties", []) if isinstance(x, dict)}
    g = lambda k: str(p.get(k) or "").strip()
    title = " ".join(x for x in (g("brand"), g("model"), g("generation")) if x)
    year = str(d.get("year") or g("year"))
    facts = [("Цвет", g("color")), ("Кузов", g("body_type")),
             ("Двигатель", " ".join(x for x in (g("engine_capacity"), g("engine_type")) if x)),
             ("Коробка", g("transmission_type")), ("Привод", g("drive_type")),
             ("Пробег", g("mileage_km") + " км" if g("mileage_km") else ""), ("Состояние", g("condition"))]
    usd = ((d.get("price") or {}).get("usd") or {}).get("amount")
    head = "%s, %s г." % (title, year)
    lines = [head, ". ".join("%s: %s" % kv for kv in facts if kv[1]) + "."]
    if usd or d.get("locationName"):
        lines.append(" ".join(x for x in ("Цена: %s USD." % usd if usd else "", str(d.get("locationName") or "")) if x))
    lines += ["", str(d.get("description") or "Описания нет.").strip()]
    photos = [(ph.get("medium") or {}).get("url") for ph in d.get("photos", [])[:8] if isinstance(ph, dict)]
    return {"ok": True, "text": "\n".join(lines)[:6000], "title": head, "generation": g("generation"),
            "url": "https://cars.av.by/offer/" + m.group(1) if not str(d.get("publicUrl", "")).startswith("https://cars.av.by/") else d["publicUrl"],
            "photos": [u for u in photos if isinstance(u, str) and u.startswith("https://avcdn.av.by/")]}


# LM Studio is local: never send these calls through a system or env proxy.
LOCAL = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def pick_model():
    with LOCAL.open(LLM_URL + "/v1/models", timeout=4) as r:
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
        if self.path not in ("/api/chat", "/api/listing"):
            self._json(404, {"error": "not found"})
            return
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0 or n > MAX_BODY:
            self._json(413, {"error": "bad body size"})
            return
        raw = self.rfile.read(n)
        if self.path == "/api/listing":
            try:
                self._json(200, fetch_listing(str(json.loads(raw)["url"])))
            except Exception:
                self._json(200, {"ok": False, "error": "bad_url"})
            return
        try:
            messages = json.loads(raw)["messages"]
            payload = {"model": pick_model(), "messages": messages, "stream": True,
                       "temperature": 0.1, "max_tokens": 3000}
            if LLM_REASONING:
                payload["reasoning_effort"] = LLM_REASONING
            req = urllib.request.Request(
                LLM_URL + "/v1/chat/completions", data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"})
            upstream = LOCAL.open(req, timeout=600)
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
