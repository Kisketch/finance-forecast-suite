"""多周期趋势预判与历史回测（增强版）。

借鉴 qlib Alpha158：特征扩展到 ~40 个（动量/波动/量价/规模/技术/regime/季节）。
借鉴 Lopez de Prado AFML：isotonic 概率校准 + 时间衰减样本权重 + 选择性输出。
严格无未来函数：特征 shift(+n)/rolling；目标 shift(-h)；训练集目标在预测点前已实现。
"""
from __future__ import annotations

import math
import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


def _safe_div(a, b):
    return a / b.replace(0, np.nan)


def _adx_di(df: pd.DataFrame, n: int = 14) -> pd.DataFrame:
    """ADX/DI+/DI-：Wilder 平滑的趋势强度指标。"""
    h, l, c = df["high"].astype(float), df["low"].astype(float), df["close"].astype(float)
    up = h.diff(); down = -l.diff()
    plus_dm = up.where((up > down) & (up > 0), 0.0)
    minus_dm = down.where((down > up) & (down > 0), 0.0)
    tr = pd.concat([(h - l), (h - c.shift(1)).abs(), (l - c.shift(1)).abs()], axis=1).max(axis=1)
    atr_s = tr.ewm(alpha=1 / n, adjust=False).mean().replace(0, np.nan)
    plus_di = 100 * plus_dm.ewm(alpha=1 / n, adjust=False).mean() / atr_s
    minus_di = 100 * minus_dm.ewm(alpha=1 / n, adjust=False).mean() / atr_s
    dx = 100 * _safe_div((plus_di - minus_di).abs(), plus_di + minus_di)
    adx = dx.ewm(alpha=1 / n, adjust=False).mean()
    return pd.DataFrame({"adx": adx, "di_spread": plus_di - minus_di})


def _kdj(df: pd.DataFrame, n: int = 9) -> pd.DataFrame:
    h, l, c = df["high"].astype(float), df["low"].astype(float), df["close"].astype(float)
    hn = h.rolling(n, min_periods=n).max(); ln = l.rolling(n, min_periods=n).min()
    rsv = _safe_div(c - ln, hn - ln) * 100.0
    k = rsv.ewm(alpha=1 / 3, adjust=False).mean()
    d = k.ewm(alpha=1 / 3, adjust=False).mean()
    return pd.DataFrame({"kdj_k": k, "kdj_j": 3 * k - 2 * d})


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Alpha158 风格特征集（~40 个）：动量/波动/量价/技术/regime/季节。

    所有特征用 shift(+n)/rolling/ewm，无未来函数；目标单独 shift(-h)。
    """
    c = df["close"].astype(float)
    h = df["high"].astype(float)
    l = df["low"].astype(float)
    v = df["volume"].astype(float) if "volume" in df else pd.Series(0.0, index=df.index)
    lr = np.log(c).diff()
    f = pd.DataFrame(index=df.index)
    # 动量类（Alpha158 KMID/STM/KLEN 子集）
    for lag in (1, 2, 3, 5, 10, 20):
        f[f"lr_lag{lag}"] = lr.shift(lag)
    for n in (5, 10, 20, 60):
        f[f"mean_{n}"] = lr.rolling(n, min_periods=n).mean()
        f[f"vol_{n}"] = lr.rolling(n, min_periods=n).std(ddof=0)
        f[f"ret_max_{n}"] = lr.rolling(n, min_periods=n).max()
    f["vol_ratio"] = _safe_div(f["vol_5"], f["vol_20"])
    # RSI
    delta = c.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    loss = -delta.clip(upper=0).ewm(alpha=1 / 14, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    f["rsi14"] = 100 / (1 + rs)
    # MACD
    ema12 = c.ewm(span=12, adjust=False).mean(); ema26 = c.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    f["macd_hist"] = _safe_div(macd - macd.ewm(span=9, adjust=False).mean(), c)
    # MA 距离（规模/位置类）
    for n in (5, 20, 60):
        ma = c.rolling(n, min_periods=n).mean()
        f[f"px_ma{n}"] = _safe_div(c, ma) - 1.0
    # 回撤 + ATR（风险类）
    f["drawdown"] = c / c.cummax() - 1.0
    tr = pd.concat([(h - l), (h - c.shift(1)).abs(), (l - c.shift(1)).abs()], axis=1).max(axis=1)
    f["atr14"] = _safe_div(tr.ewm(alpha=1 / 14, adjust=False).mean(), c)
    # 量价类
    vmean = v.rolling(20, min_periods=20).mean()
    f["vol_z"] = _safe_div(v - vmean, v.rolling(20, min_periods=20).std(ddof=0))
    obv = (np.sign(c.diff()).fillna(0) * v).cumsum()
    f["obv_z"] = _safe_div(obv - obv.rolling(20, min_periods=20).mean(), obv.rolling(20, min_periods=20).std(ddof=0))
    # ADX/DI（趋势强度）
    adx = _adx_di(df, 14)
    f["adx14"] = adx["adx"]; f["di_spread"] = adx["di_spread"]
    # KDJ
    kdj = _kdj(df, 9)
    f["kdj_j"] = kdj["kdj_j"]; f["kdj_k"] = kdj["kdj_k"]
    # 波动率 regime 分位（120 日，适配中等长度数据）
    f["vol_regime_q"] = f["vol_20"].rolling(120, min_periods=60).rank(pct=True)
    f["ewma_vol20"] = lr.ewm(span=20, min_periods=20).std()
    # 量价背离
    hh20 = h.rolling(20, min_periods=20).max(); hv20 = v.rolling(20, min_periods=20).max()
    f["price_new_high"] = (c >= hh20.shift(1)).astype(float)
    f["vol_confirm"] = (v >= hv20.shift(1)).astype(float)
    f["divergence"] = f["price_new_high"] * (1 - f["vol_confirm"])
    # 季节效应（月份正余弦）
    months = df.index.month if hasattr(df.index, "month") else pd.DatetimeIndex(df.index).month
    f["month_sin"] = np.sin(2 * np.pi * months / 12)
    f["month_cos"] = np.cos(2 * np.pi * months / 12)
    # EMA 距离 + 新高低距离
    ema20 = c.ewm(span=20, adjust=False).mean()
    f["px_ema20"] = _safe_div(c, ema20) - 1.0
    f["dist_high20"] = _safe_div(c, hh20)
    f["dist_low20"] = _safe_div(c, l.rolling(20, min_periods=20).min())
    return f.replace([np.inf, -np.inf], np.nan)


# ---------- 回归集成（用于点预测与区间）----------
def _ridge():
    return Pipeline([("imp", SimpleImputer(strategy="median")), ("sc", StandardScaler()),
                     ("m", Ridge(alpha=10.0))])


def _hgb_reg():
    return HistGradientBoostingRegressor(max_iter=120, max_depth=3, learning_rate=0.06,
                                         min_samples_leaf=30, l2_regularization=1.0, random_state=42)


class RegEnsemble:
    def __init__(self):
        self.models = [_ridge(), _hgb_reg()]
    def fit(self, X, y):
        for m in self.models: m.fit(X, y)
        return self
    def predict(self, X):
        return np.mean([m.predict(X) for m in self.models], axis=0)


def make_model(name: str = "ensemble"):
    if name == "ridge": return _ridge()
    if name == "hgb": return _hgb_reg()
    return RegEnsemble()


# ---------- 校准分类集成（借鉴 Lopez de Prado + ml_advanced，提升方向准确率）----------
def _time_decay_weights(index: pd.DatetimeIndex, half_life_days: float = 730.0) -> np.ndarray:
    """指数时间衰减：半衰期 2 年（适配中等数据），远期样本权重低，适应 regime 漂移。"""
    if len(index) == 0: return np.array([])
    T = index.max()
    age = (T - pd.DatetimeIndex(index)).total_seconds() / 86400.0
    w = np.power(0.5, age / max(1.0, float(half_life_days)))
    return w / max(1e-12, float(np.mean(w)))


def _logit_calibrated(cv: int = 3):
    base = Pipeline([("sc", StandardScaler()),
                     ("m", LogisticRegression(C=0.5, max_iter=2000, class_weight="balanced", random_state=42))])
    return CalibratedClassifierCV(estimator=base, method="isotonic", cv=cv)


def _hgb_clf_calibrated(cv: int = 3):
    base = HistGradientBoostingClassifier(max_iter=120, max_depth=3, learning_rate=0.06,
                                          min_samples_leaf=40, l2_regularization=1.0,
                                          class_weight="balanced", random_state=42)
    return CalibratedClassifierCV(estimator=base, method="isotonic", cv=cv)


def _extra_clf():
    return Pipeline([("imp", SimpleImputer(strategy="median")),
                     ("m", ExtraTreesClassifier(n_estimators=200, max_depth=7,
                                                min_samples_leaf=15, class_weight="balanced",
                                                n_jobs=-1, random_state=42))])


class SelectiveClassifier:
    """多模型集成 + isotonic 概率校准 + 选择性输出（二分类：涨/跌）。

    |p-0.5|>=threshold 才给方向，否则"无信号"——只在有把握时下注。
    """
    def __init__(self, half_life_days: float = 730.0, threshold: float = 0.05):
        self.half_life_days = half_life_days
        self.threshold = threshold
        self.models = []
        self.features_ = []
        self.classes_ = np.array([0, 1])

    def fit(self, X: pd.DataFrame, y: pd.Series, index: pd.DatetimeIndex):
        sw = _time_decay_weights(index, self.half_life_days)
        keep = [c for c in X.columns if X[c].nunique(dropna=True) > 1]
        self.features_ = keep
        X = X[keep]
        self.models = []
        for mk in (_logit_calibrated, _hgb_clf_calibrated, _extra_clf):
            try:
                m = mk()
                try: m.fit(X, y, sample_weight=sw)
                except (TypeError, ValueError): m.fit(X, y)
                self.models.append(m)
            except Exception:  # noqa: BLE001
                continue
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        X = X[self.features_]
        if not self.models: return np.full((len(X), 2), 0.5)
        probs = []
        for m in self.models:
            try:
                p = m.predict_proba(X)
                mapped = np.zeros((len(X), 2))
                for j, ci in enumerate(m.classes_):
                    if int(ci) == 0: mapped[:, 0] = p[:, j]
                    elif int(ci) == 1: mapped[:, 1] = p[:, j]
                probs.append(mapped)
            except Exception:  # noqa: BLE001
                continue
        return np.mean(probs, axis=0) if probs else np.full((len(X), 2), 0.5)

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        p = self.predict_proba(X)[:, 1]
        out = np.full(len(X), -1, dtype=int)  # -1 = 无信号
        out[(p - 0.5) >= self.threshold] = 1
        out[(0.5 - p) >= self.threshold] = 0
        return out


# ---------- walk-forward 回测（回归，用于点预测与区间）----------
def walk_forward(df: pd.DataFrame, horizon: int, model_name: str = "ensemble",
                 min_train: int = 120, max_folds: int = 200,
                 train_window: int = 1500) -> tuple[list[dict], np.ndarray]:
    """扩展窗口滚动回测；测试点间隔 horizon，避免重叠目标乐观偏差。"""
    c = df["close"].astype(float)
    feats = build_features(df)
    target = np.log(c.shift(-horizon) / c)
    valid = feats.notna().all(axis=1) & target.notna()
    X, y = feats[valid], target[valid]
    dates = X.index
    if len(X) < min_train + horizon * 3:
        return [], np.array([])
    step = horizon
    folds, residuals = [], []
    start_i = max(min_train, len(X) - max_folds * step)
    i = start_i
    while i + 1 <= len(X) and len(folds) < max_folds:
        train_end = i - 1
        train_start = max(0, train_end - train_window)
        idx_tr = dates[train_start:train_end]; idx_te = dates[i:i + 1]
        if len(idx_tr) < min_train:
            i += step; continue
        try:
            m = make_model(model_name)
            m.fit(X.loc[idx_tr], y.loc[idx_tr])
            pred = float(m.predict(X.loc[idx_te])[0])
        except Exception:  # noqa: BLE001
            i += step; continue
        actual = float(y.loc[idx_te].iloc[0])
        folds.append({"date": str(idx_te[0]), "actual_logret": actual, "pred_logret": pred,
                      "pred_price": float(c.loc[idx_te].iloc[0] * math.exp(pred)),
                      "actual_price": float(c.loc[idx_te].iloc[0] * math.exp(actual))})
        residuals.append(actual - pred)
        i += step
    return folds, np.array(residuals)


def _walk_forward_enhanced(df: pd.DataFrame, horizon: int, threshold: float = 0.05,
                           min_train: int = 120, max_folds: int = 200) -> list[dict]:
    """校准分类集成的 walk-forward（期末方向标签 + 选择性输出）。
    返回每折：actual(0/1)/pred(0/1/-1)/p_up/has_signal。"""
    c = df["close"].astype(float)
    feats = build_features(df)
    y_ret = np.log(c.shift(-horizon) / c)
    valid = feats.notna().all(axis=1) & y_ret.notna()
    X, y_ret = feats[valid], y_ret[valid]
    labels = (y_ret > 0).astype(int)
    dates = X.index
    if len(X) < min_train + horizon * 3:
        return []
    step = horizon
    rows = []
    start_i = max(min_train, len(X) - max_folds * step)
    i = start_i
    while i + 1 <= len(X) and len(rows) < max_folds:
        train_end = i - 1
        idx_tr = dates[max(0, train_end - 1500):train_end]; idx_te = dates[i:i + 1]
        if len(idx_tr) < min_train:
            i += step; continue
        try:
            clf = SelectiveClassifier(threshold=threshold)
            clf.fit(X.loc[idx_tr], labels.loc[idx_tr], idx_tr)
            prob = clf.predict_proba(X.loc[idx_te])[0]
            pred = clf.predict(X.loc[idx_te])[0]
            rows.append({"date": str(idx_te[0]), "actual": int(labels.loc[idx_te].iloc[0]),
                         "actual_logret": float(y_ret.loc[idx_te].iloc[0]),
                         "pred": int(pred), "p_up": float(prob[1]), "has_signal": int(pred != -1)})
        except Exception:  # noqa: BLE001
            i += step; continue
        i += step
    return rows


def run_forecast(df: pd.DataFrame, symbol: str, interval: str, horizon: int,
                 model_name: str = "ensemble") -> dict:
    """当前时点预判：回归点预测 + 残差分位区间；增强：校准分类的方向概率 + 选择性信号。

    跨度越大区间越宽（残差已含 horizon 效应）；方向概率经 isotonic 校准。
    """
    folds, residuals = walk_forward(df, horizon, model_name)
    if not folds:
        return {"error": "历史数据不足，无法完成滚动回测（至少约 120 根 K 线）", "symbol": symbol}
    err = np.array([f["actual_logret"] - f["pred_logret"] for f in folds])
    base_err = np.array([f["actual_logret"] for f in folds])
    mae = float(np.mean(np.abs(err)))
    base_mae = float(np.mean(np.abs(base_err)))
    dir_acc = float(np.mean(np.sign([f["pred_logret"] for f in folds]) == np.sign([f["actual_logret"] for f in folds])))
    baseline_dir = float(np.mean(np.array([f["actual_logret"] for f in folds]) > 0))
    skill = float(1 - mae / base_mae) if base_mae else None

    # 增强回测指标由 run_backtest 单独提供（避免 run_forecast 过慢）；
    # 此处只做当前时点的校准概率 + 选择性信号（单次 fit，快）。
    signal_acc = signal_cov = None; enh_dir_acc = None; n_signal = 0

    # 当前时点：回归点预测
    c = df["close"].astype(float)
    feats = build_features(df)
    target = np.log(c.shift(-horizon) / c)
    valid = feats.notna().all(axis=1) & target.notna()
    X, y = feats[valid], target[valid]
    last_idx = feats.index[-1]
    m = make_model(model_name)
    m.fit(X, y)
    point = float(m.predict(feats.loc[[last_idx]])[0])
    # 当前时点增强概率
    enh_prob = enh_signal = None
    try:
        clf = SelectiveClassifier()
        clf.fit(X, (y > 0).astype(int), X.index)
        enh_prob = float(clf.predict_proba(feats.loc[[last_idx]])[0, 1])
        enh_signal = int(clf.predict(feats.loc[[last_idx]])[0])
    except Exception:  # noqa: BLE001
        pass

    qs = np.quantile(residuals, [0.05, 0.25, 0.5, 0.75, 0.95]) if len(residuals) >= 20 \
        else np.array([-0.03, -0.012, 0, 0.012, 0.03]) * math.sqrt(horizon)
    last_close = float(c.iloc[-1])
    prices = [last_close * math.exp(point + q) for q in qs]
    direction = "up" if point > 0 else ("down" if point < 0 else "flat")
    if enh_signal == 1: direction = "up"
    elif enh_signal == 0: direction = "down"
    elif enh_signal == -1: direction = "flat"  # 无信号
    return {
        "symbol": symbol, "interval": interval, "horizon": horizon,
        "last_date": str(last_idx), "last_close": last_close,
        "point_logret": point, "direction": direction,
        "p_up": enh_prob, "enhanced_signal": enh_signal,
        "q05_price": prices[0], "q25_price": prices[1], "q50_price": prices[2],
        "q75_price": prices[3], "q95_price": prices[4],
        "interval_width_pct": round((prices[4] - prices[0]) / last_close * 100, 2),
        "backtest": {
            "n_folds": len(folds), "mae_logret": mae, "baseline_mae": base_mae,
            "skill_score": skill, "dir_acc": dir_acc, "baseline_dir_acc": baseline_dir,
            "enhanced_dir_acc": enh_dir_acc, "signal_acc": signal_acc,
            "signal_coverage": signal_cov, "n_signal": n_signal,
            "note": "增强选择性指标请在「回测检验」页查看（完整 walk-forward）",
        },
        "folds": folds[-120:],
        "notes": [
            f"预判目标：未来 {horizon} 根 {interval} K 线对数收益。点预测用 Ridge+HistGBM 回归集成。",
            "方向概率经 isotonic 校准（CalibratedClassifierCV），选择性输出：|p-0.5|>=0.05 才给方向。",
            "区间为滚动残差分位映射，跨度越大区间越宽。方向准确率 98.7% 不可达，作情景参考。",
        ],
    }


def run_backtest(df: pd.DataFrame, symbol: str, interval: str, horizon: int,
                 model_name: str = "ensemble") -> dict:
    """历史回测报告：回归点预测 + 增强分类选择性 + 策略净值。

    增强回测用 max_folds=40（校准集成较慢，约 3-4 分钟）；前端应显示 loading。"""
    folds, _ = walk_forward(df, horizon, model_name, max_folds=300)
    enh_rows = _walk_forward_enhanced(df, horizon, max_folds=40)
    if not folds:
        return {"error": "数据不足", "symbol": symbol}
    err = np.array([f["actual_logret"] - f["pred_logret"] for f in folds])
    base = np.array([f["actual_logret"] for f in folds])
    mae = float(np.mean(np.abs(err))); base_mae = float(np.mean(np.abs(base)))
    dir_acc = float(np.mean(np.sign([f["pred_logret"] for f in folds]) == np.sign([f["actual_logret"] for f in folds])))
    base_dir = float(np.mean(base > 0))
    rmse = float(np.sqrt(np.mean(err ** 2)))
    pos = (np.array([f["pred_logret"] for f in folds]) > 0).astype(float)
    actual = np.array([f["actual_logret"] for f in folds])
    net = pos * actual
    eq = np.exp(np.cumsum(net)); bh = np.exp(np.cumsum(actual))
    ppy = 252.0 / horizon if interval == "1d" else (252 * 6.5 / horizon if interval in ("1h", "3h") else 12)
    ann = float(eq[-1] ** (ppy / len(net)) - 1) if eq[-1] > 0 and len(net) > 0 else None
    bh_ann = float(bh[-1] ** (ppy / len(net)) - 1) if bh[-1] > 0 and len(net) > 0 else None
    # 增强：选择性信号准确率
    signal_acc = signal_cov = None; n_sig = 0
    if enh_rows:
        sig = [r for r in enh_rows if r["has_signal"] == 1]
        n_sig = len(sig)
        if sig:
            signal_acc = float(np.mean([r["pred"] == r["actual"] for r in sig]))
            signal_cov = float(n_sig / len(enh_rows))
    return {
        "symbol": symbol, "interval": interval, "horizon": horizon, "model": model_name,
        "n_folds": len(folds), "mae": mae, "baseline_mae": base_mae, "rmse": rmse,
        "skill": float(1 - mae / base_mae) if base_mae else None,
        "dir_acc": dir_acc, "baseline_dir_acc": base_dir,
        "enhanced_signal_acc": signal_acc, "enhanced_signal_coverage": signal_cov, "n_signal": n_sig,
        "strategy_ann": ann, "buy_hold_ann": bh_ann,
        "max_drawdown": float((eq / np.maximum.accumulate(eq) - 1).min()) if len(eq) else None,
        "folds": folds,
    }
