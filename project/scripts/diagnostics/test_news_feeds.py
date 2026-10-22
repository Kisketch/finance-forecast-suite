import urllib.request, xml.etree.ElementTree as ET, re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

URLS = {
    "fed": "https://www.federalreserve.gov/feeds/press_all.xml",
    "sec": "https://www.sec.gov/news/pressreleases.rss",
    "bls": "https://www.bls.gov/feed/bls_latest.rss",
    "bea": "https://www.bea.gov/rss/news.xml",
    "treasury": "https://home.treasury.gov/rss/press.xml",
    "whitehouse": "https://www.whitehouse.gov/feed/",
    "ustr": "https://ustr.gov/rss.xml",
    "ecb": "https://www.ecb.europa.eu/rss/press.html",
    "boe": "https://www.bankofengland.co.uk/rss/news",
    "hkma": "https://www.hkma.gov.hk/eng/news-and-media/press-releases/rss/",
    "sfc": "https://www.sfc.hk/en/News-and-announcements/Press-releases/rss",
    "hkgov": "https://www.info.gov.hk/gia/rss/general_en.xml",
    "iea": "https://www.iea.org/rss/news",
    "opec": "https://www.opec.org/opec_web/en/press_room/rss.xml",
    "imf": "https://www.imf.org/en/News/RSS?language=eng",
    "worldbank": "https://www.worldbank.org/en/news/rss",
    "bis": "https://www.bis.org/list/press_releases/rss.xml",
    "wto": "https://www.wto.org/english/news_e/news_e.rss",
    "eia": "https://www.eia.gov/rss/todayinenergy.xml",
    "nvidia": "https://nvidianews.nvidia.com/rss",
    "apple": "https://www.apple.com/newsroom/rss-feed.rss",
    "microsoft": "https://news.microsoft.com/feed/",
    "openai": "https://openai.com/news/rss.xml",
    "google": "https://blog.google/rss/",
    "meta": "https://about.fb.com/feed/",
    "tsmc": "https://pr.tsmc.com/english/rss",
    "samsung": "https://www.samsung.com/global/newsroom/rss",
    "xinhua": "https://english.news.cn/rss/world.xml",
    "nbs": "https://www.stats.gov.cn/english/PressRelease/rss.xml",
}

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
for name, url in URLS.items():
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/rss+xml, application/xml, text/xml, */*"})
        with urllib.request.urlopen(req, timeout=15) as r:
            raw = r.read()
        root = ET.fromstring(raw)
        items = root.findall(".//item")
        if not items:
            items = root.findall(".//{http://www.w3.org/2005/Atom}entry")
        title = ""
        date = ""
        if items:
            it = items[0]
            t = it.find("title")
            if t is None:
                t = it.find("{http://www.w3.org/2005/Atom}title")
            title = (t.text or "")[:80] if t is not None else ""
            d = it.find("pubDate")
            if d is None:
                d = it.find("{http://www.w3.org/2005/Atom}updated")
            date = (d.text or "")[:30] if d is not None else ""
        print(f"OK   {name:10s} n={len(items):3d} bytes={len(raw):7d} | {title} | {date}")
    except Exception as e:
        print(f"FAIL {name:10s} {type(e).__name__}: {str(e)[:90]}")
