# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['multiscreen_tray.py'],
    pathex=[],
    binaries=[],
    datas=[('icon.png', '.')],
    hiddenimports=[
        # Ensure all lumina_control submodules are bundled
        # (some are imported lazily inside methods — static analysis misses them)
        'lumina_control',
        'lumina_control.config',
        'lumina_control.style',
        'lumina_control.i18n',
        'lumina_control.profiles',
        'lumina_control.app_rules',
        'lumina_control.utils',
        'lumina_control.monitor_enumerate',
        'lumina_control.startup',
        'lumina_control.updater',
        'lumina_control.ui',
        'lumina_control.ui.tray',
        'lumina_control.ui.main_window',
        'lumina_control.ui.monitor_card',
        'lumina_control.ui.app_rules_dialog',
        'lumina_control.ui.calibration',
        'lumina_control.ui.patterns',
        # pywin32 helpers sometimes need an explicit nudge
        'win32api', 'win32con', 'win32gui', 'win32process',
        'pywintypes',
        # stdlib used at runtime
        'winreg', 'locale', 'ssl', 'urllib.request', 'urllib.error',
        # zoneinfo + tzdata — needed for city-local sunrise/sunset times
        'zoneinfo', 'tzdata',
        # cryptography — offline license verification (Ed25519)
        'cryptography',
        'cryptography.hazmat.primitives.asymmetric.ed25519',
        'cryptography.hazmat.primitives.serialization',
        'cryptography.exceptions',
    ],
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
    name='LuminaControl',
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
    icon=['icon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='LuminaControl',
)
