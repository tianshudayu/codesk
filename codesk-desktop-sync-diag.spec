# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['E:\\codex-mcp-mobile\\desktop_sync\\run_remote_assist.py'],
    pathex=['E:\\codex-mcp-mobile\\desktop_sync'],
    binaries=[],
    datas=[('E:\\codex-mcp-mobile\\desktop_sync\\app\\static', 'app\\static')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='codesk-desktop-sync-diag',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='codesk-desktop-sync-diag',
)
