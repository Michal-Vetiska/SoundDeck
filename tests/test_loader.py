"""File checks that run before FFmpeg is started."""

from __future__ import annotations

import pytest

from soundboard.audio.loader import validate_audio_file
from soundboard.errors import SoundLoadError


@pytest.mark.parametrize("name", ["hit.mp3", "hit.wav", "hit.m4a", "hit.FLAC", "hit.ogg"])
def test_supported_extensions_pass(tmp_path, name: str) -> None:
    path = tmp_path / name
    path.write_bytes(b"not-really-audio-but-non-empty")
    validate_audio_file(path)


def test_rejects_unsupported_empty_and_missing(tmp_path) -> None:
    text = tmp_path / "notes.txt"
    text.write_text("hello", encoding="utf-8")
    with pytest.raises(SoundLoadError):
        validate_audio_file(text)

    empty = tmp_path / "empty.wav"
    empty.write_bytes(b"")
    with pytest.raises(SoundLoadError):
        validate_audio_file(empty)

    with pytest.raises(SoundLoadError):
        validate_audio_file(tmp_path / "missing.mp3")
