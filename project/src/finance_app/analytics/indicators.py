"""技术指标与风险指标（纯 pandas/numpy，无未来函数）。"""
from __future__ import annotations

import numpy as np
import pandas as pd


def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=n).mean()


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False, min_periods=n).mean()


def rsi(s: pd.Series, n: int = 14) -> pd.Series:
    delta = s.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    avg_loss = loss.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def macd(s: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    line = ema(s, fast) - ema(s, slow)
    sig = line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    return pd.DataFrame({"macd": line, "signal": sig, "hist": line - sig})


def bollinger(s: pd.Series, n: int = 20, k: float = 2.0) -> pd.DataFrame:
    mid = sma(s, n)
    sd = s.rolling(n, min_periods=n).std(ddof=0)
    return pd.DataFrame({"mid": mid, "upper": mid + k * sd, "lower": mid - k * sd})


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    prev = close.shift(1)
    tr = pd.concat([(high - low).abs(), (high - prev).abs(), (low - prev).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def daily_returns(close: pd.Series) -> pd.Series:
    return close.pct_change()


def log_returns(close: pd.Series) -> pd.Series:
    return np.log(close).diff()


def rolling_vol(close: pd.Series, n: int = 21, ann: int = 252) -> pd.Series:
    return close.pct_change().rolling(n, min_periods=n).std(ddof=0) * np.sqrt(ann)


def max_drawdown(close: pd.Series) -> float:
    peak = close.cummax()
    dd = close / peak - 1.0
    return float(dd.min()) if len(dd) else float("nan")


def drawdown_series(close: pd.Series) -> pd.Series:
    return close / close.cummax() - 1.0


def sharpe(close: pd.Series, rf: float = 0.0, ann: int = 252) -> float:
    r = close.pct_change().dropna()
    if r.empty or r.std(ddof=0) == 0:
        return float("nan")
    excess = r - rf / ann
    return float(excess.mean() / r.std(ddof=0) * np.sqrt(ann))


def sortino(close: pd.Series, ann: int = 252) -> float:
    r = close.pct_change().dropna()
    downside = r[r < 0]
    if downside.empty or downside.std(ddof=0) == 0:
        return float("nan")
    return float(r.mean() / downside.std(ddof=0) * np.sqrt(ann))


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """为单标的 OHLCV 表追加常用指标列。"""
    out = df.copy()
    c = out["close"]
    for n in (5, 10, 20, 50, 120, 200):
        out[f"ma{n}"] = sma(c, n)
    out["ema12"] = ema(c, 12)
    out["ema26"] = ema(c, 26)
    m = macd(c)
    out["macd"], out["macd_signal"], out["macd_hist"] = m["macd"], m["signal"], m["hist"]
    out["rsi14"] = rsi(c, 14)
    b = bollinger(c)
    out["boll_mid"], out["boll_up"], out["boll_low"] = b["mid"], b["upper"], b["lower"]
    out["atr14"] = atr(out, 14)
    out["vol20"] = rolling_vol(c, 20)
    out["dd"] = drawdown_series(c)
    out["ret"] = c.pct_change()
    return out


def period_return(close: pd.Series, days: int | None = None, ytd: bool = False) -> float:
    if close.empty:
        return float("nan")
    if ytd:
        year = close.index[-1].year
        start = close[close.index.year == year]
        if start.empty:
            return float("nan")
        return float(close.iloc[-1] / start.iloc[0] - 1)
    if days is None or len(close) <= days:
        return float("nan")
    return float(close.iloc[-1] / close.iloc[-days - 1] - 1)
