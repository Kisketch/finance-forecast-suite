import json, time, urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
      "Referer": "https://gu.qq.com/"}

for code in ["usAVB", "usEQR", "usAAPL"]:
    url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={code},day,,,2000,qfq"
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=30) as r:
            j = json.loads(r.read())
        d = (j.get("data") or {}).get(code) or {}
        rows = d.get("qfqday") or d.get("day") or []
        print(code, "rows", len(rows), rows[0][:2] if rows else None, rows[-1][:2] if rows else None)
    except Exception as e:
        print(code, "ERR", e)
    time.sleep(5)

print("== sina us ==")
for sym in ["AVB", "EQR"]:
    url = f"https://stock.finance.sina.com.cn/usstock/api/jsonp.php/var%20_{sym}=/US_MinKService.getDailyK?symbol={sym}&___qn=3"
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
        print(sym, "bytes", len(raw), raw[:160])
    except Exception as e:
        print(sym, "ERR", e)
    time.sleep(2)
