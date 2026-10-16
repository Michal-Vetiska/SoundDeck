"""macOS platform services.

PyObjC is imported only inside methods. The rest of SoundDeck must not import
AppKit. If native vibrancy fails, the caller keeps the Qt fallback.
"""

from __future__ import annotations

import ctypes
import logging
import subprocess
from pathlib import Path

from soundboard.platform.base import PlatformAdapter

logger = logging.getLogger(__name__)

# NSWindow style bits. Integer values avoid importing every AppKit enum name.
_FULL_SIZE_CONTENT_VIEW = 1 << 15
_TITLE_HIDDEN = 1


class MacOSPlatform(PlatformAdapter):
    """Application Support, BlackHole hints, Accessibility, and window vibrancy."""

    @property
    def name(self) -> str:
        return "macos"

    def app_support_dir(self) -> Path:
        return Path.home() / "Library" / "Application Support" / "SoundDeck"

    def virtual_output_hints(self) -> tuple[str, ...]:
        return ("BlackHole 2ch", "BlackHole")

    def install_instructions(self) -> str:
        return (
            "BlackHole 2ch was not found.\n\n"
            "BlackHole is required to route the mixed audio into applications such as Discord.\n\n"
            "Install it, then restart SoundDeck:\n"
            "    brew install blackhole-2ch\n\n"
            "In Discord choose Settings → Voice & Video → Input Device → BlackHole 2ch."
        )

    def accessibility_granted(self) -> bool | None:
        """Ask the system Accessibility API. Failure is reported as unknown."""
        try:
            library = ctypes.cdll.LoadLibrary(
                "/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices"
            )
            library.AXIsProcessTrusted.restype = ctypes.c_bool
            return bool(library.AXIsProcessTrusted())
        except (OSError, AttributeError):
            logger.exception("Could not query Accessibility permission")
            return None

    def open_privacy_settings(self, kind: str) -> None:
        panes = {
            "accessibility": "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility",
            "microphone": "x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone",
        }
        target = panes.get(kind)
        if target is None:
            logger.info("Unknown privacy pane %s", kind)
            return
        try:
            subprocess.run(["open", target], check=False)
        except OSError:
            logger.exception("Could not open System Settings for %s", kind)

    def apply_window_effects(self, window: object) -> bool:
        """Transparent title bar, native traffic lights, and a vibrancy view.

        Returns False when PyObjC is missing or AppKit rejects the window, so
        the Qt theme can paint a translucent surface instead.
        """
        try:
            import objc
            from AppKit import (
                NSColor,
                NSViewHeightSizable,
                NSViewWidthSizable,
                NSVisualEffectBlendingModeBehindWindow,
                NSVisualEffectMaterialUnderWindowBackground,
                NSVisualEffectView,
            )
        except Exception:
            logger.info("PyObjC is not available; using the Qt glass fallback")
            return False

        try:
            win_id = int(window.winId())  # type: ignore[attr-defined]
            ns_view = objc.objc_object(c_void_p=win_id)
            ns_window = ns_view.window()
            if ns_window is None:
                logger.info("Native window was not ready for vibrancy")
                return False

            style = int(ns_window.styleMask())
            ns_window.setStyleMask_(style | _FULL_SIZE_CONTENT_VIEW)
            ns_window.setTitlebarAppearsTransparent_(True)
            ns_window.setTitleVisibility_(_TITLE_HIDDEN)
            ns_window.setOpaque_(False)
            ns_window.setBackgroundColor_(NSColor.clearColor())

            content = ns_window.contentView()
            if content is None:
                return False
            bounds = content.bounds()
            effect = NSVisualEffectView.alloc().initWithFrame_(bounds)
            effect.setMaterial_(NSVisualEffectMaterialUnderWindowBackground)
            effect.setBlendingMode_(NSVisualEffectBlendingModeBehindWindow)
            effect.setAutoresizingMask_(NSViewWidthSizable | NSViewHeightSizable)
            # NSWindowBelow keeps the blur behind Qt's own widgets.
            content.addSubview_positioned_relativeTo_(effect, -1, None)
            logger.info("Applied macOS vibrancy to the main window")
            return True
        except Exception:
            logger.exception("Native macOS window effects failed; using Qt fallback")
            return False
