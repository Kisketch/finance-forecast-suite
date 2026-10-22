import json, urllib.request, urllib.parse, time, sys

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"}

def get(url, timeout=25):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read()

def yahoo(sym, rng="5y", interval="1d"):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(sym)}?range={rng}&interval={interval}&events=div%2Csplits"
    st, body = get(url)
    j = json.loads(body)
    res = j["chart"]["result"]
    if not res:
        return st, 0, None
    r = res[0]
    ts = r.get("timestamp", [])
    q = r["indicators"]["quote"][0]
    return st, len(ts), (r["meta"].get("currency"), r["meta"].get("exchangeName"), ts[-1] if ts else None)

def eastmoney(secid, beg="20200101"):
    url = ("https://push2his.eastmoney.com/api/qt/stock/kline/get?"
           f"secid={secid}&klt=101&fqt=1&beg={beg}&end=20500101"
           "&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61")
    st, body = get(url)
    j = json.loads(body)
    d = j.get("data") or {}
    kl = d.get("klines") or []
    return st, len(kl), (d.get("name"), d.get("code"), kl[-1][:30] if kl else None)

def fred(series):
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}"
    st, body = get(url)
    lines = body.decode("utf-8", "replace").strip().splitlines()
    return st, len(lines)-1, lines[-1][:40] if lines else None

symbols = [
    ("^GSPC","US S&P500"),("^IXIC","US Nasdaq"),("^DJI","US Dow"),
    ("AAPL","US Apple"),("XOM","US Exxon"),("XLRE","US RealEstate ETF"),("XLE","US Energy ETF"),
    ("0700.HK","HK Tencent"),("^HSI","HK HSI"),("0823.HK","HK LinkREIT"),("0883.HK","HK CNOOC"),
    ("600519.SS","A Moutai"),("000001.SS","A SSE"),("000002.SZ","A Vanke"),("601857.SS","A PetroChina"),
    ("CL=F","WTI"),("BZ=F","Brent"),("NG=F","NatGas"),
]
print("=== YAHOO ===")
for s,n in symbols:
    try:
        st,c,meta = yahoo(s)
        print(f"{n:18s} {s:12s} status={st} rows={c} meta={meta}")
    except Exception as e:
        print(f"{n:18s} {s:12s} ERROR {e}")
    time.sleep(0.4)

print("=== EASTMONEY ===")
for secid,n in [("1.600519","A Moutai"),("0.000002","A Vanke"),("116.00700","HK Tencent"),("1.000001","A SSE")]:
    try:
        st,c,meta = eastmoney(secid)
        print(f"{n:18s} {secid:12s} status={st} rows={c} meta={meta}")
    except Exception as e:
        print(f"{n:18s} {secid:12s} ERROR {e}")

print("=== FRED ===")
for s in ["DGS10","DCOILWTICO","CPIAUCSL","VIXCLS","SP500","MORTGAGE30US"]:
    try:
        st,c,last = fred(s)
        print(f"{s:14s} status={st} rows={c} last={last}")
    except Exception as e:
        print(f"{s:14s} ERROR {e}")
