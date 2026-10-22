import sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from finance_app.news.sources import fetch_source, load_sources
from finance_app.news.store import NewsStore
from finance_app.news.analyzer import analyze_pending, rule_analyze
from finance_app.news.impact import score_news, combine, symbol_news_score

settings, sources = load_sources()
fed = next(s for s in sources if s.id == "fed")
r = fetch_source(fed, settings)
print("feed", fed.id, "items", len(r.items), "error", r.error, "fetched", r.fetched)
print("first", r.items[0].title if r.items else None, r.items[0].published_at if r.items else None)

with tempfile.TemporaryDirectory() as td:
    store = NewsStore(Path(td) / "news.db")
    print("upsert", store.upsert(r.items))
    print("stats", store.stats())
    print("analyze", analyze_pending(store, limit=5, use_llm=False))
    items = store.list(limit=3)
    for x in items:
        print("item", x["title"][:70], x["analysis"]["event_type"], x["analysis"]["direction"], x["analysis"]["confidence"])
    impact = score_news(store, hours=240)
    print("impact n", impact["n"], "global", impact["global"], "US", impact["regions"].get("US"))
    ns = symbol_news_score(impact, "^GSPC")
    print("symbol", ns)
    print("combine", combine(0.01, 5, ns["score"], impact))
