"""Build the macOS theme from tokens and styles.qss."""

from __future__ import annotations

from importlib.resources import files

from soundboard.ui.themes.base import Theme
from soundboard.ui.themes.macos.tokens import MACOS_TOKENS


def build_macos_theme() -> Theme:
    template = files("soundboard.ui.themes.macos").joinpath("styles.qss").read_text(encoding="utf-8")
    return Theme("macos", MACOS_TOKENS, template)
