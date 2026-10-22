import sys, time, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from finance_app.data.store import DataStore
from finance_app.models.forecast import run_forecast

ds = DataStore()
print("symbols", len(ds.by_symbol), "indices", len(ds.overview()["indices"]))
for sym, h, model in [("^GSPC", 5, "ridge"), ("^GSPC", 5, "gbm"), ("0700.HK", 5, "ridge")]:
    t0 = time.time()
    try:
        r = run_forecast(ds.get(sym), sym, horizon=h, model_name=model)
        print(f"{sym} h={h} {model}: {time.time()-t0:.1f}s folds={r.n_folds} mae={r.mae_logret:.5f} base={r.baseline_mae:.5f} skill={r.skill_score:.3f} dir={r.dir_acc:.3f} point={r.point_price:.2f} q05={r.q05_price:.2f} q95={r.q95_price:.2f}")
    except Exception as e:
        print(sym, model, "ERR", type(e).__name__, e)
