import time, urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"}
for u in ["https://qt.gtimg.cn/q=sh000001,hk00700",
          "https://push2.eastmoney.com/api/qt/stock/get?secid=1.000001&fields=f43,f57,f58,f60,f170"]:
    try:
        req = urllib.request.Request(u, headers=UA)
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
        print(u[:50], len(raw), raw[:220])
    except Exception as e:
        print(u[:50], "ERR", e)
    time.sleep(3)

time.sleep(10)
u = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sh000001,day,,,10,qfq"
try:
    req = urllib.request.Request(u, headers={**UA, "Referer": "https://gu.qq.com/"})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
    print("kline", len(raw), raw[:300])
except Exception as e:
    print("kline ERR", e)
