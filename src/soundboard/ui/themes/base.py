"""Theme tokens and stylesheet rendering.

Widgets read colors and spacing from a theme instead of hard-coding them.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ThemeTokens:
    """Design tokens shared by every themed widget."""

    background: str
    surface: str
    surface_secondary: str
    surface_hover: str
    border: str
    text_primary: str
    text_secondary: str
    accent: str
    accent_soft: str
    danger: str
    success: str
    dialog_background: str
    radius_small: int
    radius_medium: int
    radius_large: int
    spacing_small: int
    spacing_medium: int
    spacing_large: int
    shadow_small: str
    shadow_large: str
    animation_fast: int
    animation_normal: int
    font_family: str
    font_size: int
    window_translucent: bool


class Theme:
    """A token set plus the QSS template for one platform."""

    def __init__(self, name: str, tokens: ThemeTokens, template: str) -> None:
        self.name = name
        self.tokens = tokens
        self._template = template

    def stylesheet(self) -> str:
        template = self._template
        values = {
            key: str(value).lower() if isinstance(value, bool) else str(value)
            for key, value in asdict(self.tokens).items()
        }

        def replace(match: re.Match[str]) -> str:
            key = match.group(1)
            if key not in values:
                raise KeyError(f"Stylesheet placeholder {key} has no token")
            return values[key]

        return re.sub(r"\{\{(\w+)\}\}", replace, template)


def theme_for_platform(platform_name: str) -> Theme:
    """Pick the visual theme. macOS is the default for this version."""
    if platform_name == "windows":
        from soundboard.ui.themes.windows.theme import build_windows_theme

        return build_windows_theme()
    from soundboard.ui.themes.macos.theme import build_macos_theme

    return build_macos_theme()
