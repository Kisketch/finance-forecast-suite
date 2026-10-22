import pandas as pd
from pathlib import Path

ROOT = Path(r"C:\Users\Lgnatius\Documents\AI产出\工具\金融分析预测")
long = pd.read_csv(ROOT / "data" / "processed" / "prices_long.csv", parse_dates=["date"])

for sym in ["AVB", "EQR"]:
    g = long[long.symbol == sym].sort_values("date")
    print(sym, "rows", len(g), "start", g.date.min().date(), "end", g.date.max().date())

for sym, day in [("NG=F", "2026-01-29"), ("SI=F", "2026-01-30"), ("600028.SS", "2013-06-13"), ("CL=F", "2020-04-20")]:
    g = long[(long.symbol == sym)].sort_values("date").reset_index(drop=True)
    idx = g.index[g.date == pd.Timestamp(day)]
    if len(idx) == 0:
        print(sym, day, "not found")
        continue
    i = idx[0]
    print(f"\n== {sym} around {day} ==")
    print(g.iloc[max(0, i - 6):i + 6][["date", "open", "high", "low", "close", "volume"]].to_string(index=False))
