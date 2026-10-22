"""桌面入口：启动本地 API 服务并以 WebView2 原生窗口打开。"""
from __future__ import annotations

import socket
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import webview

from finance_app.ui.server import serve


def free_port(start: int = 8765, end: int = 8865) -> int:
    for p in range(start, end):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", p))
                return p
            except OSError:
                continue
    raise RuntimeError("no free port")


def main() -> int:
    port = free_port()
    serve(port)
    time.sleep(0.6)
    window = webview.create_window(
        "金融分析预测终端 · FIN Terminal",
        f"http://127.0.0.1:{port}/",
        width=1480, height=940, min_size=(1180, 760),
        background_color="#0A0E13",
    )
    webview.start(gui="edgechromium", debug=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
