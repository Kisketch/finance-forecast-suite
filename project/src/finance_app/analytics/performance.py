"""横截面绩效、相关性与板块分析。"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import indicators as ind


def performance_row(df: pd.DataFrame) -> dict:
    close = df["close"].astype(float)
    return {
        "last": float(close.iloc[-1]),
        "ret_1w": ind.period_return(close, 5),
        "ret_1m": ind.period_return(close, 21),
        "ret_3m": ind.period_return(close, 63),
        "ret_6m": ind.period_return(close, 126),
        "ret_ytd": ind.period_return(close, ytd=True),
        "ret_1y": ind.period_return(close, 252),
        "vol_1y": float(close.pct_change().tail(252).std(ddof=0) * np.sqrt(252)),
        "sharpe_1y": ind.sharpe(close.tail(253)),
        "max_dd_1y": ind.max_drawdown(close.tail(252)),
        "above_ma50": bool(close.iloc[-1] > ind.sma(close, 50).iloc[-1]) if len(close) >= 50 else None,
        "above_ma200": bool(close.iloc[-1] > ind.sma(close, 200).iloc[-1]) if len(close) >= 200 else None,
        "rsi14": float(ind.rsi(close, 14).iloc[-1]) if len(close) >= 15 else None,
    }


def performance_table(prices: dict[str, pd.DataFrame]) -> list[dict]:
    rows = []
    for sym, df in prices.items():
        if df is None or df.empty or len(df) < 30:
            continue
        try:
            row = performance_row(df)
        except Exception:  # noqa: BLE001
            continue
        row["symbol"] = sym
        rows.append(row)
    return rows


def correlation_matrix(prices: dict[str, pd.DataFrame], symbols: list[str], window: int = 252) -> dict:
    series = {}
    for s in symbols:
        df = prices.get(s)
        if df is None or df.empty:
            continue
        series[s] = df["close"].pct_change()
    if len(series) < 2:
        return {"symbols": [], "matrix": []}
    mat = pd.DataFrame(series).tail(window).corr()
    syms = list(mat.columns)
    return {
        "symbols": syms,
        "matrix": [[None if pd.isna(v) else round(float(v), 4) for v in row] for row in mat.values],
    }


def relative_strength(df: pd.DataFrame, bench: pd.DataFrame, window: int = 63) -> pd.Series:
    a = df["close"].pct_change().add(1).cumprod()
    b = bench["close"].pct_change().add(1).cumprod()
    a, b = a.align(b, join="inner")
    if len(a) <= window:
        return pd.Series(dtype=float)
    return (a / b).tail(window) / (a / b).tail(window).iloc[0] - 1


def breadth(prices: dict[str, pd.DataFrame], universe: list[str]) -> dict:
    above50 = above200 = total = 0
    for s in universe:
        df = prices.get(s)
        if df is None or len(df) < 200:
            continue
        c = df["close"]
        total += 1
        if c.iloc[-1] > ind.sma(c, 50).iloc[-1]:
            above50 += 1
        if c.iloc[-1] > ind.sma(c, 200).iloc[-1]:
            above200 += 1
    return {
        "total": total,
        "above_ma50_pct": above50 / total if total else None,
        "above_ma200_pct": above200 / total if total else None,
    }


def sector_scoreboard(prices: dict[str, pd.DataFrame], etfs: dict[str, str], bench: str = "^GSPC") -> list[dict]:
    """板块 ETF 相对基准的强弱与风险。"""
    bench_df = prices.get(bench)
    out = []
    for group, sym in etfs.items():
        df = prices.get(sym)
        if df is None or df.empty or bench_df is None:
            continue
        row = performance_row(df)
        rs = relative_strength(df, bench_df, 63)
        row.update({
            "group": group,
            "symbol": sym,
            "rs_3m": float(rs.iloc[-1]) if len(rs) else None,
            "corr_bench_1y": float(df["close"].pct_change().tail(252).corr(bench_df["close"].pct_change().tail(252))),
        })
        out.append(row)
    return out
