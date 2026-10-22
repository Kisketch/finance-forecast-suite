"""最终数据修补与质量分级：AVB/EQR 用新浪全历史；标记停更、换月、负价、复权疑点。"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(r"C:\Users\Lgnatius\Documents\AI产出\工具\金融分析预测")
PROC = ROOT / "data" / "processed" / "prices_long.csv"
META = ROOT / "data" / "metadata" / "data_quality.json"

PATCH_FILES = {
    "AVB": ROOT / "data" / "raw" / "sina_AVB.csv",
    "EQR": ROOT / "data" / "raw" / "sina_EQR.csv",
    "000300.SS": ROOT / "data" / "raw" / "tencent" / "sh000300.csv",
}
FUTURES = {"CL=F", "BZ=F", "NG=F", "GC=F", "SI=F", "HG=F"}
SUSPECT = {"600028.SS"}


def main() -> None:
    long = pd.read_csv(PROC, parse_dates=["date"])
    for sym, path in PATCH_FILES.items():
        df = pd.read_csv(path, parse_dates=["date"])
        df["symbol"] = sym
        base = long[long.symbol == sym].iloc[0]
        df["name_cn"], df["name_en"] = base["name_cn"], base["name_en"]
        df["market"], df["group"] = base["market"], base["group"]
        long = long[long.symbol != sym]
        long = pd.concat([long, df], ignore_index=True)
        print(f"patched {sym}: {len(df)} rows {df.date.min().date()} -> {df.date.max().date()}")

    long = long.sort_values(["symbol", "date"]).reset_index(drop=True)
    long["date_fmt"] = pd.to_datetime(long["date"]).dt.strftime("%Y-%m-%d")
    max_date = pd.Timestamp(long["date"].max()).normalize()

    per = {}
    flags_count: dict[str, int] = {}
    for sym, g in long.groupby("symbol"):
        g = g.sort_values("date")
        close = g["close"].astype(float)
        rows = len(g)
        start = pd.Timestamp(g["date"].iloc[0]).normalize()
        end = pd.Timestamp(g["date"].iloc[-1]).normalize()
        ret = close.pct_change()
        max_ret = float(ret.abs().max()) if ret.notna().any() else 0.0
        zero_vol = float((g["volume"].fillna(0) <= 0).mean())
        null_close = int(close.isna().sum())
        flags = []
        if rows < 250:
            flags.append("short_history")
        if (max_date - end).days > 30:
            flags.append("stale_data")
        if sym in FUTURES:
            flags.append("front_month_roll")
        if sym == "CL=F" and (close <= 0).any():
            flags.append("negative_price")
        if sym in SUSPECT:
            flags.append("suspect_adjustment")
        if sym == "^TNX":
            flags.append("yield_level_series")
            max_ret = float(close.diff().abs().max()) / 100.0
        elif max_ret > 0.25:
            flags.append("extreme_move")
        if zero_vol > 0.95 and not sym.startswith("^") and sym != "DX-Y.NYB":
            flags.append("zero_volume")
        if null_close > 0:
            flags.append("missing_close")
        for f in flags:
            flags_count[f] = flags_count.get(f, 0) + 1
        status = "degraded" if any(f in flags for f in
                                   ("short_history", "stale_data", "negative_price", "suspect_adjustment")) else "ok"
        per[sym] = {
            "status": status, "rows": int(rows),
            "start": str(start.date()), "end": str(end.date()),
            "last_close": float(close.iloc[-1]), "null_close": null_close,
            "zero_volume_pct": zero_vol, "max_abs_daily_return": max_ret,
            "extreme_days": int((ret.abs() > 0.25).sum()),
            "name_cn": str(g["name_cn"].iloc[-1]), "name_en": str(g["name_en"].iloc[-1]),
            "group": str(g["group"].iloc[-1]), "flags": flags,
        }

    ok = sum(1 for v in per.values() if v["status"] == "ok")
    degraded = sum(1 for v in per.values() if v["status"] == "degraded")
    failed = sum(1 for v in per.values() if v["status"] == "failed")
    quality = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "Yahoo Finance via yfinance; 腾讯/新浪补点",
        "symbols_requested": len(per), "symbols_ok": ok, "symbols_degraded": degraded,
        "symbols_failed": failed, "rows_total": int(len(long)),
        "date_min": str(pd.Timestamp(long["date"].min()).date()),
        "date_max": str(max_date.date()),
        "failed": [k for k, v in per.items() if v["status"] == "failed"],
        "degraded": [k for k, v in per.items() if v["status"] == "degraded"],
        "flags_count": flags_count,
        "per_symbol": per,
    }
    META.write_text(json.dumps(quality, ensure_ascii=False, indent=2), encoding="utf-8")
    long.drop(columns=["date_fmt"]).to_csv(PROC, index=False, encoding="utf-8")
    print(json.dumps({k: quality[k] for k in ("symbols_ok", "symbols_degraded", "symbols_failed",
                                              "rows_total", "date_min", "date_max", "flags_count")}, ensure_ascii=False))
    print("degraded:", quality["degraded"])


if __name__ == "__main__":
    main()
