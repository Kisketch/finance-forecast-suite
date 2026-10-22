import json, os, sys, threading, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8765"

RESP = {"news_weight": 0.16, "region_learned": {"US": 1.02}, "category_learned": {"tech": 1.03}, "rationale": "mock"}

class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass
    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        self.rfile.read(n)
        out = {"choices": [{"message": {"content": json.dumps(RESP)}}]}
        raw = json.dumps(out).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

srv = ThreadingHTTPServer(("127.0.0.1", 8899), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()

def post(path, body):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

try:
    print("save", post("/api/llm/config", {"base_url": "http://127.0.0.1:8899/v1", "model": "mock", "api_key": "test-key"}))
    print("test", post("/api/llm/test", {}))
    print("status", json.loads(urllib.request.urlopen(BASE + "/api/llm/status", timeout=10).read()))
finally:
    srv.shutdown()
    local = ROOT / "config" / "llm.local.json"
    if local.exists():
        local.unlink()
    print("cleaned", local.exists())
