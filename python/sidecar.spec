# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — freeze DingDa Python sidecar for Tauri externalBin."""

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

block_cipher = None
root = Path(SPECPATH)

a = Analysis(
    [str(root / "src" / "dingda_sidecar" / "main.py")],
    pathex=[str(root / "src")],
    binaries=[],
    datas=[],
    hiddenimports=collect_submodules("dingda_sidecar"),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="sidecar",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
