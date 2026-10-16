"""Cut a temporary download to the internal PCM format."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from soundboard.audio.loader import ffmpeg_to_pcm, save_pcm
from soundboard.youtube.validation import validate_clip


def cut_to_pcm(
    source: Path,
    destination: Path,
    start: float,
    end: float,
    duration: float | None = None,
) -> np.ndarray:
    """Validate the range, decode that slice, and write ``destination``."""
    validate_clip(start, end, duration)
    samples = ffmpeg_to_pcm(source, start=start, end=end)
    save_pcm(destination, samples)
    return samples
