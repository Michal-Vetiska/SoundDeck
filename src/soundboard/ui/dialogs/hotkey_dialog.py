"""Capture one global hotkey from a key press."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel

from soundboard.errors import HotkeyError
from soundboard.hotkeys.parser import format_hotkey, parse_hotkey
from soundboard.ui.components.glass import GlassButton, GlassDialog


_QT_MODIFIERS = {
    Qt.Key.Key_Control: "ctrl",
    Qt.Key.Key_Shift: "shift",
    Qt.Key.Key_Alt: "alt",
    Qt.Key.Key_Meta: "cmd",
}


class HotkeyDialog(GlassDialog):
    """Ask for the next key combination and return its canonical text."""

    def __init__(self, current: str | None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Hotkey")
        self.setMinimumWidth(420)
        self.combo: str | None = current
        self.cleared = False

        title = QLabel("Press a key combination")
        title.setObjectName("SectionTitle")
        hint = QLabel("Examples: F1, Cmd+Shift+V. Escape cancels.")
        hint.setObjectName("MutedLabel")
        self._value = QLabel(current or "None")
        self._value.setObjectName("SectionTitle")
        self._error = QLabel("")
        self._error.setObjectName("StatusError")
        self._error.hide()

        self._content.addWidget(title)
        self._content.addWidget(hint)
        self._content.addWidget(self._value)
        self._content.addWidget(self._error)

        buttons = QHBoxLayout()
        clear = GlassButton("Clear")
        clear.clicked.connect(self._clear)
        cancel = GlassButton("Cancel")
        cancel.clicked.connect(self.reject)
        save = GlassButton("Save", "PrimaryButton")
        save.clicked.connect(self._save)
        buttons.addWidget(clear)
        buttons.addStretch(1)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        self._content.addLayout(buttons)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        self.setFocus(Qt.FocusReason.ActiveWindowFocusReason)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
            return
        if event.key() in _QT_MODIFIERS or event.key() == Qt.Key.Key_unknown:
            return
        text = _event_to_combo(event)
        if text is None:
            self._error.setText("That key is not supported.")
            self._error.show()
            return
        try:
            self.combo = format_hotkey(parse_hotkey(text))
        except HotkeyError as exc:
            self._error.setText(str(exc))
            self._error.show()
            return
        self.cleared = False
        self._error.hide()
        self._value.setText(self.combo)

    def _clear(self) -> None:
        self.combo = None
        self.cleared = True
        self._value.setText("None")
        self._error.hide()

    def _save(self) -> None:
        self.accept()


def _event_to_combo(event: QKeyEvent) -> str | None:
    parts: list[str] = []
    modifiers = event.modifiers()
    if modifiers & Qt.KeyboardModifier.ControlModifier:
        parts.append("ctrl")
    if modifiers & Qt.KeyboardModifier.AltModifier:
        parts.append("alt")
    if modifiers & Qt.KeyboardModifier.ShiftModifier:
        parts.append("shift")
    if modifiers & Qt.KeyboardModifier.MetaModifier:
        parts.append("cmd")
    key = _key_name(event)
    if key is None:
        return None
    parts.append(key)
    return "+".join(parts)


def _key_name(event: QKeyEvent) -> str | None:
    key = event.key()
    if Qt.Key.Key_F1 <= key <= Qt.Key.Key_F24:
        return f"f{key - Qt.Key.Key_F1 + 1}"
    if Qt.Key.Key_A <= key <= Qt.Key.Key_Z or Qt.Key.Key_0 <= key <= Qt.Key.Key_9:
        return event.text().lower() or None
    specials = {
        Qt.Key.Key_Space: "space",
        Qt.Key.Key_Return: "enter",
        Qt.Key.Key_Enter: "enter",
        Qt.Key.Key_Left: "left",
        Qt.Key.Key_Right: "right",
        Qt.Key.Key_Up: "up",
        Qt.Key.Key_Down: "down",
        Qt.Key.Key_Minus: "minus",
        Qt.Key.Key_Equal: "equals",
    }
    return specials.get(key)
