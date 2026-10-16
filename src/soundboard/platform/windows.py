"""Windows platform stub.

The audio core already talks to whatever devices PortAudio exposes, including
VB-CABLE once it is installed. Native Fluent and Mica effects are intentionally
not implemented yet: this module documents the seam and refuses to pretend the
effects exist.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from soundboard.platform.base import PlatformAdapter

logger = logging.getLogger(__name__)


class WindowsPlatform(PlatformAdapter):
    """App data path and VB-CABLE hints. Visual effects stay on the Qt theme."""

    @property
    def name(self) -> str:
        return "windows"

    def app_support_dir(self) -> Path:
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "SoundDeck"
        return Path.home() / "AppData" / "Roaming" / "SoundDeck"

    def virtual_output_hints(self) -> tuple[str, ...]:
        return ("CABLE Input", "VB-Audio", "VB-CABLE")

    def install_instructions(self) -> str:
        return (
            "VB-CABLE was not found.\n\n"
            "A future Windows build routes the mix into VB-CABLE so Discord can "
            "use it as a microphone. SoundDeck does not install that driver itself.\n\n"
            "Install VB-CABLE from vb-audio.com, then pick its input device as the "
            "SoundDeck output."
        )

    def apply_window_effects(self, window: object) -> bool:
        logger.info("Windows native Mica/Acrylic is not implemented yet")
        return False

    def accessibility_granted(self) -> bool | None:
        return None

    def open_privacy_settings(self, kind: str) -> None:
        logger.info("Windows privacy settings shortcut is not implemented (%s)", kind)
