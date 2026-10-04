# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller Spec file for Musicat macOS Application Bundle.
Compiles Musicat into a native standalone Musicat.app bundle supporting
Apple Silicon (ARM64) and Intel (x86_64) architectures.
"""

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None
project_root = Path.cwd().resolve()

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
    'src.gui.views',
    'src.gui.views.crates_view',
]

datas = [
    (str(project_root / 'locales'), 'locales'),
    (str(project_root / 'assets'), 'assets'),
]
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
    [],
    exclude_binaries=True,
    name='Musicat',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=True,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='Musicat',
)

app = BUNDLE(
    coll,
    name='Musicat.app',
    icon=str(project_root / 'assets' / 'icon.icns') if (project_root / 'assets' / 'icon.icns').exists() else str(project_root / 'assets' / 'icon.png'),
    bundle_identifier='com.ilred89.musicat',
    info_plist={
        'CFBundleName': 'Musicat',
        'CFBundleDisplayName': 'Musicat',
        'CFBundleIdentifier': 'com.ilred89.musicat',
        'CFBundleVersion': '1.3.0',
        'CFBundleShortVersionString': '1.3.0',
        'CFBundleExecutable': 'Musicat',
        'CFBundlePackageType': 'APPL',
        'LSMinimumSystemVersion': '11.0',
        'NSHighResolutionCapable': True,
        'NSRequiresAquaSystemAppearance': False,  # Native Dark Mode
        'NSMicrophoneUsageDescription': 'Musicat uses audio access for acoustic analysis, BPM detection and DJ previewing.',
        'CFBundleDocumentTypes': [
            {
                'CFBundleTypeName': 'Audio File',
                'CFBundleTypeRole': 'Viewer',
                'LSHandlerRank': 'Alternate',
                'LSItemContentTypes': [
                    'public.audio',
                    'public.mp3',
                    'org.xiph.flac',
                    'com.apple.m4a-audio',
                    'com.microsoft.waveform-audio',
                    'public.aifc-audio',
                    'public.aiff-audio',
                    'org.xiph.ogg',
                ],
            }
        ],
    },
)
