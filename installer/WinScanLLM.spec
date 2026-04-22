# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for WinScanLLM.

Onedir build (not onefile): Inno Setup wraps the whole folder into
``WinScanLLM-Setup-<version>.exe``. Onedir starts faster and avoids
the %TEMP% unpack dance that sometimes trips AV.

Invoke from the repo root:
    pyinstaller installer/WinScanLLM.spec
"""

from pathlib import Path

block_cipher = None

repo_root = Path(SPECPATH).resolve().parent
src_dir = repo_root / "src"
assets_dir = repo_root / "assets"
icon_ico = assets_dir / "icon.ico"


a = Analysis(
    [str(src_dir / "main.py")],
    pathex=[str(src_dir)],
    binaries=[],
    datas=[
        (str(assets_dir), "assets"),
    ],
    hiddenimports=[
        "PyQt6.QtCore",
        "PyQt6.QtGui",
        "PyQt6.QtWidgets",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
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
    name="WinScanLLM",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(icon_ico),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="WinScanLLM",
)
