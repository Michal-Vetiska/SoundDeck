"""Decode audio files to the internal PCM format.

FFmpeg runs here, during import, never inside the audio callback. The result
is raw little-endian float32, 48 kHz, stereo.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

import numpy as np

from soundboard.audio.formats import CHANNELS, DTYPE, SAMPLE_RATE
from soundboard.audio.mixer import ensure_stereo_f32
from soundboard.errors import SoundLoadError

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = frozenset({".mp3", ".wav", ".m4a", ".flac", ".ogg"})


def validate_audio_file(path: Path) -> None:
    """Reject missing, empty, or unsupported files before FFmpeg starts."""
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise SoundLoadError(f"Unsupported file type. SoundDeck accepts {supported}.")
    if not path.is_file():
        raise SoundLoadError("That file could not be found.")
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise SoundLoadError("That file could not be read.") from exc
    if size <= 0:
        raise SoundLoadError("That file is empty.")


def resolve_ffmpeg(explicit: str | None = None) -> str:
    """Return a usable ffmpeg executable path."""
    if explicit:
        candidate = Path(explicit)
        if candidate.is_file() or shutil.which(explicit):
            return explicit
        raise SoundLoadError(f"FFmpeg was not found at {explicit}.")
    found = shutil.which("ffmpeg")
    if found is None:
        raise SoundLoadError(
            "FFmpeg was not found. Install it with: brew install ffmpeg"
        )
    return found


def ffmpeg_to_pcm(
    source: Path,
    *,
    start: float | None = None,
    end: float | None = None,
    ffmpeg: str | None = None,
) -> np.ndarray:
    """Decode ``source`` to a stereo float32 array.

    ``start`` and ``end`` are seconds. The cut uses ``-ss`` plus ``-t`` so the
    duration is ``end - start`` and does not depend on how FFmpeg interprets
    ``-to`` together with ``-ss``.
    """
    executable = resolve_ffmpeg(ffmpeg)
    command = [
        executable,
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(source),
    ]
    if start is not None:
        command.extend(["-ss", f"{start:.3f}"])
    if end is not None:
        duration = end - (start or 0.0)
        command.extend(["-t", f"{duration:.3f}"])
    command.extend(
        [
            "-ac",
            str(CHANNELS),
            "-ar",
            str(SAMPLE_RATE),
            "-f",
            "f32le",
            "pipe:1",
        ]
    )
    logger.info("Decoding %s", source.name)
    try:
        completed = subprocess.run(command, capture_output=True, check=False)
    except OSError as exc:
        logger.exception("Failed to start FFmpeg")
        raise SoundLoadError("FFmpeg could not be started.") from exc
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip().splitlines()
        reason = detail[-1] if detail else "FFmpeg failed."
        if len(reason) > 180:
            reason = reason[:179] + "…"
        logger.error("FFmpeg failed: %s", reason)
        raise SoundLoadError(f"Could not decode this audio. {reason}")
    audio = np.frombuffer(completed.stdout, dtype=DTYPE)
    if audio.size == 0 or audio.size % CHANNELS != 0:
        raise SoundLoadError("The decoder returned no audio.")
    return ensure_stereo_f32(audio.reshape(-1, CHANNELS))


def save_pcm(path: Path, samples: np.ndarray) -> None:
    """Write stereo float32 PCM without a header."""
    path.parent.mkdir(parents=True, exist_ok=True)
    array = ensure_stereo_f32(samples)
    path.write_bytes(array.tobytes())
    logger.info("Wrote PCM %s (%s frames)", path.name, array.shape[0])


def load_pcm(path: Path) -> np.ndarray:
    """Read a file written by :func:`save_pcm`."""
    if not path.is_file():
        raise SoundLoadError(f"Missing sound data: {path.name}")
    data = np.fromfile(path, dtype=DTYPE)
    if data.size == 0 or data.size % CHANNELS != 0:
        raise SoundLoadError(f"Sound data is damaged: {path.name}")
    return ensure_stereo_f32(data.reshape(-1, CHANNELS))


def duration_seconds(samples: np.ndarray) -> float:
    """Length of a stereo buffer at the internal sample rate."""
    return float(samples.shape[0]) / SAMPLE_RATE
