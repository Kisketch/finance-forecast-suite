"""增强模型回测审计：对比基线与 AI 增强模型的方向准确率。

基线（来自 accuracy-audit.md）：
- 1949 留出：58.8%（HistGBM 分类）
- 1950-2026 年度：55.15% vs 始终看多 56.74%
- 2000-2026 现代：52.3%（集成）vs 56.7% 始终看多

增强目标：增强特征(ADX/KDJ/波动率regime/季节/量价背离) + isotonic 校准集成 +
时间衰减样本权重 + 选择性输出。诚实立场：98.7% 方向不可达，目标是追平/略超始终看多，
并在有信号日（threshold=0.05, ~50% 覆盖）超过始终看多。
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np
import pandas as pd
from finance_app.data.store import DataStore
from finance_app.models import ml_advanced as ml


def run_period(symbol: str, start_year: int, end_year: int, horizon: int = 5,
               verbose: bool = True) -> dict:
    ds = DataStore()
    df = ds.get(symbol)
    if df is None:
        return {"error": f"unknown symbol {symbol}"}
    if verbose:
        print(f"running enhanced walk-forward {start_year}-{end_year} on {symbol} (horizon={horizon})...", flush=True)
    t0 = time.time()
    res = ml.annual_walk_forward_enhanced(
        df, start_year=start_year, end_year=end_year, horizon=horizon,
        half_life_days=1825, threshold=0.05, verbose=verbose)
    if verbose:
        print(f"  done in {time.time()-t0:.1f}s, {len(res['rows'])} folds", flush=True)
    summary = ml.summarize_enhanced(res["rows"])
    curve = ml.confidence_coverage_curve(res["rows"])
    return {
        "symbol": symbol, "horizon": horizon, "start_year": start_year, "end_year": end_year,
        "summary": summary, "confidence_curve": curve,
        "elapsed_seconds": round(time.time() - t0, 1),
    }


def run_1949_holdout(symbol: str = "^GSPC", horizon: int = 1) -> dict:
    """1948 训练 → 1949 测试（与基线 58.8% 对比；horizon=1）。"""
    ds = DataStore()
    df = ds.get(symbol)
    if df is None:
        return {"error": f"unknown symbol {symbol}"}
    from finance_app.models import advanced as adv
    X = ml.build_features_advanced(df)
    y_ret, target_dates = adv.make_target(df, horizon)
    valid = y_ret.notna() & (X.notna().sum(axis=1) >= 12)
    X, y_ret, target_dates = X[valid], y_ret[valid], target_dates[valid]
    labels = (y_ret > 0).astype(int)
    train_end = pd.Timestamp("1948-12-31")
    train_mask = (target_dates <= train_end) & y_ret.notna()
    test_mask = (pd.Series(X.index.year, index=X.index) == 1949) & y_ret.notna()
    if train_mask.sum() < 100 or test_mask.sum() < 20:
        return {"error": "insufficient data", "n_train": int(train_mask.sum()), "n_test": int(test_mask.sum())}
    t0 = time.time()
    clf = ml.SelectiveClassifier(threshold=0.05)
    clf.fit(X[train_mask], labels[train_mask], X.index[train_mask])
    prob = clf.predict_proba(X[test_mask])
    pred = clf.predict(X[test_mask])
    actual = labels[test_mask].values
    pred_full = np.where(pred != -1, pred, (prob[:, 1] >= 0.5).astype(int))
    overall = float(np.mean(pred_full == actual))
    sig = pred != -1
    sig_acc = float(np.mean(pred[sig] == actual[sig])) if sig.sum() else None
    baseline_long = float(np.mean(actual == 1))
    return {
        "symbol": symbol, "horizon": horizon, "train_end": "1948-12-31", "test_year": 1949,
        "n_train": int(train_mask.sum()), "n_test": int(test_mask.sum()),
        "overall_acc": overall, "signal_acc": sig_acc, "signal_coverage": float(sig.mean()),
        "n_signal": int(sig.sum()), "baseline_long": baseline_long,
        "baseline_reference": {"1949_best_hgb_clf": 0.588, "always_long_1949": 0.496},
        "elapsed_seconds": round(time.time() - t0, 1),
    }


def main() -> int:
    out_path = ROOT / "analysis" / "enhanced_audit.json"
    results = {}
    print("=" * 60, flush=True)
    print("1/2  1949 历史留出（horizon=1）", flush=True)
    h1949 = run_1949_holdout("^GSPC", horizon=1)
    results["holdout_1949"] = h1949
    if "overall_acc" in h1949:
        print(f"  全程方向准确率: {h1949['overall_acc']*100:.2f}% (基线 HGB-clf 58.8%, 始终看多 49.6%)")
        print(f"  有信号日准确率: {h1949['signal_acc']*100:.2f}% (覆盖率 {h1949['signal_coverage']*100:.1f}%, n={h1949['n_signal']})" if h1949.get("signal_acc") else "  无有信号日")
        print(f"  始终看多基准: {h1949['baseline_long']*100:.2f}%", flush=True)
    print("=" * 60, flush=True)
    print("2/2  现代期 2000-2026（horizon=5）", flush=True)
    modern = run_period("^GSPC", 2000, 2026, horizon=5, verbose=True)
    results["modern_2000_2026"] = modern
    if "summary" in modern:
        s = modern["summary"]
        print(f"  全程方向准确率: {s['overall_acc']*100:.2f}% (基线集成 52.3%, 始终看多 56.7%)")
        print(f"  始终看多基准:   {s['baseline_long']*100:.2f}%")
        if s.get("signal_acc") is not None:
            print(f"  有信号日准确率: {s['signal_acc']*100:.2f}% (覆盖率 {s['signal_coverage']*100:.1f}%, n={s['n_signal']})")
        print("\n  覆盖率-准确率权衡曲线:", flush=True)
        for c in modern.get("confidence_curve", []):
            acc = f"{c['accuracy']*100:.1f}%" if c.get("accuracy") is not None else "—"
            print(f"    threshold={c['threshold']:.2f}  coverage={c['coverage']*100:5.1f}%  n={c['n']:5d}  acc={acc}")
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\nwritten {out_path}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
