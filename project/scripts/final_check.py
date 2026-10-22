import json
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
TEXT_EXT = {".py", ".js", ".css", ".html", ".md", ".json", ".yaml", ".yml", ".ps1", ".txt", ".csv"}
SKIP_DIRS = {"__pycache__", ".git", "raw", "reverse", "docs", "versions", "package"}
bad = []
files = 0
for p in ROOT.rglob("*"):
    if not p.is_file() or p.suffix.lower() not in TEXT_EXT:
        continue
    rel = p.relative_to(ROOT)
    if any(part in SKIP_DIRS for part in rel.parts):
        continue
    if p.stat().st_size > 20_000_000:
        continue
    if p.name == "final_check.py":
        continue
    try:
        t = p.read_text(encoding="utf-8")
    except Exception:
        continue
    files += 1
    for token in ["\ufffd", "锟斤拷", "ï¿½", "â€", "Ã¤", "Ã¥", "Ã©"]:
        if token in t:
            bad.append((str(rel), token, t.count(token)))
            break

required = [
    "README.md", "REA.md", "requirements.txt", "pyproject.toml", "run.ps1", "run_server.ps1",
    "data/processed/prices_long.csv", "data/metadata/data_quality.json",
    "data/news/news.db", "config/news_sources.yaml", "config/llm.example.json",
    "analysis/news-methodology.md", "analysis/accuracy-audit.md",
    "analysis/market/2026-market-outlook.md", "analysis/methodology.md",
    "analysis/analysts/broker-profiles.md", "analysis/reverse/tradingview-reverse-report.md",
    "reverse/tradingview/rea-analysis.json", "reverse/tradingview/summary.json",
    "docs/overview.png", "docs/forecast.png", "docs/audit.png",
]
missing = [f for f in required if not (ROOT / f).exists()]

json_bad = []
for rel in ["data/metadata/data_quality.json", "analysis/validation_report.json",
            "analysis/forecast_results.json", "analysis/advanced_audit.json",
            "analysis/rare_weight_experiment.json", "data/research/open_source_projects.json",
            "config/llm.example.json"]:
    p = ROOT / rel
    if p.exists():
        try:
            json.loads(p.read_text(encoding="utf-8"))
        except Exception as exc:
            json_bad.append((rel, str(exc)))

db = ROOT / "data" / "news" / "news.db"
with sqlite3.connect(db) as con:
    integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
    news_n = con.execute("SELECT COUNT(*) FROM news").fetchone()[0]
    pred_n = con.execute("SELECT COUNT(*) FROM predictions").fetchone()[0]
    source_n = con.execute("SELECT COUNT(*) FROM source_health").fetchone()[0]

print(json.dumps({
    "text_files_scanned": files,
    "mojibake_or_replacement": bad[:20],
    "mojibake_count": len(bad),
    "missing_required": missing,
    "json_errors": json_bad,
    "news_db": {"integrity": integrity, "news": news_n, "predictions": pred_n, "sources": source_n},
    "test_pollution": {
        "news_weights": (ROOT / "data/models/news_weights.json").exists(),
        "llm_local": (ROOT / "config/llm.local.json").exists(),
    },
}, ensure_ascii=False, indent=2))
