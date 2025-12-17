# -*- mode: python ; coding: utf-8 -*-

import sys, os

block_cipher = None

hiddenimports = [
    # Markdown extensions for documentation rendering
    'markdown.extensions.extra',
    'markdown.extensions.tables',
    'markdown.extensions.fenced_code',
    'markdown.extensions.codehilite',
    'markdown.extensions.toc',
    'markdown.extensions.nl2br',
    'markdown.extensions.sane_lists',
    'markdown.extensions.md_in_html',
    'pymdownx.arithmatex',
    # QtWebEngine modules for documentation viewer
    'PySide6.QtWebEngineCore',
    'PySide6.QtWebEngineWidgets',
]

a = Analysis(
    ['src/manic/main.py'],
    pathex=['src'],
    binaries=[],
    datas=[
        ('src/manic/resources/*', 'src/manic/resources'),
        ('src/manic/models/schema.sql', 'src/manic/models'),
        ('docs/*.md', 'docs'),
        ('docs/_assets/mathjax/*', 'docs/_assets/mathjax'),
    ],
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

# Use .icns for macOS (will use .ico as fallback if .icns doesn't exist)
icon_file = 'src/manic/resources/manic_logo.icns'
if not os.path.exists(icon_file):
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

# macOS app bundle
app = BUNDLE(
    coll,
    name='MANIC.app',
    icon=icon_file,
    bundle_identifier='com.crick.manic',
    info_plist={
        'CFBundleName': 'MANIC',
        'CFBundleDisplayName': 'MANIC',
        'CFBundleVersion': '4.0.01',
        'CFBundleShortVersionString': '4.0.01',
        'NSHighResolutionCapable': 'True',
    },
)
