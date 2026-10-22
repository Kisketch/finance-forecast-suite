"""生成高级模型审计报告 analysis/advanced_audit.json。

内容：
- 1948 训练 / 1949 预测的历史留出
- 1950-2026 年度扩展窗口（回归 + 分类）
- 区间校准（含 98.7% 覆盖率）
- 置信度-覆盖率曲线
- 稀有事件统计
- 现代模型对比（2000-2026）
- 区域/领域模型（价格-only vs 跨资产上下文）
- 泄漏检查
"""
from __future__ import annotations

import json
import sys
import time
import warnings
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from finance_app.data.store import DataStore  # noqa: E402
from finance_app.models import advanced as adv  # noqa: E402

OUT = ROOT / "analysis"
OUT.mkdir(exist_ok=True)
ds = DataStore()
t0 = time.time()


def log(msg: str) -> None:
    print(f"[{time.time() - t0:6.1f}s] {msg}", flush=True)


def ctx_for(symbol: str, region: str) -> tuple[dict, list[str]]:
    keys = [k for k in adv.REGION_CONTEXT.get(region, []) if adv.CONTEXT_ASSETS[k] != symbol]
    ctx = {k: ds.get(adv.CONTEXT_ASSETS[k]) for k in keys if ds.get(adv.CONTEXT_ASSETS[k]) is not None}
    return ctx, list(ctx.keys())


# ---------- 1) 1949 历史留出 ----------
spx = ds.get("^GSPC")
log("historical holdout 1948->1949")
hist = adv.historical_holdout(spx, train_end="1948-12-31", test_year=1949, horizon=1)

# ---------- 2) 1950-2026 年度回归 ----------
log("annual regression 1950-2026 (h=5, ensemble)")
w_reg = adv.annual_walk_forward(spx, start_year=1950, end_year=2026, horizon=5,
                                model_name="ensemble", task="reg", test_step=5, max_train=6000,
                                verbose=True)
reg_summary = adv.summarize_walk(w_reg["rows"], "reg")
log(f"  regression n={reg_summary.get('overall', {}).get('n')} dir={reg_summary.get('overall', {}).get('dir_acc')}")

# ---------- 3) 1950-2026 年度分类 ----------
log("annual classification 1950-2026 (h=5, hgb_clf)")
w_clf = adv.annual_walk_forward(spx, start_year=1950, end_year=2026, horizon=5,
                                model_name="hgb_clf", task="clf", test_step=5, max_train=6000,
                                verbose=True)
clf_summary = adv.summarize_walk(w_clf["rows"], "clf")
log(f"  classification n={clf_summary.get('overall', {}).get('n')} acc={clf_summary.get('overall', {}).get('accuracy')}")

# ---------- 4) 区间校准 / 置信度 ----------
interval = adv.interval_calibration(w_reg["rows"], levels=(0.5, 0.8, 0.9, 0.95, 0.987), calib_frac=0.7)
interval_targeted = adv.coverage_targeted_interval(w_reg["rows"], nominal=0.987)
conf = adv.confidence_curve(w_clf["rows"], thresholds=(0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.9))

# ---------- 5) 稀有事件 ----------
rare1 = adv.rare_event_stats(spx, horizon=1, sigma=3.0)
rare5 = adv.rare_event_stats(spx, horizon=5, sigma=3.0)

# 尾部 vs 常规的误差
rows_clean = [r for r in w_reg["rows"] if "error" not in r and "actual" in r]
actual = np.array([r["actual"] for r in rows_clean])
pred = np.array([r["pred"] for r in rows_clean])
thr = 2.0 * float(np.std(actual, ddof=0))
tail_mask = np.abs(actual) > thr
tail_eval = {
    "threshold_logret": float(thr),
    "tail_n": int(tail_mask.sum()),
    "tail_share": float(tail_mask.mean()),
    "normal_mae": float(np.mean(np.abs(actual[~tail_mask] - pred[~tail_mask]))) if (~tail_mask).any() else None,
    "tail_mae": float(np.mean(np.abs(actual[tail_mask] - pred[tail_mask]))) if tail_mask.any() else None,
    "normal_dir_acc": float(np.mean(np.sign(pred[~tail_mask]) == np.sign(actual[~tail_mask]))) if (~tail_mask).any() else None,
    "tail_dir_acc": float(np.mean(np.sign(pred[tail_mask]) == np.sign(actual[tail_mask]))) if tail_mask.any() else None,
}

# ---------- 6) 现代模型对比 2000-2026 ----------
strategy = adv.strategy_eval(w_reg["rows"], horizon=5, cost_bps=5.0)

log("modern model comparison 2000-2026")
modern = {}
for name in ["ridge", "hgb", "rf", "ensemble"]:
    w = adv.annual_walk_forward(spx, start_year=2000, end_year=2026, horizon=5,
                                model_name=name, task="reg", test_step=5, max_train=4000)
    modern[name] = adv.summarize_walk(w["rows"], "reg")
    log(f"  {name}: dir={modern[name].get('overall', {}).get('dir_acc')} skill={modern[name].get('overall', {}).get('skill')}")

# ---------- 7) 区域/领域：价格 vs 上下文 ----------
log("regional / domain models 2000-2026")
regional = {}
for sym, region in [("^GSPC", "US"), ("^HSI", "HK"), ("000001.SS", "CN"),
                    ("XLE", "ENERGY"), ("XLRE", "REAL_ESTATE")]:
    df = ds.get(sym)
    if df is None:
        continue
    ctx, keys = ctx_for(sym, region)
    regional[sym] = {"name_cn": ds.info(sym)["name_cn"], "region": region, "modes": {}}
    for mode, use_ctx in [("price", False), ("context", True)]:
        w = adv.annual_walk_forward(
            df, start_year=2000, end_year=2026, horizon=5, model_name="ridge", task="reg",
            test_step=5, max_train=4000,
            context=ctx if use_ctx else None, context_keys=keys if use_ctx else None,
        )
        regional[sym]["modes"][mode] = adv.summarize_walk(w["rows"], "reg")
        log(f"  {sym} {mode}: dir={regional[sym]['modes'][mode].get('overall', {}).get('dir_acc')}")

# ---------- 8) 汇总 ----------
checks = adv.leakage_checks(spx, horizon=5)
best_hist = max((v.get("dir_acc", v.get("accuracy", 0)) or 0, k) for k, v in hist.get("models", {}).items() if "error" not in v)
best_modern = max((modern[k].get("overall", {}).get("dir_acc", 0) or 0, k) for k in modern)
interval_987 = interval.get("levels", {}).get("0.987", {})
coverage_987 = interval_987.get("empirical")
best_conf = max((c for c in conf if c.get("accuracy") is not None and (c.get("n") or 0) >= 30),
                key=lambda c: c["accuracy"], default={})
rare_weights_path = OUT / "rare_weight_experiment.json"
rare_weights = json.loads(rare_weights_path.read_text(encoding="utf-8")) if rare_weights_path.exists() else None

audit = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "symbol": "^GSPC",
    "data": {"rows": len(spx), "start": str(spx.index.min().date()), "end": str(spx.index.max().date())},
    "target": {
        "claimed_accuracy": 0.987,
        "directional_accuracy_best_1949": best_hist[0],
        "directional_accuracy_best_modern": best_modern[0],
        "directional_987_reached": bool(max(best_hist[0], best_modern[0]) >= 0.987),
        "interval_coverage_987": coverage_987,
        "interval_987_reached": bool(coverage_987 is not None and coverage_987 >= 0.987),
        "interval_coverage_987_targeted": interval_targeted.get("coverage_eval"),
        "interval_987_targeted_reached": bool((interval_targeted.get("coverage_eval") or 0) >= 0.987),
        "verdict": "方向准确率 98.7% 在真实样本外数据上不可达；区间覆盖率 98.7% 可通过校准达到，但区间会很宽。",
    },
    "historical_1949": hist,
    "annual_regression": reg_summary,
    "annual_classification": clf_summary,
    "interval_calibration": interval,
    "interval_targeted": interval_targeted,
    "confidence_curve": conf,
    "rare_events": {"h1": rare1, "h5": rare5, "tail_eval": tail_eval},
    "strategy_eval": strategy,
    "rare_weight_experiment": rare_weights,
    "model_comparison_modern": modern,
    "regional": regional,
    "leakage_checks": checks,
    "best_confidence_slice": best_conf,
}
(OUT / "advanced_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

# 保留回归/分类逐日结果，便于复查
(OUT / "advanced_walk_regression.json").write_text(
    json.dumps(w_reg["rows"], ensure_ascii=False, indent=2, default=str), encoding="utf-8")
(OUT / "advanced_walk_classification.json").write_text(
    json.dumps(w_clf["rows"], ensure_ascii=False, indent=2, default=str), encoding="utf-8")

print("\n=== SUMMARY ===")
print(json.dumps({
    "best_1949": {"model": best_hist[1], "acc": best_hist[0]},
    "best_modern": {"model": best_modern[1], "acc": best_modern[0]},
    "interval_987": interval_987,
    "best_confidence_slice": best_conf,
    "verdict": audit["target"]["verdict"],
}, ensure_ascii=False, indent=2, default=str))
print("saved", OUT / "advanced_audit.json")
