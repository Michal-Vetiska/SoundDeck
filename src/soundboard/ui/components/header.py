"""Main window header: title, engine status, devices, and primary actions."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from soundboard.ui.components.glass import GlassButton, GlassToolbar


class HeaderBar(GlassToolbar):
    """The in-window toolbar. Traffic-light buttons stay on the native title bar."""

    add_clicked = Signal()
    settings_clicked = Signal()
    start_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 14, 18, 14)
        root.setSpacing(6)

        title_row = QHBoxLayout()
        self._title = QLabel("SoundDeck")
        self._title.setObjectName("SectionTitle")
        title_row.addWidget(self._title)
        title_row.addStretch(1)
        self._dot = QLabel("")
        self._dot.setObjectName("StatusDotStopped")
        title_row.addWidget(self._dot)
        self._status = QLabel("Engine stopped")
        self._status.setObjectName("StatusStopped")
        title_row.addWidget(self._status)
        root.addLayout(title_row)

        self._input = QLabel("Input: not selected")
        self._input.setObjectName("DeviceLabel")
        self._output = QLabel("Output: not selected")
        self._output.setObjectName("DeviceLabel")
        root.addWidget(self._input)
        root.addWidget(self._output)

        actions = QHBoxLayout()
        actions.addStretch(1)
        self._start = GlassButton("Start engine", "QuietButton")
        self._start.clicked.connect(self.start_clicked.emit)
        actions.addWidget(self._start)
        self._add = GlassButton("+ Add Sound", "PrimaryButton")
        self._add.clicked.connect(self.add_clicked.emit)
        actions.addWidget(self._add)
        self._settings = GlassButton("Settings")
        self._settings.clicked.connect(self.settings_clicked.emit)
        actions.addWidget(self._settings)
        root.addLayout(actions)

    def set_status(self, state: str, text: str) -> None:
        styles = {
            "running": ("StatusDotRunning", "StatusRunning"),
            "stopped": ("StatusDotStopped", "StatusStopped"),
            "error": ("StatusDotError", "StatusError"),
        }
        dot_name, text_name = styles.get(state, styles["stopped"])
        self._dot.setObjectName(dot_name)
        self._status.setObjectName(text_name)
        self._status.setText(text)
        for widget in (self._dot, self._status):
            widget.style().unpolish(widget)
            widget.style().polish(widget)
        self._start.setVisible(state != "running")
        self._start.setText("Start engine")

    def set_devices(self, input_name: str | None, output_name: str | None) -> None:
        self._input.setText(f"Input: {input_name or 'not selected'}")
        self._output.setText(f"Output: {output_name or 'not selected'}")

    def set_busy(self, busy: bool) -> None:
        self._add.setEnabled(not busy)
        if busy:
            self._status.setText("Importing…")
