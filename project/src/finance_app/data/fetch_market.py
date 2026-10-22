"""多市场历史行情抓取与质量校验。

数据源：Yahoo Finance（通过 yfinance，自动处理 cookie/crumb）。
输出：
  data/raw/yahoo/<symbol>.csv        单标的历史
  data/processed/prices_long.csv     长表（date,symbol,...,close,volume）
  data/metadata/data_quality.json    质量报告
"""
from __future__ import annotations

import json
import math
import re
import socket
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yaml
import yfinance as yf

from .._paths import ROOT

CONFIG = ROOT / "config" / "universe.yaml"
RAW = ROOT / "data" / "raw" / "yahoo"
PROC = ROOT / "data" / "processed"
META = ROOT / "data" / "metadata"
for p in (RAW, PROC, META):
    p.mkdir(parents=True, exist_ok=True)


def load_universe() -> list[dict]:
    """解析 universe.yaml（PyYAML safe_load；此前手写正则解析对键顺序/引号变化过于脆弱）。"""
    data = yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}
    items: list[dict] = []

    def walk(node, section: str | None, subgroup: str | None) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, section, str(k))
        elif isinstance(node, list):
            for row in node:
                if isinstance(row, dict) and row.get("symbol"):
                    items.append({
                        "symbol": str(row["symbol"]),
                        "name_cn": str(row.get("name_cn") or ""),
                        "name_en": str(row.get("name_en") or ""),
                        "section": section,
                        "group": subgroup or section,
                    })
                elif isinstance(row, (dict, list)):
                    walk(row, section, subgroup)

    walk(data, None, None)
    return items


def market_of(symbol: str, section: str | None) -> str:
    if symbol.endswith(".HK"):
        return "HK"
    if symbol.endswith(".SS") or symbol.endswith(".SZ"):
        return "CN"
    if section == "markets":
        return "US" if symbol.startswith("^") or symbol == "DX-Y.NYB" else "US"
    if section == "commodities":
        return "GLOBAL"
    return "US"


def download_one(symbol: str, retries: int = 3) -> pd.DataFrame | None:
    for attempt in range(retries):
        try:
            df = yf.download(symbol, period="max", interval="1d", auto_adjust=True,
                             progress=False, threads=False, timeout=30)
            if df is None or df.empty:
                raise ValueError("empty frame")
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [c[0] for c in df.columns]
            df = df.rename(columns=str.lower)
            keep = [c for c in ["open", "high", "low", "close", "volume"] if c in df.columns]
            df = df[keep].copy()
            idx = pd.to_datetime(df.index)
            if getattr(idx, "tz", None) is not None:
                idx = idx.tz_localize(None)
            df.index = idx.normalize()
            df = df[~df.index.duplicated(keep="last")].sort_index()
            return df
        except Exception as exc:  # noqa: BLE001
            if attempt == retries - 1:
                print(f"  FAIL {symbol}: {exc}", flush=True)
                return None
            time.sleep(1.5 * (attempt + 1))
    return None


def main() -> int:
    # yfinance 的 timeout 参数并不总能覆盖底层连接；设置全局 socket 超时，
    # 避免某个标的在 DNS/TLS 握手阶段无限挂起，拖死整个每日更新。
    # （放在 main() 内，避免 import 副作用影响宿主进程）
    socket.setdefaulttimeout(30)
    universe = load_universe()
    print(f"universe: {len(universe)} symbols", flush=True)
    if not universe:
        print("universe.yaml parsed to 0 symbols; check config", flush=True)
        return 1
    frames: list[pd.DataFrame] = []
    quality: dict[str, dict] = {}
    t0 = time.time()
    consecutive_fail = 0

    for i, item in enumerate(universe, 1):
        sym = item["symbol"]
        print(f"[{i}/{len(universe)}] {sym} {item['name_cn']}", flush=True)
        df = download_one(sym)
        if df is None or df.empty:
            quality[sym] = {"status": "failed", **item}
            consecutive_fail += 1
            # 任意阶段连续 8 个标的失败，视为上游限流/断网；快速失败，保留旧数据。
            # （此前只覆盖前 3 个标的，中途故障会拖满 97×3 次重试超时。）
            if consecutive_fail >= 8:
                print("upstream appears unavailable (8 consecutive failures); aborting early to keep existing data", flush=True)
                return 1
            continue
        consecutive_fail = 0
        df.to_csv(RAW / f"{sym.replace('^','IDX_').replace('=','_' )}.csv", encoding="utf-8")
        df = df.reset_index().rename(columns={"index": "date", "Date": "date"})
        df["symbol"] = sym
        df["name_cn"] = item["name_cn"]
        df["name_en"] = item["name_en"]
        df["market"] = market_of(sym, item["section"])
        df["group"] = item["group"]
        frames.append(df)

        close = df["close"].astype(float)
        ret = close.pct_change()
        quality[sym] = {
            "status": "ok",
            "rows": int(len(df)),
            "start": str(df["date"].iloc[0].date()),
            "end": str(df["date"].iloc[-1].date()),
            "last_close": float(close.iloc[-1]),
            "null_close": int(close.isna().sum()),
            "zero_volume_pct": float((df["volume"].fillna(0) <= 0).mean()),
            "max_abs_daily_return": float(ret.abs().max()) if len(ret.dropna()) else 0.0,
            "extreme_days": int((ret.abs() > 0.25).sum()),
            **{k: item[k] for k in ("name_cn", "name_en", "group")},
        }
        time.sleep(0.25)

    if not frames:
        print("no data", flush=True)
        return 1
    long = pd.concat(frames, ignore_index=True)
    long["date"] = pd.to_datetime(long["date"]).dt.strftime("%Y-%m-%d")
    long = long.sort_values(["symbol", "date"]).reset_index(drop=True)
    long.to_csv(PROC / "prices_long.csv", index=False, encoding="utf-8")

    ok = [v for v in quality.values() if v.get("status") == "ok"]
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "Yahoo Finance via yfinance",
        "symbols_requested": len(universe),
        "symbols_ok": len(ok),
        "symbols_failed": len(universe) - len(ok),
        "rows_total": int(len(long)),
        "date_min": str(long["date"].min()),
        "date_max": str(long["date"].max()),
        "failed": [k for k, v in quality.items() if v.get("status") != "ok"],
        "per_symbol": quality,
    }
    (META / "data_quality.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("symbols_ok", "symbols_failed", "rows_total", "date_min", "date_max")}, ensure_ascii=False), flush=True)
    print(f"elapsed {time.time()-t0:.1f}s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
