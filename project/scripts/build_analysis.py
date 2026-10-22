"""批量预测实验与分析底稿。"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from finance_app.data.store import DataStore  # noqa: E402
from finance_app.models.forecast import run_forecast  # noqa: E402

OUT = ROOT / "analysis"
OUT.mkdir(exist_ok=True)
ds = DataStore()

ASSETS = ["^GSPC", "^HSI", "000001.SS", "XLRE", "XLE", "CL=F", "0700.HK", "600519.SS"]
HORIZONS = [1, 5, 20]
results = []
t0 = time.time()
for sym in ASSETS:
    for h in HORIZONS:
        try:
            r = run_forecast(ds.get(sym), sym, horizon=h, model_name="ridge")
            results.append({
                "symbol": sym, "name_cn": ds.info(sym)["name_cn"], "horizon": h, "model": "ridge",
                "last_date": r.last_date, "last_close": r.last_close,
                "point_price": r.point_price, "point_logret": r.point_logret,
                "q05": r.q05_price, "q50": r.q50_price, "q95": r.q95_price,
                "n_folds": r.n_folds, "mae": r.mae_logret, "baseline_mae": r.baseline_mae,
                "skill": r.skill_score, "dir_acc": r.dir_acc, "baseline_dir": r.baseline_dir_acc,
                "mape": r.mape_price, "dm_p": r.dm_pvalue,
            })
            print(f"{sym:10s} h={h:2d} ridge skill={r.skill_score:+.3f} dir={r.dir_acc:.3f} point={r.point_price:.2f} ({time.time()-t0:.0f}s)", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"{sym} h={h} ERR {exc}", flush=True)

for sym in ["^GSPC", "^HSI", "XLRE"]:
    try:
        r = run_forecast(ds.get(sym), sym, horizon=5, model_name="gbm")
        results.append({
            "symbol": sym, "name_cn": ds.info(sym)["name_cn"], "horizon": 5, "model": "gbm",
            "last_date": r.last_date, "last_close": r.last_close,
            "point_price": r.point_price, "point_logret": r.point_logret,
            "q05": r.q05_price, "q50": r.q50_price, "q95": r.q95_price,
            "n_folds": r.n_folds, "mae": r.mae_logret, "baseline_mae": r.baseline_mae,
            "skill": r.skill_score, "dir_acc": r.dir_acc, "baseline_dir": r.baseline_dir_acc,
            "mape": r.mape_price, "dm_p": r.dm_pvalue,
        })
        print(f"{sym:10s} h=5 gbm skill={r.skill_score:+.3f} dir={r.dir_acc:.3f} point={r.point_price:.2f}", flush=True)
    except Exception as exc:  # noqa: BLE001
        print(f"{sym} gbm ERR {exc}", flush=True)

(OUT / "forecast_results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
print("saved", len(results), "results in", round(time.time() - t0, 1), "s")
