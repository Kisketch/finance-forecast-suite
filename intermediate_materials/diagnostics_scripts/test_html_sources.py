import urllib.request, re, ssl
from urllib.parse import urljoin

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
urls = {
    "chinadaily_rss": "https://www.chinadaily.com.cn/rss/china_rss.xml",
    "xinhua_http": "http://english.news.cn/rss/world.xml",
    "xinhua_https_noverify": "https://english.news.cn/rss/world.xml",
    "gov_cn_news": "https://english.www.gov.cn/news/",
    "hkma_press": "https://www.hkma.gov.hk/eng/news-and-media/press-releases/",
    "sfc_press": "https://www.sfc.hk/en/News-and-announcements/Press-releases",
    "sse_news": "https://www.sse.com.cn/aboutus/mediacenter/hotandd/",
    "iea_news": "https://www.iea.org/news",
}
for name, url in urls.items():
    try:
        ctx = ssl._create_unverified_context() if "noverify" in name else None
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=15, context=ctx) as r:
            raw = r.read(600000)
        text = raw.decode("utf-8", "ignore")
        print(f"\n== {name} len={len(text)} ==")
        if "rss" in name or "xml" in name:
            print(text[:200])
        else:
            links = re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', text, re.I | re.S)
            out = []
            for href, label in links:
                label = re.sub(r"<[^>]+>", " ", label)
                label = re.sub(r"\s+", " ", label).strip()
                if len(label) > 18 and ("2026" in href or "press" in href.lower() or "news" in href.lower()):
                    out.append((urljoin(url, href), label[:90]))
            for x in out[:12]:
                print(x)
    except Exception as e:
        print(f"FAIL {name}: {type(e).__name__}: {str(e)[:100]}")
