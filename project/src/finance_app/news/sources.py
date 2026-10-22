"""官方新闻源：RSS/Atom + 官方列表页（HTML）适配器。

只使用政府、央行、监管、交易所、多边机构、公司新闻室；不接社交媒体/论坛。
所有文章正文都视为不可信数据，不执行其中的任何指令。
"""
from __future__ import annotations

import gzip
import hashlib
import html as html_lib
import re
import ssl
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin, urlparse, urlunparse

import yaml

from .._paths import ROOT

CONFIG = ROOT / "config" / "news_sources.yaml"
ATOM = "{http://www.w3.org/2005/Atom}"
DATE_RE = re.compile(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})")
COMPACT_RE = re.compile(r"(?<!\d)(\d{4})(\d{2})(\d{2})(?!\d)")
TAG_RE = re.compile(r"<[^>]+>")


@dataclass
class Source:
    id: str
    name: str
    type: str
    url: str
    tier: str
    region: str
    category: str
    language: str = "en"
    enabled: bool = True
    max_items: int = 20
    base_url: str = ""
    link_regex: str = ""
    article_fetch: bool = False


@dataclass
class NewsItem:
    id: str
    source_id: str
    source_name: str
    source_tier: str
    region: str
    category: str
    language: str
    title: str
    summary: str
    url: str
    published_at: str
    fetched_at: str
    date_estimated: bool = False
    meta: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "source_id": self.source_id, "source_name": self.source_name,
            "source_tier": self.source_tier, "region": self.region, "category": self.category,
            "language": self.language, "title": self.title, "summary": self.summary,
            "url": self.url, "published_at": self.published_at, "fetched_at": self.fetched_at,
            "date_estimated": int(self.date_estimated), "meta_json": self.meta or {},
        }


@dataclass
class SourceResult:
    source: Source
    items: list[NewsItem]
    error: str | None = None
    elapsed_ms: int = 0
    fetched: int = 0


DOCTYPE_RE = re.compile(rb"<!DOCTYPE[^>\[]*(\[[^\]]*\])?[^>]*>", re.I)
ENTITY_RE = re.compile(rb"<!ENTITY[^>]*>", re.I)
META_CHARSET_RE = re.compile(
    rb'<meta[^>]+charset=["\']?([a-zA-Z0-9_\-]+)', re.I)


def _decode(raw: bytes, content_type: str = "") -> str:
    """智能解码：HTTP Content-Type charset → HTML meta charset → utf-8 严格 → gb18030 回退。

    中文官方源（上交所等）普遍为 GBK/GB2312；此前一律 utf-8 ignore 会导致乱码或整段丢弃。
    """
    candidates: list[str] = []
    m = re.search(r"charset=([a-zA-Z0-9_\-]+)", content_type or "", re.I)
    if m:
        candidates.append(m.group(1))
    head = raw[:4096]
    mm = META_CHARSET_RE.search(head)
    if mm:
        candidates.append(mm.group(1).decode("ascii", "ignore"))
    candidates += ["utf-8", "gb18030"]
    for enc in candidates:
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", "replace")


def _safe_xml(raw: bytes) -> bytes:
    """剥离 DTD/内部实体，防御 XML 实体扩展（billion laughs）。"""
    if b"<!ENTITY" in raw or b"<!DOCTYPE" in raw:
        raw = DOCTYPE_RE.sub(b"", raw)
        raw = ENTITY_RE.sub(b"", raw)
    return raw


def _clean(text: str | None, limit: int = 1600) -> str:
    if not text:
        return ""
    text = html_lib.unescape(str(text))
    text = TAG_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def _parse_date(value: str | None) -> tuple[datetime | None, bool]:
    if not value:
        return None, False
    raw = str(value).strip()
    try:
        dt = parsedate_to_datetime(raw)
        if dt:
            return dt.astimezone(timezone.utc), False
    except Exception:  # noqa: BLE001
        pass
    try:
        d = raw.replace("Z", "+00:00")
        dt = datetime.fromisoformat(d)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc), False
    except Exception:  # noqa: BLE001
        pass
    m = DATE_RE.search(raw)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=timezone.utc), True
        except ValueError:
            pass
    m = COMPACT_RE.search(raw)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=timezone.utc), True
        except ValueError:
            pass
    return None, False


def _date_from_url(url: str) -> datetime | None:
    # 2026/10/20261021-4/  |  /202610/21/  |  c_20261019_  |  2026-10-21
    patterns = [
        r"/(\d{4})/(\d{2})/(\d{8})",
        r"/(\d{4})(\d{2})/(\d{2})/",
        r"_(20\d{6})_",
        r"/(20\d{2}-\d{2}-\d{2})",
        r"/(20\d{2}/\d{2}/\d{2})",
    ]
    for pat in patterns:
        m = re.search(pat, url)
        if not m:
            continue
        g = m.groups()
        try:
            if len(g) == 3 and len(g[2]) == 8:
                return datetime(int(g[2][:4]), int(g[2][4:6]), int(g[2][6:8]), tzinfo=timezone.utc)
            if len(g) == 3:
                return datetime(int(g[0]), int(g[1]), int(g[2]), tzinfo=timezone.utc)
            if len(g) == 1 and len(g[0]) == 8:
                return datetime(int(g[0][:4]), int(g[0][4:6]), int(g[0][6:8]), tzinfo=timezone.utc)
            if len(g) == 1:
                return datetime.fromisoformat(g[0]).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _id(source_id: str, url: str, title: str, published: str) -> str:
    base = url or f"{source_id}|{title}|{published[:10]}"
    return hashlib.sha1(base.encode("utf-8", "ignore")).hexdigest()[:20]


def _request(url: str, timeout: int, ua: str) -> tuple[bytes, str]:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("only http/https sources are allowed")
    req = urllib.request.Request(url, headers={
        "User-Agent": ua,
        "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, text/html, */*",
        "Accept-Encoding": "gzip",
        "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8",
    })
    with urllib.request.urlopen(req, timeout=timeout, context=ssl.create_default_context()) as resp:
        raw = resp.read(4_000_000)
        if resp.headers.get("Content-Encoding", "").lower() == "gzip":
            raw = gzip.decompress(raw)
        return raw, resp.headers.get("Content-Type", "")


def load_sources(path: Path | None = None) -> tuple[dict, list[Source]]:
    path = path or CONFIG
    if not path.exists():
        return {}, []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    settings = data.get("settings") or {}
    sources = []
    for row in data.get("sources") or []:
        if not row.get("enabled", True):
            continue
        sources.append(Source(
            id=str(row["id"]), name=str(row["name"]), type=str(row.get("type", "rss")),
            url=str(row["url"]), tier=str(row.get("tier", "official")),
            region=str(row.get("region", "GLOBAL")), category=str(row.get("category", "other")),
            language=str(row.get("language", "en")), enabled=True,
            max_items=int(row.get("max_items", settings.get("default_max_items", 20))),
            base_url=str(row.get("base_url", "")), link_regex=str(row.get("link_regex", "")),
            article_fetch=bool(row.get("article_fetch", False)),
        ))
    return settings, sources


def _parse_rss(raw: bytes) -> list[dict]:
    root = ET.fromstring(_safe_xml(raw))
    nodes = root.findall(".//item")
    if not nodes:
        nodes = root.findall(f".//{ATOM}entry")
    out = []
    for node in nodes:
        def txt(*names: str) -> str:
            for name in names:
                el = node.find(name)
                if el is not None:
                    if el.text:
                        return el.text
                    # Atom link href
                    href = el.attrib.get("href")
                    if href:
                        return href
            return ""
        link = txt("link", f"{ATOM}link")
        if not link:
            guid = node.find("guid")
            link = (guid.text or "") if guid is not None else ""
        title = txt("title", f"{ATOM}title")
        summary = txt("description", "summary", f"{ATOM}summary", f"{ATOM}content")
        published = txt("pubDate", "published", f"{ATOM}published", "updated", f"{ATOM}updated", "dc:date")
        out.append({"title": title, "link": link, "summary": summary, "published": published})
    return out


def _article_details(url: str, settings: dict, source: Source) -> tuple[str, str]:
    try:
        raw, ctype = _request(url, int(settings.get("timeout_seconds", 20)), str(settings.get("user_agent", "FinTerminal/1.0")))
        text = _decode(raw, ctype)
    except Exception:  # noqa: BLE001
        return "", ""
    desc = ""
    for pat in [
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']description["\']',
    ]:
        m = re.search(pat, text, re.I | re.S)
        if m:
            desc = _clean(m.group(1), 900)
            if len(desc) > 40:
                break
    if len(desc) < 40:
        paras = re.findall(r"<p[^>]*>(.*?)</p>", text, re.I | re.S)
        body = " ".join(_clean(p, 500) for p in paras[:4])
        desc = _clean((desc + " " + body).strip(), 1200)
    date_str = ""
    for pat in [
        r'<meta[^>]+property=["\']article:published_time["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+name=["\'](?:date|pubdate|publishdate|article:published_time)["\'][^>]+content=["\']([^"\']+)["\']',
        r'<time[^>]+datetime=["\']([^"\']+)["\']',
        r'"datePublished"\s*:\s*"([^"]+)"',
    ]:
        m = re.search(pat, text, re.I | re.S)
        if m:
            date_str = m.group(1)
            break
    return desc, date_str


def _parse_html(raw: bytes, source: Source, settings: dict) -> list[dict]:
    text = _decode(raw)
    # 先尝试 HTML 内的 RSS/Atom 自动发现
    for m in re.finditer(r'<link[^>]+type=["\']application/(?:rss|atom)\+xml["\'][^>]*>', text, re.I):
        href = re.search(r'href=["\']([^"\']+)["\']', m.group(0), re.I)
        if href:
            try:
                feed_url = urljoin(source.url, href.group(1))
                raw_feed, _ = _request(feed_url, int(settings.get("timeout_seconds", 20)), str(settings.get("user_agent", "FinTerminal/1.0")))
                parsed = _parse_rss(raw_feed)
                if parsed:
                    return [{"title": x["title"], "link": x["link"], "summary": x["summary"], "published": x["published"]} for x in parsed]
            except Exception:  # noqa: BLE001
                pass
    links = re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', text, re.I | re.S)
    regex = re.compile(source.link_regex) if source.link_regex else None
    out, seen = [], set()
    for href, label in links:
        label = _clean(label, 240)
        if len(label) < 16:
            continue
        if any(x in label.lower() for x in ("toggle filter", "read more", "view all", "load more", "sign up")):
            continue
        href = urljoin(source.base_url or source.url, href)
        if href in seen or href.startswith("javascript:"):
            continue
        if regex and not regex.search(href):
            continue
        if not regex and ("/news/" not in href and "/press" not in href):
            continue
        seen.add(href)
        out.append({"title": label, "link": href, "summary": "", "published": ""})
        if len(out) >= source.max_items:
            break
    if source.article_fetch:
        for row in out:
            desc, date_str = _article_details(row["link"], settings, source)
            if desc:
                row["summary"] = desc
            if date_str and not row.get("published"):
                row["published"] = date_str
    return out


def fetch_source(source: Source, settings: dict) -> SourceResult:
    started = time.time()
    ua = str(settings.get("user_agent", "FinTerminal/1.0"))
    timeout = int(settings.get("timeout_seconds", 20))
    try:
        raw, ctype = _request(source.url, timeout, ua)
        rows = _parse_rss(raw) if source.type == "rss" else _parse_html(raw, source, settings)
        fetched = len(rows)
        max_age = int(settings.get("max_age_days", 45))
        cutoff = _now() - timedelta(days=max_age)
        items: list[NewsItem] = []
        now = _now()
        for row in rows[: source.max_items]:
            title = _clean(row.get("title"), 400)
            link = str(row.get("link") or "").strip()
            if not title or not link:
                continue
            published, estimated = _parse_date(row.get("published"))
            if published is None:
                published = _date_from_url(link)
                estimated = published is not None
            if published is None:
                published = now
                estimated = True
            if published < cutoff:
                continue
            if published > now + timedelta(days=1):
                # 明显的未来时间戳视为源数据错误，跳过（避免影响时效权重）
                continue
            summary = _clean(row.get("summary"), 1400)
            items.append(NewsItem(
                id=_id(source.id, link, title, _iso(published)),
                source_id=source.id, source_name=source.name, source_tier=source.tier,
                region=source.region, category=source.category, language=source.language,
                title=title, summary=summary, url=link,
                published_at=_iso(published), fetched_at=_iso(now),
                date_estimated=estimated, meta={"feed_type": source.type},
            ))
        return SourceResult(source=source, items=items, fetched=fetched,
                            elapsed_ms=int((time.time() - started) * 1000))
    except Exception as exc:  # noqa: BLE001
        return SourceResult(source=source, items=[], error=f"{type(exc).__name__}: {exc}",
                            elapsed_ms=int((time.time() - started) * 1000))


def fetch_all(sources: Iterable[Source] | None = None,
              settings: dict | None = None) -> list[SourceResult]:
    configured_settings, configured = load_sources()
    use = list(sources) if sources is not None else configured
    cfg = settings or configured_settings
    workers = max(1, min(6, int(cfg.get("max_workers", 4))))
    if workers == 1 or len(use) <= 1:
        return [fetch_source(s, cfg) for s in use]
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(fetch_source, s, cfg) for s in use]
        return [f.result() for f in futures]


def dedupe(items: Iterable[NewsItem]) -> list[NewsItem]:
    seen, out = set(), []
    for item in items:
        key = item.id
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))
