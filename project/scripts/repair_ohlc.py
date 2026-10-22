"""修复 OHLC 关系并更新质量报告（不改收盘价）。"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"C:\Users\Lgnatius\Documents\AI产出\工具\金融分析预测")
PROC = ROOT / "data" / "processed" / "prices_long.csv"
META = ROOT / "data" / "metadata" / "data_quality.json"

long = pd.read_csv(PROC, parse_dates=["date"])
repaired = {}
for sym, g in long.groupby("symbol", sort=False):
    idx = g.index
    o, h, l, c = (long.loc[idx, x].astype(float) for x in ["open", "high", "low", "close"])
    new_h = np.maximum.reduce([h, o, c])
    new_l = np.minimum.reduce([l, o, c])
    mask = (np.abs(new_h - h) > 1e-6) | (np.abs(new_l - l) > 1e-6)
    n = int(mask.sum())
    if n:
        gap = float(np.max(np.maximum(np.abs(new_h - h), np.abs(new_l - l))[mask] / c[mask]))
        repaired[sym] = {"rows": n, "max_gap_pct": round(gap * 100, 3)}
        long.loc[idx, "high"] = new_h
        long.loc[idx, "low"] = new_l

long.to_csv(PROC, index=False, encoding="utf-8")
q = json.loads(META.read_text(encoding="utf-8"))
for sym, info in repaired.items():
    if sym in q["per_symbol"]:
        q["per_symbol"][sym]["ohlc_repaired_rows"] = info["rows"]
        q["per_symbol"][sym]["max_ohlc_gap_pct"] = info["max_gap_pct"]
        if "ohlc_repaired" not in q["per_symbol"][sym]["flags"]:
            q["per_symbol"][sym]["flags"].append("ohlc_repaired")
q["ohlc_repaired_symbols"] = len(repaired)
q["ohlc_repaired_total_rows"] = sum(v["rows"] for v in repaired.values())
META.write_text(json.dumps(q, ensure_ascii=False, indent=2), encoding="utf-8")
print("repaired symbols", len(repaired), "rows", q["ohlc_repaired_total_rows"])
print(json.dumps(dict(sorted(repaired.items(), key=lambda x: -x[1]["max_gap_pct"])[:10]), ensure_ascii=False))
