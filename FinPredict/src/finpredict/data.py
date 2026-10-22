"""实时行情数据获取：多源降级，无需 API Key，联网即用。

数据源优先级：
1. 腾讯行情（web.ifzq.gtimg.cn）：A 股/港股/指数，免费稳定，支持日 K + 60 分钟 K；
2. yfinance：美股/美指数/商品/外汇，免费但易被 Yahoo 限流（带 3 次重试 + 退避）。

支持周期：1h / 3h / 1d / 1月。3h 由 60m 聚合，1月由 21 个交易日近似。
所有源失败时返回友好错误，不崩溃。
"""
from __future__ import annotations

import json
import re
import ssl
import time
import urllib.request
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

# 周期 -> (腾讯周期键, 聚合倍数, 默认回看天数, 预测 horizon)
INTERVAL_MAP = {
    "1h":  ("m60", 1, 30, 1),
    "3h":  ("m60", 3, 60, 3),
    "1d":  ("day", 1, 400, 1),
    "1mo": ("day", 1, 500, 21),
}
INTERVAL_LABELS = {"1h": "1 小时", "3h": "3 小时", "1d": "1 天", "1mo": "1 个月"}

DEFAULT_SYMBOLS = [
    "000001.SS", "399001.SZ", "399006.SZ", "000300.SS",
    "^HSI", "^HSTECH", "0700.HK", "9988.HK", "3690.HK",
    "^GSPC", "^IXIC", "^DJI", "^VIX", "DX-Y.NYB",
    "AAPL", "MSFT", "NVDA", "TSLA", "GOOGL", "AMZN",
    "600519.SS", "000858.SZ", "601318.SS", "300750.SZ",
    "CL=F", "GC=F", "SI=F",
]

_cache: dict[str, tuple[float, pd.DataFrame]] = {}
_CACHE_TTL = 60
_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE


def _tencent_code(symbol: str) -> str | None:
    """Yahoo 符号 -> 腾讯代码；只支持 A 股/港股。"""
    if symbol.endswith(".SS"):
        return "sh" + symbol[:-3]
    if symbol.endswith(".SZ"):
        return "sz" + symbol[:-3]
    if symbol.endswith(".HK"):
        code = symbol[:-3]
        return "hk" + code.zfill(5)
    if symbol in ("^HSI",):
        return "hkHSI"
    if symbol in ("^HSTECH",):
        return "hkHSTECH"
    return None


def _http(url: str, timeout: int = 15) -> str:
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "http://gu.qq.com/" if "gtimg.cn" in url else "https://finance.yahoo.com/",
        "Accept": "*/*",
    })
    with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as r:
        return r.read(4_000_000).decode("utf-8", "replace")


def _tencent_kline(code: str, tencent_key: str, lookback_days: int) -> pd.DataFrame:
    """从腾讯拉 K 线。日 K 用 fqkline（不带 start 拿全量，最多 640 条≈2.5年），
    分钟用 mkline（拿近期 640 根）。返回标准 OHLCV。"""
    if tencent_key == "day":
        url = f"http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={code},{tencent_key},,,640,qfq"
    else:  # m60 分钟
        url = f"http://web.ifzq.gtimg.cn/appstock/app/kline/mkline?param={code},{tencent_key},,640"
    txt = _http(url)
    d = json.loads(txt)
    node = d.get("data", {}).get(code, {}) if isinstance(d.get("data"), dict) else d.get("data", {})
    kname = tencent_key if tencent_key in node else (f"qfq{tencent_key}" if f"qfq{tencent_key}" in node else None)
    if not kname:
        raise ValueError(f"腾讯返回无 {tencent_key} 数据")
    rows = node[kname]
    # 腾讯格式：[date, open, close, high, low, volume] —— 注意 close 在 index 2
    data = [(r[0], float(r[1]), float(r[3]), float(r[4]), float(r[2]), float(r[5]) if len(r) > 5 else 0.0) for r in rows]
    df = pd.DataFrame(data, columns=["date", "open", "high", "low", "close", "volume"])
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    df = df[~df.index.duplicated(keep="last")]
    return df


def _aggregate(df: pd.DataFrame, mult: int) -> pd.DataFrame:
    if mult <= 1 or df.empty:
        return df
    agg = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    rule = f"{mult}h"
    return df.resample(rule, label="left", closed="left").agg(agg).dropna()


def _yfinance_kline(symbol: str, tencent_key: str, lookback_days: int) -> pd.DataFrame:
    """yfinance 拉取，带 3 次重试 + 退避。"""
    import yfinance as yf
    yf_interval = {"m60": "60m", "day": "1d"}.get(tencent_key, "1d")
    period = {"m60": f"{max(5, lookback_days // 6)}d", "day": f"{max(60, lookback_days)}d"}.get(tencent_key, "1y")
    last_exc = None
    for attempt in range(3):
        try:
            raw = yf.download(symbol, period=period, interval=yf_interval, auto_adjust=True,
                              progress=False, threads=False, timeout=15)
            if raw is None or raw.empty:
                raise ValueError("empty")
            if isinstance(raw.columns, pd.MultiIndex):
                raw.columns = [c[0] for c in raw.columns]
            raw = raw.rename(columns=str.lower)
            keep = [c for c in ["open", "high", "low", "close", "volume"] if c in raw.columns]
            df = raw[keep].copy()
            idx = pd.to_datetime(df.index)
            if getattr(idx, "tz", None) is not None:
                idx = idx.tz_localize(None)
            df.index = idx.normalize() if yf_interval == "1d" else idx
            df = df[~df.index.duplicated(keep="last")].sort_index()
            return df
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            time.sleep(1.5 * (attempt + 1))
    raise last_exc


def _add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    c = df["close"].astype(float)
    df = df.copy()
    df["ma5"] = c.rolling(5, min_periods=1).mean()
    df["ma20"] = c.rolling(20, min_periods=1).mean()
    df["ma60"] = c.rolling(60, min_periods=1).mean()
    std20 = c.rolling(20, min_periods=20).std(ddof=0)
    df["boll_up"] = df["ma20"] + 2 * std20
    df["boll_low"] = df["ma20"] - 2 * std20
    delta = c.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    loss = -delta.clip(upper=0).ewm(alpha=1 / 14, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    df["rsi14"] = 100 - 100 / (1 + rs)
    ema12 = c.ewm(span=12, adjust=False).mean()
    ema26 = c.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    df["macd"] = macd
    df["macd_signal"] = macd.ewm(span=9, adjust=False).mean()
    df["macd_hist"] = df["macd"] - df["macd_signal"]
    return df


def get_quote(symbol: str, interval: str = "1d") -> dict:
    """实时拉取多周期 K 线 + 指标。腾讯优先（A/HK），yfinance 兜底（美股）。"""
    if interval not in INTERVAL_MAP:
        return {"error": f"不支持的周期 {interval}（可选: {list(INTERVAL_MAP)}）", "symbol": symbol}
    tencent_key, mult, lookback, _ = INTERVAL_MAP[interval]
    cache_key = f"{symbol}|{interval}"
    now = time.time()
    if cache_key in _cache and now - _cache[cache_key][0] < _CACHE_TTL:
        df = _cache[cache_key][1]
    else:
        df = None
        errors = []
        tcode = _tencent_code(symbol)
        if tcode:
            try:
                df = _tencent_kline(tcode, tencent_key, lookback)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"腾讯: {type(exc).__name__}")
        if df is None or df.empty:
            try:
                df = _yfinance_kline(symbol, tencent_key, lookback)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"yfinance: {type(exc).__name__}: {exc}")
                df = None
        if df is None or df.empty:
            return {"error": f"数据获取失败（{'; '.join(errors)}）。Yahoo 可能限流，A 股/港股请用 .SS/.SZ/.HK 后缀。", "symbol": symbol}
        if mult > 1:
            df = _aggregate(df, mult)
        df = _add_indicators(df)
        _cache[cache_key] = (now, df)
    info = _symbol_info(symbol, df)
    cols = ["open", "high", "low", "close", "volume", "ma5", "ma20", "ma60",
            "boll_up", "boll_low", "rsi14", "macd", "macd_signal", "macd_hist"]
    return {
        "symbol": symbol, "interval": interval, "interval_label": INTERVAL_LABELS[interval],
        "info": info,
        "dates": [str(t) for t in df.index],
        **{c: [None if pd.isna(v) else round(float(v), 6) for v in df[c]] for c in cols if c in df},
        "rows": len(df), "last_close": float(df["close"].iloc[-1]) if len(df) else None,
        "as_of": str(df.index[-1]) if len(df) else None,
    }


def _symbol_info(symbol: str, df: pd.DataFrame | None = None) -> dict:
    market = _market_of(symbol)
    name = symbol
    if df is not None and not df.empty:
        name = f"{symbol} ({market})"
    return {"symbol": symbol, "name": name, "market": market}


def _market_of(symbol: str) -> str:
    if symbol.endswith(".HK"):
        return "HK"
    if symbol.endswith(".SS") or symbol.endswith(".SZ"):
        return "CN"
    if symbol.startswith("^") or symbol == "DX-Y.NYB":
        return "INDEX"
    if "=" in symbol:
        return "FUTURES"
    return "US"
