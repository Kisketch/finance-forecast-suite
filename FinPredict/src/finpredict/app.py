"""桌面入口：启动本地 API 服务并以 WebView2 原生窗口打开。

启动优化：后台预热线程预拉默认标的数据写入缓存，用户打开窗口时缓存命中秒回，
避免"刚点开就卡着不动"。
"""
from __future__ import annotations

import socket
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import webview
from finpredict.server import serve


def free_port(start: int = 8765, end: int = 8865) -> int:
    for p in range(start, end):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", p))
                return p
            except OSError:
                continue
    raise RuntimeError("no free port")


def _prefetch_default() -> None:
    """后台预拉默认标的数据，用户打开窗口时缓存命中秒回。

    失败静默——预热只是优化，不影响功能；用户切到该标的时仍会正常拉取。
    """
    try:
        from finpredict.data import get_quote
        get_quote("000001.SS", "1d")
    except Exception:  # noqa: BLE001
        pass


def main() -> int:
    port = free_port()
    serve(port)
    # 后台预热默认标的，避免用户打开窗口时白屏等待联网拉取
    threading.Thread(target=_prefetch_default, daemon=True, name="finpredict-prefetch").start()
    time.sleep(0.4)
    window = webview.create_window(
        "FinPredict · 实时金融趋势预判",
        f"http://127.0.0.1:{port}/",
        width=1440, height=920, min_size=(1100, 720),
        background_color="#0E1318",
    )
    webview.start(gui="edgechromium", debug=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
