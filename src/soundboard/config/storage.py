"""JSON configuration storage.

``ConfigStorage`` is the seam a future SQLite backend can implement. Callers
depend on the protocol, not on the file format.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Protocol

from soundboard.config.models import AppConfig, config_from_dict, config_to_dict
from soundboard.errors import ConfigError

logger = logging.getLogger(__name__)


class ConfigStorage(Protocol):
    """Load and save the application configuration."""

    def load(self) -> AppConfig:
        """Return the saved config, or defaults when nothing is stored yet."""

    def save(self, config: AppConfig) -> None:
        """Persist ``config`` atomically."""


class JsonConfigStorage:
    """Store ``AppConfig`` as pretty-printed JSON.

    Writes go to a temporary file in the same directory and then replace the
    destination, so a crash mid-write does not leave a half file.
    """

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> AppConfig:
        if not self.path.exists():
            logger.info("No config at %s, using defaults", self.path)
            return AppConfig()
        try:
            text = self.path.read_text(encoding="utf-8")
            payload = json.loads(text)
        except (OSError, json.JSONDecodeError, UnicodeError) as exc:
            logger.exception("Could not read config %s", self.path)
            self._backup_corrupt()
            raise ConfigError("The settings file was unreadable. SoundDeck will start fresh.") from exc
        config = config_from_dict(payload)
        logger.info("Loaded config with %s sounds", len(config.sounds))
        return config

    def save(self, config: AppConfig) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = config_to_dict(config)
        text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
        temporary = self.path.with_suffix(".json.tmp")
        try:
            temporary.write_text(text, encoding="utf-8")
            temporary.replace(self.path)
        except OSError as exc:
            logger.exception("Could not save config %s", self.path)
            raise ConfigError("SoundDeck could not save settings.") from exc
        logger.info("Saved config to %s", self.path)

    def _backup_corrupt(self) -> None:
        backup = self.path.with_suffix(".json.bak")
        try:
            self.path.replace(backup)
            logger.error("Moved unreadable config to %s", backup)
        except OSError:
            logger.exception("Could not back up unreadable config")
