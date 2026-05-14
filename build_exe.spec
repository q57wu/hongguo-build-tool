# -*- mode: python ; coding: utf-8 -*-
"""
红果搭建工具 - PyInstaller 打包配置
生成单文件 exe，首次运行时自动释放 frontend/dist 和 selectors 到 exe 所在目录。
"""
import os
import sys
from pathlib import Path

block_cipher = None
ROOT = os.path.dirname(os.path.abspath(SPEC))

a = Analysis(
    [os.path.join(ROOT, 'app.py')],
    pathex=[ROOT],
    binaries=[],
    datas=[
        # 前端编译产物
        (os.path.join(ROOT, 'frontend', 'dist'), os.path.join('frontend', 'dist')),
        # 选择器配置
        (os.path.join(ROOT, 'backend', 'selectors', 'oceanengine.json'),
         os.path.join('backend', 'selectors')),
        # 静态资源（图标、二维码）
        (os.path.join(ROOT, 'assets'), 'assets'),
    ],
    hiddenimports=[
        # pywebview Windows 后端
        'webview',
        'webview.platforms.edgechromium',
        'webview.platforms',
        'clr_loader',
        'pythonnet',
        'bottle',
        'proxy_tools',
        # 标准库
        'sqlite3',
        'json',
        'logging',
        'logging.handlers',
        'asyncio',
        'concurrent.futures',
        'threading',
        'hashlib',
        'tempfile',
        # 项目依赖
        'playwright',
        'playwright.sync_api',
        'openpyxl',
        'filelock',
        # 项目内部模块
        'backend',
        'backend.api',
        'backend.bridge',
        'backend.build_adapter',
        'backend.build_engine',
        'backend.config_manager',
        'backend.task_registry',
        'backend.tool_adapter',
        'backend.core',
        'backend.core.build_steps',
        'backend.core.config_io',
        'backend.core.constants',
        'backend.core.data_parsers',
        'backend.core.exceptions',
        'backend.core.incentive_steps',
        'backend.core.incentive_tools',
        'backend.core.logging_utils',
        'backend.core.material_ops',
        'backend.core.parallel_build',
        'backend.core.parallel_build_incentive',
        'backend.core.playwright_utils',
        'backend.core.promo_chain',
        'backend.selectors',
        'backend.selectors.loader',
        'backend.services',
        'backend.services.account_pool',
        'backend.services.assign_log_service',
        'backend.services.browser_service',
        'backend.services.build_detail_service',
        'backend.services.build_progress',
        'backend.services.daily_task_service',
        'backend.services.crawl_material',
        'backend.services.vision_service',
        'backend.tools',
        'backend.tools._rta_common',
        'backend.tools.rta_check',
        'backend.tools.rta_set',
        'backend.utils',
        'backend.utils.diagnostics',
        'backend.utils.error_format',
        'backend.utils.file_utils',
        'backend.utils.interruptible',
        'backend.utils.stop_events',
        'backend.utils.win_focus',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', '_tkinter', 'unittest', 'test',
        'setuptools', 'pip', 'wheel',
        'numpy', 'pandas', 'matplotlib', 'scipy',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='红果搭建工具',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(ROOT, 'assets', 'app.ico'),
    version=None,
)
