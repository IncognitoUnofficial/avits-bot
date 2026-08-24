# -*- mode: python ; coding: utf-8 -*-

import sys
import os

# Find Tcl/Tk folder for tkinter (needed for the GUI)
python_root = sys.base_prefix
tcl_folder = os.path.join(python_root, 'tcl')
if os.path.exists(tcl_folder):
    tcl_datas = [(tcl_folder, '_tcl_data')]
else:
    import tkinter
    tcl_folder = os.path.join(os.path.dirname(tkinter.__file__), '..', 'tcl')
    if os.path.exists(tcl_folder):
        tcl_datas = [(tcl_folder, '_tcl_data')]
    else:
        tcl_datas = []

block_cipher = None

# ---- Shared data files (included in COLLECT) ----
shared_datas = [
    ('accounts.json', '.'),
    ('chrome-131', 'chrome-131'),
    ('avits_login_v3/config.json', 'avits_login_v3'),
    ('avits_login_v3', 'avits_login_v3'),
] + tcl_datas

shared_hiddenimports = [
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
    # orchestrator imports (needed by both)
    'avits_login_v3.account_manager',
    'avits_login_v3.session_pool',
    'avits_login_v3.orchestrator',
    'avits_login_v3.calendar_manager',
    'avits_login_v3.rescheduler',
    'avits_login_v3.booking_executor',
    'avits_login_v3.reschedule_navigator',
    'avits_login_v3.login_page',
    'avits_login_v3.captcha_handler',
    'avits_login_v3.network_listener',
    'avits_login_v3.driver_manager',
    'avits_login_v3.config',
    'avits_login_v3.utils',
]

# ---- 1. Analysis for the GUI ----
a_gui = Analysis(
    ['avits_gui_multi.py'],
    pathex=[],
    binaries=[],
    datas=shared_datas,
    hiddenimports=shared_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

# ---- 2. Analysis for the Orchestrator ----
a_orch = Analysis(
    ['run_orchestrator.py'],
    pathex=[],
    binaries=[],
    datas=shared_datas,
    hiddenimports=shared_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

# ---- Build the GUI executable ----
pyz_gui = PYZ(a_gui.pure)

gui_exe = EXE(
    pyz_gui,
    a_gui.scripts,
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

# ---- Build the Orchestrator executable ----
pyz_orch = PYZ(a_orch.pure)

orchestrator_exe = EXE(
    pyz_orch,
    a_orch.scripts,
    [],
    exclude_binaries=True,
    name='AVITS_Orchestrator',
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

# ---- Collect everything into a single folder ----
coll = COLLECT(
    gui_exe,
    orchestrator_exe,
    a_gui.binaries,        # binaries from either analysis are fine (they are the same)
    a_orch.binaries,
    a_gui.datas,           # include the data files once
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AVITS_Bot',
)