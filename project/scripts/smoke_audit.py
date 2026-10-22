import json
import urllib.request

base = "http://127.0.0.1:8765"
checks = [
    ("/api/meta", ["as_of", "symbols", "rows"]),
    ("/api/overview", ["indices", "sectors", "breadth", "correlation", "signals"]),
    ("/api/universe", None),
    ("/api/series?symbol=%5EGSPC&range=1y", ["dates", "close", "rsi14"]),
    ("/api/sector?group=real_estate", ["members", "excluded", "relative_strength"]),
    ("/api/forecast?symbol=%5EGSPC&horizon=5&model=ensemble", ["point_price", "dir_acc", "skill_score", "folds"]),
    ("/api/audit", ["target", "historical_1949", "annual_regression", "interval_targeted", "strategy_eval", "rare_weight_experiment", "leakage_checks"]),
    ("/api/projects", ["projects", "compliance"]),
    ("/api/quality", ["per_symbol", "symbols_ok", "symbols_degraded"]),
    ("/api/analysts", ["views", "meta"]),
    ("/api/news?limit=5", ["items", "stats"]),
    ("/api/news/stats", ["total", "analyzed", "today"]),
    ("/api/news/impact?hours=48", ["global", "regions", "sectors", "top_events"]),
    ("/api/news/sources", ["sources"]),
    ("/api/news/performance", ["n", "note"]),
    ("/api/llm/status", ["configured", "model"]),
    ("/api/optimizer/status", ["weights", "performance", "history"]),
    ("/api/market/sync/status", ["running"]),
]
ok = 0
for path, keys in checks:
    with urllib.request.urlopen(base + path, timeout=180) as r:
        body = r.read()
        data = json.loads(body)
    if keys:
        missing = [k for k in keys if not isinstance(data, dict) or k not in data]
    else:
        missing = []
    status = "OK" if not missing else f"MISSING {missing}"
    print(f"{path:65s} {r.status} {len(body):>9,d} bytes  {status}")
    ok += 0 if missing else 1
print(f"passed {ok}/{len(checks)}")

a = json.loads(urllib.request.urlopen(base + "/api/audit", timeout=60).read())
print("audit target", json.dumps(a["target"], ensure_ascii=False))
print("strategy", json.dumps(a["strategy_eval"], ensure_ascii=False))
print("rare weights", json.dumps(a["rare_weight_experiment"], ensure_ascii=False))
print("projects", len(json.loads(urllib.request.urlopen(base + "/api/projects", timeout=60).read())["projects"]))
