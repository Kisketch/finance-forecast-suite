import json, time, urllib.request
from pathlib import Path
import pandas as pd

ROOT = Path(r"C:\Users\Lgnatius\Documents\AI产出\工具\金融分析预测")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"}

def quote(codes):
    url = "https://qt.gtimg.cn/q=" + ",".join(codes)
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read().decode("gbk", "ignore")
    out = {}
    for line in raw.strip().split(";"):
        if "=" not in line:
            continue
        key, val = line.split("=", 1)
        code = key.replace("v_", "").strip()
        parts = val.strip().strip('"').split("~")
        if len(parts) > 4:
            out[code] = {"name": parts[1], "last": float(parts[3]), "prev": float(parts[4]) if parts[4] else None}
    return out

def tencent_kline(code, n=10):
    url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={code},day,,,{n},qfq"
    for _ in range(3):
        try:
            req = urllib.request.Request(url, headers={**UA, "Referer": "https://gu.qq.com/"})
            with urllib.request.urlopen(req, timeout=30) as r:
                j = json.loads(r.read())
            rows = ((j.get("data") or {}).get(code) or {}).get("qfqday") or []
            if rows:
                x = pd.DataFrame(rows).iloc[:, :6]
                x.columns = ["date", "open", "close", "high", "low", "volume"]
                return x
        except Exception:
            pass
        time.sleep(8)
    return pd.DataFrame()

long = pd.read_csv(ROOT / "data" / "processed" / "prices_long.csv", parse_dates=["date"])
app = {s: long[long.symbol == s].sort_values("date").set_index("date")["close"] for s in ["000001.SS", "0700.HK"]}

q = quote(["sh000001", "hk00700"])
print("quote", json.dumps(q, ensure_ascii=False))
for code, sym in [("sh000001", "000001.SS"), ("hk00700", "0700.HK")]:
    if code in q:
        a = q[code]["last"]
        b = float(app[sym].iloc[-1])
        print(sym, "quote", a, "app", b, "diff%", round((a - b) / b * 100, 4))

for code, sym in [("sh000001", "000001.SS"), ("hk00700", "0700.HK")]:
    x = tencent_kline(code)
    if x.empty:
        print(sym, "kline unavailable")
        continue
    x["date"] = pd.to_datetime(x["date"])
    x = x.set_index("date")
    for dt in x.index[-3:]:
        if dt in app[sym].index:
            a, b = float(x.loc[dt, "close"]), float(app[sym].loc[dt])
            print(sym, str(dt.date()), "tencent", a, "app", b, "diff%", round((a - b) / b * 100, 4))
