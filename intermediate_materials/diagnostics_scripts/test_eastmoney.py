import json, urllib.request, time

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
      "Referer": "https://quote.eastmoney.com/"}

def em(secid, klt=101):
    url = ("https://push2his.eastmoney.com/api/qt/stock/kline/get?"
           f"secid={secid}&klt={klt}&fqt=1&beg=19900101&end=20500101"
           "&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61")
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=25) as r:
        j = json.loads(r.read())
    d = j.get("data") or {}
    kl = d.get("klines") or []
    return d.get("name"), d.get("code"), len(kl), (kl[-1][:45] if kl else None)

# US stocks, indices, HK, A, commodities/futures candidates
tests = [
    ("105.AAPL","US AAPL NASDAQ"),("106.XOM","US XOM NYSE"),("105.MSFT","US MSFT"),
    ("100.NDX","Nasdaq100"),("100.SPX","S&P500"),("100.DJIA","Dow"),
    ("100.HSI","HSI"),("100.HSCEI","HSCEI"),("124.HSTECH","HSTech"),
    ("1.000001","SSE"),("0.399001","SZSE"),("1.000300","CSI300"),("0.399006","ChiNext"),
    ("101.CL00Y","WTI futures"),("101.B00Y","Brent futures"),("101.NG00Y","NatGas futures"),
    ("101.GC00Y","Gold futures"),("101.SI00Y","Silver futures"),
    ("90.BK0475","RealEstate sector"),("90.BK0437","Energy sector"),
]
for secid,name in tests:
    try:
        n,c,rows,last = em(secid)
        print(f"{name:24s} {secid:12s} rows={rows:5d} name={n} last={last}")
    except Exception as e:
        print(f"{name:24s} {secid:12s} ERROR {e}")
    time.sleep(0.3)
