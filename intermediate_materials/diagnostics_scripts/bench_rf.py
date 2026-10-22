import sys, time
from pathlib import Path
import pandas as pd
ROOT = Path(r"C:\Users\Lgnatius\Documents\AI产出\工具\金融分析预测")
sys.path.insert(0, str(ROOT / "src"))
from finance_app.data.store import DataStore
from finance_app.models import advanced as adv
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline

ds = DataStore(); df = ds.get("^GSPC")
X = adv.build_features(df); y, td = adv.make_target(df, 5)
valid = y.notna() & (X.notna().sum(axis=1) >= 8)
X, y, td = X[valid], y[valid], td[valid]
tr = (td <= pd.Timestamp("1948-12-31")) & y.notna()
Xtr, ytr = X.loc[tr].tail(6000), y.loc[tr].tail(6000)
print("train", Xtr.shape)
for n, mf, nj in [(200, 1.0, -1), (200, 0.5, 4), (120, 0.5, 4), (120, 0.5, 1), (100, "sqrt", 4)]:
    m = Pipeline([("imp", SimpleImputer(strategy="median")),
                  ("m", RandomForestRegressor(n_estimators=n, max_depth=6, min_samples_leaf=20,
                                              max_features=mf, n_jobs=nj, random_state=42))])
    t0 = time.time(); m.fit(Xtr, ytr); print(n, mf, nj, round(time.time() - t0, 2), "s")
