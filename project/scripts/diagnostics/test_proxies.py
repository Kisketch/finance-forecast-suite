import json, urllib.request
import yfinance as yf

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
      "Referer": "https://gu.qq.com/"}
url = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sz399006,day,,,320,qfq"
try:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
    print("RAW", raw[:600])
except Exception as e:
    print("TENCENT ERR", e)

print("== yfinance proxies ==")
for sym, start in [("159915.SZ", "2011-01-01"), ("588000.SS", "2020-11-01"), ("3033.HK", "2020-08-01")]:
    try:
        df = yf.download(sym, start=start, interval="1d", auto_adjust=True, progress=False, threads=False, timeout=30)
        print(sym, "rows", len(df), "first", df.index.min() if len(df) else None, "last", df.index.max() if len(df) else None)
    except Exception as e:
        print(sym, "ERR", e)
