# -*- mode: python ; coding: utf-8 -*-

import sys, os
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

block_cipher = None

hiddenimports = [
    'markdown.extensions.tables',
    'markdown.extensions.fenced_code',
    'markdown.extensions.codehilite',
    'markdown.extensions.toc',
]
hiddenimports += collect_submodules('PySide6')

datas_extra = []
try:
    datas_extra += collect_data_files('PySide6')
except Exception:
    pass

a = Analysis(
    ['src/manic/main.py'],
    pathex=['src'],
    binaries=[],
    datas=[
        ('src/manic/resources/*', 'src/manic/resources'),
        ('src/manic/models/schema.sql', 'src/manic/models'),
        ('docs/*.md', 'docs'),
    ] + datas_extra,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

icon_file = 'src/manic/resources/manic_logo.ico'
if not os.path.exists(icon_file):
    icon_file = None

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MANIC',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=icon_file
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='MANIC'
)
