"""用腾讯行情补齐 3 个缺失指数，并更新长表与质量报告。"""
from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed" / "prices_long.csv"
RAW = ROOT / "data" / "raw" / "tencent"
META = ROOT / "data" / "metadata" / "data_quality.json"
RAW.mkdir(parents=True, exist_ok=True)

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
      "Referer": "https://gu.qq.com/"}

TARGETS = [
    ("sz399006", "399006.SZ", "创业板指", "ChiNext", "CN", "cn"),
    ("sh000688", "000688.SS", "科创50", "STAR 50", "CN", "cn"),
    ("hkHSTECH", "^HSTECH", "恒生科技", "Hang Seng Tech", "HK", "hk"),
]


def fetch(code: str) -> pd.DataFrame:
    url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={code},day,,,2000,qfq"
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=40) as r:
        j = json.loads(r.read())
    d = (j.get("data") or {}).get(code) or {}
    rows = d.get("qfqday") or d.get("day") or []
    if not rows:
        raise ValueError(f"no rows for {code}")
    df = pd.DataFrame(rows)
    df = df.iloc[:, :6]
    df.columns = ["date", "open", "close", "high", "low", "volume"]
    for c in ["open", "close", "high", "low", "volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["date"] = pd.to_datetime(df["date"])
    return df[["date", "open", "high", "low", "close", "volume"]].sort_values("date")


def main() -> None:
    long = pd.read_csv(PROC, parse_dates=["date"])
    quality = json.loads(META.read_text(encoding="utf-8"))
    added = []
    for code, sym, cn, en, market, group in TARGETS:
        df = fetch(code)
        df.to_csv(RAW / f"{code}.csv", index=False, encoding="utf-8")
        df["symbol"] = sym
        df["name_cn"] = cn
        df["name_en"] = en
        df["market"] = market
        df["group"] = group
        long = long[long["symbol"] != sym]
        long = pd.concat([long, df], ignore_index=True)
        close = df["close"]
        ret = close.pct_change()
        quality["per_symbol"][sym] = {
            "status": "ok", "rows": int(len(df)),
            "start": str(df["date"].iloc[0].date()), "end": str(df["date"].iloc[-1].date()),
            "last_close": float(close.iloc[-1]), "null_close": int(close.isna().sum()),
            "zero_volume_pct": float((df["volume"].fillna(0) <= 0).mean()),
            "max_abs_daily_return": float(ret.abs().max()), "extreme_days": int((ret.abs() > 0.25).sum()),
            "name_cn": cn, "name_en": en, "group": group,
        }
        added.append(sym)
        print(f"patched {sym}: {len(df)} rows {df['date'].iloc[0].date()} -> {df['date'].iloc[-1].date()}")

    long = long.sort_values(["symbol", "date"]).reset_index(drop=True)
    long["date"] = pd.to_datetime(long["date"]).dt.strftime("%Y-%m-%d")
    long.to_csv(PROC, index=False, encoding="utf-8")
    quality["symbols_ok"] = int(sum(1 for v in quality["per_symbol"].values() if v.get("status") == "ok"))
    quality["symbols_failed"] = int(len(quality["per_symbol"]) - quality["symbols_ok"])
    quality["failed"] = [k for k, v in quality["per_symbol"].items() if v.get("status") != "ok"]
    quality["rows_total"] = int(len(long))
    quality["date_min"] = str(long["date"].min())
    quality["date_max"] = str(long["date"].max())
    quality["patched"] = added
    quality["patched_source"] = "Tencent qfq kline API"
    quality["patched_at"] = datetime.now(timezone.utc).isoformat()
    META.write_text(json.dumps(quality, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"symbols_ok": quality["symbols_ok"], "failed": quality["failed"],
                      "rows": quality["rows_total"], "range": [quality["date_min"], quality["date_max"]]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
