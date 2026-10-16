"""First-run wizard: microphone, virtual output, a sound, then Discord."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from soundboard.audio.devices import DeviceSnapshot, display_name
from soundboard.services.controller import SoundboardController
from soundboard.ui.components.glass import GlassButton, GlassDialog


class OnboardingDialog(GlassDialog):
    """Walk through the routing setup once."""

    def __init__(self, controller: SoundboardController, parent=None) -> None:
        super().__init__(parent)
        self._controller = controller
        self.setWindowTitle("Welcome to SoundDeck")
        self.setMinimumSize(640, 460)
        self._snapshot = controller.refresh_devices()

        self._stack = QStackedWidget()
        self._mic = QComboBox()
        self._output = QComboBox()
        self._stack.addWidget(self._microphone_page())
        self._stack.addWidget(self._output_page())
        self._stack.addWidget(self._sound_page())
        self._stack.addWidget(self._discord_page())
        self._content.addWidget(self._stack)

        buttons = QHBoxLayout()
        self._back = GlassButton("Back")
        self._back.clicked.connect(self._previous)
        self._next = GlassButton("Next", "PrimaryButton")
        self._next.clicked.connect(self._advance)
        skip = GlassButton("Skip", "QuietButton")
        skip.clicked.connect(self._skip)
        buttons.addWidget(skip)
        buttons.addStretch(1)
        buttons.addWidget(self._back)
        buttons.addWidget(self._next)
        self._content.addLayout(buttons)
        self._sync_buttons()

    def _microphone_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(self._heading("Choose your microphone"))
        layout.addWidget(self._body("SoundDeck mixes this microphone with your sounds."))
        self._fill(self._mic, list(self._snapshot.inputs), self._controller.config.audio.input_device)
        layout.addWidget(self._mic)
        layout.addStretch(1)
        return page

    def _output_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(self._heading("Choose the virtual output"))
        layout.addWidget(
            self._body(
                "Discord will use this device as its microphone. "
                f"On this Mac that is usually {self._controller.platform.virtual_device_label()}."
            )
        )
        self._fill(
            self._output,
            list(self._snapshot.outputs),
            self._controller.config.audio.output_device,
        )
        layout.addWidget(self._output)
        if self._snapshot.virtual_output is None:
            warning = QLabel(self._controller.platform.install_instructions())
            warning.setObjectName("WarningBanner")
            warning.setWordWrap(True)
            layout.addWidget(warning)
        layout.addStretch(1)
        return page

    def _sound_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(self._heading("Add your first sound"))
        layout.addWidget(self._body("Import an MP3, WAV, M4A, FLAC, or OGG file. You can also do this later."))
        add = GlassButton("Import file", "PrimaryButton")
        add.clicked.connect(self._import)
        layout.addWidget(add)
        layout.addStretch(1)
        return page

    def _discord_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        label = self._controller.platform.virtual_device_label()
        layout.addWidget(self._heading("Tell Discord which microphone to use"))
        layout.addWidget(
            self._body(
                "Discord\n"
                "→ Settings\n"
                "→ Voice & Video\n"
                "→ Input Device\n"
                f"→ {label}\n\n"
                "Speak and press a sound. Discord should hear both."
            )
        )
        layout.addStretch(1)
        return page

    def _heading(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("SectionTitle")
        label.setWordWrap(True)
        return label

    def _body(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setWordWrap(True)
        label.setObjectName("MutedLabel")
        return label

    def _fill(self, combo: QComboBox, devices, selected: str | None) -> None:
        labels = [display_name(device, devices) for device in devices]
        combo.addItems(labels)
        if selected:
            index = combo.findText(selected)
            if index >= 0:
                combo.setCurrentIndex(index)

    def _import(self) -> None:
        path, _selected = QFileDialog.getOpenFileName(
            self,
            "Import sound",
            "",
            "Audio (*.mp3 *.wav *.m4a *.flac *.ogg)",
        )
        if path:
            from pathlib import Path

            self._controller.import_file(Path(path))

    def _previous(self) -> None:
        self._stack.setCurrentIndex(max(0, self._stack.currentIndex() - 1))
        self._sync_buttons()

    def _advance(self) -> None:
        if self._stack.currentIndex() == self._stack.count() - 1:
            self._finish()
            return
        self._stack.setCurrentIndex(self._stack.currentIndex() + 1)
        self._sync_buttons()

    def _sync_buttons(self) -> None:
        index = self._stack.currentIndex()
        self._back.setEnabled(index > 0)
        self._next.setText("Finish" if index == self._stack.count() - 1 else "Next")

    def _skip(self) -> None:
        self._finish(apply_devices=self._stack.currentIndex() >= 1)

    def _finish(self, apply_devices: bool = True) -> None:
        if apply_devices:
            self._controller.set_devices(
                self._mic.currentText() or None,
                self._output.currentText() or None,
            )
        self._controller.complete_onboarding(True)
        self.accept()
