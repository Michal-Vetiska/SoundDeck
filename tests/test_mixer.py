"""Mixer tests use NumPy arrays only. No audio device is opened."""

from __future__ import annotations

import numpy as np

from soundboard.audio.mixer import PlaybackVoice, mix_into, soft_clip_into


def _silence(frames: int) -> np.ndarray:
    return np.zeros((frames, 2), dtype=np.float32)


def _mix(mic: np.ndarray, voices: list[PlaybackVoice], mic_volume: float = 1.0, master: float = 1.0) -> np.ndarray:
    frames = mic.shape[0]
    out = np.zeros((frames, 2), dtype=np.float32)
    scratch = np.zeros_like(out)
    cube = np.zeros_like(out)
    mix_into(mic, voices, mic_volume, master, out, scratch, cube)
    return out


def test_quiet_signal_stays_near_identity() -> None:
    block = np.full((8, 2), 0.1, dtype=np.float32)
    cube = np.zeros_like(block)
    soft_clip_into(block, cube)
    assert block[0, 0] == np.float32(np.float32(0.1) - (np.float32(0.1) ** 3) / np.float32(3))


def test_clipping_limits_a_hot_sum() -> None:
    frames = 32
    mic = np.ones((frames, 2), dtype=np.float32)
    voice = PlaybackVoice(
        sound_id="hit",
        samples=np.ones((frames, 2), dtype=np.float32),
        fade_in=0,
    )
    mixed = _mix(mic, [voice])
    expected = np.float32(1.0) - (np.float32(1.0) ** 3) / np.float32(3.0)
    assert np.allclose(mixed, expected)
    assert np.max(np.abs(mixed)) <= 1.0


def test_volume_scales_each_source() -> None:
    frames = 16
    mic = np.full((frames, 2), 0.2, dtype=np.float32)
    samples = np.full((frames, 2), 0.4, dtype=np.float32)
    voice = PlaybackVoice(sound_id="hit", samples=samples, volume=0.5, fade_in=0)
    mixed = _mix(mic, [voice], mic_volume=0.5, master=1.0)
    # 0.2 * 0.5 + 0.4 * 0.5 = 0.3, then the cubic trim.
    raw = np.float32(0.3)
    expected = raw - (raw ** 3) / np.float32(3.0)
    assert np.allclose(mixed, expected, atol=1e-6)


def test_playback_position_advances_and_stops_at_the_end() -> None:
    samples = np.ones((100, 2), dtype=np.float32)
    voice = PlaybackVoice(sound_id="hit", samples=samples, fade_in=0)
    _mix(_silence(40), [voice])
    assert voice.position == 40
    assert voice.active
    _mix(_silence(80), [voice])
    assert voice.position == 100
    assert not voice.active
    _mix(_silence(10), [voice])
    assert voice.position == 100


def test_source_samples_are_not_mutated() -> None:
    samples = np.full((8, 2), 0.25, dtype=np.float32)
    original = samples.copy()
    voice = PlaybackVoice(sound_id="hit", samples=samples, fade_in=0)
    _mix(_silence(8), [voice])
    assert np.array_equal(samples, original)
