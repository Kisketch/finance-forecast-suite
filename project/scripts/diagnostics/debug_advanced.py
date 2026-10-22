import sys, traceback
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(r"C:\Users\Lgnatius\Documents\AI产出\工具\金融分析预测")
sys.path.insert(0, str(ROOT / "src"))
from finance_app.data.store import DataStore
from finance_app.models import advanced as adv

ds = DataStore(); df = ds.get("^GSPC")
X = adv.build_features(df)
y, td = adv.make_target(df, 5)
valid = y.notna() & (X.notna().sum(axis=1) >= 8)
X2, y2, td2 = X[valid], y[valid], td[valid]
print("X", X.shape, "X2", X2.shape, "valid years", X2.index.year.min(), X2.index.year.max())
print("rows per year 2019-2021", pd.Series(X2.index.year, index=X2.index).value_counts().reindex([2019,2020,2021]).to_dict())
for year in [2019,2020,2021]:
    tm = (pd.Series(X2.index.year, index=X2.index) == year) & y2.notna()
    print(year, "test_mask", int(tm.sum()), "train", int(((td2 <= pd.Timestamp(f'{year-1}-12-31')) & y2.notna()).sum()))

train_end = pd.Timestamp("2018-12-31")
tr = (td2 <= train_end) & y2.notna()
te = (pd.Series(X2.index.year, index=X2.index) == 2019) & y2.notna()
print("tr", int(tr.sum()), "te", int(te.sum()))
try:
    pred, prob = adv._fit_predict(X2, y2, "hgb", "reg", tr, te, weight_mode="rare")
    print("hgb ok", pred[:3])
except Exception:
    traceback.print_exc()

try:
    pred, prob = adv._fit_predict(X2, y2, "ridge", "reg", tr, te, weight_mode="rare")
    print("ridge ok", pred[:3])
except Exception:
    traceback.print_exc()
