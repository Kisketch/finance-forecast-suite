"""补齐沪深300，并重新生成带分级的数据质量报告。"""
from __future__ import annotations

import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed" / "prices_long.csv"
RAW = ROOT / "data" / "raw" / "tencent"
META = ROOT / "data" / "metadata" / "data_quality.json"

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
      "Referer": "https://gu.qq.com/"}

# 需要补齐/覆盖的标的
PATCH = [("sh000300", "000300.SS", "沪深300", "CSI 300", "CN", "cn")]


def fetch(code: str) -> pd.DataFrame:
    endpoints = [
        f"https://proxy.finance.qq.com/ifzqgtimg/appstock/app/newfqkline/get?param={code},day,,,2000,qfq",
        f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={code},day,,,2000,qfq",
        f"https://web.ifzq.gtimg.cn/appstock/app/kline/kline?param={code},day,,,2000",
    ]
    last_err = None
    for url in endpoints:
        for attempt in range(3):
            try:
                req = urllib.request.Request(url, headers=UA)
                with urllib.request.urlopen(req, timeout=40) as r:
                    j = json.loads(r.read())
                rows = ((j.get("data") or {}).get(code) or {}).get("qfqday") or \
                       ((j.get("data") or {}).get(code) or {}).get("day") or []
                if rows:
                    df = pd.DataFrame(rows).iloc[:, :6]
                    df.columns = ["date", "open", "close", "high", "low", "volume"]
                    for c in ["open", "close", "high", "low", "volume"]:
                        df[c] = pd.to_numeric(df[c], errors="coerce")
                    df["date"] = pd.to_datetime(df["date"])
                    return df[["date", "open", "high", "low", "close", "volume"]].sort_values("date")
                last_err = ValueError(f"no rows for {code} via {url[:50]}")
            except Exception as exc:  # noqa: BLE001
                last_err = exc
            time.sleep(6)
    raise last_err or ValueError(f"no rows for {code}")


def main() -> None:
    long = pd.read_csv(PROC, parse_dates=["date"])
    for code, sym, cn, en, market, group in PATCH:
        df = fetch(code)
        df.to_csv(RAW / f"{code}.csv", index=False, encoding="utf-8")
        df["symbol"], df["name_cn"], df["name_en"] = sym, cn, en
        df["market"], df["group"] = market, group
        long = long[long["symbol"] != sym]
        long = pd.concat([long, df], ignore_index=True)
        print(f"patched {sym}: {len(df)} rows")

    long = long.sort_values(["symbol", "date"]).reset_index(drop=True)
    long["date_fmt"] = pd.to_datetime(long["date"]).dt.strftime("%Y-%m-%d")

    quality = json.loads(META.read_text(encoding="utf-8"))
    per = {}
    flags_count = {"short_history": 0, "extreme_move": 0, "zero_volume": 0, "missing_close": 0}
    for sym, g in long.groupby("symbol"):
        g = g.sort_values("date")
        close = g["close"].astype(float)
        ret = close.pct_change()
        rows = len(g)
        max_ret = float(ret.abs().max()) if ret.notna().any() else 0.0
        zero_vol = float((g["volume"].fillna(0) <= 0).mean())
        null_close = int(close.isna().sum())
        flags = []
        status = "ok"
        if rows < 250:
            flags.append("short_history"); status = "degraded"; flags_count["short_history"] += 1
        if sym == "^TNX":
            # 收益率指数：用百分点变化而不是百分比变化
            chg = close.diff().abs()
            max_ret = float(chg.max()) / 100.0
            flags.append("yield_level_series")
        elif max_ret > 0.25:
            flags.append("extreme_move"); flags_count["extreme_move"] += 1
        if zero_vol > 0.95 and not sym.startswith("^") and sym != "DX-Y.NYB":
            flags.append("zero_volume"); flags_count["zero_volume"] += 1
        if null_close > 0:
            flags.append("missing_close"); flags_count["missing_close"] += 1
        per[sym] = {
            "status": status, "rows": int(rows),
            "start": str(pd.Timestamp(g["date"].iloc[0]).date()),
            "end": str(pd.Timestamp(g["date"].iloc[-1]).date()),
            "last_close": float(close.iloc[-1]), "null_close": null_close,
            "zero_volume_pct": zero_vol, "max_abs_daily_return": max_ret,
            "extreme_days": int((ret.abs() > 0.25).sum()),
            "name_cn": str(g["name_cn"].iloc[-1]), "name_en": str(g["name_en"].iloc[-1]),
            "group": str(g["group"].iloc[-1]), "flags": flags,
        }

    ok = sum(1 for v in per.values() if v["status"] == "ok")
    degraded = sum(1 for v in per.values() if v["status"] == "degraded")
    failed = sum(1 for v in per.values() if v["status"] == "failed")
    quality.update({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "symbols_requested": len(per), "symbols_ok": ok, "symbols_degraded": degraded,
        "symbols_failed": failed, "rows_total": int(len(long)),
        "date_min": str(pd.Timestamp(long["date"].min()).date()),
        "date_max": str(pd.Timestamp(long["date"].max()).date()),
        "failed": [k for k, v in per.items() if v["status"] == "failed"],
        "degraded": [k for k, v in per.items() if v["status"] == "degraded"],
        "flags_count": flags_count, "per_symbol": per,
    })
    META.write_text(json.dumps(quality, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: quality[k] for k in ("symbols_ok", "symbols_degraded", "symbols_failed",
                                              "rows_total", "date_min", "date_max", "flags_count")}, ensure_ascii=False))

    # 复查 VIX / TNX 极端日
    for sym in ["^VIX", "^TNX"]:
        g = long[long.symbol == sym].sort_values("date")
        c = g["close"].astype(float)
        if sym == "^TNX":
            d = c.diff().abs().sort_values(ascending=False).head(5)
            print(sym, "top abs level changes", [(str(g.loc[i, "date"])[:10], round(float(c.loc[i]), 3)) for i in d.index])
        else:
            r = c.pct_change().abs().sort_values(ascending=False).head(5)
            print(sym, "top pct moves", [(str(g.loc[i, "date"])[:10], round(float(r.loc[i]) * 100, 1)) for i in r.index])


if __name__ == "__main__":
    main()
