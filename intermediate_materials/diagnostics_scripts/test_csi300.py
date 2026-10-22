import json, urllib.request
import pandas as pd

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
      "Referer": "https://gu.qq.com/"}
for code in ["sh000300", "sh000905", "sh000016"]:
    url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={code},day,,,2000,qfq"
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        j = json.loads(r.read())
    d = (j.get("data") or {}).get(code) or {}
    rows = d.get("qfqday") or d.get("day") or []
    print(code, len(rows), rows[0][:2] if rows else None, rows[-1][:2] if rows else None)
