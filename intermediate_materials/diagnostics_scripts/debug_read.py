from pathlib import Path
import re
p = Path(r"C:\Users\Lgnatius\Documents\AI产出\工具\金融分析预测\reverse\tradingview\rea-analysis.json")
with p.open("rb") as f:
    b = f.read(5000)
print("len", len(b))
print("head", b[:400])
print("kind count", b.count(b'"kind"'))
print("regex", len(re.findall(rb'"kind"\s*:\s*"([^"]+)"', b)))
