"""Composition root and process entry point."""

from __future__ import annotations

import logging
import sys

from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from soundboard import __version__
from soundboard.audio.engine import AudioEngine
from soundboard.config.models import AppConfig
from soundboard.config.storage import JsonConfigStorage
from soundboard.errors import ConfigError
from soundboard.hotkeys.manager import HotkeyManager
from soundboard.logging_config import configure_logging
from soundboard.platform.detect import detect_platform
from soundboard.services.controller import SoundboardController
from soundboard.services.library import SoundLibrary
from soundboard.ui.main_window import MainWindow
from soundboard.ui.themes.base import theme_for_platform

logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    """Start the Qt event loop and wire the services together."""
    del argv
    adapter = detect_platform()
    support = adapter.app_support_dir()
    log_path = configure_logging(support / "logs")
    logger.info("SoundDeck %s on %s, log at %s", __version__, adapter.name, log_path)

    app = QApplication(sys.argv)
    app.setApplicationName("SoundDeck")
    app.setOrganizationName("SoundDeck")
    app.setStyle("Fusion")

    theme = theme_for_platform(adapter.name)
    app.setStyleSheet(theme.stylesheet())
    font = QFont()
    font.setFamilies([part.strip() for part in theme.tokens.font_family.split(",") if part.strip()])
    font.setPointSize(theme.tokens.font_size)
    app.setFont(font)

    storage = JsonConfigStorage(support / "config.json")
    try:
        config = storage.load()
    except ConfigError as exc:
        logger.error("Config reset: %s", exc)
        config = AppConfig()

    library = SoundLibrary(support, storage, config)
    engine = AudioEngine()
    hotkeys = HotkeyManager(adapter.accessibility_granted)
    controller = SoundboardController(config, library, engine, hotkeys, adapter)
    window = MainWindow(controller, theme)
    controller.bootstrap()
    window.show()
    if theme.tokens.window_translucent:
        adapter.apply_window_effects(window)
    if not config.onboarding_complete:
        QTimer.singleShot(0, window.open_onboarding)
    app.aboutToQuit.connect(controller.shutdown)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
