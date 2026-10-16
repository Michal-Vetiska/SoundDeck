"""Errors that are safe to show to a person using the app."""


class SoundDeckError(Exception):
    """Base class for expected failures with a short, user-facing message."""


class ConfigError(SoundDeckError):
    """The saved configuration could not be read or written."""


class AudioEngineError(SoundDeckError):
    """The audio engine could not start or keep running."""


class SoundLoadError(SoundDeckError):
    """A sound file could not be validated or decoded."""


class HotkeyError(SoundDeckError):
    """A hotkey string is invalid or conflicts with another sound."""


class YouTubeError(SoundDeckError):
    """YouTube metadata, download, or clipping failed."""


def public_message(exc: BaseException) -> str:
    """Return a short message suitable for a dialog.

    Unexpected exceptions stay in the log. Only ``SoundDeckError`` text is
    shown, and even that is limited to the first line.
    """
    if isinstance(exc, SoundDeckError):
        text = str(exc).strip()
    else:
        text = "Something went wrong. Details are in the SoundDeck log."
    first = text.splitlines()[0] if text else "Something went wrong."
    if len(first) > 280:
        return first[:279] + "…"
    return first
