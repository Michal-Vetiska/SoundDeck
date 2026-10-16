"""Connect the window to the audio engine, hotkeys, and library.

The window emits intents. This object performs them. It is the only place
that both knows the engine and talks to Qt signals.
"""

from __future__ import annotations

import logging
import shutil
import uuid
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal

from soundboard.audio.devices import DeviceSnapshot, snapshot_devices
from soundboard.audio.engine import AudioEngine, PlaybackState
from soundboard.audio.loader import load_pcm, validate_audio_file
from soundboard.config.models import AppConfig
from soundboard.errors import AudioEngineError, SoundDeckError, public_message
from soundboard.hotkeys.manager import HotkeyManager
from soundboard.hotkeys.parser import format_hotkey, parse_hotkey
from soundboard.platform.base import PlatformAdapter
from soundboard.services.library import SoundLibrary
from soundboard.services.workers import DecodeWorker
from soundboard.utils.text import clean_name

logger = logging.getLogger(__name__)

PREVIEW_ID = "__preview__"


class SoundboardController(QObject):
    """Application service used by the main window."""

    engine_status_changed = Signal(str, str)
    sounds_changed = Signal()
    playback_changed = Signal(object)
    devices_changed = Signal(object)
    error_reported = Signal(str, str)
    notice_reported = Signal(str, str)
    import_busy = Signal(bool)
    permissions_changed = Signal()

    def __init__(
        self,
        config: AppConfig,
        library: SoundLibrary,
        engine: AudioEngine,
        hotkeys: HotkeyManager,
        platform: PlatformAdapter,
    ) -> None:
        super().__init__()
        self.config = config
        self.library = library
        self.engine = engine
        self.hotkeys = hotkeys
        self.platform = platform
        self._workers: list[DecodeWorker] = []
        self._last_playback: tuple[PlaybackState, ...] = ()
        self._timer = QTimer(self)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self._drain)
        self._timer.start()

    def bootstrap(self) -> None:
        """Load saved sounds, restore hotkeys, and start the engine if it can."""
        logger.info("Starting SoundDeck")
        self._load_saved_sounds()
        self._restore_hotkeys()
        self.refresh_devices()
        if self.config.audio.input_device and self.config.audio.output_device:
            self.start_engine()

    def shutdown(self) -> None:
        logger.info("Shutting down SoundDeck")
        self._timer.stop()
        self.hotkeys.shutdown()
        self.engine.stop()
        self.engine.unload(PREVIEW_ID)

    def refresh_devices(self) -> DeviceSnapshot:
        snapshot = snapshot_devices(self.platform.virtual_output_hints())
        if snapshot.virtual_output is None:
            logger.info("Virtual output %s was not found", self.platform.virtual_device_label())
        else:
            logger.info("Virtual output detected: %s", snapshot.virtual_output.name)
        self.devices_changed.emit(snapshot)
        return snapshot

    def start_engine(self) -> bool:
        try:
            self.engine.set_mic_volume(self.config.audio.mic_volume)
            self.engine.set_master_volume(self.config.audio.master_volume)
            self.engine.start(self.config.audio.input_device, self.config.audio.output_device)
        except AudioEngineError as exc:
            logger.error("Engine start failed: %s", exc)
            self.engine_status_changed.emit("error", public_message(exc))
            self.error_reported.emit("Audio engine", public_message(exc))
            return False
        except Exception as exc:
            logger.exception("Engine start failed unexpectedly")
            self.engine_status_changed.emit("error", public_message(exc))
            self.error_reported.emit("Audio engine", public_message(exc))
            return False
        self.engine_status_changed.emit("running", "Engine running")
        return True

    def stop_engine(self) -> None:
        self.engine.stop()
        self.engine_status_changed.emit("stopped", "Engine stopped")

    def restart_engine(self) -> None:
        if self.start_engine():
            logger.info("Audio engine restarted")

    def set_devices(self, input_name: str | None, output_name: str | None) -> None:
        self.config.audio.input_device = input_name or None
        self.config.audio.output_device = output_name or None
        self.library.storage.save(self.config)
        logger.info("Selected input=%s output=%s", input_name, output_name)
        if self.config.audio.input_device and self.config.audio.output_device:
            self.restart_engine()
        else:
            self.stop_engine()

    def set_mic_volume(self, volume: float, *, persist: bool = True) -> None:
        self.config.audio.mic_volume = min(1.0, max(0.0, volume))
        self.engine.set_mic_volume(self.config.audio.mic_volume)
        if persist:
            self.library.storage.save(self.config)

    def set_master_volume(self, volume: float, *, persist: bool = True) -> None:
        self.config.audio.master_volume = min(1.0, max(0.0, volume))
        self.engine.set_master_volume(self.config.audio.master_volume)
        if persist:
            self.library.storage.save(self.config)

    def play(self, sound_id: str) -> None:
        if not self.engine.running:
            self.notice_reported.emit("Audio engine", "Start the audio engine before playing a sound.")
            return
        logger.info("Play requested for %s", sound_id)
        self.engine.play(sound_id)

    def stop_sound(self, sound_id: str) -> None:
        self.engine.stop_sound(sound_id)

    def set_sound_volume(self, sound_id: str, volume: float, *, persist: bool = True) -> None:
        entry = self.library.find(sound_id)
        if entry is None:
            return
        entry.volume = min(1.0, max(0.0, float(volume)))
        self.engine.set_sound_volume(entry.id, entry.volume)
        if persist:
            self.library.storage.save(self.config)

    def rename(self, sound_id: str, name: str) -> None:
        try:
            self.library.rename(sound_id, name)
        except SoundDeckError as exc:
            self.error_reported.emit("Rename", public_message(exc))
            return
        self.sounds_changed.emit()

    def delete_sound(self, sound_id: str) -> None:
        self.engine.stop_sound(sound_id)
        self.engine.unload(sound_id)
        self.hotkeys.clear(sound_id)
        try:
            self.library.remove(sound_id)
        except SoundDeckError as exc:
            self.error_reported.emit("Delete", public_message(exc))
            return
        self._apply_hotkeys()
        self.sounds_changed.emit()

    def set_hotkey(self, sound_id: str, combo: str | None) -> bool:
        try:
            if combo:
                combo = format_hotkey(parse_hotkey(combo))
            self.hotkeys.set_binding(sound_id, combo)
            self.library.set_hotkey(sound_id, combo)
        except SoundDeckError as exc:
            self.error_reported.emit("Hotkey", public_message(exc))
            return False
        self._apply_hotkeys()
        self.sounds_changed.emit()
        return True

    def import_file(self, path: Path) -> None:
        try:
            validate_audio_file(path)
            clean_name(path.stem)
        except SoundDeckError as exc:
            self.error_reported.emit("Import", public_message(exc))
            return
        destination = self.library.sounds_dir / f"{uuid.uuid4().hex}.f32"
        worker = DecodeWorker(path, destination)
        worker.succeeded.connect(lambda dest, source=path: self._finish_import(source, dest))
        worker.failed.connect(self._fail_import)
        self._track(worker)
        self.import_busy.emit(True)
        logger.info("Importing %s", path)
        worker.start()

    def add_pcm_file(self, name: str, pcm_path: Path) -> None:
        """Copy an already-decoded PCM file into the library."""
        try:
            samples = load_pcm(pcm_path)
            entry = self.library.add_samples(name, samples)
        except SoundDeckError as exc:
            logger.exception("Could not add PCM sound")
            self.error_reported.emit("Import", public_message(exc))
            return
        try:
            self.engine.register_buffer(entry.id, samples)
            self.engine.set_sound_volume(entry.id, entry.volume)
        except Exception:
            logger.exception("Could not register imported sound")
        self.sounds_changed.emit()

    def preview_pcm(self, pcm_path: Path) -> None:
        if not self.engine.running:
            self.notice_reported.emit("Preview", "Start the audio engine to hear the clip.")
            return
        try:
            samples = load_pcm(pcm_path)
        except SoundDeckError as exc:
            self.error_reported.emit("Preview", public_message(exc))
            return
        self.engine.register_buffer(PREVIEW_ID, samples)
        self.engine.set_sound_volume(PREVIEW_ID, 0.8)
        self.engine.play(PREVIEW_ID)

    def stop_preview(self) -> None:
        self.engine.stop_sound(PREVIEW_ID)
        self.engine.unload(PREVIEW_ID)

    def complete_onboarding(self, done: bool = True) -> None:
        self.config.onboarding_complete = done
        self.library.storage.save(self.config)

    def hotkey_permission_blocked(self) -> bool:
        return self.hotkeys.permission_blocked

    def _finish_import(self, source: Path, destination: str) -> None:
        self.import_busy.emit(False)
        pcm_path = Path(destination)
        try:
            samples = load_pcm(pcm_path)
            entry = self.library.add_samples(source.stem, samples)
        except SoundDeckError as exc:
            logger.exception("Import failed after decode")
            pcm_path.unlink(missing_ok=True)
            self.error_reported.emit("Import", public_message(exc))
            return
        # add_samples writes a second PCM file. Drop the worker's temporary one
        # when it is not the library file.
        library_path = self.library.path_for(entry)
        if pcm_path.resolve() != library_path.resolve():
            pcm_path.unlink(missing_ok=True)
        self.engine.register_buffer(entry.id, samples)
        self.engine.set_sound_volume(entry.id, entry.volume)
        self.sounds_changed.emit()

    def _fail_import(self, message: str) -> None:
        self.import_busy.emit(False)
        self.error_reported.emit("Import", message)

    def _load_saved_sounds(self) -> None:
        missing: list[str] = []
        for entry in list(self.config.sounds):
            path = self.library.path_for(entry)
            if not path.is_file():
                logger.error("Missing sound file %s", path)
                missing.append(entry.name)
                continue
            try:
                samples = self.library.load_samples(entry)
            except SoundDeckError:
                logger.exception("Could not load %s", entry.file)
                missing.append(entry.name)
                continue
            self.engine.register_buffer(entry.id, samples)
            self.engine.set_sound_volume(entry.id, entry.volume)
        if missing:
            joined = ", ".join(missing[:4])
            self.notice_reported.emit(
                "Library",
                f"Some sounds could not be loaded: {joined}.",
            )

    def _restore_hotkeys(self) -> None:
        for entry in self.config.sounds:
            if not entry.hotkey:
                continue
            try:
                self.hotkeys.set_binding(entry.id, entry.hotkey)
            except SoundDeckError:
                logger.exception("Skipping saved hotkey for %s", entry.id)
        self._apply_hotkeys()

    def _apply_hotkeys(self) -> None:
        self.hotkeys.apply()
        self.permissions_changed.emit()

    def _drain(self) -> None:
        failure = self.engine.poll_health()
        if failure:
            self.engine_status_changed.emit("error", "Engine stopped")
            self.error_reported.emit("Audio engine", failure)
        for sound_id in self.hotkeys.poll():
            self.play(sound_id)
        snapshot = self.engine.playback_snapshot()
        if snapshot != self._last_playback:
            self._last_playback = snapshot
            self.playback_changed.emit(snapshot)

    def _track(self, worker: DecodeWorker) -> None:
        self._workers.append(worker)
        worker.finished.connect(lambda worker=worker: self._drop_worker(worker))

    def _drop_worker(self, worker: DecodeWorker) -> None:
        if worker in self._workers:
            self._workers.remove(worker)

    def make_temp_dir(self, name: str) -> Path:
        directory = self.library.support_dir / "tmp" / name
        if directory.exists():
            shutil.rmtree(directory, ignore_errors=True)
        directory.mkdir(parents=True, exist_ok=True)
        return directory
