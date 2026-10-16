"""The only place that branches on the operating system name."""

from __future__ import annotations

import platform

from soundboard.platform.base import GenericPlatform, PlatformAdapter


def detect_platform() -> PlatformAdapter:
    """Return the adapter for the current OS."""
    system = platform.system()
    if system == "Darwin":
        from soundboard.platform.macos import MacOSPlatform

        return MacOSPlatform()
    if system == "Windows":
        from soundboard.platform.windows import WindowsPlatform

        return WindowsPlatform()
    return GenericPlatform()
