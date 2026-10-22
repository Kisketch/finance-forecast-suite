"""全量数据校验 + 分析底稿生成。

输出：
  analysis/validation_report.json
  analysis/market_stats.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from finance_app.data.store import DataStore  # noqa: E402
from finance_app.analytics import performance as perf  # noqa: E402

OUT = ROOT / "analysis"
OUT.mkdir(parents=True, exist_ok=True)

ds = DataStore()
checks = []
violations = []
for sym, df in ds.by_symbol.items():
    d = df.reset_index()
    o, h, l, c = d["open"].astype(float), d["high"].astype(float), d["low"].astype(float), d["close"].astype(float)
    bad_high = int(((h + 1e-6) < np.maximum(o, c)).sum())
    bad_low = int(((l - 1e-6) > np.minimum(o, c)).sum())
    dup = int(d["date"].duplicated().sum())
    nonpos = int((c <= 0).sum())
    gaps = int((d["date"].diff().dt.days > 10).sum())
    checks.append({
        "symbol": sym, "rows": len(d), "bad_high": bad_high, "bad_low": bad_low,
        "duplicate_dates": dup, "nonpositive_close": nonpos, "gaps_gt_10d": gaps,
    })
    if bad_high or bad_low or dup:
        violations.append(sym)

# 跨源抽样核对（腾讯/新浪）
cross = []
def tencent(code: str) -> pd.DataFrame:
    import time
    import urllib.request
    url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={code},day,,,400,qfq"
    last = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://gu.qq.com/"})
            with urllib.request.urlopen(req, timeout=30) as r:
                j = json.loads(r.read())
            rows = ((j.get("data") or {}).get(code) or {}).get("qfqday") or []
            if rows:
                x = pd.DataFrame(rows).iloc[:, :6]
                x.columns = ["date", "open", "close", "high", "low", "volume"]
                x["date"] = pd.to_datetime(x["date"])
                return x
            last = ValueError("empty rows")
        except Exception as exc:  # noqa: BLE001
            last = exc
        time.sleep(6)
    raise last or ValueError("empty rows")

def tencent_quote(code: str) -> float | None:
    import urllib.request
    url = f"https://qt.gtimg.cn/q={code}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read().decode("gbk", "ignore")
    parts = raw.split("=")[-1].strip().strip('"').split("~")
    return float(parts[3]) if len(parts) > 4 else None


for code, sym in [("sh000001", "000001.SS"), ("hk00700", "0700.HK")]:
    try:
        ext = tencent(code).set_index("date")
        loc = ds.get(sym)
        common = ext.index.intersection(loc.index)[-3:]
        for dt in common:
            a, b = float(ext.loc[dt, "close"]), float(loc.loc[dt, "close"])
            cross.append({"symbol": sym, "date": str(dt.date()), "tencent": a, "app": b,
                          "diff_pct": round((a - b) / b * 100, 4) if b else None})
    except Exception as exc:  # noqa: BLE001
        try:
            a = tencent_quote(code)
            b = float(ds.get(sym)["close"].iloc[-1])
            cross.append({"symbol": sym, "date": "latest_quote", "tencent": a, "app": b,
                          "diff_pct": round((a - b) / b * 100, 4) if a and b else None,
                          "note": f"kline unavailable: {exc}"})
        except Exception as exc2:  # noqa: BLE001
            cross.append({"symbol": sym, "error": f"{exc}; {exc2}"})

market = {}
for sym in ["^GSPC", "^IXIC", "^DJI", "^HSI", "^HSCE", "^HSTECH", "000001.SS", "000300.SS", "399006.SZ"]:
    df = ds.get(sym)
    if df is None:
        continue
    market[sym] = {"name_cn": ds.info(sym)["name_cn"], **perf.performance_row(df)}

# 板块 ETF
sectors = {}
for g, s in {"real_estate": "XLRE", "energy": "XLE", "oil_gas": "XOP", "clean_energy": "ICLN",
             "solar": "TAN", "tech": "XLK", "finance": "XLF", "utilities": "XLU"}.items():
    df = ds.get(s)
    if df is not None:
        sectors[g] = {"etf": s, "name_cn": ds.info(s)["name_cn"], **perf.performance_row(df)}

# 相关性（近 252 日）
corr = perf.correlation_matrix(ds.by_symbol, ["^GSPC", "^HSI", "000001.SS", "CL=F", "GC=F", "DX-Y.NYB"], 252)

report = {
    "generated_at": pd.Timestamp.now().isoformat(timespec="seconds"),
    "symbols": len(ds.by_symbol),
    "rows": int(len(ds.df)),
    "date_range": [str(ds.df["date"].min().date()), str(ds.df["date"].max().date())],
    "ohlc_violations": violations,
    "checks": checks,
    "cross_source": cross,
    "market": market,
    "sectors": sectors,
    "correlation": corr,
}
(OUT / "validation_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
(OUT / "market_stats.json").write_text(json.dumps({"market": market, "sectors": sectors, "correlation": corr},
                                                   ensure_ascii=False, indent=2), encoding="utf-8")

print("symbols", len(ds.by_symbol), "rows", len(ds.df), "ohlc_violations", len(violations))
print("bad OHLC sample", violations[:10])
print("cross-source", json.dumps(cross, ensure_ascii=False))
print("\nIndices:")
for s, v in market.items():
    print(f"{s:11s} {v['name_cn']:8s} last={v['last']:.2f} 1m={v['ret_1m']*100:6.2f}% ytd={v['ret_ytd']*100:6.2f}% 1y={v['ret_1y']*100:6.2f}% vol={v['vol_1y']*100:5.1f}% dd={v['max_dd_1y']*100:6.1f}%")
print("\nSectors:")
for g, v in sectors.items():
    print(f"{g:12s} {v['etf']:5s} 1m={v['ret_1m']*100:6.2f}% 3m={v['ret_3m']*100:6.2f}% ytd={v['ret_ytd']*100:6.2f}% 1y={v['ret_1y']*100:6.2f}%")
