import json, os, sys, threading, tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

RESPONSE = {
    "event_type": "monetary_policy",
    "direction": 0.7,
    "magnitude": 0.6,
    "confidence": 0.8,
    "horizon_days": 1,
    "regions": ["US"],
    "sectors": ["finance", "real_estate"],
    "entities": ["Federal Reserve"],
    "novelty": 0.7,
    "rationale": "Mock: rate cut signal",
    "key_facts": ["mock fact"],
}

class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass
    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n)
        req = json.loads(body)
        content = json.dumps(RESPONSE, ensure_ascii=False)
        out = {"choices": [{"message": {"content": content}}]}
        raw = json.dumps(out).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

srv = ThreadingHTTPServer(("127.0.0.1", 8899), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
os.environ["FIN_LLM_BASE_URL"] = "http://127.0.0.1:8899/v1"
os.environ["FIN_LLM_MODEL"] = "mock-model"

from finance_app.news.llm import LLMClient, load_config, public_status
from finance_app.news.analyzer import llm_analyze
from finance_app.news.store import NewsStore
from finance_app.news.analyzer import analyze_pending

cfg = load_config()
print("status", public_status(cfg))
print("test", LLMClient(cfg).test())
item = {"source_name": "Federal Reserve", "source_tier": "official", "region": "US", "category": "monetary",
        "published_at": "2026-10-21T00:00:00+00:00", "title": "Fed cuts rates by 25bp",
        "summary": "The Federal Reserve cut rates and signaled easing.", "url": "https://example.com"}
print("llm", llm_analyze(item, LLMClient(cfg)))

with tempfile.TemporaryDirectory() as td:
    store = NewsStore(Path(td) / "news.db")
    from finance_app.news.sources import NewsItem
    it = NewsItem("x1", "fed", "Federal Reserve", "official", "US", "monetary", "en",
                  "Fed cuts rates by 25bp", "The Fed cut rates.", "https://example.com",
                  "2026-10-21T00:00:00+00:00", "2026-10-21T00:00:00+00:00")
    store.upsert([it])
    print("analyze", analyze_pending(store, limit=5, use_llm=True))
    print("saved", store.list(limit=1)[0]["analysis"])
srv.shutdown()
print("mock ok")
