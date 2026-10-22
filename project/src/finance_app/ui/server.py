"""本地 HTTP API + 静态资源服务（供 pywebview 桌面窗口使用）。"""
from __future__ import annotations

import json
import mimetypes
import os
import subprocess
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .._paths import ROOT
from ..data.store import DataStore
from ..news.analyzer import analyze_pending
from ..news.impact import load_weights, predict_combined, score_news
from ..news.llm import LLMClient, LLMConfig, load_config, public_status, save_config
from ..news.optimizer import apply_proposal, evaluate_predictions, llm_proposal, performance, update_weights
from ..news.service import get_service, start_scheduler

WEB = ROOT / "src" / "finance_app" / "ui" / "web"
ANALYSTS = ROOT / "data" / "analysts" / "analyst_views.json"
QUALITY = ROOT / "data" / "metadata" / "data_quality.json"
AUDIT = ROOT / "analysis" / "advanced_audit.json"
PROJECTS = ROOT / "data" / "research" / "open_source_projects.json"

_store: DataStore | None = None
_store_lock = threading.Lock()
_forecast_cache: dict[str, dict] = {}
_market_sync = {"running": False, "started_at": None, "finished_at": None, "ok": None, "log": ""}
_market_lock = threading.Lock()


def _run_market_sync() -> None:
    commands = [
        ROOT / "src" / "finance_app" / "data" / "fetch_market.py",
        ROOT / "scripts" / "patch_indices.py",
        ROOT / "scripts" / "finalize_quality.py",
        ROOT / "scripts" / "repair_ohlc.py",
        ROOT / "scripts" / "validate_all.py",
    ]
    lines = []
    ok = True
    for target in commands:
        lines.append(f">>> {target.name}")
        try:
            p = subprocess.run([sys.executable, str(target)], cwd=ROOT, capture_output=True,
                               text=True, timeout=1200)
            lines.append((p.stdout or "")[-2000:])
            if p.stderr:
                lines.append((p.stderr or "")[-1000:])
            lines.append(f"<<< exit={p.returncode}")
            if p.returncode != 0 and target.name != "fetch_market.py":
                ok = False
        except Exception as exc:  # noqa: BLE001
            ok = False
            lines.append(f"ERROR {type(exc).__name__}: {exc}")
        with _market_lock:
            _market_sync["log"] = "\n".join(lines)[-6000:]
    with _market_lock:
        _market_sync.update({"running": False, "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                             "ok": ok, "log": "\n".join(lines)[-6000:]})
    global _store
    with _store_lock:
        _store = None
    _forecast_cache.clear()


def market_sync_status() -> dict:
    with _market_lock:
        return dict(_market_sync)


def start_market_sync() -> dict:
    with _market_lock:
        if _market_sync["running"]:
            return dict(_market_sync)
        _market_sync.update({"running": True, "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                             "finished_at": None, "ok": None, "log": "starting..."})
    threading.Thread(target=_run_market_sync, daemon=True, name="fin-market-sync").start()
    return market_sync_status()


def get_store() -> DataStore:
    global _store
    with _store_lock:
        if _store is None:
            _store = DataStore()
        return _store


class Handler(BaseHTTPRequestHandler):
    server_version = "FinTerminal/1.0"

    def log_message(self, fmt: str, *args) -> None:  # noqa: A003
        pass

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code: int = 200) -> None:
        self._send(code, json.dumps(obj, ensure_ascii=False, default=str).encode("utf-8"),
                   "application/json; charset=utf-8")

    def _error(self, message: str, code: int = 400) -> None:
        self._json({"error": message}, code)

    def do_GET(self) -> None:  # noqa: N802
        try:
            parsed = urlparse(self.path)
            path = parsed.path
            qs = parse_qs(parsed.query)
            one = lambda k, d=None: (qs.get(k) or [d])[0]  # noqa: E731

            if path == "/" or path == "/index.html":
                return self._static("index.html")
            if path.startswith("/static/"):
                return self._static(path[len("/static/"):])
            if path == "/api/meta":
                ds = get_store()
                return self._json({
                    "as_of": ds.meta.get("date_max"),
                    "symbols": ds.meta.get("symbols_ok"),
                    "rows": ds.meta.get("rows_total"),
                    "source": ds.meta.get("source"),
                    "generated_at": ds.meta.get("generated_at"),
                })
            if path == "/api/overview":
                return self._json(get_store().overview())
            if path == "/api/universe":
                return self._json(get_store().universe())
            if path == "/api/series":
                sym = one("symbol", "^GSPC")
                return self._json(get_store().series(sym, one("range", "1y")))
            if path == "/api/series/batch":
                syms = [s for s in (one("symbols") or "").split(",") if s][:50]
                rng = one("range", "1m")
                ds = get_store()
                out = {}
                for s in syms:
                    data = ds.series(s, rng)
                    if data:
                        out[s] = {k: data.get(k) for k in ("dates", "close", "rsi14")}
                return self._json({"range": rng, "series": out})
            if path == "/api/sector":
                return self._json(get_store().sector(one("group", "real_estate")))
            if path == "/api/forecast":
                sym = one("symbol", "^GSPC")
                h = int(one("horizon", "5"))
                model = one("model", "ridge")
                key = f"{sym}|{h}|{model}"
                if key not in _forecast_cache:
                    _forecast_cache[key] = get_store().forecast(sym, h, model)
                return self._json(_forecast_cache[key])
            if path == "/api/forecast/enhanced":
                sym = one("symbol", "^GSPC")
                h = int(one("horizon", "5"))
                if h not in (1, 5, 20):
                    return self._error("horizon must be 1, 5, or 20")
                from ..models.ml_advanced import run_enhanced_forecast
                df = get_store().get(sym)
                if df is None:
                    return self._error("unknown symbol")
                return self._json(run_enhanced_forecast(df, sym, horizon=h))
            if path == "/api/audit/enhanced":
                audit_path = ROOT / "analysis" / "enhanced_audit.json"
                if audit_path.exists():
                    return self._json(json.loads(audit_path.read_text(encoding="utf-8")))
                return self._json({"error": "enhanced audit not generated; run scripts/run_enhanced_audit.py"})
            if path == "/api/fundamentals":
                sym = one("symbol", "AAPL")
                from ..data.sec_edgar import get_facts, derive_ratios
                facts = get_facts(sym)
                if "error" not in facts:
                    facts["ratios"] = derive_ratios(facts)
                return self._json(facts)
            if path == "/api/analysts":
                if ANALYSTS.exists():
                    return self._json(json.loads(ANALYSTS.read_text(encoding="utf-8")))
                return self._json({"meta": {}, "views": []})
            if path == "/api/quality":
                if QUALITY.exists():
                    return self._json(json.loads(QUALITY.read_text(encoding="utf-8")))
                return self._json({})
            if path == "/api/audit":
                if AUDIT.exists():
                    return self._json(json.loads(AUDIT.read_text(encoding="utf-8")))
                return self._json({"error": "audit not generated; run scripts/run_advanced_audit.py"})
            if path == "/api/projects":
                if PROJECTS.exists():
                    return self._json(json.loads(PROJECTS.read_text(encoding="utf-8")))
                return self._json({"projects": [], "compliance": []})
            if path == "/api/news":
                analyzed_raw = one("analyzed")
                analyzed = None if analyzed_raw is None else str(analyzed_raw).lower() in ("1", "true", "yes")
                hours = int(one("hours", "0") or 0) or None
                items = get_service().store.list(
                    limit=int(one("limit", "80")), region=one("region"), category=one("category"),
                    tier=one("tier"), analyzed=analyzed, hours=hours, q=one("q"),
                )
                return self._json({"items": items, "stats": get_service().store.stats()})
            if path == "/api/news/stats":
                return self._json(get_service().status()["news"])
            if path == "/api/news/impact":
                return self._json(score_news(get_service().store, hours=int(one("hours", "48"))))
            if path == "/api/news/sources":
                return self._json({"sources": get_service().status()["source_health"]})
            if path == "/api/news/performance":
                return self._json(performance(get_service().store))
            if path == "/api/llm/status":
                return self._json(public_status(load_config()))
            if path == "/api/optimizer/status":
                svc = get_service()
                w = load_weights()
                return self._json({
                    "weights": w, "performance": performance(svc.store),
                    "history": (w.get("history") or [])[-20:],
                })
            if path == "/api/market/sync/status":
                return self._json(market_sync_status())
            return self._error("not found", 404)
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            return self._error(f"{type(exc).__name__}: {exc}", 500)

    def _read_json(self) -> dict:
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except Exception:  # noqa: BLE001
            n = 0
        if n <= 0:
            return {}
        if n > 1_000_000:
            raise ValueError("request body too large")
        raw = self.rfile.read(n)
        obj = json.loads(raw.decode("utf-8"))
        return obj if isinstance(obj, dict) else {}

    def do_POST(self) -> None:  # noqa: N802
        try:
            parsed = urlparse(self.path)
            path = parsed.path
            body = self._read_json()
            svc = get_service()
            if path == "/api/news/sync":
                return self._json(svc.sync())
            if path == "/api/market/sync":
                return self._json(start_market_sync())
            if path == "/api/news/analyze":
                return self._json(svc.analyze(limit=int(body.get("limit", 10)),
                                               use_llm=bool(body.get("use_llm", True)),
                                               reanalyze=bool(body.get("reanalyze", False))))
            if path == "/api/news/predict":
                sym = str(body.get("symbol") or "^GSPC")
                h = int(body.get("horizon", 5))
                if h not in (1, 5, 20):
                    return self._error("horizon must be 1, 5, or 20")
                model = str(body.get("model") or "ensemble")
                if model not in ("ridge", "gbm", "rf", "ensemble"):
                    return self._error("unknown model")
                return self._json(predict_combined(svc.store, get_store(), sym, h, model))
            if path == "/api/news/evaluate":
                ev = evaluate_predictions(svc.store, get_store())
                return self._json({"evaluation": ev, "performance": performance(svc.store)})
            if path == "/api/optimizer/update":
                return self._json(update_weights(svc.store, get_store()))
            if path == "/api/optimizer/propose":
                cfg = load_config()
                if not cfg.configured:
                    return self._error("LLM 未配置")
                return self._json({"proposal": llm_proposal(LLMClient(cfg), svc.store)})
            if path == "/api/optimizer/apply":
                proposal = body.get("proposal") if isinstance(body.get("proposal"), dict) else body
                return self._json(apply_proposal(svc.store, proposal))
            if path == "/api/llm/test":
                return self._json(LLMClient(load_config()).test())
            if path == "/api/llm/config":
                old = load_config()
                base_url = str(body.get("base_url") or old.base_url).strip()
                from urllib.parse import urlparse as _urlparse
                p = _urlparse(base_url)
                if p.scheme not in ("http", "https") or not p.hostname:
                    return self._error("base_url 必须是 http/https 且包含主机名")
                cfg = LLMConfig(
                    base_url=base_url.rstrip("/"), model=str(body.get("model") or old.model).strip(),
                    api_key=str(body.get("api_key") or "").strip() or old.api_key,
                    timeout_seconds=int(body.get("timeout_seconds") or old.timeout_seconds),
                    temperature=float(body.get("temperature") if body.get("temperature") is not None else old.temperature),
                    max_tokens=int(body.get("max_tokens") or old.max_tokens),
                )
                save_config(cfg)
                return self._json(public_status(cfg))
            return self._error("not found", 404)
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            return self._error(f"{type(exc).__name__}: {exc}", 500)

    def _static(self, rel: str) -> None:
        target = (WEB / rel).resolve()
        if not target.is_relative_to(WEB.resolve()) or not target.is_file():
            return self._error("not found", 404)
        ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
            ctype = f"{ctype}; charset=utf-8"
        return self._send(200, target.read_bytes(), ctype)


def serve(port: int = 8765) -> ThreadingHTTPServer:
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True, name="fin-http")
    t.start()
    # 可选后台同步：默认开启；测试/离线时设置 FIN_DISABLE_AUTOSYNC=1。
    try:
        start_scheduler(int(os.environ.get("FIN_NEWS_SYNC_MINUTES", "15")))
    except Exception:  # noqa: BLE001
        pass
    return httpd


if __name__ == "__main__":
    import time
    s = serve(8765)
    print("serving http://127.0.0.1:8765")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        s.shutdown()
