import json, urllib.request, urllib.parse

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
      "Referer": "https://gu.qq.com/"}

codes = ["sz399006", "sh000688", "hkHSI", "hkHSTECH", "hkHSTECHI"]
for code in codes:
    url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={code},day,,,3200,qfq"
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=30) as r:
            j = json.loads(r.read())
        d = (j.get("data") or {}).get(code) or {}
        rows = d.get("qfqday") or d.get("day") or []
        print(code, "rows", len(rows), "first", rows[0][:3] if rows else None, "last", rows[-1][:3] if rows else None)
    except Exception as e:
        print(code, "ERR", e)
