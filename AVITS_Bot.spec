# -*- mode: python ; coding: utf-8 -*-

import sys
import os

# Find the Tcl/Tk folder from the Python installation
python_root = sys.base_prefix
tcl_folder = os.path.join(python_root, 'tcl')
if os.path.exists(tcl_folder):
    tcl_datas = [(tcl_folder, '_tcl_data')]
else:
    # Fallback: try to locate tcl from tkinter module
    import tkinter
    tcl_folder = os.path.join(os.path.dirname(tkinter.__file__), '..', 'tcl')
    if os.path.exists(tcl_folder):
        tcl_datas = [(tcl_folder, '_tcl_data')]
    else:
        tcl_datas = []

block_cipher = None

a = Analysis(
    ['avits_gui_multi.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('accounts.json', '.'),
        ('chrome-131', 'chrome-131'),
        ('avits_login_v3/config.json', 'avits_login_v3'),
    ] + tcl_datas,
    hiddenimports=[
        'selenium',
        'undetected_chromedriver',
        'undetected_chromedriver.options',
        'undetected_chromedriver.patcher',
        'tkinter',
        'queue',
        'threading',
        'subprocess',
        'requests',
        'json',
        'os',
        'sys',
        'time',
        'logging',
        'datetime',
        'random',
        'typing',
        'selenium.webdriver',
        'selenium.webdriver.common.by',
        'selenium.webdriver.support.ui',
        'selenium.webdriver.support.expected_conditions',
        'selenium.common.exceptions',
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
    name='AVITS_Bot',
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
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AVITS_Bot',
)