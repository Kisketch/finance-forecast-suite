import sys, time, json
from pathlib import Path
ROOT = Path(r"C:\Users\Lgnatius\Documents\AI产出\工具\金融分析预测")
sys.path.insert(0, str(ROOT / "src"))
from finance_app.data.store import DataStore
from finance_app.models import advanced as adv

ds = DataStore()
df = ds.get("^GSPC")
print("rows", len(df), df.index.min().date(), df.index.max().date())

t0 = time.time()
res = adv.historical_holdout(df, train_end="1948-12-31", test_year=1949, horizon=1,
                             models=[("ridge", "reg"), ("hgb", "reg"), ("rf", "reg"), ("ensemble", "reg"),
                                     ("logit", "clf"), ("hgb_clf", "clf"), ("ensemble_clf", "clf")])
print("1949 elapsed", round(time.time() - t0, 1), "s")
print(json.dumps(res, ensure_ascii=False, indent=2, default=str)[:4000])

print("\n== annual smoke 2019-2021 ==")
t0 = time.time()
w = adv.annual_walk_forward(df, start_year=2019, end_year=2021, horizon=5, model_name="ensemble", task="reg", test_step=5)
print("annual elapsed", round(time.time() - t0, 1), "rows", len(w["rows"]))
print(json.dumps(adv.summarize_walk(w["rows"], "reg"), ensure_ascii=False, indent=2)[:2000])

print("\n== calibration ==")
print(json.dumps(adv.interval_calibration(w["rows"], levels=(0.5, 0.9, 0.987)), ensure_ascii=False, indent=2)[:1500])
print("\n== leakage ==")
print(json.dumps(adv.leakage_checks(df, 5), ensure_ascii=False, indent=2, default=str)[:1500])
