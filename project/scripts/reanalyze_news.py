import json, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from finance_app.news.analyzer import analyze_pending
from finance_app.news.impact import score_news
from finance_app.news.store import NewsStore

store = NewsStore()
print("reset", store.reset_analysis())
print(json.dumps(analyze_pending(store, limit=300, use_llm=False), ensure_ascii=False, indent=2))
impact = score_news(store, hours=72)
print(json.dumps({k: impact[k] for k in ("n", "global", "regions", "sectors")}, ensure_ascii=False, indent=2))
for e in impact["top_events"][:8]:
    print(e["direction"], e["confidence"], e["event_type"], e["source_name"], "|", e["title"][:100])
