"""每日更新：行情 → 补点/质量 → 新闻 → 分析 → 前向评估 → 受限权重更新。

行情抓取约 4 分钟；如只想更新新闻，用 --skip-market。
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable


def run(script: str, *args: str) -> int:
    print(f"\n>>> {script} {' '.join(args)}", flush=True)
    target = Path(script)
    if not target.is_absolute():
        target = (ROOT / script) if script.startswith("src") else (ROOT / "scripts" / script)
    p = subprocess.run([PY, str(target), *args], cwd=ROOT)
    print(f"<<< {script} exit={p.returncode}", flush=True)
    return p.returncode


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-market", action="store_true")
    ap.add_argument("--no-llm", action="store_true")
    args = ap.parse_args()

    if not args.skip_market:
        run("src/finance_app/data/fetch_market.py")
        run("patch_indices.py")
        run("finalize_quality.py")
        run("repair_ohlc.py")
        run("validate_all.py")

    run("sync_news.py")

    sys.path.insert(0, str(ROOT / "src"))
    from finance_app.data.store import DataStore
    from finance_app.news.analyzer import analyze_pending
    from finance_app.news.optimizer import evaluate_predictions, performance, update_weights
    from finance_app.news.store import NewsStore

    store = NewsStore()
    print("\n>>> analyze news", flush=True)
    print(analyze_pending(store, limit=30, use_llm=not args.no_llm), flush=True)
    print("\n>>> evaluate predictions", flush=True)
    print(evaluate_predictions(store, DataStore()), flush=True)
    print("\n>>> performance", flush=True)
    print(performance(store), flush=True)
    print("\n>>> update weights", flush=True)
    print(update_weights(store, DataStore()), flush=True)


if __name__ == "__main__":
    main()
