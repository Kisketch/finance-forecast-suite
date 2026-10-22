# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for FIN Terminal — onedir 模式。

打包：py -m PyInstaller fin_terminal.spec --noconfirm
产物：dist/FIN_Terminal/FIN_Terminal.exe（双击即运行，数据与资源在同目录）
"""
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

datas = [
    # 行情数据（90MB 长表，打包进 bundle）
    ('data/processed/prices_long.csv', 'data/processed'),
    # 元数据/质量报告
    ('data/metadata', 'data/metadata'),
    # 新闻库（已分析的 165 条）
    ('data/news/news.db', 'data/news'),
    # 券商观点
    ('data/analysts', 'data/analysts'),
    # 开源项目评审
    ('data/research', 'data/research'),
    # 模型缓存目录（空，运行时生成）
    ('data/cache', 'data/cache'),
    # 配置
    ('config', 'config'),
    # 审计结果 JSON（页面展示用）
    ('analysis/advanced_audit.json', 'analysis'),
    ('analysis/forecast_results.json', 'analysis'),
    ('analysis/market_stats.json', 'analysis'),
    ('analysis/validation_report.json', 'analysis'),
    ('analysis/rare_weight_experiment.json', 'analysis'),
    ('analysis/enhanced_audit.json', 'analysis'),
    # 前端资源（ECharts 1MB + app.js + index.html + style.css）
    ('src/finance_app/ui/web', 'src/finance_app/ui/web'),
]

binaries = []

# 只显式声明 PyInstaller 自带 hook 可能漏掉的；不 collect_submodules 避免拉入 torch
hiddenimports = [
    'webview.platforms.edgechromium',
    'webview.platforms.win32',
    'webview.platforms.mswin',
    'sklearn.ensemble',
    'sklearn.ensemble._hist_gradient_boosting',
    'sklearn.ensemble._forest',
    'sklearn.calibration',
    'sklearn.linear_model',
    'sklearn.impute',
    'sklearn.preprocessing',
    'sklearn.utils._typedefs',
    'curl_cffi',
    'multitasking',
]

a = Analysis(
    ['src/finance_app/ui/app.py'],
    pathex=['src'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=['matplotlib', 'PyQt5', 'PyQt6', 'PySide2', 'PySide6',
              'tkinter', 'IPython', 'notebook', 'jupyter',
              'pytest', 'sphinx',
              # scipy 可选拉入 torch，体积巨大且本项目不用，显式排除
              'torch', 'torchvision', 'torchtext', 'tensorboard',
              'tensorflow', 'keras', 'onnxruntime'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='FIN_Terminal',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # 桌面应用，无控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='FIN_Terminal',
)
