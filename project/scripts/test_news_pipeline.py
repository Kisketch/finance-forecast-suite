import sys, tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
_TMP = tempfile.TemporaryDirectory()
import os
os.environ["FIN_NEWS_WEIGHTS_PATH"] = str(Path(_TMP.name) / "weights.json")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from finance_app.news.analyzer import analyze_pending, rule_analyze
from finance_app.news.impact import combine, score_news, symbol_news_score
from finance_app.news.optimizer import apply_proposal, performance, update_weights
from finance_app.news.sources import NewsItem
from finance_app.news.store import NewsStore

now = datetime.now(timezone.utc).isoformat(timespec="seconds")

def item(i, title, summary, source="fed", tier="official", region="US", category="monetary"):
    return NewsItem(f"id{i}", source, source.upper(), tier, region, category, "en", title, summary,
                    f"https://example.com/{i}", now, now)

with tempfile.TemporaryDirectory() as td:
    store = NewsStore(Path(td) / "news.db")
    items = [
        item(1, "Fed cuts rates by 50bp and launches stimulus", "The Federal Reserve cut rates to support growth."),
        item(2, "OPEC warns of oil supply disruption after attack", "OPEC said exports may fall.", "opec", "multilateral", "GLOBAL", "energy"),
        item(3, "China announces property stimulus and housing support", "Beijing announced support for the property market.", "gov_cn", "official", "CN", "policy"),
        item(4, "HKSAR opens temporary heat shelters", "Routine public service announcement.", "hkgov", "official", "HK", "policy"),
    ]
    store.upsert(items)
    res = analyze_pending(store, limit=10, use_llm=False)
    print("analyze", res)
    for r in store.list(limit=10):
        a = r["analysis"]
        print(r["title"][:60], "|", a["direction"], a["relevance"], a["event_type"], a["sectors"])

    impact = score_news(store, hours=24)
    print("impact n", impact["n"], "global", impact["global"], "US", impact["regions"].get("US"), "CN", impact["regions"].get("CN"))
    print("symbol", symbol_news_score(impact, "^GSPC"))
    print("combine", combine(0.01, 5, 0.5, impact))

    # 构造 25 条已实现预测：新闻命中率高、价格命中率低
    for i in range(25):
        pred = {
            "symbol": "^GSPC", "region": "US", "horizon": 5, "model": f"mock{i}",
            "last_date": "2026-01-01", "last_close": 100.0,
            "price_logret": 0.01 if i % 3 else -0.01,
            "news_score": 0.6 if i % 5 else -0.6,
            "combined_logret": 0.02 if i % 4 else -0.02,
            "weights": {}, "news_ids": [],
        }
        pid = store.save_prediction(pred)
        actual = 0.03 if i % 4 else -0.03
        store.set_actual(pid, actual)
    print("perf", performance(store))
    out = update_weights(store, None, min_samples=20)
    print("update", out)
    assert out["updated"]
    assert 0.05 <= out["after"]["news_weight"] <= 0.35
    prop = apply_proposal(store, {"news_weight": 0.99, "region_learned": {"US": 99}, "rationale": "test"})
    print("apply", prop)
    assert 0.05 <= prop["after"]["news_weight"] <= 0.35
    print("pipeline ok")
