import json
import pandas as pd
from pathlib import Path

ROOT = Path(r"C:\Users\Lgnatius\Documents\AI产出\工具\金融分析预测")
q = json.loads((ROOT / "data" / "metadata" / "data_quality.json").read_text(encoding="utf-8"))
print("degraded:", q.get("degraded"))
print("failed:", q.get("failed"))
long = pd.read_csv(ROOT / "data" / "processed" / "prices_long.csv", parse_dates=["date"])
rows = []
for sym, g in long.groupby("symbol"):
    g = g.sort_values("date").reset_index(drop=True)
    c = g["close"].astype(float)
    r = c.pct_change()
    mx = r.abs().max()
    if mx and mx > 0.25:
        idx = r.abs().idxmax()
        rows.append((sym, str(g.loc[idx, "name_cn"]), round(float(mx) * 100, 1),
                     str(g.loc[idx, "date"].date()), round(float(c.loc[idx - 1]), 3), round(float(c.loc[idx]), 3)))
rows.sort(key=lambda x: -x[2])
for r in rows:
    print(f"{r[0]:12s} {r[1]:12s} {r[2]:6.1f}% {r[3]}  {r[4]} -> {r[5]}")
