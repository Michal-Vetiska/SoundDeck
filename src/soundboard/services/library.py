"""Persisted sound library.

Files live under the application support directory. Config stores a relative
path such as ``sounds/<id>.f32``.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

import numpy as np

from soundboard.audio.formats import SAMPLE_RATE
from soundboard.audio.loader import load_pcm, save_pcm
from soundboard.audio.mixer import ensure_stereo_f32
from soundboard.config.models import AppConfig, SoundEntry
from soundboard.config.storage import ConfigStorage
from soundboard.errors import SoundDeckError
from soundboard.utils.text import clean_name

logger = logging.getLogger(__name__)


class SoundLibrary:
    """Add, rename, and delete sounds, and keep the JSON config in step."""

    def __init__(self, support_dir: Path, storage: ConfigStorage, config: AppConfig) -> None:
        self.support_dir = support_dir
        self.sounds_dir = support_dir / "sounds"
        self.storage = storage
        self.config = config
        self.sounds_dir.mkdir(parents=True, exist_ok=True)

    def path_for(self, entry: SoundEntry) -> Path:
        relative = Path(entry.file)
        if relative.is_absolute() or ".." in relative.parts:
            raise SoundDeckError("The sound path in settings is not valid.")
        return self.support_dir / relative

    def find(self, sound_id: str) -> SoundEntry | None:
        for entry in self.config.sounds:
            if entry.id == sound_id:
                return entry
        return None

    def add_samples(self, name: str, samples: np.ndarray) -> SoundEntry:
        """Store decoded PCM and append a config entry."""
        array = ensure_stereo_f32(samples)
        if array.shape[0] == 0:
            raise SoundDeckError("That sound has no audio.")
        sound_id = uuid.uuid4().hex
        relative = Path("sounds") / f"{sound_id}.f32"
        destination = self.support_dir / relative
        save_pcm(destination, array)
        entry = SoundEntry(
            id=sound_id,
            name=clean_name(name),
            file=relative.as_posix(),
            hotkey=None,
            volume=0.8,
            duration_seconds=float(array.shape[0]) / SAMPLE_RATE,
        )
        self.config.sounds.append(entry)
        self.storage.save(self.config)
        logger.info("Imported sound %s (%s)", entry.name, entry.id)
        return entry

    def load_samples(self, entry: SoundEntry) -> np.ndarray:
        return load_pcm(self.path_for(entry))

    def rename(self, sound_id: str, name: str) -> SoundEntry:
        entry = self._require(sound_id)
        entry.name = clean_name(name)
        self.storage.save(self.config)
        return entry

    def set_volume(self, sound_id: str, volume: float) -> SoundEntry:
        entry = self._require(sound_id)
        entry.volume = min(1.0, max(0.0, float(volume)))
        self.storage.save(self.config)
        return entry

    def set_hotkey(self, sound_id: str, hotkey: str | None) -> SoundEntry:
        entry = self._require(sound_id)
        entry.hotkey = hotkey
        self.storage.save(self.config)
        return entry

    def remove(self, sound_id: str) -> None:
        entry = self._require(sound_id)
        path = self.path_for(entry)
        self.config.sounds = [sound for sound in self.config.sounds if sound.id != sound_id]
        self.storage.save(self.config)
        try:
            path.unlink(missing_ok=True)
        except OSError:
            logger.exception("Could not delete %s", path)
        logger.info("Deleted sound %s", sound_id)

    def _require(self, sound_id: str) -> SoundEntry:
        entry = self.find(sound_id)
        if entry is None:
            raise SoundDeckError("That sound is no longer in the library.")
        return entry
