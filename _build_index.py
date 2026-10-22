"""Build FILE_INDEX.md and MANIFEST.csv for the full package.

Run from the package root:
    py _build_index.py
"""
from __future__ import annotations

import csv
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent

EXACT = {
    "PACKAGE_README.md": "Top-level package overview and quick start.",
    "USAGE.md": "Step-by-step usage guide.",
    "CHECK_REPORT.md": "Verification results and known issues.",
    "REASONING_AND_DECISIONS.md": "Auditable reasoning and decision log.",
    "INNOVATIONS.md": "Innovation list.",
    "VERSION_NOTES.md": "Version map and snapshot policy.",
    "DATA_DICTIONARY.md": "Dataset, database, and API data dictionary.",
    "LICENSES_AND_SOURCES.md": "Data sources, licenses, compliance.",
    "USER_REQUESTS.md": "Verbatim key user requirements.",
    "CHAT_LOG.md": "Chronological work log.",
    "FILE_INDEX.md": "This file: every packaged file with a description.",
    "MANIFEST.csv": "Machine-readable manifest with size and SHA-256.",
    "_build_index.py": "Tool that generated the index and manifest.",
    "versions/README.md": "Version snapshot overview.",
    "intermediate_materials/README.md": "Intermediate material overview.",
}

DIR_RULES = [
    ("project/data/raw/yahoo/", "Raw Yahoo Finance daily OHLCV snapshot."),
    ("project/data/raw/tencent/", "Tencent quote backfill snapshot."),
    ("project/data/raw/sina_", "Sina Finance backfill snapshot."),
    ("project/data/processed/", "Processed dataset."),
    ("project/data/metadata/", "Data-quality metadata."),
    ("project/data/analysts/", "Broker/analyst view JSON."),
    ("project/data/research/", "Open-source project review JSON."),
    ("project/data/news/", "News SQLite database and WAL files."),
    ("project/reverse/tradingview/", "TradingView reverse-engineering evidence."),
    ("project/analysis/", "Analysis report or machine-readable result."),
    ("project/scripts/diagnostics/", "Diagnostic/exploration script."),
    ("project/scripts/", "Project script."),
    ("project/src/finance_app/data/", "Data fetching and store module."),
    ("project/src/finance_app/analytics/", "Indicators, performance, correlation module."),
    ("project/src/finance_app/models/", "Forecast and advanced model module."),
    ("project/src/finance_app/news/", "Official news, LLM, impact, optimizer module."),
    ("project/src/finance_app/ui/", "HTTP API, pywebview shell, web UI."),
    ("project/docs/", "Screenshot."),
    ("versions/01_core_terminal/", "Version 01 snapshot."),
    ("versions/02_accuracy_audit/", "Version 02 snapshot."),
    ("versions/03_news_llm/", "Version 03 snapshot."),
    ("intermediate_materials/", "Intermediate material."),
]

KEY_NAMES = {
    "README.md": "Project README (Chinese).",
    "REA.md": "REA configuration and usage status.",
    "requirements.txt": "Python dependencies.",
    "pyproject.toml": "Python project metadata.",
    "run.ps1": "Launch the desktop app.",
    "run_server.ps1": "Launch the local API only.",
    "run_daily.ps1": "Daily market + news + evaluation + weight update.",
    "config/universe.yaml": "97-instrument universe.",
    "config/news_sources.yaml": "14 official news sources.",
    "config/llm.example.json": "OpenAI-compatible model config template.",
    "prices_long.csv": "Main long-format dataset (97 instruments, 685,774 rows).",
    "data_quality.json": "Per-instrument quality report.",
    "news.db": "News, analysis, predictions, and source health.",
    "accuracy-audit.md": "98.7% accuracy audit report.",
    "news-methodology.md": "Official news + LLM + weighting methodology.",
    "open-source-quant-review.md": "Open-source project review and corrections.",
    "advanced_audit.json": "Full accuracy audit results.",
    "forecast_results.json": "Walk-forward forecast results.",
    "validation_report.json": "OHLC and cross-source validation results.",
    "market_stats.json": "Index, sector, and correlation statistics.",
    "broker-profiles.md": "Broker and analyst profiles.",
    "2026-market-outlook.md": "2026 market outlook report.",
    "tradingview-reverse-report.md": "TradingView reverse-engineering report.",
    "rea-analysis.json": "419 MB REA evidence for TradingView Desktop.",
    "summary.json": "REA summary statistics and limitations.",
    "app_facts.json": "REA IPC channels, paths, keywords.",
}


def describe(rel: str) -> str:
    if rel in EXACT:
        return EXACT[rel]
    name = Path(rel).name
    if name in KEY_NAMES:
        return KEY_NAMES[name]
    for prefix, text in DIR_RULES:
        if rel.startswith(prefix):
            return f"{text} ({name})"
    if rel.startswith("project/"):
        return f"Project file ({name})."
    return f"Package file ({name})."


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


files = sorted(p for p in ROOT.rglob("*") if p.is_file() and p.name != "FILE_INDEX.md" and p.name != "MANIFEST.csv")
rows = []
lines = ["# File Index", "", f"Total files: {len(files)}", "", "| Path | Size (KB) | Description |", "|---|---:|---|"]
with open(ROOT / "MANIFEST.csv", "w", newline="", encoding="utf-8") as fh:
    writer = csv.writer(fh)
    writer.writerow(["path", "size_bytes", "sha256"])
    for p in files:
        rel = p.relative_to(ROOT).as_posix()
        size = p.stat().st_size
        lines.append(f"| `{rel}` | {size/1024:.1f} | {describe(rel)} |")
        writer.writerow([rel, size, sha256(p)])
(ROOT / "FILE_INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"indexed {len(files)} files")
