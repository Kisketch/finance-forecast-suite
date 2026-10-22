"""新闻服务：同步、分析、状态与可选后台调度。"""
from __future__ import annotations

import os
import threading
import time
from datetime import datetime, timezone

from .analyzer import analyze_pending
from .impact import load_weights
from .llm import load_config, public_status
from .sources import fetch_all, load_sources
from .store import NewsStore

_service: "NewsService | None" = None
_service_lock = threading.Lock()
_scheduler_started = False


class NewsService:
    def __init__(self):
        self.store = NewsStore()
        self._sync_lock = threading.Lock()
        self.last_sync: str | None = None
        self.last_sync_result: dict | None = None

    def sync(self) -> dict:
        with self._sync_lock:
            started = time.time()
            settings, sources = load_sources()
            if not sources:
                return {"ok": False, "error": "没有启用的新闻源"}
            results = fetch_all(sources, settings)
            total_new = total_kept = 0
            per_source = []
            for r in results:
                up = self.store.upsert(r.items)
                self.store.record_health(r, len(r.items))
                total_new += up["new"]
                total_kept += len(r.items)
                per_source.append({
                    "source_id": r.source.id, "name": r.source.name, "tier": r.source.tier,
                    "ok": r.error is None, "fetched": r.fetched, "kept": len(r.items),
                    "new": up["new"], "error": r.error, "elapsed_ms": r.elapsed_ms,
                })
            self.last_sync = datetime.now(timezone.utc).isoformat(timespec="seconds")
            self.last_sync_result = {
                "ok": True, "new": total_new, "kept": total_kept, "sources": len(results),
                "sources_ok": sum(1 for r in results if r.error is None),
                "sources_failed": sum(1 for r in results if r.error is not None),
                "elapsed_ms": int((time.time() - started) * 1000),
                "per_source": per_source, "at": self.last_sync,
            }
            return self.last_sync_result

    def analyze(self, limit: int = 10, use_llm: bool = True, reanalyze: bool = False) -> dict:
        return analyze_pending(self.store, limit=limit, use_llm=use_llm, reanalyze=reanalyze)

    def status(self) -> dict:
        cfg = load_config()
        return {
            "news": self.store.stats(),
            "source_health": self.store.source_health(),
            "llm": public_status(cfg),
            "weights": load_weights(),
            "last_sync": self.last_sync,
            "last_sync_result": self.last_sync_result,
        }


def get_service() -> NewsService:
    global _service
    with _service_lock:
        if _service is None:
            _service = NewsService()
        return _service


def start_scheduler(interval_minutes: int = 15) -> None:
    global _scheduler_started
    if _scheduler_started or os.environ.get("FIN_DISABLE_AUTOSYNC", "").lower() in ("1", "true", "yes"):
        return
    _scheduler_started = True
    interval = max(5, int(interval_minutes)) * 60
    auto_llm = os.environ.get("FIN_NEWS_AUTO_ANALYZE", "rule").lower() == "llm"

    def loop() -> None:
        # 启动后先等 2 秒，避免和窗口创建争抢
        time.sleep(2)
        while True:
            try:
                svc = get_service()
                svc.sync()
                svc.analyze(limit=10, use_llm=auto_llm)
            except Exception:  # noqa: BLE001
                pass
            time.sleep(interval)

    t = threading.Thread(target=loop, daemon=True, name="fin-news-sync")
    t.start()
