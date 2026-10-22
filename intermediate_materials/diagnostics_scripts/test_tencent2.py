import json, urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
      "Referer": "https://gu.qq.com/"}
for code in ["sz399006", "sh000688", "hkHSTECH", "hkHSI", "hkHSCEI"]:
    for n in [2000, 1024]:
        url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={code},day,,,{n},qfq"
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                j = json.loads(r.read())
            d = (j.get("data") or {}).get(code) or {}
            rows = d.get("qfqday") or d.get("day") or []
            print(code, n, "rows", len(rows), "first", rows[0][:2] if rows else None, "last", rows[-1][:2] if rows else None)
            if rows: break
        except Exception as e:
            print(code, n, "ERR", e)
