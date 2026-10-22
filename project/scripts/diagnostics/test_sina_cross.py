import json, re, urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"}
urls = {
    "A": "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketDataService.getKLineData?symbol=sh000001&scale=240&ma=no&datalen=30",
    "HK": "https://stock.finance.sina.com.cn/hkstock/api/jsonp.php/var%20_hk00700=/HK_StockService.getDayKLine?symbol=00700",
}
for k, u in urls.items():
    try:
        req = urllib.request.Request(u, headers=UA)
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode("utf-8", "ignore")
        print(k, "bytes", len(raw), "head", raw[:200])
    except Exception as e:
        print(k, "ERR", e)
