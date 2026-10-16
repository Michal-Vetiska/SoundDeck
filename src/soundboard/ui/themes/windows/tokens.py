"""Fluent / Mica inspired tokens for a future Windows build.

These are not a macOS glass skin. Controls stay the same; the surfaces,
type, and corner radius follow Windows 11.
"""

from __future__ import annotations

from soundboard.ui.themes.base import ThemeTokens

WINDOWS_TOKENS = ThemeTokens(
    background="#F3F3F3",
    surface="rgba(255, 255, 255, 0.72)",
    surface_secondary="rgba(255, 255, 255, 0.50)",
    surface_hover="#F9F9F9",
    border="rgba(0, 0, 0, 0.08)",
    text_primary="#1A1A1A",
    text_secondary="#5C5C5C",
    accent="#0067C0",
    accent_soft="rgba(0, 103, 192, 0.12)",
    danger="#C42B1C",
    success="#0F7B0F",
    dialog_background="#FBFBFB",
    radius_small=4,
    radius_medium=8,
    radius_large=8,
    spacing_small=8,
    spacing_medium=16,
    spacing_large=24,
    shadow_small="0 1px 2px rgba(0, 0, 0, 0.08)",
    shadow_large="0 8px 24px rgba(0, 0, 0, 0.14)",
    animation_fast=100,
    animation_normal=180,
    font_family="Segoe UI Variable, Segoe UI",
    font_size=13,
    window_translucent=False,
)
