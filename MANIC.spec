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
    # Dynamically loaded Qt modules (charts, SVG icon plugins, documentation viewer)
    'PySide6.QtCharts',
    'PySide6.QtSvg',
    'PySide6.QtWebEngineCore',
    'PySide6.QtWebEngineWidgets',
]

rust_lib = 'src/manic/processors/manic_fitter.dll'
if not os.path.exists(rust_lib):
    raise FileNotFoundError(
        f"Missing compiled Rust peak fitter at {rust_lib}. "
        "Run `scripts\\build_rust_fitter.bat` first."
    )
rust_binaries = [(rust_lib, 'manic/processors')]

a = Analysis(
    ['src/manic/main.py'],
    pathex=['src'],
    binaries=rust_binaries,
    datas=[
        ('src/manic/resources/*', 'src/manic/resources'),
        ('src/manic/models/schema.sql', 'src/manic/models'),
        ('docs/*.md', 'docs'),
        ('docs/_assets/mathjax/*', 'docs/_assets/mathjax'),
        ('docs/_assets/screenshots/*', 'docs/_assets/screenshots'),
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'pytest',
        '_pytest',
        'pyqtgraph',
        'pygal',
        'pygaljs',
        'tkinter',
        '_tkinter',
        'IPython',
        'jupyter',
    ],
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
    upx=False,
    console=False,
    icon=icon_file
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=['manic_fitter.dll'],
    name='MANIC'
)
