# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller Spec file for Musicat Windows x64 build.
Compiles Musicat into a standalone Windows executable.
"""

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None
project_root = Path.cwd().resolve()

# Comprehensive hidden imports for all Musicat subsystems
hiddenimports = [
    'mutagen',
    'mutagen.id3',
    'mutagen.flac',
    'mutagen.mp4',
    'mutagen.wave',
    'mutagen.aiff',
    'mutagen.oggvorbis',
    'soundfile',
    '_soundfile_data',
    'scipy',
    'scipy.signal',
    'scipy.special',
    'scipy.linalg',
    'numpy',
    'PySide6',
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    'PySide6.QtMultimedia',
    'requests',
    'urllib3',
    'musicbrainzngs',
    'acoustid',
    'vlc',
]

datas = []

# Collect soundfile bundled DLLs
try:
    datas += collect_data_files('soundfile')
except Exception:
    pass

a = Analysis(
    [str(project_root / 'main.py')],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'IPython', 'notebook', 'torch', 'tensorflow'],
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
    name='Musicat',
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
)
