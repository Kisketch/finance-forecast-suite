"""从 rea 证据中提取可核验的应用事实：端点、IPC、模块、功能关键词。"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

BASE = Path(r"C:\Users\Lgnatius\Documents\AI产出\工具\金融分析预测\reverse\tradingview")
SRC = BASE / "rea-analysis.json"
OUT = BASE / "app_facts.json"

KEYS = ["screener", "watchlist", "alert", "forecast", "technical", "fundamental", "portfolio",
        "broker", "chart", "indicator", "symbol", "news", "calendar", "replay", "paper",
        "strategy", "backtest", "pine", "drawing", "layout", "snapshot", "export", "order"]


def main() -> None:
    with SRC.open("rb") as fh:
        raw = fh.read()
    if raw[:2] == b"\xff\xfe":
        text = raw.decode("utf-16-le", "ignore")
    else:
        text = raw.decode("utf-8", "ignore")

    channels = sorted(set(re.findall(r'"channel"\s*:\s*"([^"]+)"', text)))
    urls = sorted(set(re.findall(r'https?://[A-Za-z0-9._~:/?#\[\]@!$&\'()*+,;=%-]{6,200}', text)))
    urls = [u for u in urls if "w3.org" not in u and "schema" not in u.lower()][:200]
    app_paths = sorted(set(re.findall(r'"path"\s*:\s*"(app/[^"]+)"', text)))
    module_keys = Counter(re.findall(r'"module_key"\s*:\s*"([^"]+)"', text))
    kw = {k: len(re.findall(k, text, flags=re.I)) for k in KEYS}

    facts = {
        "ipc_channels": channels,
        "urls_sample": urls,
        "app_paths_sample": app_paths[:120],
        "app_path_count": len(app_paths),
        "top_module_keys": module_keys.most_common(20),
        "keyword_hits": kw,
        "asar_entries": sorted(set(re.findall(r'"kind"\s*:\s*"asar-entry"[^}]*?"path"\s*:\s*"([^"]+)"', text)))[:80],
    }
    OUT.write_text(json.dumps(facts, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(facts, ensure_ascii=False, indent=2)[:7000])


if __name__ == "__main__":
    main()
