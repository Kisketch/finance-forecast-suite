# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for FinPredict — onedir 模式，无外部数据依赖（实时联网）。

打包：py -m PyInstaller finpredict.spec --noconfirm
产物：dist/FinPredict/FinPredict.exe（双击即运行，含 echarts 离线资源）
"""
block_cipher = None

datas = [
    # 前端资源（ECharts 1MB + app.js + index.html + style.css），离线可用
    ('src/finpredict/web', 'src/finpredict/web'),
]

hiddenimports = [
    'webview.platforms.edgechromium',
    'webview.platforms.win32',
    'sklearn.ensemble',
    'sklearn.ensemble._hist_gradient_boosting',
    'sklearn.ensemble._forest',
    'sklearn.linear_model',
    'sklearn.impute',
    'sklearn.preprocessing',
    'sklearn.utils._typedefs',
    'curl_cffi',
    'multitasking',
]

a = Analysis(
    ['src/finpredict/app.py'],
    pathex=['src'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=['matplotlib', 'PyQt5', 'PyQt6', 'PySide2', 'PySide6',
              'tkinter', 'IPython', 'notebook', 'jupyter', 'pytest', 'sphinx',
              'torch', 'torchvision', 'tensorboard', 'tensorflow', 'keras', 'onnxruntime'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name='FinPredict',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico',
)

coll = COLLECT(
    exe, a.binaries, a.zipfiles, a.datas,
    strip=False, upx=True, upx_exclude=[],
    name='FinPredict',
)
