import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from finance_app.ui.server import serve  # noqa: E402

port = 8877
srv = serve(port)
time.sleep(1.0)
base = f"http://127.0.0.1:{port}"
endpoints = [
    "/api/meta", "/api/overview", "/api/universe", "/api/series?symbol=%5EGSPC&range=1y",
    "/api/sector?group=real_estate", "/api/analysts", "/api/quality",
    "/api/forecast?symbol=%5EGSPC&horizon=5&model=ridge",
]
for ep in endpoints:
    t0 = time.time()
    with urllib.request.urlopen(base + ep, timeout=120) as r:
        body = r.read()
        data = json.loads(body)
        keys = list(data.keys())[:6] if isinstance(data, dict) else type(data).__name__
        print(f"{ep:55s} {r.status} {len(body):>10,d} bytes {time.time()-t0:5.1f}s keys={keys}")
srv.shutdown()
print("smoke ok")
