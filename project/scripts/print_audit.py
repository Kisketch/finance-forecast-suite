import json
from pathlib import Path

p = Path(r"C:\Users\Lgnatius\Documents\AI产出\工具\金融分析预测\analysis\advanced_audit.json")
a = json.load(p.open(encoding="utf-8"))
pct = lambda v, d=1: "—" if v is None else f"{v*100:.{d}f}%"

print("## 目标\n")
print(json.dumps(a.get("target", {}), ensure_ascii=False, indent=2))

print("\n## 1949\n")
print("| 模型 | 类型 | 方向准确率 | 始终看多 | AUC | MCC | Skill | n |")
print("|---|---|---:|---:|---:|---:|---:|---:|")
for k, v in a.get("historical_1949", {}).get("models", {}).items():
    if "error" in v:
        print(f"| {k} | — | ERR | — | — | — | — | — |"); continue
    acc = v.get("dir_acc", v.get("accuracy"))
    print(f"| {k} | {v.get('type','')} | {pct(acc)} | {pct(v.get('baseline_long'))} | {v.get('auc')} | {v.get('mcc')} | {pct(v.get('skill'))} | {v.get('n')} |")

print("\n## 年度回归\n")
o = a.get("annual_regression", {}).get("overall", {})
print(json.dumps(o, ensure_ascii=False, indent=2))
print("\n| 十年 | n | 方向 | 始终看多 | MAE |")
print("|---|---:|---:|---:|---:|")
for k, v in a.get("annual_regression", {}).get("by_decade", {}).items():
    print(f"| {k}s | {v.get('n')} | {pct(v.get('dir_acc'))} | {pct(v.get('baseline_long'))} | {pct(v.get('mae'),2)} |")

print("\n## 区间\n")
print("| 名义 | 实测 | 宽度 |")
print("|---|---:|---:|")
for k, v in a.get("interval_calibration", {}).get("levels", {}).items():
    print(f"| {pct(v.get('nominal'))} | {pct(v.get('empirical'))} | {pct(v.get('width_logret'),2)} |")

print("\n## 置信度\n")
print("| 阈值 | 覆盖 | 准确率 | n |")
print("|---|---:|---:|---:|")
for c in a.get("confidence_curve", []):
    print(f"| {c.get('threshold')} | {pct(c.get('coverage'))} | {pct(c.get('accuracy'))} | {c.get('n')} |")

print("\n## 现代模型\n")
print("| 模型 | 方向 | 始终看多 | Skill | MAE | DM p |")
print("|---|---:|---:|---:|---:|---:|")
for k, v in a.get("model_comparison_modern", {}).items():
    x = v.get("overall", {})
    print(f"| {k} | {pct(x.get('dir_acc'))} | {pct(x.get('baseline_long'))} | {pct(x.get('skill'))} | {pct(x.get('mae'),2)} | {x.get('dm_p')} |")

print("\n## 区域\n")
print("| 标的 | 区域 | 价格 | 上下文 | 差值 |")
print("|---|---|---:|---:|---:|")
for sym, v in a.get("regional", {}).items():
    pa = v.get("modes", {}).get("price", {}).get("overall", {}).get("dir_acc")
    ca = v.get("modes", {}).get("context", {}).get("overall", {}).get("dir_acc")
    d = None if pa is None or ca is None else ca - pa
    print(f"| {v.get('name_cn', sym)} | {v.get('region')} | {pct(pa)} | {pct(ca)} | {'—' if d is None else f'{d*100:+.1f}pp'} |")

print("\n## 稀有事件\n")
print(json.dumps(a.get("rare_events", {}), ensure_ascii=False, indent=2))
print("\n## 策略\n")
print(json.dumps(a.get("strategy_eval", {}), ensure_ascii=False, indent=2))
print("\n## 泄漏\n")
for c in a.get("leakage_checks", []):
    print(c)
