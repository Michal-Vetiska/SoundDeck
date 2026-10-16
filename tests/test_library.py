"""Library files stay inside the application support directory."""

from __future__ import annotations

import numpy as np

from soundboard.config.models import AppConfig
from soundboard.config.storage import JsonConfigStorage
from soundboard.services.library import SoundLibrary


def test_add_and_remove_sound_uses_a_relative_path(tmp_path) -> None:
    storage = JsonConfigStorage(tmp_path / "config.json")
    config = AppConfig()
    library = SoundLibrary(tmp_path, storage, config)
    samples = np.zeros((480, 2), dtype=np.float32)
    entry = library.add_samples("Vine Boom", samples)
    assert entry.file.startswith("sounds/")
    assert not entry.file.startswith("/")
    path = library.path_for(entry)
    assert path.is_file()
    assert path.is_relative_to(tmp_path)
    loaded = storage.load()
    assert loaded.sounds[0].name == "Vine Boom"
    library.remove(entry.id)
    assert library.find(entry.id) is None
    assert not path.exists()
