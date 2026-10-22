"""统一的工程根目录解析，兼容 PyInstaller frozen（打包 exe）与开发模式。

- 开发模式：root = <project>/（即 src/finance_app/_paths.py 的 parents[3]）
- PyInstaller onedir/onefile：root = exe 所在目录（数据与资源被打包到该目录或其 _MEIPASS）

数据/配置/缓存的读写一律落到 root 下，确保打包后双击 exe 即可运行。
"""
from __future__ import annotations

import sys
from pathlib import Path


def get_root() -> Path:
    """返回工程根目录（含 data/ config/ analysis/ src/）。

    PyInstaller 6.x onedir 布局可能把 datas 分散在 <exe>/ 与 <exe>/_internal/，
    本函数逐级探测，确保无论数据落在哪都能找到。
    """
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
        candidates = [base / "_internal", base]
        for c in candidates:
            if (c / "data" / "processed" / "prices_long.csv").is_file():
                return c
        # 回退：_internal 存在就用它，否则 base
        internal = base / "_internal"
        if internal.is_dir():
            return internal
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
        return base
    return Path(__file__).resolve().parents[2]


ROOT = get_root()
