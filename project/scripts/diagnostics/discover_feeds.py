import urllib.request, re
from urllib.parse import urljoin

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
SITES = {
    "pboc": "http://www.pbc.gov.cn/en/3688110/index.html",
    "nbs": "https://www.stats.gov.cn/english/",
    "csrc": "http://www.csrc.gov.cn/csrc_en/",
    "sse": "http://www.sse.com.cn/",
    "hkma": "https://www.hkma.gov.hk/eng/",
    "sfc": "https://www.sfc.hk/en/",
    "hkex": "https://www.hkex.com.hk/?sc_lang=en",
    "iea": "https://www.iea.org/news",
    "imf": "https://www.imf.org/en/News",
    "bis": "https://www.bis.org/press/index.htm",
    "opec": "https://www.opec.org/opec_web/en/press_room/",
    "sec": "https://www.sec.gov/news/pressreleases",
    "bls": "https://www.bls.gov/news.release/",
    "worldbank": "https://www.worldbank.org/en/news",
    "wto": "https://www.wto.org/english/news_e/news_e.htm",
    "china_gov": "https://english.www.gov.cn/",
    "chinadaily": "https://www.chinadaily.com.cn/",
}
for name, url in SITES.items():
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=12) as r:
            html = r.read(400000).decode("utf-8", "ignore")
        links = re.findall(r'<link[^>]+type=["\']application/(?:rss|atom)\+xml["\'][^>]*>', html, re.I)
        hrefs = []
        for l in links:
            m = re.search(r'href=["\']([^"\']+)["\']', l, re.I)
            if m:
                hrefs.append(urljoin(url, m.group(1)))
        print(f"OK {name:11s} len={len(html):6d} feeds={hrefs[:3]}")
    except Exception as e:
        print(f"FAIL {name:11s} {type(e).__name__}: {str(e)[:80]}")
