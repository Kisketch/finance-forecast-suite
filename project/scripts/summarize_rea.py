"""从 rea 的大型 JSON 证据中流式提取关键结论（不整体加载 419MB）。"""
from __future__ import annotations

import json
import mmap
import re
from collections import Counter
from pathlib import Path

BASE = Path(r"C:\Users\Lgnatius\Documents\AI产出\工具\金融分析预测\reverse\tradingview")
SRC = BASE / "rea-analysis.json"
OUT = BASE / "summary.json"


def balanced(text: str, start: int, open_ch: str = "{", close_ch: str = "}") -> str:
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return ""


def find_key_value(text: str, key: str) -> str | None:
    m = re.search(rf'"{re.escape(key)}"\s*:\s*([\[{{])', text)
    if not m:
        return None
    start = m.start(1)
    return balanced(text, start, m.group(1), "]" if m.group(1) == "[" else "}")


def main() -> None:
    size = SRC.stat().st_size
    with SRC.open("rb") as fh:
        mm = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
        head = mm[:4]
        if head[:2] == b"\xff\xfe":
            raw = mm[: min(size, 120_000_000)]
            if len(raw) % 2:
                raw = raw[:-1]
            chunk = raw.decode("utf-16-le", "ignore")
        else:
            chunk = mm[: min(size, 60_000_000)].decode("utf-8", "ignore")
        # 统计节点/边类型
        kinds = Counter(re.findall(r'"kind"\s*:\s*"([^"]+)"', chunk))
        stat = find_key_value(chunk, "statistics")
        limitations = find_key_value(chunk, "limitations")
        electron = find_key_value(chunk, "static_electron_summary") or find_key_value(chunk, "electron")
        package = find_key_value(chunk, "package_json") or find_key_value(chunk, "package")
        coverage = find_key_value(chunk, "coverage")
        result = {
            "file_size_mb": round(size / 1e6, 1),
            "kinds_top": kinds.most_common(30),
            "statistics": json.loads(stat) if stat else None,
            "limitations": json.loads(limitations) if limitations else None,
            "electron": json.loads(electron) if electron else None,
            "package": json.loads(package) if package else None,
            "coverage": json.loads(coverage) if coverage else None,
        }
        # 额外：抓取 webpack chunk 路径样本
        paths = re.findall(r'"path"\s*:\s*"(app/[^"]+\.js)"', chunk)
        result["js_path_sample"] = sorted(set(paths))[:40]
        result["js_path_count"] = len(set(paths))
        OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2)[:6000])
        mm.close()


if __name__ == "__main__":
    main()
