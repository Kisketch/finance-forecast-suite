import sys
from pathlib import Path
import pandas as pd

ROOT = Path(r"C:\Users\Lgnatius\Documents\AI产出\工具\金融分析预测")
sys.path.insert(0, str(ROOT / "src"))
from finance_app.data.store import DataStore
from finance_app.analytics import performance as perf

ds = DataStore()

def row(sym):
    d = ds.get(sym)
    p = perf.performance_row(d)
    return p

def md_table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(x) for x in r) + " |")
    return "\n".join(out)

indices = [("^GSPC", "标普500"), ("^IXIC", "纳斯达克综合"), ("^DJI", "道琼斯工业"), ("^RUT", "罗素2000"),
           ("^HSI", "恒生指数"), ("^HSCE", "恒生国企"), ("^HSTECH", "恒生科技"),
           ("000001.SS", "上证指数"), ("000300.SS", "沪深300"), ("399006.SZ", "创业板指")]
rows = []
for s, n in indices:
    p = row(s)
    rows.append([n, s, f"{p['last']:.2f}", f"{p['ret_1m']*100:+.2f}%", f"{p['ret_3m']*100:+.2f}%",
                 f"{p['ret_ytd']*100:+.2f}%", f"{p['ret_1y']*100:+.2f}%",
                 f"{p['vol_1y']*100:.1f}%", f"{p['max_dd_1y']*100:.1f}%"])
print("## 指数\n")
print(md_table(["指数", "代码", "最新", "1月", "3月", "YTD", "1年", "年化波动", "1年最大回撤"], rows))

sectors = [("real_estate", "XLRE", "房地产"), ("energy", "XLE", "能源"), ("oil_gas", "XOP", "油气开采"),
           ("clean_energy", "ICLN", "清洁能源"), ("solar", "TAN", "太阳能"), ("tech", "XLK", "科技"),
           ("finance", "XLF", "金融"), ("utilities", "XLU", "公用事业")]
rows = []
for g, s, n in sectors:
    p = row(s)
    rows.append([n, s, f"{p['ret_1m']*100:+.2f}%", f"{p['ret_3m']*100:+.2f}%", f"{p['ret_ytd']*100:+.2f}%",
                 f"{p['ret_1y']*100:+.2f}%", f"{p['vol_1y']*100:.1f}%", f"{p['max_dd_1y']*100:.1f}%"])
print("\n## 板块 ETF\n")
print(md_table(["板块", "ETF", "1月", "3月", "YTD", "1年", "年化波动", "1年最大回撤"], rows))

commodities = [("CL=F", "WTI原油"), ("BZ=F", "布伦特原油"), ("NG=F", "天然气"), ("GC=F", "黄金"), ("SI=F", "白银"), ("HG=F", "铜"), ("DX-Y.NYB", "美元指数")]
rows = []
for s, n in commodities:
    p = row(s)
    rows.append([n, s, f"{p['last']:.2f}", f"{p['ret_1m']*100:+.2f}%", f"{p['ret_3m']*100:+.2f}%",
                 f"{p['ret_ytd']*100:+.2f}%", f"{p['ret_1y']*100:+.2f}%", f"{p['vol_1y']*100:.1f}%"])
print("\n## 商品与美元\n")
print(md_table(["资产", "代码", "最新", "1月", "3月", "YTD", "1年", "年化波动"], rows))

rows = []
for s, n in [("0700.HK", "腾讯控股"), ("600519.SS", "贵州茅台"), ("000002.SZ", "万科A"),
             ("601857.SS", "中国石油"), ("XOM", "埃克森美孚"), ("PLD", "安博"), ("SPG", "西蒙地产"),
             ("0883.HK", "中国海洋石油")]:
    p = row(s)
    rows.append([n, s, f"{p['last']:.2f}", f"{p['ret_1m']*100:+.2f}%", f"{p['ret_ytd']*100:+.2f}%",
                 f"{p['ret_1y']*100:+.2f}%", f"{p['vol_1y']*100:.1f}%", f"{p['max_dd_1y']*100:.1f}%"])
print("\n## 代表性个股\n")
print(md_table(["标的", "代码", "最新", "1月", "YTD", "1年", "年化波动", "1年最大回撤"], rows))

corr = perf.correlation_matrix(ds.by_symbol, ["^GSPC", "^HSI", "000001.SS", "CL=F", "GC=F", "DX-Y.NYB"], 252)
print("\n## 相关性\n")
print("| | " + " | ".join(corr["symbols"]) + " |")
print("|" + "|".join(["---"] * (len(corr["symbols"]) + 1)) + "|")
for i, s in enumerate(corr["symbols"]):
    print("| " + s + " | " + " | ".join("—" if v is None else f"{v:.2f}" for v in corr["matrix"][i]) + " |")

print("\n## 目标价差\n")
levels = {"S&P 500": 7712.57, "恒生指数": 23651.87, "恒生科技": 3994.77}
targets = [
    ("Goldman Sachs", "S&P 500", 7600, "2026-04-02"),
    ("Morgan Stanley", "S&P 500", 7800, "2026-09-29"),
    ("J.P. Morgan", "S&P 500", 8000, "2026-08-10"),
    ("Morgan Stanley", "恒生指数", 27500, "2025-12"),
    ("浦银国际", "恒生指数", 27600, "2025-12"),
    ("光大证券国际", "恒生指数", 28000, "2026-06"),
    ("富途证券", "恒生指数", 31000, "2026-01"),
    ("海通国际", "恒生指数", 34000, "2025-12"),
    ("光大证券国际", "恒生科技", 6000, "2026-06"),
]
rows = []
for firm, idx, tgt, date in targets:
    cur = levels[idx]
    rows.append([firm, idx, f"{tgt:,}", f"{cur:,.2f}", f"{(tgt/cur-1)*100:+.2f}%", date])
print(md_table(["机构", "指数", "目标", "当前", "空间", "日期"], rows))
