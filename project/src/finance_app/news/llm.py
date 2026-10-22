"""OpenAI-compatible LLM 客户端：用户自带端点/密钥，密钥只存本地。"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, replace
from pathlib import Path
from urllib.parse import urlparse

from .._paths import ROOT

LOCAL = ROOT / "config" / "llm.local.json"
EXAMPLE = ROOT / "config" / "llm.example.json"


class LLMError(RuntimeError):
    pass


@dataclass
class LLMConfig:
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    timeout_seconds: int = 60
    temperature: float = 0.1
    max_tokens: int = 900

    @property
    def configured(self) -> bool:
        return bool(self.base_url.strip() and self.model.strip())


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def load_config() -> LLMConfig:
    raw = {}
    # 示例配置只用于文档；未显式保存/设置环境变量时不视为已配置，
    # 避免应用启动时误连本地 Ollama 并产生超时。
    if LOCAL.exists():
        raw.update(_read_json(LOCAL))
    cfg = LLMConfig(
        base_url=str(raw.get("base_url") or "").strip().rstrip("/"),
        api_key=str(raw.get("api_key") or "").strip(),
        model=str(raw.get("model") or "").strip(),
        timeout_seconds=int(raw.get("timeout_seconds") or 60),
        temperature=float(raw.get("temperature") if raw.get("temperature") is not None else 0.1),
        max_tokens=int(raw.get("max_tokens") or 900),
    )
    # 环境变量优先，便于临时切换/不落盘
    env = {
        "base_url": os.environ.get("FIN_LLM_BASE_URL"),
        "api_key": os.environ.get("FIN_LLM_API_KEY"),
        "model": os.environ.get("FIN_LLM_MODEL"),
        "timeout_seconds": os.environ.get("FIN_LLM_TIMEOUT"),
        "temperature": os.environ.get("FIN_LLM_TEMPERATURE"),
        "max_tokens": os.environ.get("FIN_LLM_MAX_TOKENS"),
    }
    for k, v in env.items():
        if v is None or str(v).strip() == "":
            continue
        try:
            if k in ("timeout_seconds", "max_tokens"):
                setattr(cfg, k, int(v))
            elif k == "temperature":
                cfg.temperature = float(v)
            elif k == "base_url":
                cfg.base_url = str(v).strip().rstrip("/")
            else:
                setattr(cfg, k, str(v).strip())
        except (TypeError, ValueError):
            # 非法环境变量值：忽略，保留文件/默认配置
            continue
    return cfg


def save_config(cfg: LLMConfig) -> None:
    LOCAL.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "base_url": cfg.base_url.strip().rstrip("/"),
        "api_key": cfg.api_key.strip(),
        "model": cfg.model.strip(),
        "timeout_seconds": int(cfg.timeout_seconds),
        "temperature": float(cfg.temperature),
        "max_tokens": int(cfg.max_tokens),
    }
    LOCAL.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        os.chmod(LOCAL, 0o600)
    except Exception:  # noqa: BLE001
        pass


def public_status(cfg: LLMConfig | None = None) -> dict:
    cfg = cfg or load_config()
    host = ""
    if cfg.base_url:
        try:
            host = urlparse(cfg.base_url).netloc
        except Exception:  # noqa: BLE001
            host = ""
    return {
        "configured": cfg.configured,
        "base_url": cfg.base_url,
        "host": host,
        "model": cfg.model,
        "has_key": bool(cfg.api_key),
        "timeout_seconds": cfg.timeout_seconds,
        "temperature": cfg.temperature,
        "max_tokens": cfg.max_tokens,
        "config_path": str(LOCAL),
    }


def _endpoint(base_url: str) -> str:
    base = base_url.strip().rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    if base.endswith("/v1"):
        return base + "/chat/completions"
    return base + "/v1/chat/completions"


def _validate_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise LLMError("base_url 必须是 http/https 且包含主机名")


def _extract_json(text: str) -> dict:
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```$", "", text)
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except Exception:  # noqa: BLE001
        pass
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        try:
            obj = json.loads(text[start:end + 1])
        except Exception:  # noqa: BLE001
            obj = None
        if isinstance(obj, dict):
            return obj
    raise LLMError("LLM 未返回 JSON 对象")


class LLMClient:
    def __init__(self, cfg: LLMConfig | None = None):
        self.cfg = cfg or load_config()

    def _chat(self, messages: list[dict], json_mode: bool = False) -> str:
        if not self.cfg.configured:
            raise LLMError("未配置 LLM：请在“模型接入”页填写 base_url 与 model")
        _validate_url(self.cfg.base_url)
        endpoint = _endpoint(self.cfg.base_url)
        body = {
            "model": self.cfg.model,
            "messages": messages,
            "temperature": self.cfg.temperature,
            "max_tokens": self.cfg.max_tokens,
            "stream": False,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.cfg.api_key:
            headers["Authorization"] = f"Bearer {self.cfg.api_key}"
        last_error = None
        retryable = True  # 超时/网络错误/5xx 允许一次退避重试
        for attempt in range(3):
            try:
                req = urllib.request.Request(endpoint, data=json.dumps(body).encode("utf-8"),
                                             headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=self.cfg.timeout_seconds) as resp:
                    raw = resp.read(4_000_000)
                data = json.loads(raw)
                choices = data.get("choices") or []
                if not choices:
                    raise LLMError(f"LLM 响应缺少 choices: {str(data)[:300]}")
                msg = choices[0].get("message") or {}
                content = msg.get("content")
                if isinstance(content, list):
                    content = "".join(str(x.get("text", "")) if isinstance(x, dict) else str(x) for x in content)
                if not content:
                    raise LLMError("LLM 返回空内容")
                return str(content)
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", "ignore")[:500]
                last_error = LLMError(f"HTTP {exc.code}: {detail}")
                # 某些服务不支持 response_format，去掉后重试一次
                if json_mode and exc.code in (400, 404, 422) and "response_format" in body:
                    body.pop("response_format", None)
                    continue
                # 服务端瞬时错误：退避 1.5s 重试一次
                if retryable and exc.code >= 500:
                    retryable = False
                    time.sleep(1.5)
                    continue
                break
            except Exception as exc:  # noqa: BLE001
                last_error = LLMError(f"{type(exc).__name__}: {exc}")
                # 超时/网络抖动：退避 1.5s 重试一次
                if retryable:
                    retryable = False
                    time.sleep(1.5)
                    continue
                break
        raise last_error or LLMError("LLM 调用失败")

    def chat_json(self, system: str, user: str) -> dict:
        content = self._chat([
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ], json_mode=True)
        return _extract_json(content)

    def test(self) -> dict:
        started = time.time()
        cfg = self.cfg
        if not cfg.configured:
            return {"ok": False, "error": "未配置 base_url/model", "latency_ms": 0}
        try:
            obj = self.chat_json(
                "You are a health check. Return only JSON.",
                'Return {"ok": true, "role": "healthcheck"}.',
            )
            return {"ok": True, "latency_ms": int((time.time() - started) * 1000),
                    "model": cfg.model, "sample": obj}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}",
                    "latency_ms": int((time.time() - started) * 1000), "model": cfg.model}
