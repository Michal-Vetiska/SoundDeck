"""Config round-trip and defensive loading."""

from __future__ import annotations

import pytest

from soundboard.config.models import AppConfig, AudioSettings, SoundEntry, config_from_dict
from soundboard.config.storage import JsonConfigStorage
from soundboard.errors import ConfigError


def test_config_round_trip(tmp_path) -> None:
    storage = JsonConfigStorage(tmp_path / "config.json")
    original = AppConfig(
        audio=AudioSettings(
            input_device="MacBook Microphone",
            output_device="BlackHole 2ch",
            mic_volume=0.7,
            master_volume=0.9,
        ),
        sounds=[
            SoundEntry(
                id="vine",
                name="Vine Boom",
                file="sounds/vine.f32",
                hotkey="F1",
                volume=0.8,
                duration_seconds=1.25,
            )
        ],
        onboarding_complete=True,
    )
    storage.save(original)
    loaded = storage.load()
    assert loaded.audio.input_device == "MacBook Microphone"
    assert loaded.audio.output_device == "BlackHole 2ch"
    assert loaded.audio.mic_volume == pytest.approx(0.7)
    assert loaded.sounds[0].name == "Vine Boom"
    assert loaded.sounds[0].file == "sounds/vine.f32"
    assert loaded.sounds[0].hotkey == "F1"
    assert loaded.onboarding_complete is True


def test_config_skips_invalid_sounds_and_clamps_volume() -> None:
    loaded = config_from_dict(
        {
            "audio": {"mic_volume": 4, "input_device": "Mic"},
            "sounds": [
                {"id": "ok", "name": "Ok", "file": "sounds/ok.f32", "volume": -2},
                {"name": "missing id"},
                {"id": "bad", "name": "Bad", "file": "../secrets.f32"},
            ],
        }
    )
    assert loaded.audio.mic_volume == 1.0
    assert len(loaded.sounds) == 1
    assert loaded.sounds[0].volume == 0.0


def test_corrupt_config_raises_and_is_backed_up(tmp_path) -> None:
    path = tmp_path / "config.json"
    path.write_text("{not json", encoding="utf-8")
    storage = JsonConfigStorage(path)
    with pytest.raises(ConfigError):
        storage.load()
    assert (tmp_path / "config.json.bak").read_text(encoding="utf-8") == "{not json"
