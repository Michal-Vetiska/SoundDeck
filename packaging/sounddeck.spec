# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for a windowed macOS app.

pyside6-deploy is a good fit for a pure Qt program. SoundDeck also ships
PortAudio (via sounddevice), pynput, and yt-dlp, so PyInstaller is the
packaging path. FFmpeg stays an external tool installed with Homebrew.
"""

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

datas = collect_data_files("soundboard")
hidden = (
    collect_submodules("soundboard")
    + collect_submodules("yt_dlp")
    + collect_submodules("pynput")
)

a = Analysis(
    ["src/soundboard/main.py"],
    pathex=["src"],
    binaries=[],
    datas=datas,
    hiddenimports=hidden + ["sounddevice", "numpy"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SoundDeck",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="SoundDeck",
)
app = BUNDLE(
    coll,
    name="SoundDeck.app",
    icon=None,
    bundle_identifier="com.sounddeck.app",
    info_plist={
        "CFBundleName": "SoundDeck",
        "CFBundleDisplayName": "SoundDeck",
        "NSHighResolutionCapable": True,
        "NSMicrophoneUsageDescription": (
            "SoundDeck uses the microphone so it can mix your voice with sound effects."
        ),
        "LSMinimumSystemVersion": "12.0",
    },
)
