import json, time, urllib.request
import yfinance as yf

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"}
endpoints = [
    "https://proxy.finance.qq.com/ifzqgtimg/appstock/app/newfqkline/get?param=sh000300,day,,,2000,qfq",
    "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sh000300,day,,,2000,qfq",
    "https://web.ifzq.gtimg.cn/appstock/app/kline/kline?param=sh000300,day,,,2000",
]
for url in endpoints:
    for attempt in range(2):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = r.read()
            j = json.loads(raw)
            data = j.get("data") or {}
            d = data.get("sh000300") or {}
            rows = d.get("qfqday") or d.get("day") or []
            print(url[:70], "rows", len(rows), rows[0][:2] if rows else None, rows[-1][:2] if rows else None)
            if rows: break
        except Exception as e:
            print(url[:70], "ERR", e)
        time.sleep(8)
    time.sleep(4)

print("== yfinance 510300.SS ==")
try:
    df = yf.download("510300.SS", start="2012-01-01", interval="1d", auto_adjust=True, progress=False, threads=False, timeout=30)
    print("510300.SS rows", len(df), df.index.min() if len(df) else None, df.index.max() if len(df) else None)
except Exception as e:
    print("510300 ERR", e)
