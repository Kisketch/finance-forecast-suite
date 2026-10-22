"""AI 增强预测引擎：在价量基础上叠加机器学习/标签工程/概率校准。

设计目标（提升方向准确率的可行路径，而非虚构 98.7%）：
1. 增强特征：ADX/DI 趋势强度、KDJ、波动率 regime 分位、季节效应、量价背离。
2. 三重障碍标签（Lopez de Prado, AFML ch.3）：上/下障碍以动态波动率设定，
   到期未触按期末方向——把"方向预测"重新定义为"路径触障碍"事件。
3. 概率校准：CalibratedClassifierCV(isotonic) 让 predict_proba 真实反映经验频率。
4. 时间衰减样本权重：远期样本权重低，适应 regime 漂移（半衰期可调）。
5. 选择性预测：输出概率 + 置信区间 + 覆盖率-准确率权衡曲线，承认"只在少数日
   有把握"。

严格无未来函数：所有特征用 shift(+n)/rolling；标签用已实现区间；训练只看目标
实现日 <= 训练截止日。新增 sklearn 依赖（CalibratedClassifierCV、ExtraTrees），
均为 sklearn 自带，无新第三方依赖。
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler

from . import advanced as adv
from ..analytics import indicators as ind


def _safe_div(a: pd.Series, b: pd.Series) -> pd.Series:
    return a / b.replace(0, np.nan)


def _adx_di(df: pd.DataFrame, n: int = 14) -> pd.DataFrame:
    """ADX/DI+ / DI-：Wilder 平滑的趋势强度指标，判断市场是否处于趋势态。"""
    h, l, c = df["high"].astype(float), df["low"].astype(float), df["close"].astype(float)
    up = h.diff()
    down = -l.diff()
    plus_dm = up.where((up > down) & (up > 0), 0.0)
    minus_dm = down.where((down > up) & (down > 0), 0.0)
    tr = ind.atr(df, n)  # 真波幅（Wilder 平滑）
    atr_s = tr.replace(0, np.nan)
    plus_di = 100 * plus_dm.ewm(alpha=1 / n, adjust=False).mean() / atr_s
    minus_di = 100 * minus_dm.ewm(alpha=1 / n, adjust=False).mean() / atr_s
    dx = 100 * _safe_div((plus_di - minus_di).abs(), plus_di + minus_di)
    adx = dx.ewm(alpha=1 / n, adjust=False).mean()
    return pd.DataFrame({"adx": adx, "plus_di": plus_di, "minus_di": minus_di})


def _kdj(df: pd.DataFrame, n: int = 9, m1: int = 3, m2: int = 3) -> pd.DataFrame:
    """KDJ 随机指标（A 股常用），捕捉短期超买超卖与拐点。"""
    h, l, c = df["high"].astype(float), df["low"].astype(float), df["close"].astype(float)
    hn = h.rolling(n, min_periods=n).max()
    ln = l.rolling(n, min_periods=n).min()
    rsv = _safe_div(c - ln, hn - ln) * 100.0
    k = rsv.ewm(alpha=1 / m1, adjust=False).mean()
    d = k.ewm(alpha=1 / m2, adjust=False).mean()
    j = 3 * k - 2 * d
    return pd.DataFrame({"kdj_k": k, "kdj_d": d, "kdj_j": j})


def build_features_advanced(df: pd.DataFrame, context: dict | None = None,
                            context_keys: Iterable[str] | None = None) -> pd.DataFrame:
    """在 advanced.build_features 基础上叠加趋势强度/超买超卖/regime/季节特征。"""
    f = adv.build_features(df, context=context, context_keys=context_keys)
    # ADX/DI：趋势态判断
    adx_df = _adx_di(df, 14)
    f["adx14"] = adx_df["adx"]
    f["di_spread"] = adx_df["plus_di"] - adx_df["minus_di"]
    # KDJ
    kdj = _kdj(df)
    f["kdj_j"] = kdj["kdj_j"]
    f["kdj_cross"] = kdj["kdj_k"] - kdj["kdj_d"]
    # 波动率 regime：当前 21 日波动率在过去 252 日的分位
    c = df["close"].astype(float)
    h = df["high"].astype(float)
    l = df["low"].astype(float)
    lr = np.log(c).diff()
    vol21 = lr.rolling(21, min_periods=21).std(ddof=0)
    f["vol_regime_q"] = vol21.rolling(252, min_periods=63).rank(pct=True)
    # EWMA 波动率（RiskMetrics 风格），捕捉波动率聚集
    f["ewma_vol20"] = lr.ewm(span=20, min_periods=20).std()
    # 量价背离：价创新高但量未创新高（顶背离风险）
    v = df["volume"].astype(float) if "volume" in df else pd.Series(0.0, index=df.index)
    hh20 = h.rolling(20, min_periods=20).max()
    hv20 = v.rolling(20, min_periods=20).max()
    f["price_new_high"] = (c >= hh20.shift(1)).astype(float)
    f["vol_confirm"] = (v >= hv20.shift(1)).astype(float)
    f["divergence"] = f["price_new_high"] * (1 - f["vol_confirm"])
    # 季节效应：月份 one-hot 压缩为余弦/正弦（避免维度爆炸）
    months = df.index.month if hasattr(df.index, "month") else pd.DatetimeIndex(df.index).month
    f["month_sin"] = np.sin(2 * np.pi * months / 12)
    f["month_cos"] = np.cos(2 * np.pi * months / 12)
    # EMA 距离（动量趋势度量，补充 SMA 距离）
    ema20 = c.ewm(span=20, adjust=False).mean()
    f["px_ema20"] = _safe_div(c, ema20) - 1.0
    # 20 日新高距离（趋势延续强度）
    f["dist_from_high20"] = _safe_div(c, h.rolling(20, min_periods=20).max())
    f["dist_from_low20"] = _safe_div(c, l.rolling(20, min_periods=20).min())
    return f.replace([np.inf, -np.inf], np.nan)


def triple_barrier_label(df: pd.DataFrame, horizon: int = 5,
                         up_mult: float = 1.0, down_mult: float = 1.0,
                         vol_window: int = 21) -> pd.Series:
    """三重障碍标签（Lopez de Prado）。

    - 用 21 日已实现波动率设障碍宽度；障碍 = entry ± mult * sigma * sqrt(horizon)
      （按 horizon 累积波动率缩放，避免短周期障碍过窄导致标签退化）；
    - 未来 horizon 天内先触上障碍=+1，先触下障碍=-1，到期未触按期末方向；
    - 所有判断只用 t 日之后的已实现数据；标签 dtype int8（-1/0/+1）。
    """
    c = df["close"].astype(float)
    h = df["high"].astype(float)
    l = df["low"].astype(float)
    lr = np.log(c).diff()
    vol = lr.rolling(vol_window, min_periods=vol_window).std(ddof=0).shift(1)  # 用 t-1 已实现波动率
    scale = math.sqrt(max(1, horizon))
    log_c = np.log(c)
    dates = df.index
    n = len(df)
    labels = pd.Series(0, index=df.index, dtype="int8")
    for i in range(n - horizon):
        sigma = vol.iloc[i]
        if not np.isfinite(sigma) or sigma <= 0:
            continue
        entry = log_c.iloc[i]
        up_bar = entry + up_mult * sigma * scale
        down_bar = entry - down_mult * sigma * scale
        future_idx = dates[i + 1: i + 1 + horizon]
        fh = h.reindex(future_idx)
        fl = l.reindex(future_idx)
        hit_up = (fh >= up_bar)
        hit_down = (fl <= down_bar)
        # 谁先触发：取最早一天
        up_days = hit_up[hit_up].index
        down_days = hit_down[hit_down].index
        up_first = up_days[0] if len(up_days) else None
        down_first = down_days[0] if len(down_days) else None
        if up_first is not None and (down_first is None or up_first <= down_first):
            labels.iloc[i] = 1
        elif down_first is not None and (up_first is None or down_first < up_first):
            labels.iloc[i] = -1
        else:
            # 到期未触：按期末方向
            end_log = log_c.iloc[i + horizon]
            labels.iloc[i] = 1 if end_log > entry else (-1 if end_log < entry else 0)
    return labels


def time_decay_weights(index: pd.DatetimeIndex, half_life_days: float = 1825.0) -> np.ndarray:
    """指数时间衰减：半衰期默认 5 年（1825 天），远期样本权重低。

    w(t) = 0.5^((T_max - t) / half_life)，归一化到均值 1。
    """
    if len(index) == 0:
        return np.array([])
    T = index.max()
    age_days = (T - pd.DatetimeIndex(index)).total_seconds() / 86400.0
    w = np.power(0.5, age_days / max(1.0, float(half_life_days)))
    w = w / max(1e-12, float(np.mean(w)))
    return w


def _extra_clf():
    return Pipeline([("imp", SimpleImputer(strategy="median")),
                     ("m", ExtraTreesClassifier(n_estimators=300, max_depth=8,
                                                min_samples_leaf=15, class_weight="balanced",
                                                n_jobs=-1, random_state=42))])


def _hgb_clf_calibrated(cv: int = 3):
    base = HistGradientBoostingClassifier(max_iter=150, max_depth=3, learning_rate=0.05,
                                          min_samples_leaf=40, l2_regularization=1.0,
                                          class_weight="balanced", random_state=42)
    # CalibratedClassifierCV 在 sklearn 1.9 支持 cv 整数；用 isotonic 校准
    return CalibratedClassifierCV(estimator=base, method="isotonic", cv=cv)


def _logit_calibrated(cv: int = 3):
    base = Pipeline([("sc", StandardScaler()),
                     ("m", LogisticRegression(C=0.5, max_iter=2000, class_weight="balanced", random_state=42))])
    return CalibratedClassifierCV(estimator=base, method="isotonic", cv=cv)


class SelectiveClassifier:
    """多模型集成 + 概率校准 + 选择性输出（二分类：涨/跌）。

    输出概率后，只在高置信（|p - 0.5| >= threshold）时给出方向，
    其余日输出"无信号"；目标是提升"有信号日"的方向准确率。
    与基线（期末方向标签 + ensemble）公平对比。
    """

    def __init__(self, half_life_days: float = 1825.0, threshold: float = 0.05):
        self.models = []
        self.half_life_days = half_life_days
        self.threshold = threshold
        self.classes_ = np.array([0, 1])

    def fit(self, X: pd.DataFrame, y: pd.Series, index: pd.DatetimeIndex):
        sw = time_decay_weights(index, self.half_life_days)
        keep = [c for c in X.columns if X[c].nunique(dropna=True) > 1]
        self.features_ = keep
        X = X[keep]
        self.models = []
        for mk in (_logit_calibrated, _hgb_clf_calibrated, _extra_clf):
            try:
                m = mk()
                try:
                    m.fit(X, y, sample_weight=sw)
                except (TypeError, ValueError):
                    m.fit(X, y)
                self.models.append(m)
            except Exception:  # noqa: BLE001
                continue
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        X = X[self.features_]
        if not self.models:
            return np.full((len(X), 2), 0.5)
        probs = []
        for m in self.models:
            try:
                p = m.predict_proba(X)
                cols = list(m.classes_)
                mapped = np.zeros((len(X), 2))
                for j, c in enumerate(cols):
                    if int(c) == 0:
                        mapped[:, 0] = p[:, j]
                    elif int(c) == 1:
                        mapped[:, 1] = p[:, j]
                probs.append(mapped)
            except Exception:  # noqa: BLE001
                continue
        if not probs:
            return np.full((len(X), 2), 0.5)
        return np.mean(probs, axis=0)

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """选择性预测：|p - 0.5| < threshold 时输出 -1（无信号）。"""
        p = self.predict_proba(X)[:, 1]
        out = np.full(len(X), -1, dtype=int)  # -1 = 无信号
        strong = (p - 0.5) >= self.threshold
        weak = (0.5 - p) >= self.threshold
        out[strong] = 1
        out[weak] = 0
        return out


def annual_walk_forward_enhanced(df: pd.DataFrame, context: dict | None = None,
                                 context_keys: Iterable[str] | None = None,
                                 start_year: int = 1950, end_year: int | None = None,
                                 horizon: int = 5, half_life_days: float = 1825.0,
                                 threshold: float = 0.05, max_train: int = 6000,
                                 min_train: int = 500, verbose: bool = False) -> dict:
    """年度扩展窗口 + 增强特征 + 校准集成 + 选择性输出（二分类：涨/跌）。

    每年只用上一年末已实现的目标训练；测试该年；评估"有信号日"与"全程"两种口径。
    标签为期末方向（与 accuracy-audit 基线一致，便于公平对比 52.3%/55.15%）。
    """
    X = build_features_advanced(df, context=context, context_keys=context_keys)
    y_ret, target_dates = adv.make_target(df, horizon)  # 对数收益
    valid = y_ret.notna() & (X.notna().sum(axis=1) >= 12)
    X, y_ret, target_dates = X[valid], y_ret[valid], target_dates[valid]
    labels = (y_ret > 0).astype(int)  # 1=涨，0=跌
    last_year = end_year or int(df.index[-1].year)
    rows = []
    step = horizon
    for year in range(start_year, last_year + 1):
        if verbose and (year - start_year) % 5 == 0:
            print(f"    [enhanced] year {year} ...", flush=True)
        train_end = pd.Timestamp(f"{year - 1}-12-31")
        train_mask = (target_dates <= train_end) & y_ret.notna()
        test_mask = (pd.Series(X.index.year, index=X.index) == year) & y_ret.notna()
        if train_mask.sum() < min_train or test_mask.sum() < 5:
            continue
        if train_mask.sum() > max_train:
            idx = X.index[train_mask][-max_train:]
            train_mask = pd.Series(X.index.isin(idx), index=X.index)
        try:
            clf = SelectiveClassifier(half_life_days=half_life_days, threshold=threshold)
            clf.fit(X[train_mask], labels[train_mask], X.index[train_mask])
            test_idx = X.index[test_mask]
            take = np.arange(0, len(test_idx), step)
            prob = clf.predict_proba(X.loc[test_idx])
            pred = clf.predict(X.loc[test_idx])
            for k in take:
                dt = test_idx[k]
                actual = int(labels.loc[dt])
                rows.append({
                    "year": year, "date": str(dt.date()),
                    "actual": actual, "actual_ret": float(y_ret.loc[dt]),
                    "pred": int(pred[k]), "p_up": float(prob[k, 1]),
                    "has_signal": int(pred[k] != -1),
                })
        except Exception as exc:  # noqa: BLE001
            rows.append({"year": year, "error": f"{type(exc).__name__}: {exc}"})
    return {"rows": rows, "horizon": horizon, "method": "enhanced_features_calibrated_ensemble_selective",
            "threshold": threshold, "start_year": start_year, "end_year": last_year}


def summarize_enhanced(rows: list[dict]) -> dict:
    clean = [r for r in rows if "error" not in r and "actual" in r]
    if not clean:
        return {"n": 0}
    actual = np.array([r["actual"] for r in clean])
    pred = np.array([r["pred"] for r in clean])
    has = np.array([r["has_signal"] for r in clean])
    # 全程口径（无信号日按 p>=0.5 判涨）
    pred_full = np.where(has == 1, pred, (np.array([r["p_up"] for r in clean]) >= 0.5).astype(int))
    overall_acc = float(np.mean(pred_full == actual))
    # 有信号口径（选择性预测核心指标）
    sig = has == 1
    sig_acc = float(np.mean(pred[sig] == actual[sig])) if sig.sum() else None
    sig_coverage = float(sig.mean())
    baseline_long = float(np.mean(actual == 1))
    by_decade = {}
    for decade in sorted({(r["year"] // 10) * 10 for r in clean}):
        sub = [r for r in clean if (r["year"] // 10) * 10 == decade]
        a = np.array([r["actual"] for r in sub])
        p = np.array([r["pred"] for r in sub])
        h = np.array([r["has_signal"] for r in sub])
        s = h == 1
        pf = np.where(s, p, (np.array([r["p_up"] for r in sub]) >= 0.5).astype(int))
        by_decade[str(decade)] = {
            "n": len(sub), "overall_acc": float(np.mean(pf == a)),
            "baseline_long": float(np.mean(a == 1)),
            "signal_acc": float(np.mean(p[s] == a[s])) if s.sum() else None,
            "signal_coverage": float(s.mean()),
        }
    return {
        "n": len(clean), "overall_acc": overall_acc, "baseline_long": baseline_long,
        "signal_acc": sig_acc, "signal_coverage": sig_coverage,
        "n_signal": int(sig.sum()),
        "by_decade": by_decade,
        "method": "enhanced features + isotonic-calibrated ensemble (logit+HistGBM+ExtraTrees) + time decay + selective output",
    }


def confidence_coverage_curve(rows: list[dict],
                              thresholds: Iterable[float] = (0.0, 0.02, 0.05, 0.08, 0.12, 0.15, 0.2, 0.25, 0.3)) -> list[dict]:
    """覆盖率-准确率权衡曲线：阈值越高，有信号日越少但准确率越高。"""
    clean = [r for r in rows if "error" not in r and "p_up" in r]
    if not clean:
        return []
    p = np.array([r["p_up"] for r in clean])
    actual = np.array([r["actual"] for r in clean])
    out = []
    for t in thresholds:
        sig = np.abs(p - 0.5) >= t
        if sig.sum() == 0:
            out.append({"threshold": float(t), "coverage": 0.0, "n": 0, "accuracy": None})
            continue
        pred = (p[sig] >= 0.5).astype(int)
        acc = float(np.mean(pred == actual[sig]))
        out.append({"threshold": float(t), "coverage": float(sig.mean()),
                    "n": int(sig.sum()), "accuracy": acc})
    return out


def run_enhanced_forecast(df: pd.DataFrame, symbol: str, horizon: int = 5,
                          lookback_years: int = 25) -> dict:
    """当前时点的增强预测：训练用最近 lookback_years 年已实现样本，预测下一周期。

    返回方向（1=涨/0=跌/-1=无信号）、概率、置信度、选择性信号、方法论说明。
    """
    X = build_features_advanced(df)
    y_ret, _ = adv.make_target(df, horizon)
    valid = y_ret.notna() & (X.notna().sum(axis=1) >= 12)
    X, y_ret = X[valid], y_ret[valid]
    labels = (y_ret > 0).astype(int)
    if len(X) < 500:
        return {"error": "样本不足，无法训练增强模型（需 ≥500 个已实现周期）"}
    cutoff = X.index[-1] - pd.Timedelta(days=int(lookback_years * 365))
    train_mask = X.index <= cutoff - pd.Timedelta(days=horizon)
    if train_mask.sum() < 500:
        train_mask = pd.Series([True] * len(X), index=X.index)
    clf = SelectiveClassifier()
    clf.fit(X[train_mask], labels[train_mask], X.index[train_mask])
    last_idx = X.index[-1]
    prob = clf.predict_proba(X.loc[[last_idx]])[0]
    pred = clf.predict(X.loc[[last_idx]])[0]
    return {
        "symbol": symbol, "horizon": horizon, "last_date": str(last_idx.date()),
        "last_close": float(df["close"].iloc[-1]),
        "direction": int(pred), "p_up": float(prob[1]), "p_down": float(1 - prob[1]),
        "has_signal": int(pred != -1), "confidence": float(abs(prob[1] - 0.5)),
        "method": "enhanced features + isotonic-calibrated ensemble (logit+HistGBM+ExtraTrees)",
        "features_count": len(clf.features_),
        "notes": [
            "方向含义：1=涨，0=跌，-1=无强信号（概率接近 0.5 时不下注）。",
            "概率经 isotonic 校准，反映经验频率；高置信日只占少数——这是选择性预测的本质。",
            "方向准确率 98.7% 在样本外不可达；本模块目标是把'有信号日'准确率提到 60%+，全程接近或略超始终看多。",
        ],
    }
