"""内存数据仓库：加载长表、构建总览与板块视图。"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from ..analytics import indicators as ind
from ..analytics import performance as perf

from .._paths import ROOT

PROC = ROOT / "data" / "processed" / "prices_long.csv"
META = ROOT / "data" / "metadata" / "data_quality.json"
CACHE = ROOT / "data" / "cache"
CACHE.mkdir(parents=True, exist_ok=True)

INDEX_SYMBOLS = ["^GSPC", "^IXIC", "^DJI", "^RUT", "^HSI", "^HSCE", "^HSTECH", "000001.SS", "000300.SS", "399006.SZ"]
SECTOR_ETFS = {
    "real_estate": "XLRE", "energy": "XLE", "tech": "XLK", "finance": "XLF",
    "health": "XLV", "consumer": "XLY", "staples": "XLP", "industrial": "XLI",
    "materials": "XLB", "communication": "XLC", "utilities": "XLU",
    "clean_energy": "ICLN", "solar": "TAN", "oil_gas": "XOP",
}
SECTOR_CN = {
    "real_estate": "房地产", "energy": "能源", "tech": "科技", "finance": "金融",
    "health": "医疗", "consumer": "可选消费", "staples": "必需消费", "industrial": "工业",
    "materials": "原材料", "communication": "通信服务", "utilities": "公用事业",
    "clean_energy": "清洁能源", "solar": "太阳能", "oil_gas": "油气开采",
}

# 板块 -> 成分标的（跨市场显式映射；YAML 的 group 是抓取分组，不适合直接当板块）
SECTOR_MEMBERS = {
    "real_estate": ["PLD", "SPG", "O", "DLR", "PSA", "EQIX", "AVB", "EQR",
                    "0016.HK", "0823.HK", "0688.HK", "1109.HK",
                    "000002.SZ", "600048.SS", "001979.SZ"],
    "energy": ["XOM", "CVX", "COP", "EOG", "SLB", "OXY", "MPC", "VLO", "KMI", "LNG",
               "0883.HK", "0386.HK", "0857.HK", "1088.HK", "1898.HK",
               "601857.SS", "600028.SS", "601088.SS"],
    "oil_gas": ["XOM", "CVX", "COP", "EOG", "OXY", "SLB", "MPC", "VLO",
                "0883.HK", "0386.HK", "0857.HK", "601857.SS", "600028.SS"],
    "clean_energy": ["601012.SS"],
    "solar": ["601012.SS"],
    "tech": ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META",
             "0700.HK", "9988.HK", "3690.HK", "300750.SZ", "002594.SZ", "601012.SS"],
    "finance": ["JPM", "GS", "MS", "BRK-B", "0388.HK", "0005.HK", "1299.HK", "2318.HK",
                "601318.SS", "600036.SS", "601398.SS", "600030.SS"],
    "utilities": ["600900.SS"],
}
CORR_SYMBOLS = ["^GSPC", "^HSI", "000001.SS", "CL=F", "GC=F", "DX-Y.NYB"]


class DataStore:
    def __init__(self) -> None:
        self.df: pd.DataFrame | None = None
        self.by_symbol: dict[str, pd.DataFrame] = {}
        self.meta: dict = {}
        self.load()

    def load(self) -> None:
        if not PROC.exists():
            raise FileNotFoundError(f"missing {PROC}; run fetch_market.py first")
        df = pd.read_csv(PROC, parse_dates=["date"])
        df = df.sort_values(["symbol", "date"]).reset_index(drop=True)
        self.df = df
        for sym, g in df.groupby("symbol", sort=False):
            g = g.set_index("date").sort_index()
            g = g[~g.index.duplicated(keep="last")]
            self.by_symbol[sym] = g
        self.meta = json.loads(META.read_text(encoding="utf-8")) if META.exists() else {}

    # ---------- 基础 ----------
    def get(self, symbol: str) -> pd.DataFrame | None:
        return self.by_symbol.get(symbol)

    def info(self, symbol: str) -> dict:
        df = self.get(symbol)
        if df is None or df.empty:
            return {}
        end = df.index[-1].normalize()
        max_date = self.df["date"].max().normalize() if self.df is not None else end
        meta = (self.meta.get("per_symbol") or {}).get(symbol, {})
        return {
            "symbol": symbol,
            "name_cn": str(df["name_cn"].iloc[-1]),
            "name_en": str(df["name_en"].iloc[-1]),
            "market": str(df["market"].iloc[-1]),
            "group": str(df["group"].iloc[-1]),
            "rows": int(len(df)),
            "start": str(df.index[0].date()),
            "end": str(end.date()),
            "last": float(df["close"].iloc[-1]),
            "stale": bool((max_date - end).days > 30),
            "flags": meta.get("flags", []),
        }

    def universe(self) -> list[dict]:
        out = []
        for sym, df in self.by_symbol.items():
            out.append(self.info(sym))
        return sorted(out, key=lambda x: (x.get("market", ""), x.get("group", ""), x["symbol"]))

    # ---------- 总览 ----------
    def overview(self) -> dict:
        as_of = str(self.df["date"].max().date()) if self.df is not None else None
        indices = []
        for s in INDEX_SYMBOLS:
            df = self.get(s)
            if df is None or len(df) < 30:
                continue
            row = perf.performance_row(df)
            info = self.info(s)
            row.update({"symbol": s, "name_cn": info.get("name_cn", s),
                        "market": info.get("market", ""), "last_date": str(df.index[-1].date())})
            indices.append(row)

        sectors = perf.sector_scoreboard(self.by_symbol, SECTOR_ETFS, bench="^GSPC")
        for row in sectors:
            row["name_cn"] = SECTOR_CN.get(row["group"], row["group"])

        # 股票池宽度
        stock_groups = {"US": [], "HK": [], "CN": []}
        for sym, df in self.by_symbol.items():
            m = str(df["market"].iloc[-1])
            if m in stock_groups and not sym.startswith("^") and sym != "DX-Y.NYB" and len(df) > 200:
                if not self.info(sym).get("stale"):
                    stock_groups[m].append(sym)
        breadth = {m: perf.breadth(self.by_symbol, syms) for m, syms in stock_groups.items()}

        corr = perf.correlation_matrix(self.by_symbol, CORR_SYMBOLS, 252)

        signals = self._signals()
        return {
            "as_of": as_of,
            "generated_at": pd.Timestamp.now().isoformat(timespec="seconds"),
            "indices": indices,
            "sectors": sectors,
            "breadth": breadth,
            "correlation": corr,
            "signals": signals,
            "coverage": {
                "symbols": len(self.by_symbol),
                "rows": int(len(self.df)) if self.df is not None else 0,
                "start": str(self.df["date"].min().date()) if self.df is not None else None,
            },
        }

    def _signals(self) -> list[dict]:
        out = []
        for sym, df in self.by_symbol.items():
            if len(df) < 210:
                continue
            c = df["close"]
            rsi = ind.rsi(c, 14).iloc[-1]
            ma50, ma200 = ind.sma(c, 50), ind.sma(c, 200)
            last = float(c.iloc[-1])
            if pd.notna(rsi) and (rsi >= 70 or rsi <= 30):
                out.append({"symbol": sym, "name_cn": str(df["name_cn"].iloc[-1]),
                            "type": "RSI", "value": round(float(rsi), 1),
                            "text": f"RSI {rsi:.1f}（{'超买' if rsi >= 70 else '超卖'}）",
                            "direction": "down" if rsi >= 70 else "up"})
            if pd.notna(ma50.iloc[-1]) and pd.notna(ma50.iloc[-2]):
                if ma50.iloc[-2] <= c.iloc[-2] and ma50.iloc[-1] > last:
                    out.append({"symbol": sym, "name_cn": str(df["name_cn"].iloc[-1]),
                                "type": "MA50", "value": round(last, 2),
                                "text": "跌破 50 日均线", "direction": "down"})
                elif ma50.iloc[-2] >= c.iloc[-2] and ma50.iloc[-1] < last:
                    out.append({"symbol": sym, "name_cn": str(df["name_cn"].iloc[-1]),
                                "type": "MA50", "value": round(last, 2),
                                "text": "站上 50 日均线", "direction": "up"})
        return out[:24]

    # ---------- 序列 ----------
    def series(self, symbol: str, rng: str = "1y") -> dict:
        df = self.get(symbol)
        if df is None:
            return {}
        days = {"1m": 21, "3m": 63, "6m": 126, "1y": 252, "3y": 756, "5y": 1260, "max": None}.get(rng, 252)
        d = df if days is None else df.tail(days + 1)
        d = ind.add_indicators(d)
        cols = ["open", "high", "low", "close", "volume", "ma20", "ma50", "ma200",
                "boll_up", "boll_low", "rsi14", "macd", "macd_signal", "macd_hist", "vol20", "dd"]
        payload = {"symbol": symbol, "info": self.info(symbol), "dates": [str(x.date()) for x in d.index]}
        for c in cols:
            if c in d:
                payload[c] = [None if pd.isna(v) else round(float(v), 6) for v in d[c]]
        return payload

    # ---------- 板块 ----------
    def sector(self, group: str) -> dict:
        etf = SECTOR_ETFS.get(group)
        if not etf:
            return {}
        members = []
        excluded = []
        candidate_symbols = SECTOR_MEMBERS.get(group)
        if candidate_symbols is None:
            candidate_symbols = [s for s, df in self.by_symbol.items()
                                 if str(df["group"].iloc[-1]) == group]
        for sym in candidate_symbols:
            df = self.get(sym)
            if df is None or len(df) < 30 or sym == etf:
                continue
            info = self.info(sym)
            if info.get("stale"):
                excluded.append({"symbol": sym, "name_cn": info.get("name_cn"), "end": info.get("end")})
                continue
            row = perf.performance_row(df)
            row.update({"symbol": sym, "name_cn": str(df["name_cn"].iloc[-1])})
            members.append(row)
        members.sort(key=lambda r: (r.get("ret_1m") is None, -(r.get("ret_1m") or 0)))
        bench = self.get("^GSPC")
        rs = perf.relative_strength(self.get(etf), bench, 126) if bench is not None else pd.Series(dtype=float)
        return {
            "group": group,
            "name_cn": SECTOR_CN.get(group, group),
            "etf": etf,
            "etf_perf": perf.performance_row(self.get(etf)) if self.get(etf) is not None else None,
            "members": members,
            "excluded": excluded,
            "relative_strength": [None if pd.isna(v) else round(float(v), 4) for v in rs],
            "rs_dates": [str(x.date()) for x in rs.index],
        }

    # ---------- 预测 ----------
    def forecast(self, symbol: str, horizon: int, model: str) -> dict:
        from ..models.forecast import run_forecast, save_result
        key = f"{symbol.replace('^','IDX_').replace('=','_')}_{horizon}_{model}.json"
        path = CACHE / key
        df = self.get(symbol)
        if df is None:
            return {"error": "unknown symbol"}
        result = run_forecast(df, symbol, horizon=horizon, model_name=model)
        save_result(result, path)
        data = result.__dict__.copy()
        data["info"] = self.info(symbol)
        return data


if __name__ == "__main__":
    ds = DataStore()
    print(len(ds.by_symbol), "symbols")
    print(json.dumps(ds.overview()["coverage"], ensure_ascii=False))
