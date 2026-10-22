import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from finance_app.news.sources import fetch_source, load_sources
from finance_app.news.store import NewsStore

settings, sources = load_sources()
store = NewsStore()
for sid in ["iea", "boe", "eia"]:
    src = next((s for s in sources if s.id == sid), None)
    if not src:
        continue
    r = fetch_source(src, settings)
    deleted = store.delete_source(sid) if sid == "iea" else 0
    up = store.upsert(r.items)
    store.record_health(r, len(r.items))
    print(sid, "deleted", deleted, "fetched", len(r.items), "new", up["new"], "error", r.error)
    for x in r.items[:3]:
        print("  ", x.published_at, x.title[:90])
