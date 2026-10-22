"""可复现的预测实验：特征、滚动回测、基准对比与情景区间。

原则：
- 只使用 t 时刻已知信息；训练集目标必须在 t 之前已实现，杜绝未来函数。
- 必须与随机游走基准对比；skill_score <= 0 时明确标注“未跑赢基准”。
- 输出区间来自滚动回测残差的分位数，属于条件情景，不是保证。
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestRegressor

from ..analytics import indicators as ind


@dataclass
class ForecastResult:
    symbol: str
    horizon: int
    model: str
    last_date: str
    last_close: float
    point_logret: float
    point_price: float
    q05_price: float
    q25_price: float
    q50_price: float
    q75_price: float
    q95_price: float
    n_folds: int
    mae_logret: float
    rmse_logret: float
    mape_price: float
    dir_acc: float
    baseline_mae: float
    baseline_dir_acc: float
    skill_score: float
    dm_pvalue: float | None
    folds: list[dict]
    notes: list[str]


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    c = df["close"].astype(float)
    v = df["volume"].astype(float) if "volume" in df else pd.Series(index=df.index, dtype=float)
    lr = np.log(c).diff()
    f = pd.DataFrame(index=df.index)
    for lag in (1, 2, 3, 5, 10, 21):
        f[f"lr_lag{lag}"] = lr.shift(lag)
    for n in (5, 21, 63):
        f[f"mean_{n}"] = lr.rolling(n, min_periods=n).mean()
        f[f"vol_{n}"] = lr.rolling(n, min_periods=n).std(ddof=0)
    f["rsi14"] = ind.rsi(c, 14)
    m = ind.macd(c)
    f["macd_hist"] = m["hist"] / c
    for n in (20, 50, 200):
        f[f"px_ma{n}"] = c / ind.sma(c, n) - 1.0
    f["drawdown"] = ind.drawdown_series(c)
    f["vol_z"] = (v - v.rolling(21, min_periods=21).mean()) / v.rolling(21, min_periods=21).std(ddof=0)
    return f.replace([np.inf, -np.inf], np.nan)


def make_model(name: str):
    if name == "ridge":
        return Pipeline([("scaler", StandardScaler()), ("ridge", Ridge(alpha=10.0))])
    if name == "gbm":
        from sklearn.ensemble import HistGradientBoostingRegressor
        return HistGradientBoostingRegressor(
            max_iter=200, max_depth=3, learning_rate=0.05,
            min_samples_leaf=30, l2_regularization=1.0, random_state=42,
        )
    if name == "rf":
        return Pipeline([
            ("imp", SimpleImputer(strategy="median")),
            ("rf", RandomForestRegressor(n_estimators=200, max_depth=6, min_samples_leaf=20,
                                         n_jobs=-1, random_state=42)),
        ])
    if name == "ensemble":
        from .advanced import make_model as make_advanced_model
        return make_advanced_model("ensemble", "reg")
    raise ValueError(f"unknown model: {name}")


def _fit_predict(X: pd.DataFrame, y: pd.Series, model_name: str, idx_train: pd.Index, idx_test: pd.Index) -> np.ndarray:
    model = make_model(model_name)
    model.fit(X.loc[idx_train], y.loc[idx_train])
    return model.predict(X.loc[idx_test])


def walk_forward(df: pd.DataFrame, horizon: int, model_name: str,
                 min_train: int = 750, step: int | None = None,
                 max_folds: int = 500, train_window: int = 2000) -> tuple[list[dict], np.ndarray]:
    """扩展窗口滚动回测；step 默认等于 horizon，避免重叠目标造成乐观偏差。

    只保留最近 max_folds 折，且每次训练最多使用最近 train_window 个样本，
    避免用 1927 年以来的全部历史做数千次拟合（既慢又不符合 regime 相关性）。
    """
    c = df["close"].astype(float)
    feats = build_features(df)
    target = np.log(c.shift(-horizon) / c)
    valid = feats.notna().all(axis=1) & target.notna()
    X = feats[valid]
    y = target[valid]
    dates = X.index
    if len(X) < min_train + horizon * 5:
        return [], np.array([])

    step = step or horizon
    folds: list[dict] = []
    residuals: list[float] = []
    start_i = max(min_train, len(X) - max_folds * step)
    i = start_i
    while i + horizon <= len(X) and len(folds) < max_folds:
        train_end = i - horizon + 1
        train_start = max(0, train_end - train_window)
        idx_train = dates[train_start:train_end]
        idx_test = dates[i:i + 1]
        if len(idx_train) < min_train:
            i += step
            continue
        try:
            pred = float(_fit_predict(X, y, model_name, idx_train, idx_test)[0])
        except Exception:  # noqa: BLE001
            i += step
            continue
        actual = float(y.loc[idx_test].iloc[0])
        base = 0.0
        folds.append({
            "date": str(idx_test[0].date()),
            "actual_logret": actual,
            "pred_logret": pred,
            "pred_price": float(c.loc[idx_test].iloc[0] * math.exp(pred)),
            "actual_price": float(c.loc[idx_test].iloc[0] * math.exp(actual)),
            "baseline_logret": base,
        })
        residuals.append(actual - pred)
        i += step
    return folds, np.array(residuals)


def _dm_test(err_model: np.ndarray, err_base: np.ndarray) -> float | None:
    """Diebold-Mariano 检验（平方损失，无自协方差修正）。"""
    d = err_model ** 2 - err_base ** 2
    n = len(d)
    if n < 10:
        return None
    mean = d.mean()
    var = d.var(ddof=1)
    if var <= 0:
        return None
    stat = mean / math.sqrt(var / n)
    # 正态近似双侧 p 值
    return float(math.erfc(abs(stat) / math.sqrt(2)))


def run_forecast(df: pd.DataFrame, symbol: str, horizon: int = 5, model_name: str = "ridge") -> ForecastResult:
    notes = [
        "价格为前复权口径；预测目标为 h 日对数收益。",
        "滚动回测使用扩展窗口，测试点间隔 h 日，训练集目标均已实现，无未来函数。",
        "区间为滚动残差分位数映射，属条件情景，不构成收益承诺。",
    ]
    folds, residuals = walk_forward(df, horizon, model_name,
                                    max_folds=200 if model_name == "gbm" else 120 if model_name in ("rf", "ensemble") else 500)
    if not folds:
        raise ValueError("历史长度不足，无法完成滚动回测（至少约 4 年日线）。")

    err_model = np.array([f["actual_logret"] - f["pred_logret"] for f in folds])
    err_base = np.array([f["actual_logret"] - f["baseline_logret"] for f in folds])
    mae = float(np.mean(np.abs(err_model)))
    rmse = float(np.sqrt(np.mean(err_model ** 2)))
    base_mae = float(np.mean(np.abs(err_base)))
    actual_price = np.array([f["actual_price"] for f in folds])
    pred_price = np.array([f["pred_price"] for f in folds])
    mape = float(np.mean(np.abs((actual_price - pred_price) / actual_price)) * 100)
    dir_acc = float(np.mean(np.sign([f["pred_logret"] for f in folds]) == np.sign([f["actual_logret"] for f in folds])))
    base_dir = float(np.mean(np.array([f["actual_logret"] for f in folds]) > 0))  # 始终看多基准
    skill = float(1 - mae / base_mae) if base_mae else float("nan")
    dm_p = _dm_test(err_model, err_base)
    if skill <= 0:
        notes.append("样本外 MAE 未跑赢随机游走基准：该模型/周期不建议用于方向性决策。")
    if dir_acc <= 0.52:
        notes.append("方向准确率接近抛硬币（<=52%），方向信号弱。")

    # 当前时点预测：训练集只保留目标已实现的样本
    feats = build_features(df)
    c = df["close"].astype(float)
    target = np.log(c.shift(-horizon) / c)
    valid = feats.notna().all(axis=1) & target.notna()
    X, y = feats[valid], target[valid]
    last_idx = feats.index[-1]
    model = make_model(model_name)
    model.fit(X, y)
    point = float(model.predict(feats.loc[[last_idx]])[0])

    qs = np.quantile(residuals, [0.05, 0.25, 0.5, 0.75, 0.95]) if len(residuals) >= 20 else np.array([-0.05, -0.02, 0, 0.02, 0.05]) * math.sqrt(horizon)
    last_close = float(c.iloc[-1])
    prices = [last_close * math.exp(point + q) for q in qs]
    return ForecastResult(
        symbol=symbol, horizon=horizon, model=model_name,
        last_date=str(df.index[-1].date()), last_close=last_close,
        point_logret=point, point_price=prices[2],
        q05_price=prices[0], q25_price=prices[1], q50_price=prices[2],
        q75_price=prices[3], q95_price=prices[4],
        n_folds=len(folds), mae_logret=mae, rmse_logret=rmse, mape_price=mape,
        dir_acc=dir_acc, baseline_mae=base_mae, baseline_dir_acc=base_dir,
        skill_score=skill, dm_pvalue=dm_p,
        folds=folds[-180:], notes=notes,
    )


def save_result(result: ForecastResult, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(result), ensure_ascii=False, indent=2), encoding="utf-8")
