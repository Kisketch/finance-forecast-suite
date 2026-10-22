import json, re, time, urllib.request
import pandas as pd

ROOT = r"C:\Users\Lgnatius\Documents\AI产出\工具\金融分析预测"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"}

def sina_us(sym):
    url = f"https://stock.finance.sina.com.cn/usstock/api/jsonp.php/var%20_{sym}=/US_MinKService.getDailyK?symbol={sym}&___qn=3"
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=40) as r:
        raw = r.read().decode("utf-8", "ignore")
    m = re.search(r"=\s*\((\[.*\])\)\s*;?\s*$", raw, re.S)
    if not m:
        raise ValueError("parse failed")
    arr = json.loads(m.group(1))
    df = pd.DataFrame(arr)
    df = df.rename(columns={"d": "date", "o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"})
    for c in ["open", "high", "low", "close", "volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["date"] = pd.to_datetime(df["date"])
    return df[["date", "open", "high", "low", "close", "volume"]].sort_values("date")

def tencent(code):
    url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={code},day,,,2000,qfq"
    req = urllib.request.Request(url, headers={**UA, "Referer": "https://gu.qq.com/"})
    with urllib.request.urlopen(req, timeout=40) as r:
        j = json.loads(r.read())
    rows = ((j.get("data") or {}).get(code) or {}).get("qfqday") or []
    df = pd.DataFrame(rows).iloc[:, :6]
    df.columns = ["date", "open", "close", "high", "low", "volume"]
    for c in ["open", "close", "high", "low", "volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["date"] = pd.to_datetime(df["date"])
    return df[["date", "open", "high", "low", "close", "volume"]].sort_values("date")

for sym in ["AVB", "EQR"]:
    df = sina_us(sym)
    df.to_csv(f"{ROOT}\\data\\raw\\sina_{sym}.csv", index=False, encoding="utf-8")
    print(sym, "sina rows", len(df), df.date.min().date(), df.date.max().date())

time.sleep(4)
df = tencent("sh600028")
print("600028 tencent rows", len(df), df.date.min().date(), df.date.max().date())
print(df[(df.date >= "2013-06-10") & (df.date <= "2013-06-21")].to_string(index=False))
