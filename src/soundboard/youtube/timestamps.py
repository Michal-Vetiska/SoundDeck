"""Timestamp helpers for the YouTube clip dialog.

Accepted forms:

* ``12.5``
* ``1:23``
* ``1:23.5``
* ``00:01:23.500``
"""

from __future__ import annotations

from soundboard.errors import YouTubeError


def parse_timestamp(text: str) -> float:
    """Parse a timestamp into seconds."""
    raw = text.strip()
    if not raw:
        raise YouTubeError("Enter a timestamp.")
    parts = raw.split(":")
    if len(parts) > 3:
        raise YouTubeError(f"Could not read the timestamp “{raw}”.")
    try:
        if len(parts) == 1:
            seconds = float(parts[0])
        elif len(parts) == 2:
            seconds = int(parts[0]) * 60 + float(parts[1])
        else:
            seconds = int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    except ValueError as exc:
        raise YouTubeError(f"Could not read the timestamp “{raw}”.") from exc
    if seconds < 0:
        raise YouTubeError("A timestamp cannot be negative.")
    return seconds


def format_timestamp(seconds: float) -> str:
    """Format seconds as ``HH:MM:SS.mmm``."""
    if seconds < 0:
        seconds = 0.0
    total_ms = int(round(seconds * 1000))
    millis = total_ms % 1000
    total_seconds = total_ms // 1000
    secs = total_seconds % 60
    minutes = (total_seconds // 60) % 60
    hours = total_seconds // 3600
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"
