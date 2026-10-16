"""Realtime mixer.

The callback calls :func:`mix_into` with buffers it already owns. The function
adds the microphone and every active sound, then soft-clips the sum.

Soft clip
---------
Quiet samples stay nearly unchanged because the curve is ``y = x - x³/3``,
whose slope at zero is 1. Samples outside ±1 are hard-limited first, so the
cubic stage never has to handle a huge value. The loudest result is ±2/3,
which leaves headroom instead of wrapping into digital distortion.

One voice per sound id is the engine's job. This module only advances the
voices it is given.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from soundboard.audio.formats import DTYPE, FADE_FRAMES


@dataclass
class PlaybackVoice:
    """One playing sound. The PCM array is shared and never copied here."""

    sound_id: str
    samples: np.ndarray
    position: int = 0
    volume: float = 1.0
    active: bool = True
    fade_in: int = FADE_FRAMES
    fading_out: bool = False
    fade_out_left: int = 0


def soft_clip_into(block: np.ndarray, cube: np.ndarray) -> None:
    """Soft-clip ``block`` in place. ``cube`` is scratch of the same shape."""
    np.clip(block, -1.0, 1.0, out=block)
    np.multiply(block, block, out=cube)
    np.multiply(cube, block, out=cube)
    cube *= np.float32(1.0 / 3.0)
    block -= cube


def mix_into(
    mic: np.ndarray,
    voices: list[PlaybackVoice],
    mic_volume: float,
    master_volume: float,
    out: np.ndarray,
    scratch: np.ndarray,
    cube: np.ndarray,
) -> None:
    """Mix ``mic`` and ``voices`` into ``out``.

    ``mic``, ``out``, ``scratch``, and ``cube`` are float32 arrays shaped
    ``(frames, 2)``. Active voices move their playback position forward.
    """
    frames = mic.shape[0]
    np.multiply(mic, np.float32(mic_volume), out=out)
    for voice in voices:
        if not voice.active:
            continue
        remaining = int(voice.samples.shape[0] - voice.position)
        count = remaining if remaining < frames else frames
        if count <= 0:
            voice.active = False
            continue
        chunk = voice.samples[voice.position : voice.position + count]
        np.multiply(chunk, np.float32(voice.volume), out=scratch[:count])
        heard = _apply_fade(scratch[:count], voice, count)
        out[:heard] += scratch[:heard]
        voice.position += heard
        if voice.position >= voice.samples.shape[0]:
            voice.active = False
    out *= np.float32(master_volume)
    soft_clip_into(out, cube[:frames])


def _apply_fade(scratch_view: np.ndarray, voice: PlaybackVoice, count: int) -> int:
    """Shape the start or the stop of a voice. Returns frames that stay audible."""
    if voice.fade_in > 0:
        fading = voice.fade_in if voice.fade_in < count else count
        base = FADE_FRAMES - voice.fade_in
        for index in range(fading):
            gain = (base + index + 1) / FADE_FRAMES
            scratch_view[index, 0] *= gain
            scratch_view[index, 1] *= gain
        voice.fade_in -= fading

    if not voice.fading_out:
        return count

    fading = voice.fade_out_left if voice.fade_out_left < count else count
    start_left = voice.fade_out_left
    for index in range(fading):
        gain = (start_left - index - 1) / FADE_FRAMES
        if gain < 0:
            gain = 0.0
        scratch_view[index, 0] *= gain
        scratch_view[index, 1] *= gain
    if fading < count:
        scratch_view[fading:count] = 0
    voice.fade_out_left -= fading
    if voice.fade_out_left <= 0:
        voice.active = False
    return fading


def voice_ratio(voice: PlaybackVoice) -> float:
    """Playback progress from 0 to 1."""
    total = int(voice.samples.shape[0])
    if total <= 0:
        return 0.0
    if voice.position >= total:
        return 1.0
    if voice.position <= 0:
        return 0.0
    return voice.position / total


def ensure_stereo_f32(samples: np.ndarray) -> np.ndarray:
    """Return a contiguous float32 array shaped ``(frames, 2)``."""
    array = np.asarray(samples)
    if array.ndim != 2 or array.shape[1] != 2:
        raise ValueError("Expected stereo samples shaped (frames, 2).")
    if array.dtype != DTYPE:
        array = array.astype(DTYPE)
    if not array.flags["C_CONTIGUOUS"]:
        array = np.ascontiguousarray(array)
    return array
