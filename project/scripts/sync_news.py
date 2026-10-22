"""同步官方新闻源到本地 SQLite。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from finance_app.news.service import get_service  # noqa: E402


def main() -> None:
    svc = get_service()
    result = svc.sync()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("\nstats:", json.dumps(svc.store.stats(), ensure_ascii=False))


if __name__ == "__main__":
    main()
