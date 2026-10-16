"""Glass-styled building blocks.

The look comes from the active stylesheet. These classes exist so screens
share one set of surfaces, buttons, and dialogs.
"""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt
from PySide6.QtWidgets import QDialog, QFrame, QPushButton, QSlider, QVBoxLayout, QWidget


class GlassPanel(QFrame):
    """Translucent surface used for grouped content."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("GlassPanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)


class GlassButton(QPushButton):
    """Button that picks up PrimaryButton, DangerButton, or QuietButton styling."""

    def __init__(self, text: str, role: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        if role:
            self.setObjectName(role)
        self.setCursor(Qt.CursorShape.PointingHandCursor)


class GlassSlider(QSlider):
    """Horizontal slider styled by the theme."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.setObjectName("GlassSlider")


class GlassToolbar(QFrame):
    """Top bar. It is a glass surface, not a second set of window buttons."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("HeaderBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)


class GlassDialog(QDialog):
    """Modal dialog with a short fade-in. Audio never waits on this animation."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setModal(True)
        self._fade: QPropertyAnimation | None = None
        self._content = QVBoxLayout(self)
        self._content.setContentsMargins(24, 24, 24, 24)
        self._content.setSpacing(16)

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        self.setWindowOpacity(0.0)
        fade = QPropertyAnimation(self, b"windowOpacity", self)
        fade.setDuration(180)
        fade.setStartValue(0.0)
        fade.setEndValue(1.0)
        fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        fade.start()
        self._fade = fade
