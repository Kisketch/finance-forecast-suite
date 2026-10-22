import urllib.request
import pandas as pd
import yfinance as yf

print("== yfinance retry ==")
for sym in ["AVB", "EQR"]:
    for period in ["10y", "5y", "max"]:
        try:
            df = yf.download(sym, period=period, interval="1d", auto_adjust=True, progress=False, threads=False, timeout=30)
            print(sym, period, "rows", len(df), df.index.min() if len(df) else None, df.index.max() if len(df) else None)
            if len(df) > 250:
                break
        except Exception as e:
            print(sym, period, "ERR", e)

print("== stooq ==")
for sym in ["avb.us", "eqr.us"]:
    url = f"https://stooq.com/q/d/l/?s={sym}&i=d"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
        print(sym, "bytes", len(raw), raw[:120])
    except Exception as e:
        print(sym, "ERR", e)
