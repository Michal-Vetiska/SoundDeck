"""Platform services that the rest of the app can call without OS checks.

Core code asks the adapter for a data directory, a virtual-device hint, or a
window effect. It does not ask which operating system is running.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path

logger = logging.getLogger(__name__)


class PlatformAdapter(ABC):
    """OS-specific services with a shared interface."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Short id used to pick a theme: ``macos``, ``windows``, or ``generic``."""

    @abstractmethod
    def app_support_dir(self) -> Path:
        """Directory for config, sounds, and logs. Not the source tree."""

    @abstractmethod
    def virtual_output_hints(self) -> tuple[str, ...]:
        """Substrings that identify the virtual output device, most specific first."""

    def virtual_device_label(self) -> str:
        """Human name of the expected virtual device."""
        hints = self.virtual_output_hints()
        return hints[0] if hints else "a virtual audio device"

    @abstractmethod
    def install_instructions(self) -> str:
        """Shown when the virtual device is missing. The app keeps running."""

    @abstractmethod
    def apply_window_effects(self, window: object) -> bool:
        """Try native blur or vibrancy. Return False when the fallback should be used."""

    @abstractmethod
    def accessibility_granted(self) -> bool | None:
        """Whether global hotkeys are allowed.

        ``None`` means the platform has no such permission.
        """

    @abstractmethod
    def open_privacy_settings(self, kind: str) -> None:
        """Open the OS page for ``microphone`` or ``accessibility``."""


class GenericPlatform(PlatformAdapter):
    """Fallback for systems that are not macOS or Windows."""

    @property
    def name(self) -> str:
        return "generic"

    def app_support_dir(self) -> Path:
        return Path.home() / ".local" / "share" / "SoundDeck"

    def virtual_output_hints(self) -> tuple[str, ...]:
        return ()

    def install_instructions(self) -> str:
        return (
            "Choose a virtual audio output provided by your system. "
            "SoundDeck does not install its own audio driver."
        )

    def apply_window_effects(self, window: object) -> bool:
        return False

    def accessibility_granted(self) -> bool | None:
        return None

    def open_privacy_settings(self, kind: str) -> None:
        logger.info("No privacy settings page for kind=%s on this platform", kind)
