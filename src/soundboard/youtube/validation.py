"""Rules for a YouTube clip before any download or FFmpeg work."""

from __future__ import annotations

from soundboard.errors import YouTubeError

MAX_CLIP_SECONDS = 120.0


def validate_clip(start: float, end: float, duration: float | None = None) -> float:
    """Return the clip length in seconds, or raise :class:`YouTubeError`."""
    if start < 0 or end < 0:
        raise YouTubeError("Start and end cannot be negative.")
    if end <= start:
        raise YouTubeError("The end of the clip has to be after the start.")
    length = end - start
    if length > MAX_CLIP_SECONDS:
        raise YouTubeError(f"Clips can be at most {int(MAX_CLIP_SECONDS)} seconds.")
    if duration is not None and end > duration + 0.05:
        raise YouTubeError("The clip ends after the video.")
    return length
