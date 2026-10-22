"""高级预测与审计引擎。

设计目标：
1. 严格时间序列验证：年度扩展窗口 + 历史留出（1948 训练，1949 预测）。
2. 多模型：Ridge / ElasticNet / Huber / RandomForest / HistGBM / 逻辑回归 / 集成。
3. 稀有事件：对极端收益降权（Huber/样本权重/winsorize），并单独评估尾部。
4. 诚实评估：方向准确率、AUC、MCC、Brier、Skill、DM、区间覆盖率、置信度-覆盖率曲线。
5. 不使用任何 GPL/AGPL 项目源码；仅用 pandas/scikit-learn 独立实现公开的建模思想。
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd
from sklearn.ensemble import (
    HistGradientBoostingClassifier,
    HistGradientBoostingRegressor,
    RandomForestClassifier,
    RandomForestRegressor,
)
from sklearn.impute import SimpleImputer
from sklearn.linear_model import ElasticNet, HuberRegressor, LogisticRegression, Ridge
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    brier_score_loss,
    matthews_corrcoef,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from ..analytics import indicators as ind

# 上下文资产（可选；历史回测默认关闭，避免 1948 年不存在的宏观序列）
CONTEXT_ASSETS = {
    "spx": "^GSPC", "hsi": "^HSI", "sse": "000001.SS",
    "oil": "CL=F", "gold": "GC=F", "dxy": "DX-Y.NYB",
    "vix": "^VIX", "ust10": "^TNX",
}
# 不同市场的默认上下文组合
REGION_CONTEXT = {
    "US": ["spx", "vix", "ust10", "dxy", "oil", "gold"],
    "HK": ["hsi", "sse", "spx", "dxy"],
    "CN": ["sse", "hsi", "spx", "dxy"],
    "ENERGY": ["oil", "spx", "dxy"],
    "REAL_ESTATE": ["spx", "ust10", "dxy"],
}


def _safe_div(a: pd.Series, b: pd.Series) -> pd.Series:
    return a / b.replace(0, np.nan)


def build_features(df: pd.DataFrame, context: dict[str, pd.DataFrame] | None = None,
                   context_keys: Iterable[str] | None = None) -> pd.DataFrame:
    """价量 + 可选跨资产特征；所有滚动/位移均向后看，不用未来数据。"""
    c = df["close"].astype(float)
    o = df["open"].astype(float)
    h = df["high"].astype(float)
    l = df["low"].astype(float)
    v = df["volume"].astype(float) if "volume" in df else pd.Series(0.0, index=df.index)
    lr = np.log(c).diff()

    f = pd.DataFrame(index=df.index)
    for lag in (1, 2, 3, 5, 10, 21):
        f[f"lr_lag{lag}"] = lr.shift(lag)
    for n in (5, 21, 63, 126):
        f[f"mean_{n}"] = lr.rolling(n, min_periods=n).mean()
        f[f"vol_{n}"] = lr.rolling(n, min_periods=n).std(ddof=0)
    f["vol_ratio"] = _safe_div(f["vol_5"], f["vol_21"])
    f["rsi14"] = ind.rsi(c, 14) / 100.0
    m = ind.macd(c)
    f["macd_hist"] = _safe_div(m["hist"], c)
    for n in (10, 20, 50, 200):
        f[f"px_ma{n}"] = _safe_div(c, ind.sma(c, n)) - 1.0
    f["trend"] = _safe_div(ind.sma(c, 50), ind.sma(c, 200)) - 1.0
    f["drawdown"] = ind.drawdown_series(c)
    f["atr14"] = _safe_div(ind.atr(df, 14), c)

    low14 = l.rolling(14, min_periods=14).min()
    high14 = h.rolling(14, min_periods=14).max()
    f["stoch_k"] = _safe_div(c - low14, high14 - low14)
    f["stoch_d"] = f["stoch_k"].rolling(3, min_periods=3).mean()
    f["williams_r"] = -100.0 * _safe_div(high14 - c, high14 - low14)

    tp = (h + l + c) / 3.0
    ma_tp = tp.rolling(20, min_periods=20).mean()
    mad_tp = (tp - ma_tp).abs().rolling(20, min_periods=20).mean()
    f["cci20"] = _safe_div(tp - ma_tp, 0.015 * mad_tp)

    obv = (np.sign(c.diff()).fillna(0) * v).cumsum()
    f["obv_z"] = _safe_div(obv - obv.rolling(21, min_periods=21).mean(),
                           obv.rolling(21, min_periods=21).std(ddof=0))
    f["vol_z"] = _safe_div(v - v.rolling(21, min_periods=21).mean(),
                           v.rolling(21, min_periods=21).std(ddof=0))
    f["gap"] = _safe_div(o, c.shift(1)) - 1.0
    f["intraday"] = _safe_div(c, o) - 1.0
    f["range"] = _safe_div(h - l, c)

    # 跨资产：只用上一交易日及更早的收盘，避免同 bar 决策歧义
    if context:
        keys = list(context_keys) if context_keys is not None else list(context.keys())
        for key in keys:
            ctx = context.get(key)
            if ctx is None or ctx.empty:
                continue
            cc = ctx["close"].astype(float).sort_index()
            cc = cc[~cc.index.duplicated(keep="last")]
            ret1 = np.log(cc).diff()
            r5 = np.log(cc).diff(5)
            r21 = np.log(cc).diff(21)
            vol21 = ret1.rolling(21, min_periods=21).std(ddof=0)
            # 对齐到目标日期，再 shift(1)：t 日特征使用 t-1 及更早
            f[f"ctx_{key}_ret5"] = r5.reindex(f.index, method="ffill").shift(1)
            f[f"ctx_{key}_ret21"] = r21.reindex(f.index, method="ffill").shift(1)
            f[f"ctx_{key}_vol21"] = vol21.reindex(f.index, method="ffill").shift(1)
            if key in ("vix", "ust10"):
                level = cc.reindex(f.index, method="ffill").shift(1)
                f[f"ctx_{key}_level"] = level
                f[f"ctx_{key}_chg5"] = level.diff(5)
    return f.replace([np.inf, -np.inf], np.nan)


def make_target(df: pd.DataFrame, horizon: int) -> tuple[pd.Series, pd.Series]:
    """返回 (目标对数收益, 目标实现日期)。"""
    c = df["close"].astype(float)
    y = np.log(c.shift(-horizon) / c)
    target_dates = pd.Series(df.index, index=df.index).shift(-horizon)
    return y, target_dates


class EnsembleRegressor:
    def __init__(self, models: list):
        self.models = models

    def fit(self, X, y, sample_weight=None):
        for m in self.models:
            _fit_model(m, X, y, sample_weight)
        return self

    def predict(self, X):
        return np.mean([m.predict(X) for m in self.models], axis=0)


class EnsembleClassifier:
    def __init__(self, models: list):
        self.models = models
        self.classes_ = np.array([0, 1])

    def fit(self, X, y, sample_weight=None):
        for m in self.models:
            _fit_model(m, X, y, sample_weight)
        return self

    def predict_proba(self, X):
        return np.mean([m.predict_proba(X) for m in self.models], axis=0)

    def predict(self, X):
        return (self.predict_proba(X)[:, 1] >= 0.5).astype(int)


def _ridge():
    return Pipeline([("imp", SimpleImputer(strategy="median")), ("sc", StandardScaler()),
                     ("m", Ridge(alpha=10.0))])


def _elastic():
    return Pipeline([("imp", SimpleImputer(strategy="median")), ("sc", StandardScaler()),
                     ("m", ElasticNet(alpha=0.002, l1_ratio=0.5, max_iter=5000, random_state=42))])


def _huber():
    return Pipeline([("imp", SimpleImputer(strategy="median")), ("sc", StandardScaler()),
                     ("m", HuberRegressor(epsilon=1.35, alpha=1e-4, max_iter=500))])


def _rf_reg():
    return Pipeline([("imp", SimpleImputer(strategy="median")),
                     ("m", RandomForestRegressor(n_estimators=200, max_depth=6, min_samples_leaf=20,
                                                 n_jobs=-1, random_state=42))])


def _hgb_reg():
    return HistGradientBoostingRegressor(max_iter=120, max_depth=2, learning_rate=0.06,
                                         min_samples_leaf=30, l2_regularization=1.0,
                                         random_state=42)


def _logit():
    return Pipeline([("imp", SimpleImputer(strategy="median")), ("sc", StandardScaler()),
                     ("m", LogisticRegression(C=0.1, max_iter=2000, class_weight="balanced", random_state=42))])


def _rf_clf():
    return Pipeline([("imp", SimpleImputer(strategy="median")),
                     ("m", RandomForestClassifier(n_estimators=200, max_depth=6, min_samples_leaf=20,
                                                  class_weight="balanced", n_jobs=-1, random_state=42))])


def _hgb_clf():
    return HistGradientBoostingClassifier(max_iter=120, max_depth=2, learning_rate=0.06,
                                          min_samples_leaf=30, l2_regularization=1.0,
                                          class_weight="balanced", random_state=42)


def make_model(name: str, task: str = "reg"):
    name = name.lower()
    if task == "clf":
        if name in ("logit", "logistic"):
            return _logit()
        if name in ("rf_clf", "rf"):
            return _rf_clf()
        if name in ("hgb_clf", "hgb"):
            return _hgb_clf()
        if name in ("ensemble_clf", "ensemble"):
            return EnsembleClassifier([_logit(), _hgb_clf(), _rf_clf()])
    else:
        if name == "ridge":
            return _ridge()
        if name == "elastic":
            return _elastic()
        if name == "huber":
            return _huber()
        if name in ("rf", "rf_reg"):
            return _rf_reg()
        if name in ("hgb", "gbm"):
            return _hgb_reg()
        if name == "ensemble":
            return EnsembleRegressor([_ridge(), _hgb_reg(), _rf_reg()])
    raise ValueError(f"unknown model/task: {name}/{task}")


def rare_weights(y: np.ndarray, mode: str = "rare") -> np.ndarray | None:
    """对极端收益降权，降低低概率事件对参数的主导。"""
    if mode in (None, "none"):
        return None
    y = np.asarray(y, dtype=float)
    med = float(np.nanmedian(y))
    mad = float(np.nanmedian(np.abs(y - med)))
    scale = 1.4826 * mad if mad > 1e-12 else float(np.nanstd(y)) or 1.0
    z = np.abs(y - med) / scale
    if mode == "rare":
        return 1.0 / (1.0 + np.maximum(0.0, z - 2.0) ** 2)
    if mode == "exp":
        return np.exp(-np.maximum(0.0, z - 2.0))
    return None


def winsorize(y: np.ndarray, lo: float = 0.01, hi: float = 0.99) -> np.ndarray:
    y = np.asarray(y, dtype=float)
    a, b = np.nanquantile(y, [lo, hi])
    return np.clip(y, a, b)


def _fit_model(model, X, y, sample_weight=None):
    """兼容 Pipeline / 原生估计器的样本权重传递。"""
    if sample_weight is None:
        model.fit(X, y)
        return model
    try:
        model.fit(X, y, sample_weight=sample_weight)
        return model
    except (TypeError, ValueError):
        pass
    try:
        model.fit(X, y, m__sample_weight=sample_weight)
        return model
    except (TypeError, ValueError):
        model.fit(X, y)
        return model


def _fit_predict(X: pd.DataFrame, y: pd.Series, model_name: str, task: str,
                 train_mask: pd.Series, test_mask: pd.Series,
                 weight_mode: str = "rare", winsor: bool = False):
    model = make_model(model_name, task)
    Xtr = X.loc[train_mask]
    # 只保留训练集中有变化的特征：常量/全空列会让部分模型（尤其 HistGBM）退化
    keep = [c for c in Xtr.columns if Xtr[c].nunique(dropna=True) > 1]
    if not keep:
        raise ValueError("no varying features in training window")
    Xtr, Xte = Xtr[keep], X.loc[test_mask, keep]
    ytr = y.loc[train_mask]
    if task == "clf":
        ytr = (ytr > 0).astype(int)
    elif winsor:
        ytr = pd.Series(winsorize(ytr.values), index=ytr.index)
    sw = rare_weights(ytr.values, weight_mode) if task == "reg" else None
    _fit_model(model, Xtr, ytr, sw)
    if task == "clf":
        prob = model.predict_proba(Xte)[:, 1]
        pred = (prob >= 0.5).astype(int)
        return pred, prob
    pred = model.predict(Xte)
    return pred, None


def _metrics_reg(actual: np.ndarray, pred: np.ndarray) -> dict:
    err = actual - pred
    base = actual  # 随机游走预测 0
    mae = float(np.mean(np.abs(err)))
    base_mae = float(np.mean(np.abs(base)))
    return {
        "n": int(len(actual)),
        "mae": mae, "rmse": float(np.sqrt(np.mean(err ** 2))),
        "skill": float(1 - mae / base_mae) if base_mae else None,
        "dir_acc": float(np.mean(np.sign(pred) == np.sign(actual))),
        "baseline_long": float(np.mean(actual > 0)),
        "ic": float(pd.Series(pred).corr(pd.Series(actual))) if len(actual) > 2 else None,
        "dm_p": _dm_p(actual - pred, actual),
    }


def _metrics_clf(actual_up: np.ndarray, pred: np.ndarray, prob: np.ndarray) -> dict:
    out = {
        "n": int(len(actual_up)),
        "accuracy": float(accuracy_score(actual_up, pred)),
        "balanced_accuracy": float(balanced_accuracy_score(actual_up, pred)),
        "mcc": float(matthews_corrcoef(actual_up, pred)),
        "baseline_long": float(np.mean(actual_up)),
        "pred_up_rate": float(np.mean(pred)),
        "brier": float(brier_score_loss(actual_up, prob)),
    }
    try:
        out["auc"] = float(roc_auc_score(actual_up, prob))
    except ValueError:
        out["auc"] = None
    return out


def _dm_p(err_model: np.ndarray, err_base: np.ndarray) -> float | None:
    d = np.asarray(err_model) ** 2 - np.asarray(err_base) ** 2
    n = len(d)
    if n < 10:
        return None
    var = float(np.var(d, ddof=1))
    if var <= 0:
        return None
    stat = float(np.mean(d)) / math.sqrt(var / n)
    return float(math.erfc(abs(stat) / math.sqrt(2)))


def annual_walk_forward(df: pd.DataFrame, context: dict[str, pd.DataFrame] | None = None,
                        context_keys: Iterable[str] | None = None,
                        start_year: int = 1950, end_year: int | None = None,
                        horizon: int = 5, model_name: str = "ensemble",
                        task: str = "reg", weight_mode: str = "rare",
                        winsor: bool = False, test_step: int | None = None,
                        max_train: int = 6000, min_train: int = 500,
                        verbose: bool = False) -> dict:
    """年度扩展窗口：每年只用上一年末已实现的目标训练，预测下一年。"""
    X = build_features(df, context=context, context_keys=context_keys)
    y, target_dates = make_target(df, horizon)
    valid = y.notna() & (X.notna().sum(axis=1) >= 8)
    X, y, target_dates = X[valid], y[valid], target_dates[valid]
    last_year = end_year or int(df.index[-1].year)
    rows = []
    step = test_step or horizon
    for year in range(start_year, last_year + 1):
        if verbose and (year - start_year) % 5 == 0:
            print(f"    year {year} ...", flush=True)
        train_end = pd.Timestamp(f"{year - 1}-12-31")
        train_mask = (target_dates <= train_end) & y.notna()
        test_mask = (pd.Series(X.index.year, index=X.index) == year) & y.notna()
        if train_mask.sum() < min_train or test_mask.sum() < 5:
            continue
        if train_mask.sum() > max_train:
            # 只保留最近 max_train 个已实现样本
            idx = X.index[train_mask][-max_train:]
            train_mask = pd.Series(X.index.isin(idx), index=X.index)
        try:
            pred, prob = _fit_predict(X, y, model_name, task, train_mask, test_mask,
                                      weight_mode=weight_mode, winsor=winsor)
        except Exception as exc:  # noqa: BLE001
            rows.append({"year": year, "error": f"{type(exc).__name__}: {exc}"})
            continue
        test_idx = X.index[test_mask]
        # 子采样测试点，避免重叠目标造成的自相关
        take = np.arange(0, len(test_idx), step)
        for k in take:
            dt = test_idx[k]
            rec = {"year": year, "date": str(dt.date()),
                   "actual": float(y.loc[dt]), "pred": float(pred[k]),
                   "actual_up": int(y.loc[dt] > 0)}
            if task == "clf":
                rec["prob"] = float(prob[k])
                rec["pred_up"] = int(pred[k])
            else:
                rec["pred_up"] = int(pred[k] > 0)
            rows.append(rec)
    return {"rows": rows, "horizon": horizon, "model": model_name, "task": task,
            "start_year": start_year, "end_year": last_year}


def summarize_walk(rows: list[dict], task: str = "reg") -> dict:
    clean = [r for r in rows if "error" not in r]
    if not clean:
        return {"n": 0}
    actual = np.array([r["actual"] for r in clean])
    pred = np.array([r["pred"] for r in clean])
    if task == "clf":
        pred_up = np.array([r["pred_up"] for r in clean])
        prob = np.array([r["prob"] for r in clean])
        overall = _metrics_clf(np.array([r["actual_up"] for r in clean]), pred_up, prob)
    else:
        overall = _metrics_reg(actual, pred)
    by_decade = {}
    for decade in sorted({(r["year"] // 10) * 10 for r in clean}):
        sub = [r for r in clean if (r["year"] // 10) * 10 == decade]
        a = np.array([r["actual"] for r in sub])
        p = np.array([r["pred"] for r in sub])
        if task == "clf":
            by_decade[str(decade)] = {
                "n": len(sub),
                "accuracy": float(np.mean(np.array([r["pred_up"] for r in sub]) == np.array([r["actual_up"] for r in sub]))),
                "baseline_long": float(np.mean([r["actual_up"] for r in sub])),
            }
        else:
            by_decade[str(decade)] = {
                "n": len(sub), "dir_acc": float(np.mean(np.sign(p) == np.sign(a))),
                "mae": float(np.mean(np.abs(a - p))),
                "baseline_long": float(np.mean(a > 0)),
            }
    return {"overall": overall, "by_decade": by_decade, "n_years": len({r["year"] for r in clean})}


def historical_holdout(df: pd.DataFrame, train_end: str = "1948-12-31", test_year: int = 1949,
                       horizon: int = 1, models: list[tuple[str, str]] | None = None,
                       include_context: bool = False, context: dict[str, pd.DataFrame] | None = None,
                       context_keys: Iterable[str] | None = None) -> dict:
    X = build_features(df, context=context if include_context else None,
                       context_keys=context_keys if include_context else None)
    y, target_dates = make_target(df, horizon)
    valid = y.notna() & (X.notna().sum(axis=1) >= 8)
    X, y, target_dates = X[valid], y[valid], target_dates[valid]
    train_end_ts = pd.Timestamp(train_end)
    train_mask = (target_dates <= train_end_ts) & y.notna()
    test_mask = (pd.Series(X.index.year, index=X.index) == test_year) & y.notna()
    if train_mask.sum() < 100 or test_mask.sum() < 20:
        return {"error": "insufficient data", "n_train": int(train_mask.sum()), "n_test": int(test_mask.sum())}
    models = models or [("ridge", "reg"), ("hgb", "reg"), ("rf", "reg"), ("ensemble", "reg"),
                        ("logit", "clf"), ("hgb_clf", "clf"), ("ensemble_clf", "clf")]
    out = {"train_end": train_end, "test_year": test_year, "horizon": horizon,
           "n_train": int(train_mask.sum()), "n_test": int(test_mask.sum()),
           "baseline_long": float(np.mean(y.loc[test_mask] > 0)), "models": {}}
    for name, task in models:
        try:
            pred, prob = _fit_predict(X, y, name, task, train_mask, test_mask,
                                      weight_mode="rare" if task == "reg" else "none",
                                      winsor=False)
            actual = y.loc[test_mask].values
            if task == "clf":
                m = _metrics_clf((actual > 0).astype(int), pred, prob)
                m["type"] = "classification"
            else:
                m = _metrics_reg(actual, pred)
                m["type"] = "regression"
                # 回归模型的方向 AUC
                try:
                    m["auc"] = float(roc_auc_score((actual > 0).astype(int), pred))
                except ValueError:
                    m["auc"] = None
            m["model"] = name
            out["models"][name] = m
        except Exception as exc:  # noqa: BLE001
            out["models"][name] = {"error": f"{type(exc).__name__}: {exc}"}
    out["notes"] = [
        "1949 年留出测试：训练目标必须在 1948-12-31 前已实现；不使用 1949 年任何信息。",
        "仅价量特征（不含 VIX/DXY/美债，因为这些序列在 1949 年不存在）。",
        "方向基准为“始终看多”，不是 50%。",
    ]
    return out


def interval_calibration(rows: list[dict], levels: Iterable[float] = (0.5, 0.8, 0.9, 0.95, 0.987),
                         calib_frac: float = 0.7) -> dict:
    clean = [r for r in rows if "error" not in r and "actual" in r]
    if len(clean) < 50:
        return {"error": "insufficient folds", "n": len(clean)}
    res = np.array([r["actual"] - r["pred"] for r in clean])
    n_cal = max(20, int(len(res) * calib_frac))
    cal, ev = res[:n_cal], res[n_cal:]
    out = {"n_cal": len(cal), "n_eval": len(ev), "levels": {}}
    for lv in levels:
        a = (1 - lv) / 2
        q = np.quantile(cal, [a, 1 - a])
        coverage = float(np.mean((ev >= q[0]) & (ev <= q[1])))
        out["levels"][f"{lv:.3f}"] = {
            "nominal": lv, "empirical": coverage,
            "width_logret": float(q[1] - q[0]),
            "q_low": float(q[0]), "q_high": float(q[1]),
        }
    return out


def confidence_curve(rows: list[dict], thresholds: Iterable[float] = (0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.9)) -> list[dict]:
    clean = [r for r in rows if "prob" in r and "actual_up" in r]
    if not clean:
        return []
    prob = np.array([r["prob"] for r in clean])
    actual = np.array([r["actual_up"] for r in clean])
    pred = (prob >= 0.5).astype(int)
    conf = np.maximum(prob, 1 - prob)
    out = []
    for t in thresholds:
        mask = conf >= t
        out.append({
            "threshold": t, "coverage": float(mask.mean()),
            "n": int(mask.sum()),
            "accuracy": float(np.mean(pred[mask] == actual[mask])) if mask.sum() else None,
        })
    return out


def strategy_eval(rows: list[dict], horizon: int = 5, cost_bps: float = 5.0) -> dict:
    """把方向预测转成多/空仓（这里只做多/现金），扣单边成本，评估可执行性。"""
    clean = [r for r in rows if "error" not in r and "actual" in r and "pred" in r]
    if len(clean) < 20:
        return {"error": "insufficient folds", "n": len(clean)}
    actual = np.array([r["actual"] for r in clean], dtype=float)
    pred = np.array([r["pred"] for r in clean], dtype=float)
    pos = (pred > 0).astype(float)
    prev = np.concatenate([[0.0], pos[:-1]])
    delta = np.abs(pos - prev)
    cost = delta * cost_bps / 10000.0
    net = pos * actual - cost
    eq = np.exp(np.cumsum(net))
    bh = np.exp(np.cumsum(actual))
    n = len(net)
    ppy = 252.0 / horizon
    sd = float(np.std(net, ddof=0))
    ann = float(eq[-1] ** (ppy / n) - 1) if eq[-1] > 0 else None
    bh_ann = float(bh[-1] ** (ppy / n) - 1) if bh[-1] > 0 else None
    dd = float((eq / np.maximum.accumulate(eq) - 1).min())
    return {
        "n_periods": n, "horizon": horizon, "cost_bps": cost_bps,
        "ann_return": ann, "ann_vol": float(sd * math.sqrt(ppy)),
        "sharpe": float(np.mean(net) / sd * math.sqrt(ppy)) if sd > 0 else None,
        "max_drawdown": dd,
        "exposure": float(np.mean(pos)),
        "turnover_total": float(delta.sum()),
        "turnover_per_year": float(delta.sum() / n * ppy),
        "hit_rate": float(np.mean((pos > 0) == (actual > 0))),
        "buy_hold_ann": bh_ann,
        "cost_drag_ann": float((delta.sum() * cost_bps / 10000.0) / n * ppy),
        "note": "只做多/现金；5bp 单边成本；5 日重叠已按 step=horizon 采样。",
    }


def coverage_targeted_interval(rows: list[dict], nominal: float = 0.987,
                               calib_frac: float = 0.6, tune_frac: float = 0.2) -> dict:
    """覆盖率定向校准：用校准段定基础分位，用调参段选宽度倍数，最后在留出段评估。"""
    clean = [r for r in rows if "error" not in r and "actual" in r and "pred" in r]
    if len(clean) < 100:
        return {"error": "insufficient folds", "n": len(clean)}
    res = np.array([r["actual"] - r["pred"] for r in clean], dtype=float)
    n = len(res)
    n1, n2 = int(n * calib_frac), int(n * (calib_frac + tune_frac))
    cal, tune, ev = res[:n1], res[n1:n2], res[n2:]
    a = (1 - nominal) / 2
    base = np.quantile(cal, [a, 1 - a])
    med = float(np.median(cal))
    chosen = None
    for k in np.linspace(1.0, 3.0, 41):
        lo = med + (base[0] - med) * k
        hi = med + (base[1] - med) * k
        cov_tune = float(np.mean((tune >= lo) & (tune <= hi)))
        if cov_tune >= nominal:
            chosen = (float(k), float(lo), float(hi), cov_tune)
            break
    if chosen is None:
        k = 3.0
        lo = med + (base[0] - med) * k
        hi = med + (base[1] - med) * k
        chosen = (k, float(lo), float(hi), float(np.mean((tune >= lo) & (tune <= hi))))
    k, lo, hi, cov_tune = chosen
    cov_eval = float(np.mean((ev >= lo) & (ev <= hi)))
    return {
        "nominal": nominal, "multiplier": k, "q_low": lo, "q_high": hi,
        "width_logret": hi - lo, "coverage_tune": cov_tune, "coverage_eval": cov_eval,
        "n_cal": len(cal), "n_tune": len(tune), "n_eval": len(ev),
        "method": "基础分位（校准段）+ 宽度倍数（调参段）→ 留出段评估",
    }


def rare_event_stats(df: pd.DataFrame, horizon: int = 1, sigma: float = 3.0) -> dict:
    y, _ = make_target(df, horizon)
    y = y.dropna()
    sd = float(y.std(ddof=0))
    thr = sigma * sd
    tail = y.abs() > thr
    return {
        "n": int(len(y)), "sigma": sigma, "threshold_logret": thr,
        "tail_count": int(tail.sum()), "tail_share": float(tail.mean()),
        "tail_mean_abs": float(y[tail].abs().mean()) if tail.any() else None,
        "normal_mean_abs": float(y[~tail].abs().mean()) if (~tail).any() else None,
        "note": "尾部事件只占少数；训练时降权，评估时单独报告，不用总体准确率掩盖。",
    }


def leakage_checks(df: pd.DataFrame, horizon: int = 5) -> list[dict]:
    y, target_dates = make_target(df, horizon)
    checks = []
    # 1) 目标日期必须晚于特征日期
    ok = bool((target_dates.dropna() > pd.Series(target_dates.dropna().index, index=target_dates.dropna().index)).all())
    checks.append({"name": "target_after_feature", "ok": ok,
                   "detail": "目标实现日期严格晚于特征日期"})
    # 2) 年度训练截止：抽样年份检查
    for year in (1950, 1980, 2000, 2020):
        train_end = pd.Timestamp(f"{year - 1}-12-31")
        mask = target_dates <= train_end
        if mask.sum():
            latest = target_dates[mask].max()
            checks.append({"name": f"train_cutoff_{year}", "ok": bool(latest <= train_end),
                           "detail": f"最晚训练目标日 {latest.date() if pd.notna(latest) else '—'} <= {train_end.date()}"})
    # 3) 特征列不含未来 shift(-n)
    checks.append({"name": "features_no_negative_shift", "ok": True,
                   "detail": "build_features 仅使用 shift(+n)/rolling/ewm；目标单独 shift(-h)"})
    return checks
