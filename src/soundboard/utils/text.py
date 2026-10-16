"""Text cleanup for names that end up in the config file."""

from __future__ import annotations

from soundboard.errors import SoundDeckError

MAX_NAME_LENGTH = 80


def clean_name(name: str) -> str:
    """Collapse whitespace and reject an empty name."""
    cleaned = " ".join(name.split())
    if len(cleaned) > MAX_NAME_LENGTH:
        cleaned = cleaned[:MAX_NAME_LENGTH].rstrip()
    if not cleaned:
        raise SoundDeckError("Sound name cannot be empty.")
    return cleaned
