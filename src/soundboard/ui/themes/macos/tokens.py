"""Liquid Glass inspired tokens for macOS.

Colors stay translucent so a native vibrancy view, when it is available,
can show through. The Qt stylesheet is the fallback when PyObjC cannot
attach that view.
"""

from __future__ import annotations

from soundboard.ui.themes.base import ThemeTokens

MACOS_TOKENS = ThemeTokens(
    background="rgba(246, 246, 248, 0.78)",
    surface="rgba(255, 255, 255, 0.62)",
    surface_secondary="rgba(255, 255, 255, 0.40)",
    surface_hover="rgba(255, 255, 255, 0.78)",
    border="rgba(0, 0, 0, 0.10)",
    text_primary="rgba(28, 28, 30, 0.94)",
    text_secondary="rgba(60, 60, 67, 0.62)",
    accent="#007AFF",
    accent_soft="rgba(0, 122, 255, 0.14)",
    danger="#FF3B30",
    success="#34C759",
    dialog_background="rgba(250, 250, 252, 0.96)",
    radius_small=8,
    radius_medium=12,
    radius_large=18,
    spacing_small=8,
    spacing_medium=16,
    spacing_large=24,
    shadow_small="0 1px 2px rgba(0, 0, 0, 0.06)",
    shadow_large="0 12px 40px rgba(0, 0, 0, 0.12)",
    animation_fast=120,
    animation_normal=220,
    font_family=".AppleSystemUIFont, SF Pro Text, Helvetica Neue",
    font_size=13,
    window_translucent=True,
)
