"""Stylesheets substitute every token placeholder."""

from __future__ import annotations

from soundboard.ui.themes.macos.theme import build_macos_theme
from soundboard.ui.themes.windows.theme import build_windows_theme


def test_stylesheets_have_no_leftover_placeholders() -> None:
    for theme in (build_macos_theme(), build_windows_theme()):
        css = theme.stylesheet()
        assert "{{" not in css
        assert theme.tokens.accent in css
