"""稀有事件降权对照：none / rare / exp / winsor。"""
import json
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(r"C:\Users\Lgnatius\Documents\AI产出\工具\金融分析预测")
sys.path.insert(0, str(ROOT / "src"))
from finance_app.data.store import DataStore
from finance_app.models import advanced as adv

ds = DataStore()
df = ds.get("^GSPC")
out = {"1949": {}, "2000_2026_ridge": {}}

for mode in ["none", "rare", "exp"]:
    X = adv.build_features(df)
    y, td = adv.make_target(df, 1)
    valid = y.notna() & (X.notna().sum(axis=1) >= 8)
    X, y, td = X[valid], y[valid], td[valid]
    tr = (td <= __import__("pandas").Timestamp("1948-12-31")) & y.notna()
    te = (__import__("pandas").Series(X.index.year, index=X.index) == 1949) & y.notna()
    rec = {}
    for name, task in [("ensemble", "reg"), ("hgb_clf", "clf")]:
        pred, prob = adv._fit_predict(X, y, name, task, tr, te, weight_mode=mode)
        actual = y.loc[te].values
        if task == "clf":
            m = adv._metrics_clf((actual > 0).astype(int), pred, prob)
            rec[name] = {"accuracy": m["accuracy"], "auc": m["auc"]}
        else:
            m = adv._metrics_reg(actual, pred)
            rec[name] = {"dir_acc": m["dir_acc"], "skill": m["skill"], "mae": m["mae"]}
    out["1949"][mode] = rec
    print("1949", mode, rec, flush=True)

for mode in ["none", "rare", "exp"]:
    w = adv.annual_walk_forward(df, start_year=2000, end_year=2026, horizon=5,
                                model_name="ridge", task="reg", test_step=5,
                                max_train=4000, weight_mode=mode)
    s = adv.summarize_walk(w["rows"], "reg")["overall"]
    out["2000_2026_ridge"][mode] = {k: s.get(k) for k in ("dir_acc", "skill", "mae", "baseline_long")}
    print("2000-2026 ridge", mode, out["2000_2026_ridge"][mode], flush=True)

(ROOT / "analysis" / "rare_weight_experiment.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print("saved")
