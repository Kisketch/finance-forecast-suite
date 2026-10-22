"""分析待处理新闻：默认优先 LLM，未配置时用规则评分。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from finance_app.news.analyzer import analyze_pending  # noqa: E402
from finance_app.news.impact import score_news  # noqa: E402
from finance_app.news.llm import load_config  # noqa: E402
from finance_app.news.store import NewsStore  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--no-llm", action="store_true")
    args = ap.parse_args()
    cfg = load_config()
    store = NewsStore()
    result = analyze_pending(store, limit=args.limit, use_llm=not args.no_llm)
    print(json.dumps({"llm_configured": cfg.configured, "result": result}, ensure_ascii=False, indent=2))
    print("\nimpact:", json.dumps(score_news(store, hours=72), ensure_ascii=False, indent=2)[:2500])


if __name__ == "__main__":
    main()
