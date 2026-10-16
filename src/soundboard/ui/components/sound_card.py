"""One sound on the board.

The card emits intents. It does not talk to the audio engine.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QPropertyAnimation, Signal
from PySide6.QtWidgets import (
    QAbstractButton,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QMenu,
    QProgressBar,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from soundboard.config.models import SoundEntry
from soundboard.ui.components.glass import GlassButton


class SoundCard(QFrame):
    """Playable card with volume, hotkey, rename, and delete."""

    play_requested = Signal(str)
    stop_requested = Signal(str)
    delete_requested = Signal(str)
    rename_requested = Signal(str, str)
    volume_changed = Signal(str, float)
    volume_committed = Signal(str, float)
    hotkey_edit_requested = Signal(str)

    def __init__(self, entry: SoundEntry, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.sound_id = entry.id
        self._playing = False
        self.setObjectName("SoundCard")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 12)
        layout.setSpacing(8)

        top = QHBoxLayout()
        self._name = QLabel(entry.name)
        self._name.setObjectName("SectionTitle")
        font = self._name.font()
        font.setPointSize(15)
        font.setBold(True)
        self._name.setFont(font)
        top.addWidget(self._name, 1)
        self._menu_button = GlassButton("···", "QuietButton")
        self._menu_button.setFixedWidth(36)
        self._menu_button.clicked.connect(self._open_menu)
        top.addWidget(self._menu_button)
        layout.addLayout(top)

        layout.addStretch(1)
        self._play = GlassButton("▶", "PlayButton")
        self._play.clicked.connect(self._toggle_playback)
        play_row = QHBoxLayout()
        play_row.addStretch(1)
        play_row.addWidget(self._play)
        play_row.addStretch(1)
        layout.addLayout(play_row)
        layout.addStretch(1)

        footer = QHBoxLayout()
        self._hotkey = GlassButton(entry.hotkey or "Hotkey", "QuietButton")
        self._hotkey.clicked.connect(lambda: self.hotkey_edit_requested.emit(self.sound_id))
        footer.addWidget(self._hotkey)
        footer.addStretch(1)
        self._volume_label = QLabel(f"{int(round(entry.volume * 100))} %")
        self._volume_label.setObjectName("MutedLabel")
        footer.addWidget(self._volume_label)
        layout.addLayout(footer)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, 100)
        self._slider.setValue(int(round(entry.volume * 100)))
        self._slider.valueChanged.connect(self._on_volume)
        self._slider.sliderReleased.connect(self._on_volume_commit)
        layout.addWidget(self._slider)

        self._progress = QProgressBar()
        self._progress.setRange(0, 1000)
        self._progress.setValue(0)
        self._progress.setTextVisible(False)
        self._progress.setFixedHeight(4)
        layout.addWidget(self._progress)

        self._pulse_effect = QGraphicsOpacityEffect(self._progress)
        self._progress.setGraphicsEffect(self._pulse_effect)
        self._pulse = QPropertyAnimation(self._pulse_effect, b"opacity", self)
        self._pulse.setStartValue(0.45)
        self._pulse.setKeyValueAt(0.5, 1.0)
        self._pulse.setEndValue(0.45)
        self._pulse.setDuration(900)
        self._pulse.setLoopCount(-1)

    def set_playback(self, playing: bool, ratio: float) -> None:
        """Update the playing treatment. Playback itself does not wait on this."""
        if playing != self._playing:
            self._playing = playing
            self.setProperty("playing", playing)
            self.style().unpolish(self)
            self.style().polish(self)
            self._play.setText("■" if playing else "▶")
            if playing and self._pulse.state() != QPropertyAnimation.State.Running:
                self._pulse.start()
            elif not playing:
                self._pulse.stop()
                self._pulse_effect.setOpacity(1.0)
        self._progress.setValue(int(max(0.0, min(1.0, ratio)) * 1000) if playing else 0)

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton and not self._interactive(event):
            self.setProperty("pressed", True)
            self.style().unpolish(self)
            self.style().polish(self)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        self.setProperty("pressed", False)
        self.style().unpolish(self)
        self.style().polish(self)
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self.rect().contains(event.position().toPoint())
            and not self._interactive(event)
        ):
            self.play_requested.emit(self.sound_id)
        super().mouseReleaseEvent(event)

    def _toggle_playback(self) -> None:
        if self._playing:
            self.stop_requested.emit(self.sound_id)
        else:
            self.play_requested.emit(self.sound_id)

    def _on_volume(self, value: int) -> None:
        self._volume_label.setText(f"{value} %")
        self.volume_changed.emit(self.sound_id, value / 100)

    def _on_volume_commit(self) -> None:
        self.volume_committed.emit(self.sound_id, self._slider.value() / 100)

    def _open_menu(self) -> None:
        menu = QMenu(self)
        menu.addAction("Rename", self._rename)
        menu.addAction("Set hotkey", lambda: self.hotkey_edit_requested.emit(self.sound_id))
        menu.addAction("Delete", lambda: self.delete_requested.emit(self.sound_id))
        menu.exec(self._menu_button.mapToGlobal(self._menu_button.rect().bottomLeft()))

    def _rename(self) -> None:
        from PySide6.QtWidgets import QInputDialog

        name, accepted = QInputDialog.getText(self, "Rename sound", "Name", text=self._name.text())
        if accepted:
            self.rename_requested.emit(self.sound_id, name)

    def _interactive(self, event) -> bool:
        widget = self.childAt(event.position().toPoint())
        while widget is not None and widget is not self:
            if isinstance(widget, (QAbstractButton, QSlider)):
                return True
            widget = widget.parentWidget()
        return False
