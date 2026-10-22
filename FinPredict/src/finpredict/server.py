"""本地 HTTP API + 静态资源服务（供 pywebview 桌面窗口使用）。"""
from __future__ import annotations

import json
import mimetypes
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import data as data_mod
from . import model as model_mod
from .ai import AIClient, PROMPT_TEMPLATES, AIConfig, load_config, public_status, render_prompt, save_config, run_committee

if getattr(sys, "frozen", False):
    BASE = Path(sys.executable).resolve().parent
    INTERNAL = BASE / "_internal"
    WEB = (INTERNAL / "src" / "finpredict" / "web") if INTERNAL.is_dir() else (BASE / "src" / "finpredict" / "web")
else:
    BASE = Path(__file__).resolve().parents[2]
    WEB = Path(__file__).resolve().parent / "web"

_forecast_cache: dict[str, dict] = {}
_forecast_lock = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    server_version = "FinPredict/1.0"

    def log_message(self, fmt, *args):  # noqa: A003
        pass

    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False, default=str).encode("utf-8"),
                   "application/json; charset=utf-8")

    def _error(self, msg, code=400):
        self._json({"error": msg}, code)

    def do_GET(self):  # noqa: N802
        try:
            parsed = urlparse(self.path)
            path = parsed.path
            qs = parse_qs(parsed.query)
            one = lambda k, d=None: (qs.get(k) or [d])[0]  # noqa: E731

            if path in ("/", "/index.html"):
                return self._static("index.html")
            if path.startswith("/static/"):
                return self._static(path[len("/static/"):])
            if path == "/api/symbols":
                return self._json({"symbols": data_mod.DEFAULT_SYMBOLS,
                                   "intervals": list(data_mod.INTERVAL_MAP.keys()),
                                   "interval_labels": data_mod.INTERVAL_LABELS})
            if path == "/api/quote":
                sym = one("symbol", "^GSPC")
                interval = one("interval", "1d")
                return self._json(data_mod.get_quote(sym, interval))
            if path == "/api/forecast":
                sym = one("symbol", "^GSPC")
                interval = one("interval", "1d")
                model = one("model", "ensemble")
                if interval not in data_mod.INTERVAL_MAP:
                    return self._error(f"不支持的周期 {interval}")
                horizon = data_mod.INTERVAL_MAP[interval][3]
                key = f"{sym}|{interval}|{model}"
                with _forecast_lock:
                    if key not in _forecast_cache:
                        q = data_mod.get_quote(sym, interval)
                        if "error" in q:
                            _forecast_cache[key] = q
                        else:
                            # 用最近 2 年日线或全周期 K 线做回测+预判
                            import pandas as pd
                            idx = pd.to_datetime(q["dates"])
                            df = pd.DataFrame({c: q[c] for c in ["open", "high", "low", "close", "volume"] if c in q}, index=idx)
                            _forecast_cache[key] = model_mod.run_forecast(df, sym, interval, horizon, model)
                    return self._json(_forecast_cache[key])
            if path == "/api/backtest":
                sym = one("symbol", "^GSPC")
                interval = one("interval", "1d")
                model = one("model", "ensemble")
                if interval not in data_mod.INTERVAL_MAP:
                    return self._error(f"不支持的周期 {interval}")
                horizon = data_mod.INTERVAL_MAP[interval][3]
                q = data_mod.get_quote(sym, interval)
                if "error" in q:
                    return self._json(q)
                import pandas as pd
                idx = pd.to_datetime(q["dates"])
                df = pd.DataFrame({c: q[c] for c in ["open", "high", "low", "close", "volume"] if c in q}, index=idx)
                return self._json(model_mod.run_backtest(df, sym, interval, horizon, model))
            if path == "/api/ai/status":
                return self._json(public_status())
            if path == "/api/ai/templates":
                return self._json({"templates": [{"id": k, "name": v["name"], "desc": v.get("desc", "")}
                                                for k, v in PROMPT_TEMPLATES.items()]})
            return self._error("not found", 404)
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            return self._error(f"{type(exc).__name__}: {exc}", 500)

    def _read_json(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0 or n > 1_000_000:
            return {}
        return json.loads(self.rfile.read(n).decode("utf-8"))

    def do_POST(self):  # noqa: N802
        try:
            parsed = urlparse(self.path)
            path = parsed.path
            body = self._read_json()
            if path == "/api/ai/config":
                old = load_config()
                cfg = AIConfig(
                    base_url=str(body.get("base_url") or old.base_url).strip().rstrip("/"),
                    api_key=str(body.get("api_key") or "").strip() or old.api_key,
                    model=str(body.get("model") or old.model).strip(),
                    timeout_seconds=int(body.get("timeout_seconds") or old.timeout_seconds),
                    temperature=float(body.get("temperature") if body.get("temperature") is not None else old.temperature),
                    max_tokens=int(body.get("max_tokens") or old.max_tokens),
                )
                save_config(cfg)
                return self._json(public_status(cfg))
            if path == "/api/ai/test":
                return self._json(AIClient(load_config()).test())
            if path == "/api/ai/chat":
                tpl_id = str(body.get("template") or "trend_analysis")
                context = body.get("context") or {}
                rendered = render_prompt(tpl_id, context)
                if rendered is None:
                    return self._error(f"未知模板 {tpl_id}")
                if isinstance(rendered, tuple) and len(rendered) == 2 and isinstance(rendered[1], str) and rendered[1].startswith("模板变量缺失"):
                    return self._error(rendered[1])
                system, user = rendered
                custom = str(body.get("custom_prompt") or "").strip()
                if custom:
                    user = custom + "\n\n---\n" + user
                return self._json(AIClient(load_config()).chat(system, user))
            if path == "/api/ai/committee":
                # 多智能体委员会（借鉴 TradingAgents/ai-hedge-fund）：4 角色分析 + 投资经理综合
                ctx = body.get("context") or {}
                return self._json(run_committee(AIClient(load_config()), ctx))
            return self._error("not found", 404)
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            return self._error(f"{type(exc).__name__}: {exc}", 500)

    def _static(self, rel):
        target = (WEB / rel).resolve()
        if not target.is_relative_to(WEB.resolve()) or not target.is_file():
            return self._error("not found", 404)
        ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype == "application/javascript":
            ctype += "; charset=utf-8"
        return self._send(200, target.read_bytes(), ctype)


def serve(port: int = 8765) -> ThreadingHTTPServer:
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True, name="finpredict-http").start()
    return httpd


if __name__ == "__main__":
    s = serve(8765)
    print("serving http://127.0.0.1:8765")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        s.shutdown()
