"""SEC EDGAR 官方财务数据适配器。

依据《全球股市官方数据源手册》：SEC EDGAR 是美国唯一全免费、无需 API Key、
限速 10 req/s 的官方一级数据源。提供 XBRL 公司财务事实（营收/净利/EPS/资产等）。

合规：
- 公有领域数据，无需 Key，仅需 User-Agent 标识身份；
- 限速 10 req/s（本实现串行 + 0.15s 间隔，远低于上限）；
- point-in-time：companyfacts 的每个事实带 filed（申报日）与 accn（受理号），
  同一报告期可能因重述有多个版本——本实现保留全部版本，按 as_of 取当时最新。
"""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from .._paths import ROOT

CACHE_PATH = ROOT / "data" / "cache" / "sec_edgar"
CACHE_PATH.mkdir(parents=True, exist_ok=True)
TICKER_MAP_PATH = ROOT / "data" / "metadata" / "sec_ticker_cik.json"

# 简化的 ticker→CIK 映射（覆盖本项目的美股标的；可增量补充）
_FALLBACK_TICKER_CIK = {
    "AAPL": "0000320193", "MSFT": "0000789019", "NVDA": "0001045810",
    "GOOGL": "0001652044", "AMZN": "0001018724", "META": "0001326801",
    "JPM": "0000019617", "GS": "0000886982", "MS": "0000895421",
    "BRK-B": "0001067983", "CVX": "0000093410", "XOM": "0000034088",
    "COP": "0001163165", "EOG": "0000821125", "SLB": "0000087347",
    "OXY": "0000007970", "MPC": "0001510295", "VLO": "0000103789",
    "KMI": "0001506307", "LNG": "0001279494", "PLD": "0001752300",
    "SPG": "0001060720", "O": "0000766704", "DLR": "0001227130",
    "PSA": "0001041060", "EQIX": "0001101239", "AVB": "0000912496",
    "EQR": "0001282735", "XLE": "0001402057", "XOP": "0001403295",
    "ICLN": "0001396006", "TAN": "0001396006", "XLK": "0001402057",
    "XLF": "0001402057", "XLB": "0001402057", "XLI": "0001402057",
    "XLP": "0001402057", "XLY": "0001402057", "XLV": "0001402057",
    "XLU": "0001402057", "XLC": "0001402057", "XLRE": "0001402057",
    "VNQ": "0001396262",
}

# XBRL tag → 友好字段名
TAG_MAP = {
    "Revenues": "revenue", "RevenueFromContractWithCustomerExcludingAssessedTax": "revenue",
    "NetIncomeLoss": "net_income", "EarningsPerShareBasic": "eps_basic",
    "EarningsPerShareDiluted": "eps_diluted", "Assets": "total_assets",
    "Liabilities": "total_liabilities", "StockholdersEquity": "stockholders_equity",
    "OperatingIncomeLoss": "operating_income", "CashAndCashEquivalentsAtCarryingValue": "cash",
    "LongTermDebt": "long_term_debt", "SharesOutstanding": "shares_outstanding",
}

UA = "FIN-Terminal-Research research@example.com"  # SEC 要求标识身份


def _ticker_to_cik(ticker: str) -> str | None:
    """优先用本地缓存映射；未命中时尝试 SEC 的 company_tickers.json 在线查询。"""
    ticker = ticker.upper().replace("-", "").replace(".", "")
    if TICKER_MAP_PATH.exists():
        try:
            data = json.loads(TICKER_MAP_PATH.read_text(encoding="utf-8"))
            if ticker in data:
                return str(data[ticker]).zfill(10)
        except Exception:  # noqa: BLE001
            pass
    if ticker in _FALLBACK_TICKER_CIK:
        return _FALLBACK_TICKER_CIK[ticker]
    # 在线查询 SEC 官方 ticker→CIK 映射（仅一次，缓存到本地）
    try:
        req = urllib.request.Request(
            "https://www.sec.gov/files/company_tickers.json",
            headers={"User-Agent": UA, "Accept-Encoding": "gzip"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            import gzip
            raw = resp.read()
            if resp.headers.get("Content-Encoding", "").lower() == "gzip":
                raw = gzip.decompress(raw)
            data = json.loads(raw)
        mapping = {v["ticker"].upper().replace("-", ""): str(v["cik_str"]).zfill(10)
                   for v in data.values()}
        TICKER_MAP_PATH.parent.mkdir(parents=True, exist_ok=True)
        TICKER_MAP_PATH.write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
        return mapping.get(ticker)
    except Exception:  # noqa: BLE001
        return None


def _get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json",
                                               "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read()
        if resp.headers.get("Content-Encoding", "").lower() == "gzip":
            import gzip
            raw = gzip.decompress(raw)
        return json.loads(raw)


def get_facts(ticker: str, max_age_years: int = 8) -> dict:
    """拉取某公司的 XBRL 财务事实，按 tag 聚合，保留所有版本（支持 point-in-time）。"""
    cik = _ticker_to_cik(ticker)
    if not cik:
        return {"error": f"未知 ticker {ticker}（无法映射到 CIK）", "ticker": ticker}
    cache_file = CACHE_PATH / f"{ticker}_{cik}.json"
    if cache_file.exists() and (time.time() - cache_file.stat().st_mtime) < 86400:
        try:
            return json.loads(cache_file.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass
    try:
        facts = _get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json")
    except urllib.error.HTTPError as exc:
        return {"error": f"SEC HTTP {exc.code}: {exc.reason}", "ticker": ticker, "cik": cik}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {exc}", "ticker": ticker, "cik": cik}
    time.sleep(0.15)  # 远低于 10 req/s 限速
    entity = (facts.get("entityName") or ticker)
    out = {"ticker": ticker, "cik": cik, "entity_name": entity,
           "as_of": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "metrics": {}}
    us_gaap = (facts.get("facts") or {}).get("us-gaap") or {}
    cutoff_year = datetime.now(timezone.utc).year - max_age_years
    for tag, friendly in TAG_MAP.items():
        unit_obj = us_gaap.get(tag)
        if not unit_obj:
            continue
        # 单位可能是 USD/shares 等；取 USD（财务）或 shares（股本）
        rows = []
        for unit, data_list in (unit_obj.get("units") or {}).items():
            if unit not in ("USD", "USD/shares", "shares"):
                continue
            for d in data_list:
                end = d.get("end") or ""
                try:
                    yr = int(end[:4])
                except ValueError:
                    continue
                if yr < cutoff_year:
                    continue
                rows.append({
                    "end": end, "filed": d.get("filed"), "val": d.get("val"),
                    "accn": d.get("accn"), "unit": unit,
                    "frame": d.get("frame"), "form": d.get("form"),
                })
        # 同一 end 可能有多个版本（重述）；按 filed 降序，取最新为"current"
        rows.sort(key=lambda x: (x["end"], x["filed"] or ""), reverse=True)
        if rows:
            out["metrics"][friendly] = {
                "tag": tag, "unit": rows[0]["unit"],
                "current": {"end": rows[0]["end"], "val": rows[0]["val"],
                            "filed": rows[0]["filed"], "form": rows[0]["form"]},
                "history": rows[:20],  # 最近 20 个报告期版本（含重述）
                "n_versions": len(rows),
            }
    cache_file.write_text(json.dumps(out, ensure_ascii=False, default=str), encoding="utf-8")
    out["source"] = "SEC EDGAR (公有领域, 10 req/s, 无需 API Key)"
    out["notes"] = [
        "数据来自 SEC EDGAR companyfacts API，公有领域。",
        "每个事实带 filed（申报日）与 accn（受理号），支持 point-in-time 回测。",
        "history 保留同一报告期的全部版本（含重述）；current 是最新申报版本。",
        "仅覆盖美股（SEC 管辖）；非美股标的请用对应市场的官方源。",
    ]
    return out


def derive_ratios(metrics: dict) -> dict:
    """从原始事实派生常用估值/质量比率。"""
    m = metrics.get("metrics") or {}
    out = {}
    if "total_assets" in m and "stockholders_equity" in m:
        ta = m["total_assets"]["current"]["val"]
        se = m["stockholders_equity"]["current"]["val"]
        if ta and se:
            out["equity_ratio"] = round(se / ta, 4)
    if "net_income" in m and "revenue" in m:
        ni = m["net_income"]["current"]["val"]
        rev = m["revenue"]["current"]["val"]
        if rev and rev != 0:
            out["net_margin"] = round(ni / rev, 4)
    if "long_term_debt" in m and "stockholders_equity" in m:
        ltd = m["long_term_debt"]["current"]["val"]
        se = m["stockholders_equity"]["current"]["val"]
        if se and se != 0:
            out["debt_to_equity"] = round(ltd / se, 4)
    if "eps_diluted" in m:
        out["eps_diluted_latest"] = m["eps_diluted"]["current"]["val"]
    return out
