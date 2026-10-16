"""Build the Windows theme from tokens and styles.qss."""

from __future__ import annotations

from importlib.resources import files

from soundboard.ui.themes.base import Theme
from soundboard.ui.themes.windows.tokens import WINDOWS_TOKENS


def build_windows_theme() -> Theme:
    template = files("soundboard.ui.themes.windows").joinpath("styles.qss").read_text(encoding="utf-8")
    return Theme("windows", WINDOWS_TOKENS, template)
