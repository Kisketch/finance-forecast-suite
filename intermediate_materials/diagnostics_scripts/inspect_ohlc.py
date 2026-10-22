import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(r"C:\Users\Lgnatius\Documents\AI产出\工具\金融分析预测")
sys.path.insert(0, str(ROOT / "src"))
from finance_app.data.store import DataStore

ds = DataStore()
rows = []
for sym, df in ds.by_symbol.items():
    d = df.reset_index()
    o, h, l, c = (d[x].astype(float) for x in ["open", "high", "low", "close"])
    hi_gap = (np.maximum(o, c) - h)
    lo_gap = (l - np.minimum(o, c))
    n_hi = int((hi_gap > 1e-6).sum())
    n_lo = int((lo_gap > 1e-6).sum())
    if n_hi or n_lo:
        rows.append((sym, n_hi, n_lo, float(hi_gap.max()), float(lo_gap.max()),
                     float((hi_gap / c).max() * 100), float((lo_gap / c).max() * 100)))
rows.sort(key=lambda x: -max(x[3], x[4]))
print(f"{'symbol':12s} {'n_hi':>5s} {'n_lo':>5s} {'max_hi_gap':>11s} {'max_lo_gap':>11s} {'hi_%':>7s} {'lo_%':>7s}")
for r in rows[:20]:
    print(f"{r[0]:12s} {r[1]:5d} {r[2]:5d} {r[3]:11.4f} {r[4]:11.4f} {r[5]:7.3f} {r[6]:7.3f}")

# 展示一个典型标的的违例行
sym = rows[0][0]
d = ds.get(sym).reset_index()
o, h, l, c = (d[x].astype(float) for x in ["open", "high", "low", "close"])
mask = (np.maximum(o, c) - h > 1e-6) | (l - np.minimum(o, c) > 1e-6)
print("\n", sym, "violations sample:")
print(d.loc[mask, ["date", "open", "high", "low", "close"]].head(8).to_string(index=False))
