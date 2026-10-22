import json
from pathlib import Path

p = Path(r"C:\Users\Lgnatius\Documents\AI产出\工具\金融分析预测\analysis\forecast_results.json")
d = json.load(p.open(encoding="utf-8"))
print("| 标的 | 周期 | 模型 | Skill | 方向准确率 | 始终看多 | MAPE | DM p | 点预测 | 90% 区间 |")
print("|---|---:|---|---:|---:|---:|---:|---:|---:|---|")
for x in d:
    dm = "—" if x["dm_p"] is None else f'{x["dm_p"]:.3f}'
    print(f'| {x["name_cn"]} | {x["horizon"]}日 | {x["model"]} | {x["skill"]*100:+.1f}% | '
          f'{x["dir_acc"]*100:.1f}% | {x["baseline_dir"]*100:.1f}% | {x["mape"]:.2f}% | {dm} | '
          f'{x["point_price"]:.2f} | {x["q05"]:.2f}–{x["q95"]:.2f} |')
