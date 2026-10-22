import json
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\Lgnatius\Documents\AI产出\工具\金融分析预测")
sys.path.insert(0, str(ROOT / "src"))
from finance_app.models import advanced as adv

audit_path = ROOT / "analysis" / "advanced_audit.json"
rows_path = ROOT / "analysis" / "advanced_walk_regression.json"
a = json.load(audit_path.open(encoding="utf-8"))
rows = json.load(rows_path.open(encoding="utf-8"))

a["strategy_eval"] = adv.strategy_eval(rows, horizon=5, cost_bps=5.0)
a["interval_targeted"] = adv.coverage_targeted_interval(rows, nominal=0.987)
conf = a.get("confidence_curve", [])
eligible = [c for c in conf if c.get("accuracy") is not None and (c.get("n") or 0) >= 30]
a["best_confidence_slice"] = max(eligible, key=lambda c: c["accuracy"]) if eligible else {}
t = a.setdefault("target", {})
t["interval_coverage_987_targeted"] = a["interval_targeted"].get("coverage_eval")
t["interval_987_targeted_reached"] = bool((a["interval_targeted"].get("coverage_eval") or 0) >= 0.987)
audit_path.write_text(json.dumps(a, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

print(json.dumps({
    "strategy_eval": a["strategy_eval"],
    "interval_targeted": a["interval_targeted"],
    "best_confidence_slice": a["best_confidence_slice"],
    "target": t,
}, ensure_ascii=False, indent=2, default=str))
