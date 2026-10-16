"""The main SoundDeck window.

Cards emit intents. This window forwards them to the controller and renders
whatever the controller reports back.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressDialog,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from soundboard.audio.devices import DeviceSnapshot
from soundboard.audio.engine import PlaybackState
from soundboard.services.controller import SoundboardController
from soundboard.ui.components.flow_layout import FlowLayout
from soundboard.ui.components.header import HeaderBar
from soundboard.ui.components.sound_card import SoundCard
from soundboard.ui.dialogs.hotkey_dialog import HotkeyDialog
from soundboard.ui.dialogs.onboarding_dialog import OnboardingDialog
from soundboard.ui.dialogs.settings_dialog import SettingsDialog
from soundboard.ui.dialogs.youtube_dialog import YouTubeDialog
from soundboard.ui.themes.base import Theme


class _Board(QWidget):
    """Scrollable grid that reports a height matching its column count."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SoundBoard")
        self.flow = FlowLayout(self)
        self.setLayout(self.flow)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        height = self.flow.heightForWidth(max(self.width(), 1))
        if height != self.minimumHeight():
            self.setMinimumHeight(height)


class MainWindow(QMainWindow):
    """Soundboard grid, header, and the dialogs those controls open."""

    def __init__(self, controller: SoundboardController, theme: Theme) -> None:
        super().__init__()
        self._controller = controller
        self._theme = theme
        self._cards: dict[str, SoundCard] = {}
        self._import_dialog: QProgressDialog | None = None
        self._settings: SettingsDialog | None = None
        self._device_snapshot: DeviceSnapshot | None = None
        self.setWindowTitle("SoundDeck")
        self.setMinimumSize(1024, 700)
        self.resize(1120, 760)
        if theme.tokens.window_translucent:
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        root = QWidget()
        root.setObjectName("AppRoot")
        root.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(24, 36, 24, 24)
        layout.setSpacing(16)

        self._header = HeaderBar()
        layout.addWidget(self._header)

        self._banner = QLabel("")
        self._banner.setObjectName("WarningBanner")
        self._banner.setWordWrap(True)
        self._banner.hide()
        layout.addWidget(self._banner)

        self._scroll = QScrollArea()
        self._scroll.setObjectName("SoundScroll")
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._board = _Board()
        self._scroll.setWidget(self._board)
        layout.addWidget(self._scroll, 1)

        self._empty = QLabel("No sounds yet.\nUse Add Sound to import a file or a YouTube clip.")
        self._empty.setObjectName("EmptyState")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._empty)

        self._header.add_clicked.connect(self._open_add_menu)
        self._header.settings_clicked.connect(self.open_settings)
        self._header.start_clicked.connect(self._start_or_restart)

        controller.engine_status_changed.connect(self._on_engine_status)
        controller.sounds_changed.connect(self.reload_sounds)
        controller.playback_changed.connect(self._on_playback)
        controller.devices_changed.connect(self._on_devices)
        controller.permissions_changed.connect(self._on_permissions)
        controller.error_reported.connect(self._on_error)
        controller.notice_reported.connect(self._on_notice)
        controller.import_busy.connect(self._on_import_busy)

        self._on_engine_status("stopped", "Engine stopped")
        self._header.set_devices(controller.config.audio.input_device, controller.config.audio.output_device)
        self.reload_sounds()

    def reload_sounds(self) -> None:
        while item := self._board.flow.takeAt(0):
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._cards.clear()
        for entry in self._controller.config.sounds:
            card = SoundCard(entry)
            card.play_requested.connect(self._controller.play)
            card.stop_requested.connect(self._controller.stop_sound)
            card.delete_requested.connect(self._confirm_delete)
            card.rename_requested.connect(self._controller.rename)
            card.volume_changed.connect(
                lambda sound_id, volume: self._controller.set_sound_volume(sound_id, volume, persist=False)
            )
            card.volume_committed.connect(
                lambda sound_id, volume: self._controller.set_sound_volume(sound_id, volume, persist=True)
            )
            card.hotkey_edit_requested.connect(self._edit_hotkey)
            self._board.flow.addWidget(card)
            self._cards[entry.id] = card
        has_sounds = bool(self._cards)
        self._empty.setVisible(not has_sounds)
        self._scroll.setVisible(has_sounds)
        self._board.updateGeometry()

    def open_settings(self) -> None:
        if self._settings is None:
            self._settings = SettingsDialog(self._controller, self)
        self._settings.show()
        self._settings.raise_()
        self._settings.activateWindow()

    def open_onboarding(self) -> None:
        dialog = OnboardingDialog(self._controller, self)
        dialog.exec()
        self._header.set_devices(
            self._controller.config.audio.input_device,
            self._controller.config.audio.output_device,
        )

    def _open_add_menu(self) -> None:
        menu = QMenu(self)
        menu.addAction("Import File", self._import_file)
        menu.addAction("Import from YouTube", self._import_youtube)
        menu.exec(self._header.mapToGlobal(self._header.rect().bottomRight()))

    def _import_file(self) -> None:
        path, _selected = QFileDialog.getOpenFileName(
            self,
            "Import sound",
            "",
            "Audio (*.mp3 *.wav *.m4a *.flac *.ogg)",
        )
        if path:
            self._controller.import_file(Path(path))

    def _import_youtube(self) -> None:
        dialog = YouTubeDialog(self._controller, self)
        dialog.exec()

    def _edit_hotkey(self, sound_id: str) -> None:
        current = self._controller.hotkeys.binding_for(sound_id)
        dialog = HotkeyDialog(current, self)
        if dialog.exec() != HotkeyDialog.DialogCode.Accepted:
            return
        combo = None if dialog.cleared else dialog.combo
        self._controller.set_hotkey(sound_id, combo)

    def _confirm_delete(self, sound_id: str) -> None:
        entry = self._controller.library.find(sound_id)
        name = entry.name if entry is not None else "this sound"
        answer = QMessageBox.question(
            self,
            "Delete sound",
            f"Delete {name}?",
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._controller.delete_sound(sound_id)

    def _start_or_restart(self) -> None:
        if self._controller.engine.running:
            self._controller.restart_engine()
        else:
            self._controller.start_engine()

    def _on_engine_status(self, state: str, text: str) -> None:
        self._header.set_status(state, text)

    def _on_playback(self, snapshot: object) -> None:
        playing: dict[str, float] = {}
        if isinstance(snapshot, tuple):
            for item in snapshot:
                if isinstance(item, PlaybackState) and item.playing:
                    playing[item.sound_id] = item.ratio
        for sound_id, card in self._cards.items():
            if sound_id in playing:
                card.set_playback(True, playing[sound_id])
            else:
                card.set_playback(False, 0.0)

    def _on_devices(self, snapshot: object) -> None:
        if isinstance(snapshot, DeviceSnapshot):
            self._device_snapshot = snapshot
        self._header.set_devices(
            self._controller.config.audio.input_device,
            self._controller.config.audio.output_device,
        )
        self._render_banner()

    def _on_permissions(self) -> None:
        self._render_banner()

    def _render_banner(self) -> None:
        messages: list[str] = []
        snapshot = self._device_snapshot
        if snapshot is not None and not snapshot.inputs and not snapshot.outputs:
            messages.append(
                "No audio devices were found. Open Settings and refresh the device list."
            )
        if snapshot is not None and snapshot.virtual_output is None:
            messages.append(self._controller.platform.install_instructions())
        if self._controller.hotkey_permission_blocked():
            messages.append(
                "Global hotkeys need Accessibility permission for this app. "
                "Open Settings and allow SoundDeck, or the terminal that launched it."
            )
        if messages:
            self._banner.setText("\n\n".join(messages))
            self._banner.show()
        else:
            self._banner.hide()

    def _on_error(self, title: str, message: str) -> None:
        QMessageBox.warning(self, title, message)

    def _on_notice(self, title: str, message: str) -> None:
        QMessageBox.information(self, title, message)

    def _on_import_busy(self, busy: bool) -> None:
        self._header.set_busy(busy)
        if busy:
            dialog = QProgressDialog("Importing sound…", None, 0, 0, self)
            dialog.setWindowTitle("Import")
            dialog.setCancelButton(None)
            dialog.setMinimumDuration(0)
            dialog.show()
            self._import_dialog = dialog
        elif self._import_dialog is not None:
            self._import_dialog.close()
            self._import_dialog = None
