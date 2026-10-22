import sys, time, warnings
from pathlib import Path
warnings.filterwarnings("ignore")
ROOT = Path(r"C:\Users\Lgnatius\Documents\AI产出\工具\金融分析预测")
sys.path.insert(0, str(ROOT / "src"))
from finance_app.data.store import DataStore
from finance_app.models import advanced as adv

ds = DataStore(); df = ds.get("^GSPC")
for name in ["ridge", "hgb", "rf", "ensemble"]:
    t0 = time.time()
    w = adv.annual_walk_forward(df, start_year=1950, end_year=1955, horizon=5,
                                model_name=name, task="reg", test_step=5, max_train=6000)
    s = adv.summarize_walk(w["rows"], "reg")
    print(name, "elapsed", round(time.time() - t0, 1), "rows", len(w["rows"]),
          "dir", s.get("overall", {}).get("dir_acc"), flush=True)
