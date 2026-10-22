import json, time, urllib.request, urllib.parse
import pandas as pd
import yfinance as yf

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
      "Referer": "https://quote.eastmoney.com/"}

def em(secid, beg="20100101"):
    params = {
        "secid": secid, "ut": "fa5fd1943c7b386f172d6893dbfba10b", "klt": "101", "fqt": "1",
        "beg": beg, "end": "20500101",
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
    }
    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        j = json.loads(r.read())
    d = j.get("data") or {}
    return d.get("name"), d.get("klines") or []

print("== Eastmoney HSTECH ==")
for secid in ["124.HSTECH", "100.HSTECH", "100.HSTECHI"]:
    try:
        name, kl = em(secid)
        print(secid, name, len(kl), kl[-1] if kl else None)
    except Exception as e:
        print(secid, "ERR", e)
    time.sleep(5)

print("== yfinance retries ==")
for sym, start in [("399006.SZ", "2010-01-01"), ("000688.SS", "2019-01-01"), ("3033.HK", "2016-01-01")]:
    try:
        df = yf.download(sym, start=start, interval="1d", auto_adjust=True, progress=False, threads=False, timeout=30)
        print(sym, len(df), df.index.min() if len(df) else None, df.index.max() if len(df) else None)
    except Exception as e:
        print(sym, "ERR", e)
    time.sleep(1)
