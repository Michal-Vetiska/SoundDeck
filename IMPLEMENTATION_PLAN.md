# Implementation plan

SoundDeck is a desktop soundboard. A physical microphone and local sounds are mixed in real time and sent to a virtual audio device. Discord then uses that device as its microphone. The first build targets macOS on Apple Silicon. The core does not depend on a specific operating system.

## Architecture

The window emits intents (`play`, `stop`, `rename`, `volume`, `hotkey`). `SoundboardController` performs them. `AudioEngine` never imports Qt. Platform checks live only in `src/soundboard/platform/detect.py`.

```
UI (cards, dialogs)
        │
        ▼
SoundboardController
        │
        ├── AudioEngine ── Mixer
        ├── HotkeyManager
        ├── SoundLibrary / JsonConfigStorage
        └── YouTube workers
                │
                ▼
        PlatformAdapter
        ├── macOS: BlackHole, Liquid Glass, Accessibility
        └── Windows (stub): VB-CABLE, Fluent tokens
```

Audio path:

```
Microphone → InputStream → ring buffer ─┐
PCM library (already decoded) ──────────┼→ Mixer → soft clip → OutputStream → BlackHole → Discord
```

The microphone and BlackHole are different devices, so the engine opens two streams. The input callback only copies samples. The output callback mixes. There is no duplex stream and no resampling inside the callback.

## Dependencies

Declared in `pyproject.toml` (src layout, Python 3.12+):

- PySide6 for the UI
- sounddevice and numpy for realtime audio
- pynput for global hotkeys
- yt-dlp for YouTube metadata and temporary downloads
- FFmpeg on the PATH for decode and cutting (external, not a Python package)
- pyobjc-framework-Cocoa on macOS for optional vibrancy
- pytest and PyInstaller as development extras

Internal audio is 48 kHz, float32, stereo. Compressed files are decoded once at import into `sounds/<id>.f32`.

## Project structure

```
src/soundboard/
  main.py                 composition root
  audio/                  engine, mixer, devices, loader, ring buffer
  hotkeys/                parser and listener
  youtube/                metadata, download, cut, waveform seam
  config/                 dataclasses and JSON storage
  platform/               macOS, Windows stub, detection
  services/               controller, library, workers
  ui/                     window, glass widgets, dialogs, themes
tests/
packaging/sounddeck.spec
```

## Phases

1. Skeleton, config, device enumeration.
2. Microphone to virtual-output passthrough, start/stop/restart, device-loss handling.
3. PCM playback, mixer, soft clip.
4. File import, sound cards, persisted library.
5. Global hotkeys, conflicts, Accessibility.
6. Liquid Glass tokens, native vibrancy with a Qt fallback, responsive grid.
7. YouTube metadata, timeline, preview, cut, progress, temporary-file cleanup.
8. Onboarding and user-facing errors.
9. Tests, README, this plan, Czech `HOW_IT_WORKS.md`, PyInstaller spec.

## Technical risks

- Two devices drift. A ring buffer absorbs it: underrun becomes silence, overrun drops the oldest frames.
- The audio callback must not log, allocate large arrays, or take a lock for long. The ring lock covers one block copy. Commands are a short queue drained at the start of the output callback.
- PyObjC vibrancy can fail on a Qt window. The app keeps running on the translucent stylesheet.
- pynput on macOS needs Accessibility permission. Without it, hotkeys stay saved and the window explains why they are idle.
- BlackHole may be missing. The app shows install instructions and does not crash.
- FFmpeg may be missing. Import fails with a short message. Passthrough still works.

## macOS permissions

- Microphone, requested when the input stream starts. The bundled app sets `NSMicrophoneUsageDescription`.
- Accessibility, required for global hotkeys. Checked with `AXIsProcessTrusted`.

## Audio routing

SoundDeck does not ship a driver. On macOS the expected output is BlackHole 2ch. A later Windows build looks for VB-CABLE (`CABLE Input` / `VB-Audio`) through the same device resolver. Local monitoring of the mix is a reserved engine method and a disabled checkbox, because a monitor can create a feedback loop.

## Packaging

PyInstaller (`packaging/sounddeck.spec`) builds `SoundDeck.app`. `pyside6-deploy` is a poor fit once PortAudio, pynput, and yt-dlp are included. FFmpeg remains an external Homebrew install.
